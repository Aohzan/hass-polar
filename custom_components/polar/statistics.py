"""Import Polar history as Home Assistant long-term statistics.

Sensors only record history from the moment they are created, while Polar keeps
the last 28 days of nightly data and per-day continuous heart rate samples.
That history is published as external statistics (``polar:<user_id>_<metric>``)
which can be displayed with the statistics graph card.

External statistics are used on purpose: importing into the sensors' own
statistics would collide with the rows compiled by the recorder from their
state and break the statistics compilation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from requests.exceptions import RequestException

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DurationConverter

from .const import (
    ATTR_CARDIO_LOAD_DATA,
    ATTR_RECHARGE_DATA,
    ATTR_SLEEP_DATA,
    DOMAIN,
)
from .coordinator import PolarConfigEntry, PolarCoordinator

_LOGGER = logging.getLogger(__name__)

HISTORY_DAYS = 28
HEART_RATE_IMPORT_INTERVAL = timedelta(hours=1)


@dataclass(frozen=True, kw_only=True)
class PolarDailyStatistic:
    """Describe a statistic built from a list of daily Polar records."""

    key: str
    name: str
    data_key: str
    value_fn: Callable[[dict[str, Any]], float | None]
    unit: str | None = None
    unit_class: str | None = None


def _seconds_to_minutes(seconds: float | None) -> float | None:
    """Convert a duration in seconds to minutes."""
    return None if seconds is None else round(seconds / 60, 1)


DAILY_STATISTICS = (
    PolarDailyStatistic(
        key="sleep_score",
        name="Sleep score",
        data_key=ATTR_SLEEP_DATA,
        value_fn=lambda night: night.get("sleep_score"),
        unit="score",
    ),
    *(
        PolarDailyStatistic(
            key=stage,
            name=name,
            data_key=ATTR_SLEEP_DATA,
            value_fn=lambda night, stage=stage: _seconds_to_minutes(night.get(stage)),
            unit=UnitOfTime.MINUTES,
            unit_class=DurationConverter.UNIT_CLASS,
        )
        for stage, name in (
            ("deep_sleep", "Deep sleep"),
            ("light_sleep", "Light sleep"),
            ("rem_sleep", "REM sleep"),
        )
    ),
    PolarDailyStatistic(
        key="nightly_recharge_status",
        name="Nightly recharge",
        data_key=ATTR_RECHARGE_DATA,
        value_fn=lambda recharge: recharge.get("nightly_recharge_status"),
        unit="score",
    ),
    PolarDailyStatistic(
        key="heart_rate_variability",
        name="Heart rate variability",
        data_key=ATTR_RECHARGE_DATA,
        value_fn=lambda recharge: recharge.get("heart_rate_variability_avg"),
        unit=UnitOfTime.MILLISECONDS,
        unit_class=DurationConverter.UNIT_CLASS,
    ),
    PolarDailyStatistic(
        key="breathing_rate",
        name="Breathing rate",
        data_key=ATTR_RECHARGE_DATA,
        value_fn=lambda recharge: recharge.get("breathing_rate_avg"),
        unit="br/min",
    ),
    PolarDailyStatistic(
        key="cardio_load",
        name="Cardio load",
        data_key=ATTR_CARDIO_LOAD_DATA,
        value_fn=lambda cardioload: cardioload.get("cardio_load"),
    ),
)


def _hour_start(day: date, hour: int) -> datetime:
    """Return the UTC start of an hour of a local day, as statistics require."""
    local = datetime.combine(day, time(hour), tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_utc(local).replace(minute=0, second=0, microsecond=0)


def build_daily_statistics(
    records: list[dict[str, Any]], value_fn: Callable[[dict[str, Any]], Any]
) -> list[StatisticData]:
    """Build one statistic per dated record.

    Each value is stored at noon of its day, so it stays in the right day
    whatever the time zone offset once truncated to the hour in UTC.
    """
    values: dict[datetime, float] = {}
    for record in records:
        day = dt_util.parse_date(record.get("date") or "")
        if day is None or (value := value_fn(record)) is None:
            continue
        values[_hour_start(day, 12)] = value
    return [
        StatisticData(start=start, mean=value, min=value, max=value)
        for start, value in sorted(values.items())
    ]


def build_heart_rate_statistics(
    samples_by_day: dict[date, list[dict[str, Any]]],
) -> list[StatisticData]:
    """Aggregate continuous heart rate samples into hourly statistics."""
    values: dict[datetime, list[int]] = {}
    for day, samples in samples_by_day.items():
        for sample in samples:
            sample_time = dt_util.parse_time(sample.get("sample_time") or "")
            if sample_time is None or (heart_rate := sample.get("heart_rate")) is None:
                continue
            values.setdefault(_hour_start(day, sample_time.hour), []).append(heart_rate)
    return [
        StatisticData(
            start=start,
            mean=round(sum(hour_values) / len(hour_values), 1),
            min=min(hour_values),
            max=max(hour_values),
        )
        for start, hour_values in sorted(values.items())
    ]


class PolarStatisticsImporter:
    """Publish the Polar history as external statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PolarConfigEntry,
        coordinator: PolarCoordinator,
    ) -> None:
        """Initialize the importer."""
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._imported: dict[str, list[StatisticData]] = {}
        self._heart_rate_lock = asyncio.Lock()
        self._heart_rate_next_day: date | None = None

    @callback
    def async_start(self) -> None:
        """Import the history now and keep it up to date."""
        self.entry.async_on_unload(
            self.coordinator.async_add_listener(self._async_import_daily_statistics)
        )
        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_schedule_heart_rate_import,
                HEART_RATE_IMPORT_INTERVAL,
            )
        )
        self._async_import_daily_statistics()
        self._async_schedule_heart_rate_import()

    def _statistic_id(self, key: str) -> str:
        """Return the external statistic id of a metric."""
        return f"{DOMAIN}:{self.entry.unique_id}_{key}"

    def _import(
        self,
        key: str,
        name: str,
        unit: str | None,
        unit_class: str | None,
        statistics: list[StatisticData],
    ) -> None:
        """Import statistics, skipping the ones already imported unchanged."""
        if not statistics or self._imported.get(key) == statistics:
            return
        async_add_external_statistics(
            self.hass,
            StatisticMetaData(
                mean_type=StatisticMeanType.ARITHMETIC,
                has_sum=False,
                name=f"{self.coordinator.user_name} {name}",
                source=DOMAIN,
                statistic_id=self._statistic_id(key),
                unit_class=unit_class,
                unit_of_measurement=unit,
            ),
            statistics,
        )
        self._imported[key] = statistics
        _LOGGER.debug("Imported %s statistics for %s", len(statistics), key)

    @callback
    def _async_import_daily_statistics(self) -> None:
        """Import the daily metrics from the data already fetched."""
        if not self.coordinator.last_update_success:
            return
        for description in DAILY_STATISTICS:
            self._import(
                description.key,
                description.name,
                description.unit,
                description.unit_class,
                build_daily_statistics(
                    self.coordinator.data.get(description.data_key) or [],
                    description.value_fn,
                ),
            )

    @callback
    def _async_schedule_heart_rate_import(self, _now: datetime | None = None) -> None:
        """Start a heart rate import unless one is already running."""
        if not self._heart_rate_lock.locked():
            self.entry.async_create_background_task(
                self.hass,
                self._async_import_heart_rate(),
                f"{DOMAIN}_{self.entry.entry_id}_heart_rate_import",
            )

    async def _async_import_heart_rate(self) -> None:
        """Import continuous heart rate, one API call per day."""
        async with self._heart_rate_lock:
            today = dt_util.now().date()
            first_day = self._heart_rate_next_day
            if first_day is None:
                first_day = await self._async_first_heart_rate_day(today)

            samples_by_day: dict[date, list[dict[str, Any]]] = {}
            day = first_day
            while day <= today:
                try:
                    samples_by_day[day] = await self.hass.async_add_executor_job(
                        self.coordinator.accesslink.get_continuous_heart_rate,
                        self.coordinator.access_token,
                        day.isoformat(),
                    )
                except RequestException as err:
                    _LOGGER.warning("Unable to import continuous heart rate: %s", err)
                    return
                day += timedelta(days=1)

            # Polar keeps adding samples to a day after its first sync, so the
            # previous day is fetched again on the next run.
            self._heart_rate_next_day = today - timedelta(days=1)
            self._import(
                "heart_rate",
                "Heart rate",
                "bpm",
                None,
                build_heart_rate_statistics(samples_by_day),
            )

    async def _async_first_heart_rate_day(self, today: date) -> date:
        """Return the first day to fetch, resuming after the last import."""
        first_day = today - timedelta(days=HISTORY_DAYS - 1)
        statistic_id = self._statistic_id("heart_rate")
        last_statistics = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, False, {"mean"}
        )
        if last := last_statistics.get(statistic_id):
            last_day = dt_util.as_local(
                dt_util.utc_from_timestamp(last[0]["start"])
            ).date()
            first_day = max(first_day, last_day - timedelta(days=1))
        return first_day

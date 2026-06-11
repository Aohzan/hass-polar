"""Import historical Polar data as Home Assistant long-term statistics.

Home Assistant sensors only build history forward from the moment they start
polling and cannot backfill past states. Polar however keeps the last ~28 days
of nightly/daily data and per-day continuous heart rate samples. This module
imports that history as long-term statistics attached to each sensor's own
``entity_id`` (via ``async_import_statistics``), so the past shows up directly
on the entity's History/statistics view, including data from before the
integration was installed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import PolarCoordinator

_LOGGER = logging.getLogger(__name__)

# How to declare a "mean" statistic. Newer Home Assistant wants ``mean_type``;
# fall back to the legacy ``has_mean`` boolean on older cores.
try:
    from homeassistant.components.recorder.models import StatisticMeanType

    _MEAN_META: dict = {"mean_type": StatisticMeanType.ARITHMETIC}
except ImportError:  # pragma: no cover - older Home Assistant
    _MEAN_META = {"has_mean": True}

# Continuous heart rate is fetched one API call per day, so keep the dense
# backfill window modest to stay friendly with Polar rate limits.
CHR_BACKFILL_DAYS = 7


def _hour_start(value: datetime) -> datetime:
    """Return the UTC hour-aligned start for a datetime (required by stats)."""
    return dt_util.as_utc(value).replace(minute=0, second=0, microsecond=0)


def _date_to_hour(date_str: Any, hour: int = 12) -> datetime | None:
    """Map a local ``YYYY-MM-DD`` string to an hour-aligned UTC datetime."""
    day = dt_util.parse_date(date_str) if isinstance(date_str, str) else None
    if day is None:
        return None
    local = datetime.combine(
        day, time(hour=hour), tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    return _hour_start(local)


def _seconds_to_minutes(seconds: Any) -> float | None:
    """Convert a duration in seconds to whole minutes."""
    if seconds is None:
        return None
    return round(seconds / 60)


def _metadata(statistic_id: str, unit: str | None) -> StatisticMetaData:
    """Build statistic metadata targeting an existing sensor entity."""
    return StatisticMetaData(
        **_MEAN_META,
        has_sum=False,
        name=None,
        source="recorder",
        statistic_id=statistic_id,
        unit_of_measurement=unit,
        unit_class=None,
    )


def _nightly_stats(
    records: list[dict], value_fn: Callable[[dict], Any]
) -> list[StatisticData]:
    """Build one statistic point per dated record (sleep/recharge/cardio)."""
    by_hour: dict[datetime, float] = {}
    for record in records:
        start = _date_to_hour(record.get("date"))
        value = value_fn(record)
        if start is None or value is None:
            continue
        by_hour[start] = value  # one value per day; last wins
    return [
        StatisticData(start=start, mean=value, min=value, max=value)
        for start, value in sorted(by_hour.items())
    ]


def _heart_rate_stats(
    samples_by_day: list[tuple[str, list[dict]]],
) -> list[StatisticData]:
    """Aggregate per-day 5-minute HR samples into hourly statistics."""
    buckets: dict[datetime, list[int]] = {}
    for date_str, samples in samples_by_day:
        day = dt_util.parse_date(date_str)
        if day is None:
            continue
        for sample in samples:
            heart_rate = sample.get("heart_rate")
            sample_time = sample.get("sample_time")
            if heart_rate is None or not sample_time:
                continue
            try:
                hour = int(str(sample_time).split(":", 1)[0])
            except ValueError:
                continue
            start = _hour_start(
                datetime.combine(
                    day, time(hour=hour), tzinfo=dt_util.DEFAULT_TIME_ZONE
                )
            )
            buckets.setdefault(start, []).append(heart_rate)
    return [
        StatisticData(
            start=start,
            mean=round(sum(values) / len(values), 1),
            min=min(values),
            max=max(values),
        )
        for start, values in sorted(buckets.items())
    ]


async def async_import_history(
    hass: HomeAssistant, coordinator: PolarCoordinator, entry: ConfigEntry
) -> None:
    """Fetch the available Polar history and import it into the sensors.

    Statistics are imported against each sensor's own ``entity_id`` (resolved
    from the entity registry via the sensor's unique_id), so the backfilled
    history shows up directly on the entity (its statistics graph), including
    data from before the integration was installed.
    """
    token = entry.data[CONF_ACCESS_TOKEN]
    accesslink = coordinator.accesslink
    ent_reg = er.async_get(hass)

    def _entity_id(unique_suffix: str) -> str | None:
        """Resolve a sensor entity_id from its unique_id suffix."""
        return ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{unique_suffix}"
        )

    # Nightly/daily metrics each come from a single "last 28 days" list call.
    sleep = await hass.async_add_executor_job(accesslink.get_sleep, token)
    recharge = await hass.async_add_executor_job(accesslink.get_recharge, token)
    cardio = await hass.async_add_executor_job(accesslink.get_cardio_load, token)

    # (sensor unique_id suffix, native unit, statistics) - units MUST match the
    # sensor's native_unit_of_measurement or Home Assistant rejects the import.
    plans: list[tuple[str, str | None, list[StatisticData]]] = [
        (
            "deep_sleep",
            "min",
            _nightly_stats(sleep, lambda r: _seconds_to_minutes(r.get("deep_sleep"))),
        ),
        (
            "light_sleep",
            "min",
            _nightly_stats(sleep, lambda r: _seconds_to_minutes(r.get("light_sleep"))),
        ),
        (
            "rem_sleep",
            "min",
            _nightly_stats(sleep, lambda r: _seconds_to_minutes(r.get("rem_sleep"))),
        ),
        (
            "last_sleep",
            "score",
            _nightly_stats(sleep, lambda r: r.get("sleep_score")),
        ),
        (
            "heart_rate_variability",
            "ms",
            _nightly_stats(recharge, lambda r: r.get("heart_rate_variability_avg")),
        ),
        (
            "breathing_rate",
            "bpm",
            _nightly_stats(recharge, lambda r: r.get("breathing_rate_avg")),
        ),
        (
            "cardio_load",
            None,
            _nightly_stats(cardio, lambda r: r.get("cardio_load")),
        ),
    ]

    # Dense continuous heart rate: one call per day for the recent window.
    today = dt_util.now().date()
    samples_by_day: list[tuple[str, list[dict]]] = []
    for offset in range(1, CHR_BACKFILL_DAYS + 1):
        day = (today - timedelta(days=offset)).isoformat()
        samples = await hass.async_add_executor_job(
            accesslink.get_continuous_heart_rate_samples, token, day
        )
        if samples:
            samples_by_day.append((day, samples))
    plans.append(("continuous_heart_rate", "bpm", _heart_rate_stats(samples_by_day)))

    imported_points = 0
    imported_metrics = 0
    for unique_suffix, unit, statistics in plans:
        if not statistics:
            continue
        entity_id = _entity_id(unique_suffix)
        if entity_id is None:
            _LOGGER.debug(
                "Polar: sensor for '%s' not registered yet, skipping its backfill",
                unique_suffix,
            )
            continue
        async_import_statistics(hass, _metadata(entity_id, unit), statistics)
        imported_points += len(statistics)
        imported_metrics += 1

    _LOGGER.info(
        "Polar: imported %s historical statistics points across %s sensors",
        imported_points,
        imported_metrics,
    )

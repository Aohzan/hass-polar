"""Support for the polar sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import isodate

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LAST_CARDIO_LOAD,
    ATTR_LAST_DAILY,
    ATTR_LAST_EXERCISE,
    ATTR_LAST_RECHARGE,
    ATTR_LAST_SLEEP,
    ATTR_USER_DATA,
    ATTRIBUTION,
    DOMAIN,
)
from .coordinator import PolarConfigEntry, PolarCoordinator

# Data is fetched by the coordinator
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PolarEntityDescription(SensorEntityDescription):
    """Provide a description of a Polar sensor."""

    key_category: str
    translation_key: str
    attributes_keys: list[str]
    value_fn: Callable[[dict[str, Any]], StateType | datetime] | None = None


def _duration_seconds(raw_duration: str) -> float | None:
    """Convert a Polar ISO 8601 duration to seconds."""
    try:
        return isodate.parse_duration(raw_duration).total_seconds()
    except (isodate.ISO8601Error, TypeError, ValueError):
        return None


def _exercise_start(exercise: dict[str, Any]) -> datetime | None:
    """Return the start time of an exercise, in its own time zone."""
    if (start := dt_util.parse_datetime(exercise["start_time"])) is None:
        return None
    if (offset := exercise.get("start_time_utc_offset")) is not None:
        return start.replace(tzinfo=timezone(timedelta(minutes=offset)))
    return start.replace(tzinfo=dt_util.get_default_time_zone())


SENSOR_DESCRIPTIONS = (
    # personal
    PolarEntityDescription(
        key_category=ATTR_USER_DATA,
        key="weight",
        translation_key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        attributes_keys=[],
    ),
    # daily
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="calories",
        native_unit_of_measurement="kcal",
        translation_key="daily_activity_calories",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:walk",
        attributes_keys=[
            "date",
            "active-calories",
        ],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="duration",
        translation_key="daily_activity_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-time-three",
        attributes_keys=["date"],
        value_fn=lambda daily: _duration_seconds(daily["duration"]),
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="active-steps",
        native_unit_of_measurement="steps",
        translation_key="daily_activity_steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:shoe-print",
        attributes_keys=["date"],
    ),
    # exercise
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="start_time",
        translation_key="last_exercise",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:run",
        attributes_keys=[
            "distance",
            "duration",
            "heart_rate",
            "training_load",
            "sport",
            "calories",
            "running_index",
            "device",
        ],
        value_fn=_exercise_start,
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="heart_rate",
        translation_key="last_exercise_heart_rate_average",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["start_time"],
        value_fn=lambda exercise: (exercise["heart_rate"] or {}).get("average"),
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="heart_rate",
        translation_key="last_exercise_heart_rate_maximum",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["start_time"],
        value_fn=lambda exercise: (exercise["heart_rate"] or {}).get("maximum"),
    ),
    # sleep
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="sleep_score",
        translation_key="last_sleep",
        native_unit_of_measurement="score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=[
            "date",
            "sleep_start_time",
            "sleep_end_time",
            "continuity",
            "continuity_class",
            "light_sleep",
            "deep_sleep",
            "rem_sleep",
            "unrecognized_sleep_stage",
            "total_interruption_duration",
            "sleep_charge",
            "sleep_rating",
            "sleep_goal",
            "short_interruption_duration",
            "long_interruption_duration",
            "sleep_cycles",
            "group_duration_score",
            "group_solidity_score",
            "group_regeneration_score",
        ],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="deep_sleep",
        translation_key="deep_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="light_sleep",
        translation_key="light_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="rem_sleep",
        translation_key="rem_sleep",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
    ),
    # recharge
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="nightly_recharge_status",
        translation_key="last_recharge",
        native_unit_of_measurement="score",
        icon="mdi:bed-clock",
        attributes_keys=[
            "date",
            "heart_rate_avg",
            "beat_to_beat_avg",
            "heart_rate_variability_avg",
            "breathing_rate_avg",
            "ans_charge",
            "ans_charge_status",
        ],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="heart_rate_variability_avg",
        translation_key="heart_rate_variability",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["date"],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="breathing_rate_avg",
        translation_key="breathing_rate",
        native_unit_of_measurement="br/min",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:lungs",
        attributes_keys=["date"],
    ),
    # cardio load
    PolarEntityDescription(
        key_category=ATTR_LAST_CARDIO_LOAD,
        key="cardio_load",
        translation_key="cardio_load",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:heart-flash",
        attributes_keys=[
            "date",
            "cardio_load_status",
            "strain",
            "tolerance",
            "cardio_load_ratio",
            "cardio_load_level",
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Polar sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        PolarSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class PolarSensor(CoordinatorEntity[PolarCoordinator], SensorEntity):
    """Implementation of the Polar sensor."""

    entity_description: PolarEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PolarCoordinator,
        description: PolarEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            configuration_url="https://flow.polar.com/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="Polar",
            name=coordinator.user_name,
        )
        self._attr_unique_id = f"{coordinator.entry_id}_{description.translation_key}"

    @property
    def _record(self) -> dict[str, Any]:
        """Return the Polar record the sensor is built from."""
        return self.coordinator.data[self.entity_description.key_category]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.key in self._record

    @property
    def native_value(self) -> StateType | datetime:
        """Return sensor state."""
        if self._record.get(self.entity_description.key) is None:
            return None
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self._record)
        return self._record[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return attributes."""
        if not self.entity_description.attributes_keys:
            return None
        return {
            key: self._record[key]
            for key in self.entity_description.attributes_keys
            if key in self._record
        }

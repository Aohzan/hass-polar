"""Support for the polar sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PolarCoordinator
from .const import (
    ATTR_CONTINUOUS_HEART_RATE,
    ATTR_LAST_CARDIO_LOAD,
    ATTR_LAST_DAILY,
    ATTR_LAST_EXERCISE,
    ATTR_LAST_RECHARGE,
    ATTR_LAST_SLEEP,
    ATTR_USER_DATA,
    ATTRIBUTION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _format_hours_minutes(seconds: Any) -> str | None:
    """Format a duration in seconds as a human readable "Xh Ym" string."""
    if seconds is None:
        return None
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


@dataclass(frozen=True, kw_only=True)
class PolarEntityDescription(SensorEntityDescription):
    """Provide a description of a Polar sensor."""

    key_category: str
    unique_id: str
    attributes_keys: list[str]
    value_fn: Callable[[Any], Any] | None = None
    attributes_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None


SENSOR_DESCRIPTIONS = (
    # personal
    PolarEntityDescription(
        key_category=ATTR_USER_DATA,
        key="weight",
        name="Weight",
        unique_id="weight",
        native_unit_of_measurement="kg",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        attributes_keys=[],
    ),
    # daily
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="calories",
        native_unit_of_measurement="kcal",
        name="Daily activity Calories",
        unique_id="daily_activity_calories",
        icon="mdi:walk",
        attributes_keys=[
            "active-calories",
        ],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="duration",
        name="Daily activity Duration",
        unique_id="daily_activity_duration",
        icon="mdi:clock-time-three",
        attributes_keys=[],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="active-steps",
        native_unit_of_measurement="steps",
        name="Daily activity Steps",
        unique_id="daily_activity_steps",
        icon="mdi:shoe-print",
        attributes_keys=[],
    ),
    # exercise
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="start_time",
        name="Last exercise",
        unique_id="last_exercise",
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
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="heart_rate_average",
        name="Last exercise heart rate average",
        unique_id="last_exercise_heart_rate_average",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["start_time", "sport"],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="heart_rate_maximum",
        name="Last exercise heart rate maximum",
        unique_id="last_exercise_heart_rate_maximum",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["start_time", "sport"],
    ),
    # sleep
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="sleep_score",
        name="Last sleep score",
        unique_id="last_sleep",
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
    # recharge
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="nightly_recharge_status",
        name="Last nightly recharge",
        unique_id="last_recharge",
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
        name="Heart rate variability",
        unique_id="heart_rate_variability",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["date"],
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="breathing_rate_avg",
        name="Breathing rate",
        unique_id="breathing_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lungs",
        attributes_keys=["date"],
    ),
    # continuous heart rate
    PolarEntityDescription(
        key_category=ATTR_CONTINUOUS_HEART_RATE,
        key="latest",
        name="Heart rate",
        unique_id="continuous_heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        attributes_keys=["date", "min", "max", "average", "samples_count"],
    ),
    # cardio load (training load)
    PolarEntityDescription(
        key_category=ATTR_LAST_CARDIO_LOAD,
        key="cardio_load",
        name="Cardio load",
        unique_id="cardio_load",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weight-lifter",
        attributes_keys=[
            "date",
            "strain",
            "tolerance",
            "cardio_load_ratio",
            "cardio_load_status",
        ],
    ),
    # sleep stages
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="deep_sleep",
        name="Deep sleep",
        unique_id="deep_sleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
        value_fn=lambda seconds: round(seconds / 60),
        attributes_fn=lambda data: {
            "duration": _format_hours_minutes(data.get("deep_sleep"))
        },
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="light_sleep",
        name="Light sleep",
        unique_id="light_sleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
        value_fn=lambda seconds: round(seconds / 60),
        attributes_fn=lambda data: {
            "duration": _format_hours_minutes(data.get("light_sleep"))
        },
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="rem_sleep",
        name="REM sleep",
        unique_id="rem_sleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        attributes_keys=["date"],
        value_fn=lambda seconds: round(seconds / 60),
        attributes_fn=lambda data: {
            "duration": _format_hours_minutes(data.get("rem_sleep"))
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Polar sensor platform."""
    coordinator: PolarCoordinator = hass.data[DOMAIN][entry.entry_id]
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
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{description.unique_id or description.key}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return (
            super().available
            and self.entity_description.key
            in self.coordinator.data[self.entity_description.key_category]
        )

    @property
    def native_value(self) -> float | None:
        """Return sensor state."""
        if (
            value := self.coordinator.data[self.entity_description.key_category][
                self.entity_description.key
            ]
        ) is None:
            return None
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value)
        return value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return attributes."""
        category_data = self.coordinator.data[self.entity_description.key_category]
        attributes: dict[str, Any] = {}
        for key in self.entity_description.attributes_keys:
            if key in category_data:
                attributes[key] = category_data[key]
        if self.entity_description.attributes_fn is not None:
            attributes.update(self.entity_description.attributes_fn(category_data))
        return attributes or None

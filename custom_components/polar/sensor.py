"""Support for the polar sensors."""
from __future__ import annotations

from collections.abc import Mapping
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PolarCoordinator
from .const import (
    ATTR_LAST_DAILY,
    ATTR_LAST_EXERCISE,
    ATTR_LAST_RECHARGE,
    ATTR_LAST_SLEEP,
    ATTR_USER_DATA,
    ATTRIBUTION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PolarEntityDescription(SensorEntityDescription):
    """Provide a description of a Polar sensor."""

    key_category: str | None = None
    unique_id: str | None = None
    attributes_keys: list[str] | None = None


SENSORS = (
    # personal
    PolarEntityDescription(
        key_category=ATTR_USER_DATA,
        key="weight",
        name="Weight",
        unique_id="weight",
        native_unit_of_measurement="kg",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # daily
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="calories",
        native_unit_of_measurement="kcal",
        name="Daily activity Calories",
        unique_id="daily_activity_calories",
        attributes_keys=[
            "active-calories",
        ],
        icon="mdi:walk",
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="duration",
        name="Daily activity Duration",
        unique_id="daily_activity_duration",
        icon="mdi:clock-time-three",
    ),
    PolarEntityDescription(
        key_category=ATTR_LAST_DAILY,
        key="active-steps",
        native_unit_of_measurement="steps",
        name="Daily activity Steps",
        unique_id="daily_activity_steps",
        icon="mdi:shoe-print",
    ),
    # exercise
    PolarEntityDescription(
        key_category=ATTR_LAST_EXERCISE,
        key="start_time",
        name="Last exercise",
        unique_id="last_exercise",
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
        icon="mdi:run",
    ),
    # sleep
    PolarEntityDescription(
        key_category=ATTR_LAST_SLEEP,
        key="sleep_score",
        name="Last sleep score",
        unique_id="last_sleep",
        native_unit_of_measurement="score",
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
        icon="mdi:sleep",
    ),
    # recharge
    PolarEntityDescription(
        key_category=ATTR_LAST_RECHARGE,
        key="nightly_recharge_status",
        name="Last nightly recharge",
        unique_id="last_recharge",
        native_unit_of_measurement="score",
        attributes_keys=[
            "date",
            "heart_rate_avg",
            "beat_to_beat_avg",
            "heart_rate_variability_avg",
            "breathing_rate_avg",
            "ans_charge",
            "ans_charge_status",
        ],
        icon="mdi:bed-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Polar sensor platform."""
    coordinator: PolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PolarSensor(coordinator, description) for description in SENSORS)


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
            default_manufacturer="Polar",
            default_name=coordinator.user_name,
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
        return value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return attributes."""
        if self.entity_description.attributes_keys:
            attributes = {}
            for key in self.entity_description.attributes_keys:
                if key in self.coordinator.data[self.entity_description.key_category]:
                    value = self.coordinator.data[self.entity_description.key_category][
                        key
                    ]
                    attributes.update({key: value})
            return attributes
        return None

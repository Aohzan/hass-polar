"""Tests for the Polar sensors."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    ("entity_id", "state", "unit"),
    [
        ("sensor.john_doe_weight", "70.5", "kg"),
        ("sensor.john_doe_daily_activity_calories", "2100", "kcal"),
        ("sensor.john_doe_daily_activity_duration", "330.0", "min"),
        ("sensor.john_doe_daily_activity_steps", "12000", "steps"),
        ("sensor.john_doe_last_exercise", "2026-10-05T16:00:00+00:00", None),
        ("sensor.john_doe_last_exercise_heart_rate_average", "140", "bpm"),
        ("sensor.john_doe_last_exercise_heart_rate_maximum", "175", "bpm"),
        ("sensor.john_doe_last_sleep_score", "80", "score"),
        ("sensor.john_doe_deep_sleep", "60.0", "min"),
        ("sensor.john_doe_light_sleep", "240.0", "min"),
        ("sensor.john_doe_rem_sleep", "90.0", "min"),
        ("sensor.john_doe_last_nightly_recharge", "4", "score"),
        ("sensor.john_doe_heart_rate_variability", "45", "ms"),
        ("sensor.john_doe_breathing_rate", "14.2", "br/min"),
        ("sensor.john_doe_cardio_load", "42.5", None),
        ("sensor.john_doe_last_sync", "2026-10-05T20:00:00+00:00", None),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
    state: str,
    unit: str | None,
) -> None:
    """Test the sensor states."""
    sensor = hass.states.get(entity_id)
    assert sensor is not None
    assert sensor.state == state
    assert sensor.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit


async def test_sensor_attributes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the attributes of a sensor."""
    state = hass.states.get("sensor.john_doe_daily_activity_calories")
    assert state.attributes["date"] == "2026-10-05"
    assert state.attributes["active-calories"] == 800


async def test_sensor_unavailable_without_data(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_accesslink
) -> None:
    """Test sensors are unavailable when Polar has no data."""
    mock_accesslink.get_exercises.return_value = []
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.john_doe_last_exercise").state == "unavailable"


async def test_last_sync_diagnostic(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the last sync sensor is a diagnostic entity."""
    entry = entity_registry.async_get("sensor.john_doe_last_sync")
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

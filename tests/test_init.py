"""Tests for the Polar integration setup."""

from datetime import timedelta
from http import HTTPStatus
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.polar.const import CONF_USER_ID, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    ACCESS_TOKEN,
    CLIENT_ID,
    CLIENT_SECRET,
    DAILY_ACTIVITIES,
    USER_ID,
    http_error,
)


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_accesslink: MagicMock
) -> None:
    """Test the entry is set up and unloaded."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (http_error(HTTPStatus.UNAUTHORIZED), ConfigEntryState.SETUP_ERROR),
        (http_error(HTTPStatus.INTERNAL_SERVER_ERROR), ConfigEntryState.SETUP_RETRY),
        (http_error(HTTPStatus.TOO_MANY_REQUESTS), ConfigEntryState.SETUP_RETRY),
        (ClientConnectionError(), ConfigEntryState.SETUP_RETRY),
        (TimeoutError(), ConfigEntryState.SETUP_RETRY),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_setup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_accesslink: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test the entry setup when Polar fails."""
    mock_accesslink.get_userdata.side_effect = side_effect
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state
    reauth_started = any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )
    assert reauth_started is (state is ConfigEntryState.SETUP_ERROR)
    # Nothing is consumed from Polar when a request fails
    mock_accesslink.get_daily_activities.assert_not_called()


async def test_daily_activities_are_stored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_accesslink: MagicMock,
    hass_storage: dict[str, Any],
) -> None:
    """Test the daily activities are kept between updates and restarts."""
    key = f"{DOMAIN}_dailydata_{init_integration.entry_id}"
    assert hass_storage[key]["data"] == [DAILY_ACTIVITIES[0]]

    mock_accesslink.get_daily_activities.return_value = []
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.john_doe_daily_activity_steps")
    assert state.state == "12000"

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_migrate_from_version_1(
    hass: HomeAssistant, mock_accesslink: MagicMock
) -> None:
    """Test an entry of the previous config flow is migrated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=USER_ID,
        title="John Doe",
        data={
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            CONF_SCAN_INTERVAL: 15,
            "external_url": "https://example.com",
            CONF_USER_ID: USER_ID,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_NAME: "John Doe",
        },
    )
    entry.add_to_hass(hass)
    legacy_path = hass.config.path(".storage", f"polar_dailydata_{entry.entry_id}.json")
    legacy_activities = [
        {
            "date": "2026-10-04",
            "created": "2026-10-04T22:00:00.000Z",
            "calories": 2500,
            "duration": "4:00:00",
            "active-steps": 15000,
        }
    ]

    def write_legacy_file() -> None:
        path = Path(legacy_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(legacy_activities), encoding="utf-8")

    await hass.async_add_executor_job(write_legacy_file)
    mock_accesslink.get_daily_activities.return_value = []

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == str(USER_ID)
    assert entry.data == {
        "auth_implementation": f"{DOMAIN}_{CLIENT_ID}",
        CONF_TOKEN: {
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            "token_type": "bearer",
            "x_user_id": USER_ID,
        },
        CONF_USER_ID: USER_ID,
        CONF_NAME: "John Doe",
    }
    assert entry.options == {CONF_SCAN_INTERVAL: 15}
    mock_accesslink.get_exercises.assert_called_with(ACCESS_TOKEN)

    # The legacy backup is moved to the store
    assert not await hass.async_add_executor_job(Path(legacy_path).exists)
    state = hass.states.get("sensor.john_doe_daily_activity_steps")
    assert state.state == "15000"


async def test_setup_without_credentials(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_accesslink: MagicMock
) -> None:
    """Test the account must be linked again when its credentials are removed."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH]
    mock_accesslink.get_userdata.assert_not_called()


@pytest.mark.parametrize(
    ("headers", "next_update"),
    [({"Retry-After": "3600"}, timedelta(hours=1)), ({}, timedelta(minutes=30))],
)
async def test_rate_limited(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_accesslink: MagicMock,
    headers: dict[str, str],
    next_update: timedelta,
) -> None:
    """Test the next update waits for the delay asked by Polar."""
    coordinator = init_integration.runtime_data
    mock_accesslink.get_userdata.side_effect = http_error(
        HTTPStatus.TOO_MANY_REQUESTS, headers
    )
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not coordinator.last_update_success

    mock_accesslink.get_userdata.side_effect = None
    freezer.tick(next_update - timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not coordinator.last_update_success

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success

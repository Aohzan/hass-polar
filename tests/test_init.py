"""Tests for the Polar integration setup."""

from http import HTTPStatus
import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError

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

from .conftest import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET, DAILY_ACTIVITIES, USER_ID


def _http_error(status: int) -> HTTPError:
    """Return a requests HTTP error with the given status."""
    response = Response()
    response.status_code = status
    return HTTPError(str(status), response=response)


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_accesslink: MagicMock
) -> None:
    """Test the entry is set up and unloaded."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_accesslink.close.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (_http_error(HTTPStatus.UNAUTHORIZED), ConfigEntryState.SETUP_ERROR),
        (_http_error(HTTPStatus.INTERNAL_SERVER_ERROR), ConfigEntryState.SETUP_RETRY),
        (RequestsConnectionError(), ConfigEntryState.SETUP_RETRY),
    ],
)
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
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, "w", encoding="utf-8") as legacy_file:
            json.dump(legacy_activities, legacy_file)

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
    assert not await hass.async_add_executor_job(os.path.exists, legacy_path)
    state = hass.states.get("sensor.john_doe_daily_activity_steps")
    assert state.state == "15000"

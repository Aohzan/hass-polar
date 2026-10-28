"""Fixtures for the Polar integration tests."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp import ClientResponseError
from multidict import CIMultiDict
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.polar.const import CONF_USER_ID, DOMAIN
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"
USER_ID = 123456
ACCESS_TOKEN = "access-token"

USER_URL = f"https://www.polaraccesslink.com/v3/users/{USER_ID}"

USER_DATA = {
    "polar-user-id": USER_ID,
    "member-id": "member",
    "registration-date": "2020-01-01T10:00:00.000Z",
    "first-name": "John",
    "last-name": "Doe",
    "birthdate": "1990-01-01",
    "gender": "MALE",
    "weight": 70.5,
    "height": 180,
}
EXERCISES = [
    {
        "start_time": "2026-10-05T18:00:00",
        "start_time_utc_offset": 120,
        "duration": "1:00:00",
        "heart_rate": {"average": 140, "maximum": 175},
        "sport": "RUNNING",
        "detailed_sport_info": "RUNNING",
        "upload_time": "2026-10-05T19:30:00.000Z",
        "polar_user": USER_URL,
    }
]
SLEEP = [
    {
        "date": "2026-10-05",
        "sleep_score": 80,
        "deep_sleep": 3600,
        "light_sleep": 14400,
        "rem_sleep": 5400,
        "polar_user": USER_URL,
    }
]
RECHARGE = [
    {
        "date": "2026-10-05",
        "nightly_recharge_status": 4,
        "heart_rate_variability_avg": 45,
        "breathing_rate_avg": 14.2,
        "polar_user": USER_URL,
    }
]
CARDIO_LOAD = [
    {"date": "2026-10-05", "cardio_load": 42.5, "cardio_load_status": "LOAD_STATUS_OK"}
]
DAILY_ACTIVITIES = [
    {
        "date": "2026-10-05",
        "created": "2026-10-05T20:00:00.000Z",
        "calories": 2100,
        "active-calories": 800,
        "duration": "PT5H30M",
        "active-steps": 12000,
        "polar-user": USER_URL,
    },
    {
        "date": "2026-10-05",
        "created": "2026-10-05T10:00:00.000Z",
        "calories": 1000,
        "active-calories": 300,
        "duration": "PT2H",
        "active-steps": 5000,
        "polar-user": USER_URL,
    },
]


def http_error(
    status: int, headers: dict[str, str] | None = None
) -> ClientResponseError:
    """Return the error raised by the Polar client for an HTTP status."""
    return ClientResponseError(
        MagicMock(), (), status=status, headers=CIMultiDict(headers or {})
    )


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return the snapshot assertion with the Home Assistant serializer."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable(recorder_mock: Any, enable_custom_integrations: None) -> None:
    """Enable the recorder and the custom integrations."""


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up the application credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), DOMAIN
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a Polar config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        # Fixed, as the unique IDs of the sensors contain it
        entry_id="01JPOLARENTRY0000000000000",
        version=2,
        unique_id=str(USER_ID),
        title="John Doe",
        data={
            "auth_implementation": DOMAIN,
            CONF_TOKEN: {
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                "token_type": "bearer",
                "x_user_id": USER_ID,
            },
            CONF_USER_ID: USER_ID,
            CONF_NAME: "John Doe",
        },
        options={CONF_SCAN_INTERVAL: 30},
    )


@pytest.fixture
def mock_accesslink() -> Generator[MagicMock]:
    """Mock the Polar AccessLink client used by the coordinator."""
    with patch(
        "custom_components.polar.coordinator.AccessLink", autospec=True
    ) as mock_class:
        accesslink = mock_class.return_value
        accesslink.get_userdata.return_value = deepcopy(USER_DATA)
        accesslink.get_exercises.return_value = deepcopy(EXERCISES)
        accesslink.get_sleep.return_value = deepcopy(SLEEP)
        accesslink.get_recharge.return_value = deepcopy(RECHARGE)
        accesslink.get_cardio_load.return_value = deepcopy(CARDIO_LOAD)
        accesslink.get_daily_activities.return_value = deepcopy(DAILY_ACTIVITIES)
        accesslink.get_continuous_heart_rate.return_value = []
        yield accesslink


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    setup_credentials: None,
    config_entry: MockConfigEntry,
    mock_accesslink: MagicMock,
) -> MockConfigEntry:
    """Set up the Polar integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry

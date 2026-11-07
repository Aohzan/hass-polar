"""Tests for the diagnostics of the Polar integration."""

import json

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import USER_ID


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the diagnostics redact the token and the user information."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics == snapshot
    # Neither the user ID nor the URLs containing it are left
    assert str(USER_ID) not in json.dumps(diagnostics)

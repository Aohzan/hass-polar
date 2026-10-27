"""Diagnostics support for the Polar integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_USER_ID
from .coordinator import PolarConfigEntry

TO_REDACT = {
    # Contains the client ID of the application credentials
    "auth_implementation",
    CONF_NAME,
    CONF_TOKEN,
    CONF_USER_ID,
    # User information
    "birthdate",
    "first-name",
    "last-name",
    "member-id",
    "polar-user-id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PolarConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }

"""The Polar integration."""

from __future__ import annotations

import logging

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_USER_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import PolarConfigEntry, PolarCoordinator, daily_store
from .statistics import PolarStatisticsImporter

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PolarConfigEntry) -> bool:
    """Set up Polar from a config entry."""
    coordinator = PolarCoordinator(hass, entry)
    entry.async_on_unload(coordinator.accesslink.close)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    PolarStatisticsImporter(hass, entry, coordinator).async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PolarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PolarConfigEntry) -> None:
    """Remove the data stored for a config entry."""
    await daily_store(hass, entry.entry_id).async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: PolarConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        # The client credentials move to application credentials, and the
        # access token to the format of the OAuth2 config flow.
        client_id = entry.data[CONF_CLIENT_ID]
        auth_domain = f"{DOMAIN}_{client_id}"
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(client_id, entry.data[CONF_CLIENT_SECRET], entry.title),
            auth_domain,
        )
        hass.config_entries.async_update_entry(
            entry,
            data={
                "auth_implementation": auth_domain,
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: entry.data[CONF_ACCESS_TOKEN],
                    "token_type": "bearer",
                    "x_user_id": entry.data[CONF_USER_ID],
                },
                CONF_USER_ID: entry.data[CONF_USER_ID],
                CONF_NAME: entry.data[CONF_NAME],
            },
            options={
                CONF_SCAN_INTERVAL: entry.options.get(
                    CONF_SCAN_INTERVAL,
                    entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                )
            },
            unique_id=str(entry.data[CONF_USER_ID]),
            version=2,
        )
        _LOGGER.debug("Migrated config entry %s to version 2", entry.entry_id)

    return True

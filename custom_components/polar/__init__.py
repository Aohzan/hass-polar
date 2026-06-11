"""The Polar integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_USER_ID, DOMAIN
from .coordinator import PolarCoordinator
from .statistics import async_import_history

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]
HISTORY_IMPORT_INTERVAL = timedelta(hours=24)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Polar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # migrate unique_id to str to fix invalid unique_id
    if entry.unique_id != str(entry.data[CONF_USER_ID]):
        hass.config_entries.async_update_entry(
            entry, unique_id=str(entry.data[CONF_USER_ID])
        )

    coordinator = PolarCoordinator(hass, entry)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _import_history(now=None) -> None:
        """Backfill Polar history into long-term statistics (best effort)."""
        try:
            await async_import_history(hass, coordinator, entry)
        except Exception:  # noqa: BLE001 - never fail setup on history import
            _LOGGER.exception("Polar: failed to import historical statistics")

    # Run once now (in the background) and then refresh once a day.
    entry.async_create_background_task(
        hass, _import_history(), "polar_history_import"
    )
    entry.async_on_unload(
        async_track_time_interval(hass, _import_history, HISTORY_IMPORT_INTERVAL)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

"""Polar data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_DAILY_DATA,
    ATTR_EXERCISE_DATA,
    ATTR_LAST_DAILY,
    ATTR_LAST_EXERCISE,
    ATTR_LAST_RECHARGE,
    ATTR_LAST_SLEEP,
    ATTR_RECHARGE_DATA,
    ATTR_SLEEP_DATA,
    ATTR_USER_DATA,
    CONF_USER_ID,
    DOMAIN,
)
from .polaraccesslink.accesslink import AccessLink

_LOGGER = logging.getLogger(__name__)


class PolarCoordinator(DataUpdateCoordinator):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(
                    CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL)
                )
            ),
        )
        self._entry = entry
        self.accesslink = AccessLink(
            client_id=self._entry.data[CONF_CLIENT_ID],
            client_secret=self._entry.data[CONF_CLIENT_SECRET],
        )

    @property
    def user_name(self) -> str:
        """Return name of the user."""
        return self._entry.data[CONF_NAME]

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> dict:
        """Fetch the latest data from the source."""
        userdata = await self.hass.async_add_executor_job(
            self.accesslink.get_userdata,
            self._entry.data[CONF_USER_ID],
            self._entry.data[CONF_ACCESS_TOKEN],
        )
        exercisedata = await self.hass.async_add_executor_job(
            self.accesslink.get_exercises, self._entry.data[CONF_ACCESS_TOKEN]
        )
        sleepdata = await self.hass.async_add_executor_job(
            self.accesslink.get_sleep, self._entry.data[CONF_ACCESS_TOKEN]
        )
        rechargedata = await self.hass.async_add_executor_job(
            self.accesslink.get_recharge, self._entry.data[CONF_ACCESS_TOKEN]
        )
        dailydata = await self.hass.async_add_executor_job(
            self.accesslink.get_daily_activities,
            self._entry.data[CONF_USER_ID],
            self._entry.data[CONF_ACCESS_TOKEN],
            self.hass.config.path(
                f".storage/polar_dailydata_{self._entry.entry_id}.json"
            ),
        )
        return {
            ATTR_USER_DATA: userdata,
            ATTR_EXERCISE_DATA: exercisedata,
            ATTR_SLEEP_DATA: sleepdata,
            ATTR_RECHARGE_DATA: rechargedata,
            ATTR_DAILY_DATA: dailydata,
            ATTR_LAST_EXERCISE: next(iter(exercisedata), {}),
            ATTR_LAST_SLEEP: next(iter(sleepdata), {}),
            ATTR_LAST_RECHARGE: next(iter(rechargedata), {}),
            ATTR_LAST_DAILY: next(iter(dailydata), {}),
        }

"""Polar data coordinator."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from itertools import chain
import json
import logging
from pathlib import Path
from typing import Any

from requests.exceptions import HTTPError, RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CARDIO_LOAD_DATA,
    ATTR_DAILY_DATA,
    ATTR_EXERCISE_DATA,
    ATTR_LAST_CARDIO_LOAD,
    ATTR_LAST_DAILY,
    ATTR_LAST_EXERCISE,
    ATTR_LAST_RECHARGE,
    ATTR_LAST_SLEEP,
    ATTR_RECHARGE_DATA,
    ATTR_SLEEP_DATA,
    ATTR_USER_DATA,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .polaraccesslink.accesslink import AccessLink

_LOGGER = logging.getLogger(__name__)

DAILY_STORAGE_VERSION = 1
DAILY_HISTORY_DAYS = 28

type PolarConfigEntry = ConfigEntry[PolarCoordinator]


def daily_store(hass: HomeAssistant, entry_id: str) -> Store[list[dict[str, Any]]]:
    """Return the store keeping the daily activities of an entry."""
    return Store(hass, DAILY_STORAGE_VERSION, f"{DOMAIN}_dailydata_{entry_id}")


def merge_daily_activities(
    stored: list[dict[str, Any]], new: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep the most recent summary of each day, most recent day first."""
    by_date: dict[str, dict[str, Any]] = {}
    for activity in sorted(
        chain(stored, new), key=lambda activity: activity.get("created") or ""
    ):
        by_date[activity["date"]] = activity
    return [by_date[day] for day in sorted(by_date, reverse=True)][:DAILY_HISTORY_DAYS]


class PolarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator."""

    config_entry: PolarConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PolarConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.accesslink = AccessLink()
        self._daily_store = daily_store(hass, entry.entry_id)
        self._daily_activities: list[dict[str, Any]] = []

    @property
    def user_name(self) -> str:
        """Return name of the user."""
        return self.config_entry.data[CONF_NAME]

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self.config_entry.entry_id

    @property
    def access_token(self) -> str:
        """Return the access token of the user."""
        return self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]

    async def _async_setup(self) -> None:
        """Load the daily activities already fetched."""
        activities = await self._daily_store.async_load()
        if activities is None and (
            activities := await self.hass.async_add_executor_job(
                self._pop_legacy_daily_activities
            )
        ):
            await self._daily_store.async_save(activities)
        self._daily_activities = activities or []

    def _pop_legacy_daily_activities(self) -> list[dict[str, Any]] | None:
        """Read and remove the daily activities backup of previous versions."""
        legacy_path = Path(
            self.hass.config.path(".storage", f"polar_dailydata_{self.entry_id}.json")
        )
        try:
            activities = json.loads(legacy_path.read_text(encoding="utf-8"))
            legacy_path.unlink()
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as err:
            _LOGGER.warning("Unable to migrate daily activities backup: %s", err)
            return None
        return activities

    def _fetch_data(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Fetch the data from Polar, and the daily activities synced since last call."""
        user_id = self.config_entry.data[CONF_USER_ID]
        data = {
            ATTR_USER_DATA: self.accesslink.get_userdata(user_id, self.access_token),
            ATTR_EXERCISE_DATA: self.accesslink.get_exercises(self.access_token),
            ATTR_SLEEP_DATA: self.accesslink.get_sleep(self.access_token),
            ATTR_RECHARGE_DATA: self.accesslink.get_recharge(self.access_token),
            ATTR_CARDIO_LOAD_DATA: self.accesslink.get_cardio_load(self.access_token),
        }
        # Fetched last: the daily activities are consumed once fetched, so they
        # would be lost if a following request failed.
        return data, self.accesslink.get_daily_activities(user_id, self.access_token)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the source."""
        try:
            data, new_activities = await self.hass.async_add_executor_job(
                self._fetch_data
            )
        except HTTPError as err:
            if err.response.status_code == HTTPStatus.UNAUTHORIZED:
                raise ConfigEntryAuthFailed(
                    f"Polar rejected the access token: {err}"
                ) from err
            raise UpdateFailed(f"Error fetching Polar data: {err}") from err
        except RequestException as err:
            raise UpdateFailed(f"Unable to connect to Polar: {err}") from err

        if new_activities:
            self._daily_activities = merge_daily_activities(
                self._daily_activities, new_activities
            )
            await self._daily_store.async_save(self._daily_activities)

        return {
            **data,
            ATTR_DAILY_DATA: self._daily_activities,
            ATTR_LAST_EXERCISE: next(iter(data[ATTR_EXERCISE_DATA]), {}),
            ATTR_LAST_SLEEP: next(iter(data[ATTR_SLEEP_DATA]), {}),
            ATTR_LAST_RECHARGE: next(iter(data[ATTR_RECHARGE_DATA]), {}),
            ATTR_LAST_DAILY: next(iter(self._daily_activities), {}),
            ATTR_LAST_CARDIO_LOAD: next(iter(data[ATTR_CARDIO_LOAD_DATA]), {}),
        }

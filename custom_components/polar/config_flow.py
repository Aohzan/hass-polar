"""Config flow for Polar integration."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from requests.exceptions import HTTPError, RequestException
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_USER_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL
from .polaraccesslink.accesslink import AccessLink

_LOGGER = logging.getLogger(__name__)


def _register_user(user_id: int, access_token: str) -> dict[str, Any]:
    """Register the user to the Polar client and return its data."""
    accesslink = AccessLink()
    try:
        try:
            accesslink.users.register(access_token)
        except HTTPError as err:
            # Conflict means the user is already registered for this client
            if err.response.status_code != HTTPStatus.CONFLICT:
                raise
        return accesslink.get_userdata(user_id, access_token)
    finally:
        accesslink.close()


class ConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Polar."""

    DOMAIN = DOMAIN
    VERSION = 2

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Register the user to the Polar client, then create or update the entry."""
        user_id = data[CONF_TOKEN]["x_user_id"]
        await self.async_set_unique_id(str(user_id))
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
        else:
            self._abort_if_unique_id_configured()

        try:
            userdata = await self.hass.async_add_executor_job(
                _register_user, user_id, data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            )
        except RequestException as err:
            _LOGGER.error("Unable to register the user to Polar: %s", err)
            return self.async_abort(reason="cannot_connect")

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )

        name = f"{userdata['first-name']} {userdata['last-name']}"
        return self.async_create_entry(
            title=name,
            data={**data, CONF_USER_ID: user_id, CONF_NAME: name},
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle Polar options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)

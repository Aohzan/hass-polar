"""Config flow for Polar integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_oauth2_flow import _decode_jwt, _encode_jwt

from .const import (
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .polaraccesslink.accesslink import AccessLink

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Polar."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize class variables."""
        self.data = {}
        self.external_data = {}
        self.accesslink: AccessLink = None

    def get_callback_url(self) -> str:
        """Get callback url."""
        return f"{self.hass.config.external_url}{AUTH_CALLBACK_PATH}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            self.hass.http.register_view(PolarAuthCallbackView())

            return self.async_show_form(
                step_id="user",
                description_placeholders={"callback_url": self.get_callback_url()},
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        self.data = user_input
        self.accesslink = AccessLink(
            client_id=self.data[CONF_CLIENT_ID],
            client_secret=self.data[CONF_CLIENT_SECRET],
            redirect_url=self.get_callback_url(),
        )

        return await self.async_step_oauth()

    async def async_step_oauth(self, user_input=None) -> FlowResult:
        """Proceed oauth."""
        if not user_input:
            return self.async_external_step(
                step_id="oauth",
                url=self.accesslink.get_authorization_url(
                    state=_encode_jwt(
                        self.hass,
                        {
                            "flow_id": self.flow_id,
                            "redirect_uri": self.get_callback_url(),
                        },
                    )
                ),
            )

        self.external_data = user_input
        return self.async_external_step_done(next_step_id="creation")

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create config entry from external data."""
        token_response = await self.hass.async_add_executor_job(
            self.accesslink.get_access_token, self.external_data["code"]
        )

        self.data[CONF_USER_ID] = token_response["x_user_id"]
        self.data[CONF_ACCESS_TOKEN] = token_response["access_token"]

        try:
            await self.hass.async_add_executor_job(
                self.accesslink.users.register, self.data[CONF_ACCESS_TOKEN]
            )
        except requests.exceptions.HTTPError as err:
            # Error 409 Conflict means that the user has already been registered for this client, which is okay.
            if err.response.status_code != 409:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"http_error": err.response.status_code},
                )

        await self.async_set_unique_id(self.data[CONF_USER_ID])
        self._abort_if_unique_id_configured()

        userdata = await self.hass.async_add_executor_job(
            self.accesslink.get_userdata,
            self.data[CONF_USER_ID],
            self.data[CONF_ACCESS_TOKEN],
        )

        self.data[CONF_NAME] = f"{userdata['first-name']} {userdata['last-name']}"
        return self.async_create_entry(
            title=self.data[CONF_NAME],
            data=self.data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Polar options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, self.config_entry.data[CONF_SCAN_INTERVAL]
                    ),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class PolarAuthCallbackView(HomeAssistantView):
    """Polar Accesslink Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    @callback
    async def get(self, request: web.Request) -> web.Response:
        """Receive authorization token."""
        if "state" not in request.query:
            return web.Response(text="Missing state parameter")

        hass = request.app["hass"]

        state = _decode_jwt(hass, request.query["state"])

        if state is None:
            return web.Response(text="Invalid state")

        user_input: dict[str, Any] = {"state": state}

        if "code" in request.query:
            user_input["code"] = request.query["code"]
        elif "error" in request.query:
            user_input["error"] = request.query["error"]
        else:
            return web.Response(text="Missing code or error parameter")

        await hass.config_entries.flow.async_configure(
            flow_id=state["flow_id"], user_input=user_input
        )

        return web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )

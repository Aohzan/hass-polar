"""Application credentials platform for the Polar integration."""

from http import HTTPStatus
import logging
from typing import Any, cast

from aiohttp import ClientError, ClientResponseError, encode_basic_auth

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
)

from .const import ADMIN_URL
from .polaraccesslink.accesslink import ACCESS_TOKEN_URL, AUTHORIZATION_URL

_LOGGER = logging.getLogger(__name__)

# Default redirect URL used by Home Assistant for OAuth2 (My Home Assistant)
OAUTH_REDIRECT_URL = "https://my.home-assistant.io/redirect/oauth"


class PolarOAuth2Implementation(AuthImplementation):
    """Polar OAuth2 implementation.

    Polar requires the client id and secret in a Basic Authorization header
    instead of the request body.
    """

    async def _token_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Make a token request, raising the Home Assistant OAuth2 errors."""
        session = async_get_clientsession(self.hass)
        try:
            resp = await session.post(
                self.token_url,
                data=data,
                headers={
                    "Accept": "application/json;charset=UTF-8",
                    "Authorization": encode_basic_auth(
                        self.client_id, self.client_secret
                    ),
                },
            )
            if resp.status >= 400:
                try:
                    body = await resp.text()
                except ClientError:
                    body = ""
                _LOGGER.error("Polar token request failed (%s): %s", resp.status, body)
            resp.raise_for_status()
        except ClientResponseError as err:
            kwargs: dict[str, Any] = {
                "request_info": err.request_info,
                "history": err.history,
                "status": err.status,
                "message": err.message,
                "headers": err.headers,
                "domain": self.service_domain,
            }
            if (
                err.status == HTTPStatus.TOO_MANY_REQUESTS
                or err.status >= HTTPStatus.INTERNAL_SERVER_ERROR
            ):
                raise OAuth2TokenRequestTransientError(**kwargs) from err
            # Rejected request: invalid client credentials, code or token
            raise OAuth2TokenRequestReauthError(**kwargs) from err
        except ClientError as err:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain) from err

        try:
            return cast(dict[str, Any], await resp.json())
        except (ClientError, ValueError) as err:
            # Accepted request with an unusable response: not an auth failure
            _LOGGER.warning("Invalid Polar token response: %s", err)
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain) from err


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the Polar auth implementation."""
    return PolarOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=AUTHORIZATION_URL,
            token_url=ACCESS_TOKEN_URL,
        ),
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "polar_admin_url": ADMIN_URL,
        "redirect_url": OAUTH_REDIRECT_URL,
    }

"""Tests for the Polar application credentials."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.polar.application_credentials import (
    async_get_auth_implementation,
)
from custom_components.polar.const import DOMAIN
from custom_components.polar.polaraccesslink.accesslink import ACCESS_TOKEN_URL
from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from .conftest import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET

EXTERNAL_DATA = {
    "code": "abcd",
    "state": {"redirect_uri": "https://example.com/auth/external/callback"},
}


async def _resolve_token(hass: HomeAssistant) -> dict[str, Any]:
    """Exchange the authorization code for a token."""
    implementation = await async_get_auth_implementation(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )
    return await implementation.async_resolve_external_data(EXTERNAL_DATA)


async def test_token_request(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the token is returned."""
    aioclient_mock.post(
        ACCESS_TOKEN_URL, json={"access_token": ACCESS_TOKEN, "token_type": "bearer"}
    )

    assert await _resolve_token(hass) == {
        "access_token": ACCESS_TOKEN,
        "token_type": "bearer",
    }


@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [
        ({"status": HTTPStatus.BAD_REQUEST}, OAuth2TokenRequestReauthError),
        ({"status": HTTPStatus.UNAUTHORIZED}, OAuth2TokenRequestReauthError),
        ({"status": HTTPStatus.TOO_MANY_REQUESTS}, OAuth2TokenRequestTransientError),
        (
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            OAuth2TokenRequestTransientError,
        ),
        ({"status": HTTPStatus.BAD_GATEWAY}, OAuth2TokenRequestTransientError),
        ({"text": "<html>maintenance</html>"}, OAuth2TokenRequestConnectionError),
        ({"exc": ClientConnectionError()}, OAuth2TokenRequestConnectionError),
    ],
)
async def test_token_request_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_kwargs: dict[str, Any],
    error: type[Exception],
) -> None:
    """Test only a rejected token request asks to link the account again."""
    aioclient_mock.post(ACCESS_TOKEN_URL, **mock_kwargs)

    with pytest.raises(error):
        await _resolve_token(hass)

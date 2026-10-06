"""Tests for the Polar config flow."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError

from custom_components.polar.const import CONF_USER_ID, DOMAIN
from custom_components.polar.polaraccesslink.accesslink import (
    ACCESS_TOKEN_URL,
    AUTHORIZATION_URL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import ACCESS_TOKEN, CLIENT_ID, USER_DATA, USER_ID

REDIRECT_URL = "https://example.com/auth/external/callback"


def _http_error(status: int) -> HTTPError:
    """Return a requests HTTP error with the given status."""
    response = Response()
    response.status_code = status
    return HTTPError(str(status), response=response)


@pytest.fixture
def mock_flow_accesslink() -> Generator[MagicMock]:
    """Mock the Polar AccessLink client used by the config flow."""
    with patch(
        "custom_components.polar.config_flow.AccessLink", autospec=True
    ) as mock_class:
        accesslink = mock_class.return_value
        accesslink.users = MagicMock()
        accesslink.get_userdata.return_value = dict(USER_DATA)
        yield accesslink


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Do not set up the entry created by the flow."""
    with patch("custom_components.polar.async_setup_entry", return_value=True):
        yield


async def _authorize(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    url: str,
    user_id: int = USER_ID,
) -> None:
    """Check the authorize url and simulate the Polar callback."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": flow_id, "redirect_uri": REDIRECT_URL}
    )
    assert url == (
        f"{AUTHORIZATION_URL}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}&state={state}"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        ACCESS_TOKEN_URL,
        json={
            "access_token": ACCESS_TOKEN,
            "token_type": "bearer",
            "expires_in": 315359999,
            "x_user_id": user_id,
        },
    )


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_accesslink: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the whole OAuth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    await _authorize(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], result["url"]
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "John Doe"
    assert result["result"].unique_id == str(USER_ID)
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_USER_ID] == USER_ID
    assert result["data"][CONF_NAME] == "John Doe"
    assert result["options"] == {CONF_SCAN_INTERVAL: 30}

    # Polar expects the client credentials in a Basic Authorization header
    _, _, token_data, _ = aioclient_mock.mock_calls[0]
    assert "client_secret" not in token_data
    mock_flow_accesslink.users.register.assert_called_once_with(ACCESS_TOKEN)


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_flow_user_already_registered(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_accesslink: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test a user already registered to the client is accepted."""
    mock_flow_accesslink.users.register.side_effect = _http_error(HTTPStatus.CONFLICT)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _authorize(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], result["url"]
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "side_effect",
    [_http_error(HTTPStatus.INTERNAL_SERVER_ERROR), RequestsConnectionError()],
)
@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_flow_cannot_connect(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_accesslink: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the flow aborts when the user cannot be registered."""
    mock_flow_accesslink.users.register.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _authorize(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], result["url"]
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_flow_invalid_client(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow aborts when Polar rejects the client credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _authorize(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], result["url"]
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(ACCESS_TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_flow_user_rejected(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test the flow aborts when the user denies the access on Polar."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URL}
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?error=access_denied&state={state}")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_flow_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    mock_flow_accesslink: MagicMock,
) -> None:
    """Test the flow aborts when the account is already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _authorize(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], result["url"]
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_flow_accesslink.users.register.assert_not_called()


@pytest.mark.parametrize(
    ("user_id", "reason"),
    [(USER_ID, "reauth_successful"), (654321, "wrong_account")],
)
@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    mock_flow_accesslink: MagicMock,
    mock_setup_entry: None,
    user_id: int,
    reason: str,
) -> None:
    """Test the reauthentication flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _authorize(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        result["url"],
        user_id,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_options_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the options flow updates the scan interval and reloads the entry."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 10}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {CONF_SCAN_INTERVAL: 10}
    assert init_integration.runtime_data.update_interval.total_seconds() == 600


async def test_options_flow_minimum_interval(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the scan interval cannot be lower than the minimum."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 0}
        )

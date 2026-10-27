"""Tests for the Polar AccessLink client."""

from http import HTTPStatus

from aiohttp import ClientResponseError
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.polar.polaraccesslink.accesslink import (
    ACCESSLINK_URL,
    AccessLink,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import ACCESS_TOKEN, USER_ID

TRANSACTION_URL = f"{ACCESSLINK_URL}/users/{USER_ID}/activity-transactions/42"


@pytest.fixture
async def accesslink(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> AccessLink:
    """Return the client with the mocked session of Home Assistant."""
    return AccessLink(async_get_clientsession(hass))


async def test_request_headers(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the requests are authenticated with the access token."""
    aioclient_mock.get(f"{ACCESSLINK_URL}/users/{USER_ID}", json={"weight": 70})

    assert await accesslink.get_userdata(USER_ID, ACCESS_TOKEN) == {"weight": 70}
    _, _, _, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


async def test_register(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the registration sends a member id."""
    aioclient_mock.post(f"{ACCESSLINK_URL}/users", json={"polar-user-id": USER_ID})

    assert await accesslink.users.register(ACCESS_TOKEN, "member") == {
        "polar-user-id": USER_ID
    }
    _, _, data, _ = aioclient_mock.mock_calls[0]
    assert data == {"member-id": "member"}


async def test_error_status(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an error status is raised with the status and headers."""
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/exercises",
        status=HTTPStatus.TOO_MANY_REQUESTS,
        text="slow down",
        headers={"Retry-After": "60"},
    )

    with pytest.raises(ClientResponseError) as err:
        await accesslink.get_exercises(ACCESS_TOKEN)

    assert err.value.status == HTTPStatus.TOO_MANY_REQUESTS
    assert err.value.headers["Retry-After"] == "60"
    assert "slow down" in err.value.message


async def test_exercises(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the exercises are sorted by start time, invalid ones last."""
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/exercises",
        json=[
            {"id": "invalid", "start_time": "yesterday"},
            {
                "id": "paris",
                "start_time": "2026-10-05T18:30:00",
                "start_time_utc_offset": 120,
                "duration": "PT1H30M",
            },
            {"id": "utc", "start_time": "2026-10-05T17:00:00.500"},
            {"id": "offset", "start_time": "2026-10-05T12:00:00-04:00"},
            {"id": "missing"},
            {
                "id": "bad_duration",
                "start_time": "2026-10-01T08:00:00",
                "duration": "1h",
            },
        ],
    )

    exercises = await accesslink.get_exercises(ACCESS_TOKEN)

    assert [exercise["id"] for exercise in exercises] == [
        "utc",
        "paris",
        "offset",
        "bad_duration",
        "invalid",
        "missing",
    ]
    assert exercises[1]["duration"] == "1:30:00"
    assert exercises[3]["duration"] == "1h"


async def test_daily_records(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the daily records are sorted by date, most recent first."""
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/sleep/",
        json={"nights": [{"date": "2026-10-04"}, {"date": "2026-10-05"}, {}]},
    )
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/nightly-recharge/",
        json={"recharges": [{"date": "2026-10-04"}, {"date": "2026-10-05"}]},
    )
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/cardio-load",
        json=[
            {"date": "2026-10-04", "cardio_load_status": "LOAD_STATUS_OK"},
            {"date": "2026-10-05", "cardio_load_status": "LOAD_STATUS_NOT_AVAILABLE"},
            {"date": "2026-10-03", "cardio_load_status": "LOAD_STATUS_OK"},
        ],
    )

    assert await accesslink.get_sleep(ACCESS_TOKEN) == [
        {"date": "2026-10-05"},
        {"date": "2026-10-04"},
        {},
    ]
    assert [
        recharge["date"] for recharge in await accesslink.get_recharge(ACCESS_TOKEN)
    ] == ["2026-10-05", "2026-10-04"]
    assert [
        cardioload["date"]
        for cardioload in await accesslink.get_cardio_load(ACCESS_TOKEN)
    ] == ["2026-10-04", "2026-10-03"]


async def test_optional_data_unavailable(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test data depending on the device or consents is empty when unavailable."""
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/cardio-load", status=HTTPStatus.FORBIDDEN
    )
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/continuous-heart-rate/2026-10-05",
        status=HTTPStatus.NOT_FOUND,
    )

    assert await accesslink.get_cardio_load(ACCESS_TOKEN) == []
    assert await accesslink.get_continuous_heart_rate(ACCESS_TOKEN, "2026-10-05") == []


async def test_continuous_heart_rate(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the heart rate samples of a day."""
    samples = [{"heart_rate": 60, "sample_time": "08:00:00"}]
    aioclient_mock.get(
        f"{ACCESSLINK_URL}/users/continuous-heart-rate/2026-10-05",
        json={"heart_rate_samples": samples},
    )

    assert (
        await accesslink.get_continuous_heart_rate(ACCESS_TOKEN, "2026-10-05")
        == samples
    )


async def test_daily_activities(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the daily activities are read from a committed transaction."""
    aioclient_mock.post(
        f"{ACCESSLINK_URL}/users/{USER_ID}/activity-transactions",
        status=HTTPStatus.CREATED,
        json={"resource-uri": TRANSACTION_URL},
    )
    aioclient_mock.get(
        TRANSACTION_URL, json={"activity-log": [f"{TRANSACTION_URL}/activities/1"]}
    )
    aioclient_mock.get(f"{TRANSACTION_URL}/activities/1", json={"date": "2026-10-05"})
    aioclient_mock.put(TRANSACTION_URL, status=HTTPStatus.NO_CONTENT)

    assert await accesslink.get_daily_activities(USER_ID, ACCESS_TOKEN) == [
        {"date": "2026-10-05"}
    ]
    assert [method for method, *_ in aioclient_mock.mock_calls] == [
        "post",
        "get",
        "get",
        "put",
    ]


async def test_no_daily_activity(
    accesslink: AccessLink, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test nothing is read when there is no new daily activity."""
    aioclient_mock.post(
        f"{ACCESSLINK_URL}/users/{USER_ID}/activity-transactions",
        status=HTTPStatus.NO_CONTENT,
    )

    assert await accesslink.get_daily_activities(USER_ID, ACCESS_TOKEN) == []
    assert aioclient_mock.call_count == 1

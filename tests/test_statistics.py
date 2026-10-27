"""Tests for the Polar statistics builders."""

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.polar.statistics import (
    build_daily_statistics,
    build_heart_rate_statistics,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant

from .conftest import USER_ID, http_error

HEART_RATE_STATISTIC_ID = f"polar:{USER_ID}_heart_rate"


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Use a fixed time zone."""
    await hass.config.async_set_time_zone("Europe/Paris")


async def test_build_daily_statistics() -> None:
    """Test one statistic per day, at noon local time."""
    records = [
        {"date": "2026-10-05", "value": 2},
        {"date": "2026-10-04", "value": 1},
        {"date": "2026-10-03", "value": None},
        {"value": 3},
    ]

    statistics = build_daily_statistics(records, lambda record: record.get("value"))

    assert statistics == [
        {"start": datetime(2026, 10, 4, 10, tzinfo=UTC), "mean": 1, "min": 1, "max": 1},
        {"start": datetime(2026, 10, 5, 10, tzinfo=UTC), "mean": 2, "min": 2, "max": 2},
    ]


async def test_build_heart_rate_statistics() -> None:
    """Test the samples are aggregated per hour."""
    samples = [
        {"sample_time": "08:00:00", "heart_rate": 60},
        {"sample_time": "08:30:00", "heart_rate": 71},
        {"sample_time": "09:00:00", "heart_rate": 80},
        {"sample_time": "09:10:00"},
    ]

    statistics = build_heart_rate_statistics({date(2026, 10, 5): samples})

    assert statistics == [
        {
            "start": datetime(2026, 10, 5, 6, tzinfo=UTC),
            "mean": 65.5,
            "min": 60,
            "max": 71,
        },
        {
            "start": datetime(2026, 10, 5, 7, tzinfo=UTC),
            "mean": 80,
            "min": 80,
            "max": 80,
        },
    ]


def _requested_days(mock_accesslink: MagicMock) -> list[str]:
    """Return the days of the continuous heart rate requests, and forget them."""
    days = [
        call.args[1] for call in mock_accesslink.get_continuous_heart_rate.mock_calls
    ]
    mock_accesslink.get_continuous_heart_rate.reset_mock()
    return days


async def _heart_rate_days(hass: HomeAssistant) -> list[date]:
    """Return the local days having heart rate statistics."""
    await async_wait_recording_done(hass)
    statistics = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2026, 9, 1, tzinfo=UTC),
        None,
        {HEART_RATE_STATISTIC_ID},
        "hour",
        None,
        {"mean"},
    )
    return sorted(
        {
            datetime.fromtimestamp(row["start"], UTC).date()
            for row in statistics.get(HEART_RATE_STATISTIC_ID, [])
        }
    )


@pytest.mark.parametrize(
    "status", [HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.UNAUTHORIZED]
)
@pytest.mark.usefixtures("setup_credentials")
async def test_heart_rate_import_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    mock_accesslink: MagicMock,
    status: HTTPStatus,
) -> None:
    """Test a failed day of the backfill is fetched again on the next run."""
    freezer.move_to(datetime(2026, 10, 5, 10, tzinfo=UTC))
    failed_day = "2026-09-20"

    def get_heart_rate(_access_token: str, day: str) -> list[dict[str, Any]]:
        if day == failed_day:
            raise http_error(status)
        return [{"sample_time": "08:00:00", "heart_rate": 60}]

    mock_accesslink.get_continuous_heart_rate.side_effect = get_heart_rate
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    days = _requested_days(mock_accesslink)
    assert days[0] == "2026-09-08"
    assert days[-1] == failed_day
    # The days fetched before the failure are imported
    assert await _heart_rate_days(hass) == [date(2026, 9, day) for day in range(8, 20)]

    failed_day = ""
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    days = _requested_days(mock_accesslink)
    assert days[0] == "2026-09-20"
    assert days[-1] == "2026-10-05"
    assert (await _heart_rate_days(hass))[-1] == date(2026, 10, 5)

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Only the previous day and today once the backfill is done
    assert _requested_days(mock_accesslink) == ["2026-10-04", "2026-10-05"]

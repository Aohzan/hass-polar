"""Tests for the Polar statistics builders."""

from datetime import UTC, date, datetime

import pytest

from custom_components.polar.statistics import (
    build_daily_statistics,
    build_heart_rate_statistics,
)
from homeassistant.core import HomeAssistant


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

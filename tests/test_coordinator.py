"""Tests for the Polar coordinator helpers."""

from datetime import UTC, datetime

from custom_components.polar.coordinator import last_sync, merge_daily_activities


def test_merge_daily_activities_keeps_latest_summary() -> None:
    """Test the most recent summary of each day is kept, newest day first."""
    stored = [
        {"date": "2026-10-04", "created": "2026-10-04T22:00:00.000Z", "steps": 1},
        {"date": "2026-10-05", "created": "2026-10-05T08:00:00.000Z", "steps": 2},
    ]
    new = [
        {"date": "2026-10-05", "created": "2026-10-05T20:00:00.000Z", "steps": 4},
        {"date": "2026-10-05", "created": "2026-10-05T12:00:00.000Z", "steps": 3},
    ]

    assert merge_daily_activities(stored, new) == [new[0], stored[0]]


def test_merge_daily_activities_limits_history() -> None:
    """Test only the last 28 days are kept."""
    activities = [{"date": f"2026-09-{day:02}"} for day in range(1, 31)]

    merged = merge_daily_activities([], activities)

    assert len(merged) == 28
    assert merged[0]["date"] == "2026-09-30"
    assert merged[-1]["date"] == "2026-09-03"


def test_last_sync() -> None:
    """Test the most recent upload of daily activities and exercises is used."""
    daily_activities = [{"created": "2026-10-05T08:00:00.000Z"}, {"date": "2026-10-04"}]
    exercises = [{"upload_time": "2026-10-05T19:30:00.000Z"}, {"upload_time": None}]

    assert last_sync(daily_activities, exercises) == datetime(
        2026, 10, 5, 19, 30, tzinfo=UTC
    )
    assert last_sync([], []) is None


def test_last_sync_without_time_zone() -> None:
    """Test timestamps sent without time zone are read as UTC."""
    daily_activities = [{"created": "2026-10-05T20:00:00.000"}]
    exercises = [{"upload_time": "2026-10-05T19:30:00.000Z"}]

    assert last_sync(daily_activities, exercises) == datetime(
        2026, 10, 5, 20, tzinfo=UTC
    )

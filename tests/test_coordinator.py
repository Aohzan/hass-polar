"""Tests for the Polar coordinator helpers."""

from custom_components.polar.coordinator import merge_daily_activities


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

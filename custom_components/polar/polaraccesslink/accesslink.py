"""Accesslink library."""

from datetime import UTC, datetime, timedelta, timezone
import logging
from typing import Any

from aiohttp import ClientResponseError, ClientSession
import isodate

from homeassistant.util import dt as dt_util

from .endpoints.daily_activity import DailyActivity
from .endpoints.users import Users
from .oauth2 import OAuth2Client

AUTHORIZATION_URL = "https://flow.polar.com/oauth2/authorization"
ACCESS_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
ACCESSLINK_URL = "https://www.polaraccesslink.com/v3"

_LOGGER = logging.getLogger(__name__)


def format_duration(raw_duration: str) -> str:
    """Format a Polar ISO 8601 duration as H:MM:SS, unchanged when invalid."""
    try:
        return str(isodate.parse_duration(raw_duration))
    except isodate.ISO8601Error, TypeError, ValueError:
        return raw_duration


def exercise_start_utc(exercise: dict[str, Any]) -> datetime | None:
    """Return the start time of an exercise in UTC, None when invalid.

    Polar sends the local start time without time zone, and its offset to UTC
    in minutes apart. Without offset, the start time is read as UTC.
    """
    start = dt_util.parse_datetime(exercise.get("start_time") or "")
    if start is None:
        return None
    if start.tzinfo is None:
        offset = exercise.get("start_time_utc_offset") or 0
        start = start.replace(tzinfo=timezone(timedelta(minutes=offset)))
    return dt_util.as_utc(start)


def _by_date(record: dict[str, Any]) -> str:
    """Return the ISO 8601 date of a daily record, to sort records by date."""
    return record.get("date") or ""


class AccessLink:
    """Wrapper class for Polar Open AccessLink API v3."""

    def __init__(self, session: ClientSession) -> None:
        """Init an Accesslink access."""
        self.oauth = OAuth2Client(session, url=ACCESSLINK_URL)
        self.users = Users(oauth=self.oauth)
        self.daily_activity = DailyActivity(oauth=self.oauth)

    async def get_exercises(self, access_token: str) -> list[dict[str, Any]]:
        """Get the exercises of the last 30 days, most recent first."""
        exercises = await self.oauth.get(
            endpoint="/exercises", access_token=access_token
        )
        for exercise in exercises:
            if "duration" in exercise:
                exercise["duration"] = format_duration(exercise["duration"])
        # Exercises without a valid start time are listed last
        oldest = datetime.min.replace(tzinfo=UTC)
        return sorted(
            exercises,
            key=lambda exercise: exercise_start_utc(exercise) or oldest,
            reverse=True,
        )

    async def get_sleep(self, access_token: str) -> list[dict[str, Any]]:
        """Get last sleeps."""
        sleepdata = await self.oauth.get(
            endpoint="/users/sleep/", access_token=access_token
        )
        return sorted(sleepdata["nights"], key=_by_date, reverse=True)

    async def get_recharge(self, access_token: str) -> list[dict[str, Any]]:
        """Get last nightly recharges."""
        rechargedata = await self.oauth.get(
            endpoint="/users/nightly-recharge/", access_token=access_token
        )
        return sorted(rechargedata["recharges"], key=_by_date, reverse=True)

    async def get_cardio_load(self, access_token: str) -> list[dict[str, Any]]:
        """Get cardio loads of the last 28 days, most recent first.

        Days without a computed value are dropped. Returns an empty list when
        the data is not available (unsupported device or missing consents).
        """
        try:
            cardioloads = await self.oauth.get(
                endpoint="/users/cardio-load", access_token=access_token
            )
        except ClientResponseError as err:
            _LOGGER.debug("Unable to get cardio load: %s", err)
            return []
        return sorted(
            (
                cardioload
                for cardioload in cardioloads or []
                if cardioload.get("cardio_load_status") != "LOAD_STATUS_NOT_AVAILABLE"
            ),
            key=_by_date,
            reverse=True,
        )

    async def get_continuous_heart_rate(
        self, access_token: str, day: str
    ) -> list[dict[str, Any]]:
        """Get continuous heart rate samples of a day (ISO-8601 date).

        Returns an empty list when there is no data for that day or when the
        data is not available (unsupported device or missing consents).
        """
        try:
            heartrate = await self.oauth.get(
                endpoint=f"/users/continuous-heart-rate/{day}",
                access_token=access_token,
            )
        except ClientResponseError as err:
            _LOGGER.debug("Unable to get continuous heart rate for %s: %s", day, err)
            return []
        return heartrate.get("heart_rate_samples") or []

    async def get_userdata(self, user_id: int, access_token: str) -> dict[str, Any]:
        """Get user data."""
        return await self.users.get_information(user_id, access_token)

    async def get_daily_activities(
        self, user_id: int, access_token: str
    ) -> list[dict[str, Any]]:
        """Get the daily activity summaries synced since the last call.

        Polar only returns the summaries that were not committed yet, and may
        return several summaries for the same day (one per sync).
        """
        transaction = await self.daily_activity.create_transaction(
            user_id=user_id, access_token=access_token
        )
        if not transaction:
            _LOGGER.debug("No new daily activity available")
            return []

        activities = [
            await transaction.get_activity_summary(url)
            for url in (await transaction.list_activities())["activity-log"]
        ]
        await transaction.commit()
        _LOGGER.debug("Got %s new daily activities", len(activities))
        return activities

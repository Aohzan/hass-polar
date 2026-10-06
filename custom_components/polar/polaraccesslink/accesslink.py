"""Accesslink library."""

from datetime import datetime
import logging

import isodate
from requests.exceptions import HTTPError

from .endpoints.daily_activity import DailyActivity
from .endpoints.users import Users
from .oauth2 import OAuth2Client

AUTHORIZATION_URL = "https://flow.polar.com/oauth2/authorization"
ACCESS_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
ACCESSLINK_URL = "https://www.polaraccesslink.com/v3"

_LOGGER = logging.getLogger(__name__)


def format_duration(raw_duration: str) -> str:
    """Format a Polar ISO 8601 duration as H:MM:SS."""
    return str(isodate.parse_duration(raw_duration))


class AccessLink:
    """Wrapper class for Polar Open AccessLink API v3."""

    def __init__(self):
        """Init an Accesslink access."""
        self.oauth = OAuth2Client(url=ACCESSLINK_URL)
        self.users = Users(oauth=self.oauth)
        self.daily_activity = DailyActivity(oauth=self.oauth)

    def close(self):
        """Close the underlying HTTP connections."""
        self.oauth.close()

    def get_exercises(self, access_token):
        """Get last exercises."""
        exercises = self.oauth.get(endpoint="/exercises", access_token=access_token)
        for exercise in exercises:
            if "duration" in exercise:
                exercise["duration"] = format_duration(exercise["duration"])
        return sorted(
            exercises,
            key=lambda t: datetime.strptime(t["start_time"], "%Y-%m-%dT%H:%M:%S"),
            reverse=True,
        )

    def get_sleep(self, access_token):
        """Get last sleeps."""
        sleepdata = self.oauth.get(endpoint="/users/sleep/", access_token=access_token)[
            "nights"
        ]
        return sorted(
            sleepdata,
            key=lambda t: datetime.strptime(t["date"], "%Y-%m-%d"),
            reverse=True,
        )

    def get_recharge(self, access_token):
        """Get last nightly recharges."""
        rechargedata = self.oauth.get(
            endpoint="/users/nightly-recharge/", access_token=access_token
        )["recharges"]
        return sorted(
            rechargedata,
            key=lambda t: datetime.strptime(t["date"], "%Y-%m-%d"),
            reverse=True,
        )

    def get_cardio_load(self, access_token):
        """Get cardio loads of the last 28 days, most recent first.

        Days without a computed value are dropped. Returns an empty list when
        the data is not available (unsupported device or missing consents).
        """
        try:
            cardioloads = self.oauth.get(
                endpoint="/users/cardio-load", access_token=access_token
            )
        except HTTPError as err:
            _LOGGER.debug("Unable to get cardio load: %s", err)
            return []
        return sorted(
            (
                cardioload
                for cardioload in cardioloads or []
                if cardioload.get("cardio_load_status") != "LOAD_STATUS_NOT_AVAILABLE"
            ),
            key=lambda t: datetime.strptime(t["date"], "%Y-%m-%d"),
            reverse=True,
        )

    def get_continuous_heart_rate(self, access_token, day):
        """Get continuous heart rate samples of a day (ISO-8601 date).

        Returns an empty list when there is no data for that day or when the
        data is not available (unsupported device or missing consents).
        """
        try:
            heartrate = self.oauth.get(
                endpoint=f"/users/continuous-heart-rate/{day}",
                access_token=access_token,
            )
        except HTTPError as err:
            _LOGGER.debug("Unable to get continuous heart rate for %s: %s", day, err)
            return []
        return heartrate.get("heart_rate_samples") or []

    def get_userdata(self, user_id, access_token):
        """Get user data."""
        return self.users.get_information(user_id, access_token)

    def get_daily_activities(self, user_id, access_token):
        """Get the daily activity summaries synced since the last call.

        Polar only returns the summaries that were not committed yet, and may
        return several summaries for the same day (one per sync).
        """
        transaction = self.daily_activity.create_transaction(
            user_id=user_id, access_token=access_token
        )
        if not transaction:
            _LOGGER.debug("No new daily activity available")
            return []

        activities = [
            transaction.get_activity_summary(url)
            for url in transaction.list_activities()["activity-log"]
        ]
        transaction.commit()
        _LOGGER.debug("Got %s new daily activities", len(activities))
        return activities

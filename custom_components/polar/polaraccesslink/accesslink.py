"""Accesslink library."""
from datetime import date, datetime, timedelta
import json
import logging
from os import path

import isodate
from requests.exceptions import HTTPError

from .endpoints.daily_activity import DailyActivity
from .endpoints.physical_info import PhysicalInfo
from .endpoints.pull_notifications import PullNotifications
from .endpoints.training_data import TrainingData
from .endpoints.users import Users
from .oauth2 import OAuth2Client

AUTHORIZATION_URL = "https://flow.polar.com/oauth2/authorization"
ACCESS_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
ACCESSLINK_URL = "https://www.polaraccesslink.com/v3"

_LOGGER = logging.getLogger(__name__)


def parse_date(raw_date: str) -> str:
    """Parse Polar date format."""
    return str(isodate.parse_duration(raw_date))


class AccessLink:
    """Wrapper class for Polar Open AccessLink API v3."""

    def __init__(self, client_id, client_secret, redirect_url=None):
        """Init an Accesslink access."""
        if not client_id or not client_secret:
            raise ValueError("Client id and secret must be provided.")

        self.oauth = OAuth2Client(
            url=ACCESSLINK_URL,
            authorization_url=AUTHORIZATION_URL,
            access_token_url=ACCESS_TOKEN_URL,
            redirect_url=redirect_url,
            client_id=client_id,
            client_secret=client_secret,
        )

        self.users = Users(oauth=self.oauth)
        self.pull_notifications = PullNotifications(oauth=self.oauth)
        self.training_data = TrainingData(oauth=self.oauth)
        self.physical_info = PhysicalInfo(oauth=self.oauth)
        self.daily_activity = DailyActivity(oauth=self.oauth)

    def get_authorization_url(self, state=None):
        """Get the authorization url for the client."""
        return self.oauth.get_authorization_url(state=state)

    def get_access_token(self, authorization_code):
        """Request access token for a user."""
        return self.oauth.get_access_token(authorization_code)

    def get_exercises(self, access_token):
        """Get last exercises."""
        exercises = self.oauth.get(endpoint="/exercises", access_token=access_token)
        for exercise in exercises:
            exercise["duration"] = parse_date(exercise["duration"])
            # Flatten the nested heart-rate statistics so they can be exposed
            # as dedicated sensors (the API returns {"average": .., "maximum": ..}).
            heart_rate = exercise.get("heart_rate") or exercise.get("heart-rate") or {}
            exercise["heart_rate_average"] = heart_rate.get("average")
            exercise["heart_rate_maximum"] = heart_rate.get("maximum")
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

    def get_continuous_heart_rate(self, access_token):
        """Get latest continuous heart rate samples.

        Tries today first and falls back to yesterday, since the current day
        may not have any samples yet. Returns a summary dict with the latest
        value plus min/max/average computed from the 5-minute samples, or an
        empty dict when no data is available (or the device does not support
        continuous heart rate).
        """
        for day in (date.today(), date.today() - timedelta(days=1)):
            try:
                data = self.oauth.get(
                    endpoint=f"/users/continuous-heart-rate/{day.isoformat()}",
                    access_token=access_token,
                )
            except HTTPError as err:
                status = getattr(err.response, "status_code", None)
                if status == 404:
                    continue
                _LOGGER.warning(
                    "Unable to get continuous heart rate (HTTP %s)", status
                )
                return {}

            values = [
                sample["heart_rate"]
                for sample in data.get("heart_rate_samples") or []
                if sample.get("heart_rate") is not None
            ]
            if values:
                return {
                    "date": data.get("date"),
                    "latest": values[-1],
                    "min": min(values),
                    "max": max(values),
                    "average": round(sum(values) / len(values)),
                    "samples_count": len(values),
                }
        return {}

    def get_continuous_heart_rate_samples(self, access_token, day):
        """Return raw continuous heart rate samples for an ISO date.

        Used for historical statistics import. Returns the list of
        ``{"heart_rate", "sample_time"}`` samples, or an empty list when there
        is no data for the day (or the device does not support it).
        """
        try:
            data = self.oauth.get(
                endpoint=f"/users/continuous-heart-rate/{day}",
                access_token=access_token,
            )
        except HTTPError as err:
            status = getattr(err.response, "status_code", None)
            if status != 404:
                _LOGGER.warning(
                    "Unable to get continuous heart rate for %s (HTTP %s)",
                    day,
                    status,
                )
            return []
        return data.get("heart_rate_samples") or []

    def get_cardio_load(self, access_token):
        """Get cardio load (training load) entries for the last 28 days.

        Entries without a computed value (status ``LOAD_STATUS_NOT_AVAILABLE``)
        are filtered out. Returns the remaining entries sorted most recent
        first, or an empty list when no data is available.
        """
        try:
            data = self.oauth.get(
                endpoint="/users/cardio-load", access_token=access_token
            )
        except HTTPError as err:
            _LOGGER.warning(
                "Unable to get cardio load (HTTP %s)",
                getattr(err.response, "status_code", None),
            )
            return []

        entries = [
            entry
            for entry in (data or [])
            if entry.get("cardio_load_status") != "LOAD_STATUS_NOT_AVAILABLE"
        ]
        return sorted(entries, key=lambda entry: entry.get("date", ""), reverse=True)

    def get_userdata(self, user_id, access_token):
        """Get user data."""
        return self.oauth.get(
            endpoint="/users/" + str(user_id), access_token=access_token
        )

    def get_daily_activities(self, user_id, access_token, state_file_path):
        """Get daily activities from Polar or backup file."""
        activities = []

        transaction = self.daily_activity.create_transaction(
            user_id=user_id, access_token=access_token
        )

        if not transaction:
            try:
                if path.isfile(state_file_path):
                    _LOGGER.debug(
                        "No new daily activity available, get from backup file"
                    )
                    with open(state_file_path, encoding="utf-8") as state_file:
                        activities = json.loads(state_file.read())
                else:
                    _LOGGER.debug(
                        "No daily activity available, will try for the next sync"
                    )
            except OSError as exc:
                _LOGGER.error(
                    "Unable to get daily activities from backup file %s: %s",
                    state_file_path,
                    exc,
                )
        else:
            _LOGGER.debug(
                "New daily activity available, get it and save to backup file"
            )
            resource_urls = transaction.list_activities()["activity-log"]

            for url in resource_urls:
                actity = transaction.get_activity_summary(url)
                actity["duration"] = parse_date(actity["duration"])
                activities.append(actity)

            transaction.commit()

            # sort by date
            activities = sorted(
                activities,
                key=lambda t: datetime.strptime(t["date"], "%Y-%m-%d"),
                reverse=True,
            )

            # backup activities
            try:
                with open(state_file_path, "w+", encoding="utf-8") as state_file:
                    json.dump(activities, state_file, sort_keys=True, indent=4)
            except OSError as exc:
                _LOGGER.error(
                    "Unable to write daily activities to backup file %s: %s",
                    state_file_path,
                    exc,
                )

        return activities

"""Accesslink library."""
from datetime import datetime
import json
import logging

import isodate

from . import endpoints
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

        self.users = endpoints.Users(oauth=self.oauth)
        self.pull_notifications = endpoints.PullNotifications(oauth=self.oauth)
        self.training_data = endpoints.TrainingData(oauth=self.oauth)
        self.physical_info = endpoints.PhysicalInfo(oauth=self.oauth)
        self.daily_activity = endpoints.DailyActivity(oauth=self.oauth)

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
            _LOGGER.debug("No new daily activity available, get from backup file")
            try:
                state_file = open(state_file_path, encoding="utf-8")
                activities = json.loads(state_file.read())
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

"""Daily activity endpoint."""
from .daily_activity_transaction import DailyActivityTransaction
from .resource import Resource


class DailyActivity(Resource):
    """This resource allows partners to access their users' daily activity data."""

    def create_transaction(self, user_id, access_token):
        """Initiate daily activity transaction."""
        response = self._post(
            endpoint=f"/users/{user_id}/activity-transactions",
            access_token=access_token,
        )
        if not response:
            return None

        return DailyActivityTransaction(
            oauth=self.oauth,
            transaction_url=response["resource-uri"],
            user_id=user_id,
            access_token=access_token,
        )

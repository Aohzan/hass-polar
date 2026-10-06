"""Daily activity transaction."""

from .transaction import Transaction


class DailyActivityTransaction(Transaction):
    """Daily activity transaction."""

    def list_activities(self):
        """Get a list of activity resource urls in the transaction."""
        return self._get(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

    def get_activity_summary(self, url):
        """Get user's activity summary from the transaction."""
        return self._get(endpoint=None, url=url, access_token=self.access_token)

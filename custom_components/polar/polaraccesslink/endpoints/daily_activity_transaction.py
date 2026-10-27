"""Daily activity transaction."""

from typing import Any

from .transaction import Transaction


class DailyActivityTransaction(Transaction):
    """Daily activity transaction."""

    async def list_activities(self) -> dict[str, Any]:
        """Get a list of activity resource urls in the transaction."""
        return await self._get(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

    async def get_activity_summary(self, url: str) -> dict[str, Any]:
        """Get user's activity summary from the transaction."""
        return await self._get(endpoint=None, url=url, access_token=self.access_token)

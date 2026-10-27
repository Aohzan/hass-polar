"""Generic transaction."""

from typing import Any

from ..oauth2 import OAuth2Client
from .resource import Resource


class Transaction(Resource):
    """Generic transaction."""

    def __init__(
        self,
        oauth: OAuth2Client,
        transaction_url: str,
        user_id: int,
        access_token: str,
    ) -> None:
        """Init the transaction object."""
        super().__init__(oauth)
        self.transaction_url = transaction_url
        self.user_id = user_id
        self.access_token = access_token

    async def commit(self) -> Any:
        """Commit the transaction."""
        return await self._put(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

"""Generic class for resource."""

from typing import Any

from ..oauth2 import OAuth2Client


class Resource:
    """Resource class."""

    def __init__(self, oauth: OAuth2Client) -> None:
        """Init class."""
        self.oauth = oauth

    async def _get(self, *args: Any, **kwargs: Any) -> Any:
        return await self.oauth.get(*args, **kwargs)

    async def _post(self, *args: Any, **kwargs: Any) -> Any:
        return await self.oauth.post(*args, **kwargs)

    async def _put(self, *args: Any, **kwargs: Any) -> Any:
        return await self.oauth.put(*args, **kwargs)

    async def _delete(self, *args: Any, **kwargs: Any) -> Any:
        return await self.oauth.delete(*args, **kwargs)

"""Users."""

from typing import Any
import uuid

from .resource import Resource


class Users(Resource):
    """Manage the users registered to the client."""

    async def register(self, access_token: str, member_id: str | None = None) -> Any:
        """Registration."""
        return await self._post(
            endpoint="/users",
            access_token=access_token,
            json={"member-id": member_id or uuid.uuid4().hex},
        )

    async def get_information(self, user_id: int, access_token: str) -> dict[str, Any]:
        """List user's basic information."""
        return await self._get(
            endpoint=f"/users/{user_id}",
            access_token=access_token,
        )

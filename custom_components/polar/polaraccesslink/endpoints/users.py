"""Users."""

import uuid

from .resource import Resource


class Users(Resource):
    """Manage the users registered to the client."""

    def register(self, access_token, member_id=None):
        """Registration."""
        return self._post(
            endpoint="/users",
            access_token=access_token,
            json={"member-id": member_id or uuid.uuid4().hex},
        )

    def get_information(self, user_id, access_token):
        """List user's basic information."""
        return self._get(
            endpoint=f"/users/{user_id}",
            access_token=access_token,
        )

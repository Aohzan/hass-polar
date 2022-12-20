"""Users."""
import uuid

from .resource import Resource


class Users(Resource):
    """This resource provides all the necessary functions to manage users."""

    def register(self, access_token, member_id=uuid.uuid4().hex):
        """Registration."""
        return self._post(
            endpoint="/users", access_token=access_token, json={"member-id": member_id}
        )

    def delete(self, user_id, access_token):
        """De-registration."""
        return self._delete(
            endpoint=f"/users/{user_id}",
            access_token=access_token,
        )

    def get_information(self, user_id, access_token):
        """List user's basic information."""
        return self._get(
            endpoint=f"/users/{user_id}",
            access_token=access_token,
        )

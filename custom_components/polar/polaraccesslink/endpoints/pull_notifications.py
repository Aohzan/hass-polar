"""Pull notifications."""
from .resource import Resource


class PullNotifications(Resource):
    """This resource allows partners to check if their users have available data for downloading."""

    def list(self):
        """List available data."""
        return self._get(endpoint="/notifications")

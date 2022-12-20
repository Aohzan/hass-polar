"""Generic transaction."""
from .resource import Resource


class Transaction(Resource):
    """Generic transaction."""

    def __init__(self, oauth, transaction_url, user_id, access_token):
        """Init the transaction object."""
        super().__init__(oauth)
        self.transaction_url = transaction_url
        self.user_id = user_id
        self.access_token = access_token

    def commit(self):
        """Commit the transaction."""
        return self._put(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

"""Physical information transaction."""
from .transaction import Transaction


class PhysicalInfoTransaction(Transaction):
    """Physical information transaction."""

    def list_physical_infos(self):
        """Get a list of physical info resource urls in the transaction."""
        return self._get(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

    def get_physical_info(self, url):
        """Get user's physical information from the transaction."""
        return self._get(endpoint=None, url=url, access_token=self.access_token)

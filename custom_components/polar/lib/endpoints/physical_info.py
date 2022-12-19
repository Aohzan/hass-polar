"""Physical information."""
from .physical_info_transaction import PhysicalInfoTransaction
from .resource import Resource


class PhysicalInfo(Resource):
    """This resource allows partners to access their users' physical information."""

    def create_transaction(self, user_id, access_token):
        """Initiate physical info transaction."""
        response = self._post(
            endpoint=f"/users/{user_id}/physical-information-transactions",
            access_token=access_token,
        )
        if not response:
            return None

        return PhysicalInfoTransaction(
            oauth=self.oauth,
            transaction_url=response["resource-uri"],
            user_id=user_id,
            access_token=access_token,
        )

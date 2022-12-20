"""Training data."""
from .resource import Resource
from .training_data_transaction import TrainingDataTransaction


class TrainingData(Resource):
    """This resource allows partners to access their users' training data."""

    def create_transaction(self, user_id, access_token):
        """Initiate exercise transaction."""
        response = self._post(
            endpoint=f"/users/{user_id}/exercise-transactions",
            access_token=access_token,
        )
        if not response:
            return None

        return TrainingDataTransaction(
            oauth=self.oauth,
            transaction_url=response["resource-uri"],
            user_id=user_id,
            access_token=access_token,
        )

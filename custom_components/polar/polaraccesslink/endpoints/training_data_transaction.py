"""Training data transaction."""
from .transaction import Transaction


class TrainingDataTransaction(Transaction):
    """Training data transaction."""

    def list_exercises(self):
        """Retrieve list of urls to available exercises."""
        return self._get(
            endpoint=None, url=self.transaction_url, access_token=self.access_token
        )

    def get_exercise_summary(self, url):
        """Retrieve training session summary data."""
        return self._get(endpoint=None, url=url, access_token=self.access_token)

    def get_gpx(self, url):
        """Retrieve training session summary data in GPX format."""
        return self._get(
            endpoint=None,
            url=url + "/gpx",
            access_token=self.access_token,
            headers={"Accept": "application/gpx+xml"},
        )

    def get_tcx(self, url):
        """Retrieve training session summary data in TCX format."""
        return self._get(
            endpoint=None,
            url=url + "/tcx",
            access_token=self.access_token,
            headers={"Accept": "application/vnd.garmin.tcx+xml"},
        )

    def get_heart_rate_zones(self, url):
        """Retrieve heart rate zones in training session."""
        return self._get(
            endpoint=None, url=url + "/heart-rate-zones", access_token=self.access_token
        )

    def get_available_samples(self, url):
        """Retrieve list of urls to available samples in training session."""
        return self._get(
            endpoint=None, url=url + "/samples", access_token=self.access_token
        )

    def get_samples(self, url):
        """Retrieve sample data of given type."""
        return self._get(endpoint=None, url=url, access_token=self.access_token)

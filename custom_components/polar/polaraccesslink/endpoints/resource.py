"""Generic class for resource."""


class Resource:
    """Resource class."""

    def __init__(self, oauth):
        """Init class."""
        self.oauth = oauth

    def _get(self, *args, **kwargs):
        return self.oauth.get(*args, **kwargs)

    def _post(self, *args, **kwargs):
        return self.oauth.post(*args, **kwargs)

    def _put(self, *args, **kwargs):
        return self.oauth.put(*args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self.oauth.delete(*args, **kwargs)

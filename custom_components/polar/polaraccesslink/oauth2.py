"""OAuth access for Polar Access Link."""

import logging

import requests
from requests.exceptions import HTTPError

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60


class OAuth2Client:
    """Make requests to Polar Access Link on behalf of a user."""

    def __init__(self, url):
        """Init the client object."""
        self.url = url
        self.session = requests.Session()

    def close(self):
        """Close the underlying HTTP connections."""
        self.session.close()

    def get_auth_headers(self, access_token):
        """Get authorization headers for user level api resources."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def __parse_response(self, response):
        """Parse response."""
        if response.status_code >= 400:
            message = f"{response.status_code} {response.reason}: {response.text}"
            raise HTTPError(message, response=response)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except ValueError:
            return response.text

    def __request(self, method, endpoint, access_token, url=None, **kwargs):
        """Make a request, to `url` or to the `endpoint` of the API."""
        if endpoint is not None:
            url = self.url + endpoint

        _LOGGER.debug("%s request to URL: %s", method.upper(), url)

        response = self.session.request(
            method=method,
            url=url,
            headers=self.get_auth_headers(access_token),
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        return self.__parse_response(response)

    def get(self, endpoint, access_token, **kwargs):
        """Make a GET request."""
        return self.__request("get", endpoint, access_token, **kwargs)

    def post(self, endpoint, access_token, **kwargs):
        """Make a POST request."""
        return self.__request("post", endpoint, access_token, **kwargs)

    def put(self, endpoint, access_token, **kwargs):
        """Make a PUT request."""
        return self.__request("put", endpoint, access_token, **kwargs)

    def delete(self, endpoint, access_token, **kwargs):
        """Make a DELETE request."""
        return self.__request("delete", endpoint, access_token, **kwargs)

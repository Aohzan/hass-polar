"""OAuth access for Polar Access Link."""
import logging
from urllib.parse import urlencode

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

_LOGGER = logging.getLogger(__name__)


class OAuth2Client:
    """Wrapper class for OAuth2 requests."""

    def __init__(
        self,
        url,
        authorization_url,
        access_token_url,
        redirect_url,
        client_id,
        client_secret,
    ):
        """Init the client object."""
        self.url = url
        self.authorization_url = authorization_url
        self.access_token_url = access_token_url
        self.redirect_url = redirect_url
        self.client_id = client_id
        self.client_secret = client_secret

    def get_auth_headers(self, access_token):
        """Get authorization headers for user level api resources."""

        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_authorization_url(self, response_type="code", state=None):
        """Build authorization url for the client."""

        params = {
            "client_id": self.client_id,
            "response_type": response_type,
        }

        if state:
            params["state"] = state

        if self.redirect_url:
            params["redirect_uri"] = self.redirect_url

        return "{url}?{params}".format(
            url=self.authorization_url, params=urlencode(params)
        )

    def get_access_token(self, authorization_code):
        """Exchange authorization code for an access token."""

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json;charset=UTF-8",
        }

        data = {"grant_type": "authorization_code", "code": authorization_code}

        if self.redirect_url:
            data["redirect_uri"] = self.redirect_url

        _LOGGER.debug("Fetching access token from auth code")

        return self.post(
            endpoint=None, url=self.access_token_url, data=data, headers=headers
        )

    def __build_endpoint_kwargs(self, **kwargs):
        """Create endpoint url for requests."""

        if "endpoint" in kwargs:
            if kwargs["endpoint"] is not None:
                kwargs["url"] = self.url + kwargs["endpoint"]
            del kwargs["endpoint"]

        return kwargs

    def __build_auth_kwargs(self, **kwargs):
        """Build the authentication to make requests."""

        if "access_token" in kwargs:
            headers = self.get_auth_headers(kwargs["access_token"])

            if "headers" in kwargs:
                headers.update(kwargs["headers"])

            kwargs["headers"] = headers
            del kwargs["access_token"]
        elif "auth" not in kwargs:
            kwargs["auth"] = HTTPBasicAuth(self.client_id, self.client_secret)

        return kwargs

    def __build_request_kwargs(self, **kwargs):
        """Build requests."""
        kwargs = self.__build_endpoint_kwargs(**kwargs)
        kwargs = self.__build_auth_kwargs(**kwargs)
        return kwargs

    def __parse_response(self, response):
        """Parse response."""
        if response.status_code >= 400:
            message = "{code} {reason}: {body}".format(
                code=response.status_code, reason=response.reason, body=response.text
            )
            raise HTTPError(message, response=response)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except ValueError:
            return response.text

    def __request(self, method, **kwargs):
        """Make a request."""
        kwargs = self.__build_request_kwargs(**kwargs)

        _LOGGER.debug("%s request to URL: %s", method.upper(), kwargs["url"])

        response = requests.request(method=method, timeout=60, **kwargs)
        return self.__parse_response(response)

    def get(self, endpoint, **kwargs):
        """Make a GET request."""
        return self.__request("get", endpoint=endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        """Make a POST request."""
        return self.__request("post", endpoint=endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        """Make a PUT request."""
        return self.__request("put", endpoint=endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        """Make a DELETE request."""
        return self.__request("delete", endpoint=endpoint, **kwargs)

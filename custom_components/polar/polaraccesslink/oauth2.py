"""OAuth access for Polar Access Link."""

import json
import logging
from typing import Any

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=60)


class OAuth2Client:
    """Make requests to Polar Access Link on behalf of a user.

    Errors are raised as aiohttp exceptions: ClientResponseError when Polar
    answers with an error status, other ClientError or TimeoutError otherwise.
    """

    def __init__(self, session: ClientSession, url: str) -> None:
        """Init the client object."""
        self.session = session
        self.url = url

    def get_auth_headers(self, access_token: str) -> dict[str, str]:
        """Get authorization headers for user level api resources."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str | None,
        access_token: str,
        url: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make a request, to `url` or to the `endpoint` of the API."""
        if endpoint is not None:
            url = self.url + endpoint
        assert url is not None

        _LOGGER.debug("%s request to URL: %s", method.upper(), url)

        async with self.session.request(
            method,
            url,
            headers=self.get_auth_headers(access_token),
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        ) as response:
            body = await response.text()
            try:
                response.raise_for_status()
            except ClientResponseError as err:
                # Polar explains the error in the body
                err.message = f"{err.message}: {body}"
                raise

        if response.status == 204:
            return {}

        try:
            return json.loads(body)
        except ValueError:
            return body

    async def get(self, endpoint: str | None, access_token: str, **kwargs: Any) -> Any:
        """Make a GET request."""
        return await self._request("get", endpoint, access_token, **kwargs)

    async def post(self, endpoint: str | None, access_token: str, **kwargs: Any) -> Any:
        """Make a POST request."""
        return await self._request("post", endpoint, access_token, **kwargs)

    async def put(self, endpoint: str | None, access_token: str, **kwargs: Any) -> Any:
        """Make a PUT request."""
        return await self._request("put", endpoint, access_token, **kwargs)

    async def delete(
        self, endpoint: str | None, access_token: str, **kwargs: Any
    ) -> Any:
        """Make a DELETE request."""
        return await self._request("delete", endpoint, access_token, **kwargs)

"""Dahua access control panel HTTP API client."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener

_LOGGER = logging.getLogger(__name__)

_STATUS_RE = re.compile(r"Info\.status=(\w+)")


class DahuaAcsApiError(Exception):
    """Base API error."""


class DahuaAcsConnectionError(DahuaAcsApiError):
    """Connection or transport error."""


class DahuaAcsApi:
    """Sync HTTP Digest client wrapped for async use."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        channel: int = 1,
    ) -> None:
        host = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        self._host = host
        self._username = username
        self._password = password
        self._channel = channel

    @property
    def host(self) -> str:
        """Return normalized host."""
        return self._host

    @property
    def channel(self) -> int:
        """Return door channel."""
        return self._channel

    def _url(self, action: str, **params: Any) -> str:
        query = {"action": action, "channel": self._channel, **params}
        return f"http://{self._host}/cgi-bin/accessControl.cgi?{urlencode(query)}"

    def _sync_request(self, url: str) -> str:
        password_mgr = HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, url, self._username, self._password)
        opener = build_opener(HTTPDigestAuthHandler(password_mgr))
        request = Request(url, method="GET")
        try:
            with opener.open(request, timeout=10) as response:
                return response.read().decode(errors="replace")
        except HTTPError as err:
            raise DahuaAcsApiError(f"HTTP {err.code}: {err.reason}") from err
        except URLError as err:
            raise DahuaAcsConnectionError(str(err.reason)) from err
        except TimeoutError as err:
            raise DahuaAcsConnectionError("Request timed out") from err

    async def _request(self, url: str) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, self._sync_request, url
        )

    @staticmethod
    def parse_door_status(body: str) -> str:
        """Parse door status from CGI response body."""
        match = _STATUS_RE.search(body)
        if match:
            return match.group(1)
        return "unknown"

    async def get_door_status(self) -> str:
        """Return door status: Open, Close, Break, or unknown."""
        body = await self._request(self._url("getDoorStatus"))
        return self.parse_door_status(body)

    async def open_door(self) -> None:
        """Remotely open the door."""
        body = await self._request(self._url("openDoor", Type="Remote"))
        if "OK" not in body.upper():
            raise DahuaAcsApiError(f"Unexpected openDoor response: {body.strip()}")

    async def close_door(self) -> None:
        """Remotely close the door."""
        body = await self._request(self._url("closeDoor", Type="Remote"))
        if "OK" not in body.upper():
            raise DahuaAcsApiError(f"Unexpected closeDoor response: {body.strip()}")

    async def get_system_info(self) -> str:
        """Return raw system info for validation during config flow."""
        url = f"http://{self._host}/cgi-bin/magicBox.cgi?action=getSystemInfo"
        return await self._request(url)

"""Client for the SchuleIntern timetable (rsdintern.de and other SchuleIntern portals)."""

from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=30)


class StundenplanError(Exception):
    """Base error for the timetable client."""


class StundenplanAuthError(StundenplanError):
    """Username or password were rejected."""


class StundenplanConnectionError(StundenplanError):
    """The portal could not be reached or returned something unexpected."""


class SchuleInternClient:
    """Logs in to a SchuleIntern portal and reads the timetable REST API.

    The session needs its own cookie jar: the portal authenticates the REST
    calls with the PHP session cookie set during login.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._logged_in = False

    async def async_login(self) -> None:
        """Log in and keep the session cookie."""
        form = aiohttp.FormData()
        form.add_field("username", self._username)
        form.add_field("password", self._password)
        form.add_field("keepLogin", "1")
        data = await self._request(
            "post",
            "index.php",
            params={"page": "login", "authorize": "1"},
            data=form,
        )
        if not isinstance(data, dict) or not data.get("success"):
            self._logged_in = False
            raise StundenplanAuthError(
                (data or {}).get("errorMessage", "Login rejected")
                if isinstance(data, dict)
                else "Login rejected"
            )
        self._logged_in = True

    async def async_get_defaults(self) -> dict[str, Any]:
        """Return period times, today's weekday and the user's classes."""
        return await self._api("get", "getDefault")

    async def async_get_plan(self, school_class: str) -> dict[str, Any]:
        """Return the current week plan and today's substitutions for a class."""
        form = aiohttp.FormData()
        form.add_field("key", "grade")
        form.add_field("value", school_class)
        return await self._api("post", "getStundenplan", data=form)

    async def _api(self, method: str, action: str, **kwargs: Any) -> dict[str, Any]:
        if not self._logged_in:
            await self.async_login()
        try:
            data = await self._request(method, f"rest.php/stundenplan/{action}", **kwargs)
        except StundenplanAuthError:
            # Session expired (the portal logs out after 30 minutes): log in again once.
            await self.async_login()
            data = await self._request(method, f"rest.php/stundenplan/{action}", **kwargs)
        if not isinstance(data, dict):
            raise StundenplanConnectionError(f"Unexpected response from {action}")
        if data.get("error"):
            raise StundenplanConnectionError(str(data.get("msg") or "API error"))
        return data

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}/{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers={"Accept": "application/json"},
                timeout=TIMEOUT,
                **kwargs,
            ) as resp:
                if resp.status in (401, 403):
                    self._logged_in = False
                    raise StundenplanAuthError(f"HTTP {resp.status}")
                if resp.status != 200:
                    raise StundenplanConnectionError(f"HTTP {resp.status} for {path}")
                try:
                    return await resp.json(content_type=None)
                except ValueError as err:
                    # An HTML page instead of JSON means we were sent to the login page.
                    self._logged_in = False
                    raise StundenplanAuthError("Not logged in") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise StundenplanConnectionError(str(err)) from err

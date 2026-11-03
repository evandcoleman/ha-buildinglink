"""Authentication for BuildingLink via the iOS app OAuth2 code + PKCE flow."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp
from lxml import html as lxml_html

from .const import (
    AUTH_HOST,
    AUTH_URL,
    AUTHORIZE_URL,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    USER_AGENT,
)
from .exceptions import AuthenticationError

_LOGGER = logging.getLogger(__name__)


def _get_hidden_inputs(text: str) -> dict[str, str]:
    """Extract all hidden input fields from HTML forms."""
    doc = lxml_html.fromstring(text)
    hidden_inputs = doc.xpath('//form//input[@type="hidden"]')
    return {
        el.attrib["name"]: el.attrib.get("value", "")
        for el in hidden_inputs
        if "name" in el.attrib
    }


def _get_form_action(text: str, base_url: str) -> str | None:
    """Extract form action URL from HTML."""
    doc = lxml_html.fromstring(text)
    forms = doc.xpath("//form/@action")
    if not forms:
        return None
    action = forms[0]
    if action.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{action}"
    return action


MAX_REDIRECT_HOPS = 10
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class BuildingLinkAuth:
    """Manage authentication for BuildingLink.

    Drives the iOS app's authorization-code + PKCE flow with the user's
    username/password (scraping the hosted login form), then refreshes with
    the refresh token and falls back to a full login when refresh fails.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        if not username and not refresh_token:
            raise AuthenticationError(
                "Either username/password or refresh_token must be provided"
            )
        self._username = username
        self._password = password
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._token_expiry: float = 0

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def is_token_valid(self) -> bool:
        return self._access_token is not None and time.time() < self._token_expiry - 30

    async def async_login_with_credentials(
        self, session: aiohttp.ClientSession
    ) -> str:
        """Authenticate with username/password. Returns the access token.

        Raises AuthenticationError on failure.
        """
        if not self._username or not self._password:
            raise AuthenticationError("Username and password required")

        headers = {"User-Agent": USER_AGENT}
        verifier, challenge = _pkce_pair()
        query = urlencode(
            {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": secrets.token_hex(8),
                "nonce": secrets.token_urlsafe(16),
            }
        )
        try:
            async with session.get(
                f"{AUTHORIZE_URL}?{query}", headers=headers, allow_redirects=True
            ) as resp:
                login_html = await resp.text()
                login_url = str(resp.url)

            try:
                form = _get_hidden_inputs(login_html)
            except Exception as err:  # unparsable page
                raise AuthenticationError("Login form not found") from err
            form["Username"] = self._username
            form["Password"] = self._password
            form["RememberLogin"] = "false"
            action = _get_form_action(login_html, login_url) or login_url

            async with session.post(
                action, data=form, headers=headers, allow_redirects=False
            ) as resp:
                if resp.status not in _REDIRECT_STATUSES:
                    # The form is re-rendered (HTTP 200) on bad credentials.
                    raise AuthenticationError("Invalid username or password")
                location = resp.headers.get("Location", "")

            code = await self._async_follow_to_code(session, location, headers)
            return await self._async_exchange_code(session, code, verifier)
        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            raise AuthenticationError(f"Network error during login: {err}") from err

    async def _async_follow_to_code(
        self,
        session: aiohttp.ClientSession,
        location: str,
        headers: dict[str, str],
    ) -> str:
        """Follow redirects manually until the app-scheme callback; return code."""
        scheme = REDIRECT_URI.split(":", 1)[0] + ":"
        for _ in range(MAX_REDIRECT_HOPS):
            if not location:
                raise AuthenticationError("Login flow ended without a redirect")
            if location.startswith(scheme):
                code = parse_qs(urlparse(location).query).get("code", [None])[0]
                if not code:
                    raise AuthenticationError("Callback missing authorization code")
                return code
            async with session.get(
                urljoin(AUTH_HOST, location), headers=headers, allow_redirects=False
            ) as resp:
                location = resp.headers.get("Location", "")
        raise AuthenticationError("Too many redirects during login")

    async def _async_token_refresh(self, session: aiohttp.ClientSession) -> str:
        """Refresh access token using refresh_token."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available")

        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }
        async with session.post(AUTH_URL, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise AuthenticationError(f"Token refresh failed ({resp.status}): {text}")
            result = await resp.json()

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + result.get("expires_in", 900)
        return self._access_token

    async def _async_exchange_code(
        self, session: aiohttp.ClientSession, code: str, verifier: str
    ) -> str:
        """Exchange auth code (+ PKCE verifier) for tokens."""
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }
        async with session.post(AUTH_URL, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise AuthenticationError(f"Code exchange failed ({resp.status}): {text}")
            result = await resp.json()

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token")
        self._token_expiry = time.time() + result.get("expires_in", 900)
        return self._access_token

    async def async_refresh_token(self, session: aiohttp.ClientSession) -> dict:
        """Public refresh method. Returns full token response dict."""
        token = await self._async_token_refresh(session)
        return {"access_token": token, "refresh_token": self._refresh_token}

    async def async_get_access_token(self, session: aiohttp.ClientSession) -> str:
        """Get a valid access token, refreshing or re-logging in as needed."""
        if self.is_token_valid:
            return self._access_token  # type: ignore[return-value]

        # Try refresh first
        if self._refresh_token:
            try:
                return await self._async_token_refresh(session)
            except AuthenticationError:
                _LOGGER.debug("Refresh failed, falling back to login")

        # Re-login
        if self._username and self._password:
            return await self.async_login_with_credentials(session)

        raise AuthenticationError("No valid authentication method available")

"""Authentication for BuildingLink via web scraping login flow."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import aiohttp
from lxml import html as lxml_html

from .const import AUTH_URL, CLIENT_ID, LOGIN_URL, OIDC_CALLBACK_URL, USER_AGENT
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


def _extract_auth_redirect_url(content: bytes) -> str:
    """Extract the auth redirect URL from the login page JavaScript."""
    # The login page has a script like: window.top.location.href="https://auth..."
    start = content.find(b"https://auth")
    if start == -1:
        raise AuthenticationError("Could not find auth redirect URL in login page")
    # Find the end of the URL (terminated by "; or ')
    end = content.find(b'";', start)
    if end == -1:
        end = content.find(b"';", start)
    if end == -1:
        raise AuthenticationError("Could not parse auth redirect URL")
    return content[start:end].decode("utf-8")


class BuildingLinkAuth:
    """Manage authentication for BuildingLink.

    Uses a web scraping login flow matching the approach used by
    buildinglink-mqtt and the johnagan/buildinglink npm package:
    1. GET login page → extract auth redirect URL
    2. GET auth URL → get login form with hidden CSRF fields
    3. POST form with username + password → get OIDC callback form
    4. POST OIDC callback → session authenticated, extract token
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
        """Authenticate using username/password via web scraping.

        Follows the same flow as buildinglink-mqtt (proven working).
        Returns access token. Raises AuthenticationError on failure.
        """
        if not self._username or not self._password:
            raise AuthenticationError("Username and password required")

        headers = {"User-Agent": USER_AGENT}

        try:
            # Step 1: GET the login page
            _LOGGER.debug("Step 1: Loading login page")
            async with session.get(
                LOGIN_URL, headers=headers, allow_redirects=True
            ) as resp:
                content = await resp.read()

            # Step 2: Extract the auth redirect URL from the page's JavaScript
            auth_url = _extract_auth_redirect_url(content)
            _LOGGER.debug("Step 2: Following auth redirect")

            # Step 3: GET the auth form
            async with session.get(
                auth_url, headers=headers, allow_redirects=True
            ) as resp:
                login_html = await resp.text()
                login_post_url = str(resp.url)

            # Check if we got a form
            form_data = _get_hidden_inputs(login_html)
            
            # Get form action if different from current URL
            form_action = _get_form_action(login_html, login_post_url)
            if form_action:
                login_post_url = form_action

            # Step 4: Fill in credentials and POST
            form_data["Username"] = self._username
            form_data["Password"] = self._password
            _LOGGER.debug("Step 3: Submitting login form to %s", login_post_url)

            async with session.post(
                login_post_url,
                data=form_data,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=False,
            ) as resp:
                resp_text = await resp.text()
                
                # Handle redirect after login
                if resp.status in (301, 302):
                    redirect_url = resp.headers.get("Location", "")
                    _LOGGER.debug("Login redirected to: %s", redirect_url[:80])
                    async with session.get(
                        redirect_url, headers=headers, allow_redirects=True
                    ) as redir_resp:
                        resp_text = await redir_resp.text()

            # Check for login errors in the response
            if "validation-summary-errors" in resp_text:
                raise AuthenticationError("Invalid username or password")

            # Step 5: Extract callback form and POST to OIDC callback
            callback_data = _get_hidden_inputs(resp_text)
            if not callback_data:
                raise AuthenticationError(
                    "Login failed: no OIDC callback data. Check credentials."
                )

            _LOGGER.debug("Step 4: Posting OIDC callback with %d fields", len(callback_data))

            # The callback form data contains the tokens
            # Save access_token if present in the form
            token = callback_data.get("access_token")

            async with session.post(
                OIDC_CALLBACK_URL,
                data=callback_data,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=True,
            ) as resp:
                _LOGGER.debug("OIDC callback response: %d", resp.status)

            # If we got a token from the form, use it
            if token:
                self._access_token = token
                self._token_expiry = time.time() + 900
                _LOGGER.debug("Got access token from OIDC callback form")
                return token

            # If no direct token, try token endpoint with refresh token from form
            if "refresh_token" in callback_data:
                self._refresh_token = callback_data["refresh_token"]
                result = await self._async_token_refresh(session)
                return result

            # Last resort: try the code flow
            if "code" in callback_data:
                _LOGGER.debug("Got auth code, exchanging for token")
                return await self._async_exchange_code(session, callback_data["code"])

            raise AuthenticationError("Login flow completed but no token obtained")

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            raise AuthenticationError(f"Network error during login: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during login")
            raise AuthenticationError(f"Login failed: {err}") from err

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

    async def _async_exchange_code(self, session: aiohttp.ClientSession, code: str) -> str:
        """Exchange auth code for access token."""
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "com.buildinglink.buildinglink://",
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

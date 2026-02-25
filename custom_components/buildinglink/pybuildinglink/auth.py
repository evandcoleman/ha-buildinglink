"""Authentication for BuildingLink via web scraping login or refresh token."""

from __future__ import annotations

import re
import time
import logging

import aiohttp
from lxml import html as lxml_html

from .const import AUTH_URL, CLIENT_ID, LOGIN_URL, OIDC_CALLBACK_URL, USER_AGENT
from .exceptions import AuthenticationError

_LOGGER = logging.getLogger(__name__)


def _get_hidden_inputs(text: str) -> dict[str, str]:
    """Extract hidden input fields from an HTML form."""
    doc = lxml_html.fromstring(text)
    hidden_inputs = doc.xpath(r'//form//input[@type="hidden"]')
    return {el.attrib["name"]: el.attrib["value"] for el in hidden_inputs if "name" in el.attrib}


def _extract_auth_redirect_url(content: bytes) -> str:
    """Extract the auth redirect URL from the login page script."""
    start = content.find(b"https://auth")
    if start == -1:
        raise AuthenticationError("Could not find auth redirect URL in login page")
    end = content.find(b'";', start)
    if end == -1:
        end = content.find(b"';", start)
    if end == -1:
        raise AuthenticationError("Could not parse auth redirect URL from login page")
    return content[start:end].decode("utf-8")


def _extract_access_token_from_form(form_data: dict[str, str]) -> str | None:
    """Try to extract an access token from OIDC callback form fields."""
    # The callback form may contain the token directly or in a code field
    for key in ("access_token", "code", "id_token"):
        if key in form_data:
            return form_data[key]
    return None


class BuildingLinkAuth:
    """Manage authentication for BuildingLink API.
    
    Supports two auth methods:
    1. Username/password via web scraping login flow (preferred)
    2. Refresh token via OAuth2 token endpoint (legacy fallback)
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Initialize auth.
        
        Provide either username+password or refresh_token.
        """
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
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def is_token_valid(self) -> bool:
        """Check if the current access token is still valid."""
        return (
            self._access_token is not None
            and time.time() < self._token_expiry - 30  # 30s buffer
        )

    async def async_login_with_credentials(
        self, session: aiohttp.ClientSession
    ) -> str:
        """Authenticate using username/password via web scraping login flow.
        
        Returns the access token.
        Raises AuthenticationError on failure.
        """
        if not self._username or not self._password:
            raise AuthenticationError("Username and password are required for login")

        try:
            # Step 1: GET login page
            async with session.get(LOGIN_URL, allow_redirects=True) as resp:
                content = await resp.read()

            # Step 2: Extract auth redirect URL from script
            auth_url = _extract_auth_redirect_url(content)
            _LOGGER.debug("Found auth redirect URL: %s", auth_url[:80])

            # Step 3: GET auth URL to get login form
            async with session.get(auth_url, allow_redirects=True) as resp:
                login_page = await resp.text()
                form_action_url = str(resp.url)

            # Step 4: Parse form, fill credentials, POST
            form_data = _get_hidden_inputs(login_page)
            form_data["Username"] = self._username
            form_data["Password"] = self._password

            # Extract form action URL if present
            doc = lxml_html.fromstring(login_page)
            forms = doc.xpath("//form/@action")
            if forms:
                action = forms[0]
                if action.startswith("/"):
                    # Resolve relative URL
                    from urllib.parse import urlparse
                    parsed = urlparse(form_action_url)
                    action = f"{parsed.scheme}://{parsed.netloc}{action}"
                form_action_url = action

            async with session.post(
                form_action_url, data=form_data, allow_redirects=False
            ) as resp:
                # Check for failed login (usually redirects back to login with error)
                if resp.status == 200:
                    resp_text = await resp.text()
                    if "invalid" in resp_text.lower() or "error" in resp_text.lower():
                        raise AuthenticationError("Invalid username or password")
                    callback_form = _get_hidden_inputs(resp_text)
                elif resp.status in (301, 302):
                    redirect_url = resp.headers.get("Location", "")
                    async with session.get(redirect_url, allow_redirects=True) as redir_resp:
                        resp_text = await redir_resp.text()
                    callback_form = _get_hidden_inputs(resp_text)
                else:
                    resp_text = await resp.text()
                    callback_form = _get_hidden_inputs(resp_text)

            if not callback_form:
                raise AuthenticationError(
                    "Login failed: no callback form data received. Check credentials."
                )

            # Step 5: POST to OIDC callback
            async with session.post(
                OIDC_CALLBACK_URL, data=callback_form, allow_redirects=True
            ) as resp:
                # After this, session cookies should be set
                # Try to extract access token from cookies or response
                pass

            # Extract access token from cookies
            access_token = None
            
            # Check if access_token was in the callback form fields
            access_token = _extract_access_token_from_form(callback_form)
            
            if not access_token:
                # Try getting token via refresh token endpoint using cookies
                # The OIDC flow may have set cookies that allow token refresh
                for cookie in session.cookie_jar:
                    if "oidc" in cookie.key.lower() or "auth" in cookie.key.lower():
                        _LOGGER.debug("Found auth cookie: %s", cookie.key)

            if not access_token:
                # Fall back to trying the token endpoint with session cookies
                # Some implementations get the token from cookie-authenticated requests
                try:
                    access_token = await self._try_token_from_session(session)
                except Exception:
                    pass

            if not access_token:
                raise AuthenticationError(
                    "Login succeeded but could not extract access token"
                )

            self._access_token = access_token
            self._token_expiry = time.time() + 900  # 15 min expiry
            _LOGGER.debug("Successfully authenticated via web login")
            return access_token

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            raise AuthenticationError(f"Login request failed: {err}") from err
        except Exception as err:
            raise AuthenticationError(f"Login failed: {err}") from err

    async def _try_token_from_session(
        self, session: aiohttp.ClientSession
    ) -> str | None:
        """Try to obtain an access token using the authenticated session cookies."""
        # After OIDC login, try refreshing via the token endpoint
        # The session should have auth cookies that can be used
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token or "",
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }
        async with session.post(AUTH_URL, data=data, headers=headers) as resp:
            if resp.status == 200:
                result = await resp.json()
                self._refresh_token = result.get("refresh_token")
                return result.get("access_token")
        return None

    async def async_refresh_token(
        self, session: aiohttp.ClientSession
    ) -> dict:
        """Refresh the access token using refresh_token.

        Returns the token response dict. Updates internal state.
        Raises AuthenticationError on failure.
        """
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

        try:
            async with session.post(AUTH_URL, data=data, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise AuthenticationError(
                        f"Token refresh failed ({resp.status}): {text}"
                    )
                result = await resp.json()
        except aiohttp.ClientError as err:
            raise AuthenticationError(f"Token refresh request failed: {err}") from err

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + result.get("expires_in", 900)
        return result

    async def async_get_access_token(
        self, session: aiohttp.ClientSession
    ) -> str:
        """Get a valid access token, refreshing/re-logging in if necessary."""
        if self.is_token_valid:
            assert self._access_token is not None
            return self._access_token

        # Try refresh token first if available
        if self._refresh_token:
            try:
                await self.async_refresh_token(session)
                if self._access_token:
                    return self._access_token
            except AuthenticationError:
                _LOGGER.debug("Refresh token failed, falling back to login")

        # Fall back to username/password login
        if self._username and self._password:
            return await self.async_login_with_credentials(session)

        raise AuthenticationError("No valid authentication method available")

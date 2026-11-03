from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import aiohttp
import pytest
from aioresponses import aioresponses

from pybuildinglink.auth import BuildingLinkAuth
from pybuildinglink.const import AUTH_URL, CLIENT_ID, REDIRECT_URI
from pybuildinglink.exceptions import AuthenticationError

AUTHORIZE = re.compile(r"^https://auth\.buildinglink\.com/connect/authorize\?.*")
LOGIN_PAGE = "https://auth.buildinglink.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fx%3D1"
LOGIN_FORM = """
<html><body><form method="post" action="/Account/Login?ReturnUrl=abc">
<input type="hidden" name="ReturnUrl" value="/connect/authorize/callback?x=1"/>
<input type="hidden" name="__RequestVerificationToken" value="tok123"/>
<input name="Username"/><input name="Password" type="password"/>
</form></body></html>
"""
BAD_FORM = LOGIN_FORM.replace(
    "<form", '<div class="validation-summary-errors">bad</div><form'
)
LOGIN_POST = "https://auth.buildinglink.com/Account/Login?ReturnUrl=abc"
HOP1 = "https://auth.buildinglink.com/connect/authorize/callback?x=1"
CODE_URL = f"{REDIRECT_URI}?code=THECODE&state=s"
TOKEN = {"access_token": "AT", "refresh_token": "RT", "expires_in": 900}


def mock_happy(m: aioresponses) -> None:
    m.get(AUTHORIZE, status=302, headers={"Location": "/Account/Login?ReturnUrl=x"})
    m.get("https://auth.buildinglink.com/Account/Login?ReturnUrl=x", body=LOGIN_FORM)
    m.post(LOGIN_POST, status=302, headers={"Location": "/connect/authorize/callback?x=1"})
    m.get(HOP1, status=302, headers={"Location": CODE_URL})
    m.post(AUTH_URL, payload=TOKEN)


async def test_login_follows_relative_redirects_and_exchanges_code():
    with aioresponses() as m:
        mock_happy(m)
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p")
            token = await auth.async_login_with_credentials(s)

        assert token == "AT"
        assert auth.refresh_token == "RT"
        authorize_req = next(k for k in m.requests if k[1].path == "/connect/authorize")
        q = parse_qs(authorize_req[1].query_string)
        assert q["client_id"] == [CLIENT_ID]
        assert q["code_challenge_method"] == ["S256"]
        post = m.requests[("POST", __import__("yarl").URL(LOGIN_POST))][0].kwargs["data"]
        assert post["Username"] == "u" and post["Password"] == "p"
        assert post["__RequestVerificationToken"] == "tok123"
        tok = m.requests[("POST", __import__("yarl").URL(AUTH_URL))][0].kwargs["data"]
        assert tok["code"] == "THECODE"
        assert tok["grant_type"] == "authorization_code"
        assert tok["redirect_uri"] == REDIRECT_URI
        assert tok["code_verifier"]


async def test_bad_credentials_raise_authentication_error():
    with aioresponses() as m:
        m.get(AUTHORIZE, status=302, headers={"Location": "/Account/Login?ReturnUrl=x"})
        m.get("https://auth.buildinglink.com/Account/Login?ReturnUrl=x", body=LOGIN_FORM)
        m.post(LOGIN_POST, status=200, body=BAD_FORM)
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="bad")
            with pytest.raises(AuthenticationError):
                await auth.async_login_with_credentials(s)


async def test_refresh_failure_falls_back_to_login():
    with aioresponses() as m:
        m.post(AUTH_URL, status=400, body="invalid_grant")
        mock_happy(m)
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p", refresh_token="old")
            assert await auth.async_get_access_token(s) == "AT"


async def test_refresh_success_skips_login():
    with aioresponses() as m:
        m.post(AUTH_URL, payload={"access_token": "NEW", "refresh_token": "R2", "expires_in": 900})
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p", refresh_token="old")
            assert await auth.async_get_access_token(s) == "NEW"
            assert auth.refresh_token == "R2"
        assert not any(k[1].path == "/connect/authorize" for k in m.requests)


def _hit(m: aioresponses, url: str) -> bool:
    return any(str(k[1]).startswith(url) for k in m.requests)


async def test_authorize_redirecting_straight_to_callback_skips_login():
    with aioresponses() as m:
        m.get(AUTHORIZE, status=302, headers={"Location": CODE_URL})
        m.post(AUTH_URL, payload=TOKEN)
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p")
            assert await auth.async_login_with_credentials(s) == "AT"
        assert not any(k[0] == "POST" and k[1].path == "/Account/Login" for k in m.requests)


async def test_off_origin_form_action_is_rejected_without_posting_credentials():
    evil = LOGIN_FORM.replace('action="/Account/Login?ReturnUrl=abc"', 'action="https://evil.example/steal"')
    with aioresponses() as m:
        m.get(AUTHORIZE, status=302, headers={"Location": "/Account/Login?ReturnUrl=x"})
        m.get("https://auth.buildinglink.com/Account/Login?ReturnUrl=x", body=evil)
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p")
            with pytest.raises(AuthenticationError):
                await auth.async_login_with_credentials(s)
        assert not _hit(m, "https://evil.example")


async def test_off_origin_redirect_mid_flow_is_rejected():
    with aioresponses() as m:
        m.get(AUTHORIZE, status=302, headers={"Location": "https://evil.example/hop"})
        async with aiohttp.ClientSession() as s:
            auth = BuildingLinkAuth(username="u", password="p")
            with pytest.raises(AuthenticationError):
                await auth.async_login_with_credentials(s)
        assert not _hit(m, "https://evil.example")


async def test_http_downgrade_redirect_is_rejected():
    with aioresponses() as m:
        m.get(AUTHORIZE, status=302, headers={"Location": "http://auth.buildinglink.com/x"})
        async with aiohttp.ClientSession() as s:
            with pytest.raises(AuthenticationError):
                await BuildingLinkAuth(username="u", password="p").async_login_with_credentials(s)
        assert not _hit(m, "http://auth.buildinglink.com")

from __future__ import annotations

import re

import aiohttp
from aioresponses import aioresponses

from pybuildinglink.client import BuildingLinkClient
from pybuildinglink.const import API_KEY, APIM_SUBSCRIPTION_KEY, USER_AGENT


async def _headers_for(url: str) -> dict:
    with aioresponses() as m:
        m.get(re.compile(".*"), payload={})
        async with aiohttp.ClientSession() as s:
            c = BuildingLinkClient(username="u", password="p", session=s)
            c._auth._access_token = "AT"
            c._auth._token_expiry = 1e12
            await c._request("GET", url)
        return next(iter(m.requests.values()))[0].kwargs["headers"]


async def test_us1_hosts_get_x_api_key():
    h = await _headers_for("https://eventlog-us1.buildinglink.com/x")
    assert h["X-API-Key"] == API_KEY
    assert "Ocp-Apim-Subscription-Key" not in h
    assert h["User-Agent"] == USER_AGENT


async def test_api_host_gets_subscription_key():
    h = await _headers_for("https://api.buildinglink.com/x")
    assert h["Ocp-Apim-Subscription-Key"] == APIM_SUBSCRIPTION_KEY
    assert "X-API-Key" not in h


async def test_legacy_host_gets_neither():
    h = await _headers_for("https://www.buildinglink.com/x")
    assert "X-API-Key" not in h and "Ocp-Apim-Subscription-Key" not in h

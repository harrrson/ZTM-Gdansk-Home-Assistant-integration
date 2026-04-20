"""Tests for ZTMGdanskClient."""
from __future__ import annotations

import asyncio

import pytest
from aiohttp import ClientSession
from aioresponses import aioresponses

from custom_components.ztm_gdansk.api import ZTMApiError, ZTMGdanskClient
from custom_components.ztm_gdansk.const import (
    API_BSK_URL,
    API_DEPARTURES_URL,
    API_DISPLAY_MESSAGES_URL,
    API_DISPLAYS_URL,
    API_STOPS_URL,
    API_ZNT_URL,
)
from tests.conftest import load_fixture


@pytest.fixture
async def client():
    async with ClientSession() as session:
        yield ZTMGdanskClient(session)


def test_ztm_api_error_carries_context():
    err = ZTMApiError("boom", url="http://x", status=500, body_snippet="oops")
    assert "http://x" in str(err)
    assert err.status == 500
    assert err.body_snippet == "oops"


async def test_get_departures_happy_path(client, fixture_loader):
    payload = fixture_loader("departures")
    with aioresponses() as m:
        m.get(f"{API_DEPARTURES_URL}?stopId=1234", payload=payload)
        result = await client.get_departures(1234)
    assert result == payload


async def test_get_departures_http_500(client):
    with aioresponses() as m:
        m.get(f"{API_DEPARTURES_URL}?stopId=1234", status=500, body="server down")
        with pytest.raises(ZTMApiError) as exc_info:
            await client.get_departures(1234)
    assert exc_info.value.status == 500


async def test_get_departures_invalid_json(client):
    with aioresponses() as m:
        m.get(f"{API_DEPARTURES_URL}?stopId=1234", body="<html>not json</html>",
              headers={"Content-Type": "text/html"})
        with pytest.raises(ZTMApiError):
            await client.get_departures(1234)


async def test_get_departures_timeout(client):
    with aioresponses() as m:
        m.get(f"{API_DEPARTURES_URL}?stopId=1234", exception=asyncio.TimeoutError())
        with pytest.raises(ZTMApiError):
            await client.get_departures(1234)


async def test_get_bsk_alerts(client, fixture_loader):
    payload = fixture_loader("bsk")
    with aioresponses() as m:
        m.get(API_BSK_URL, payload=payload)
        assert await client.get_bsk_alerts() == payload


async def test_get_display_messages(client, fixture_loader):
    payload = fixture_loader("display_messages")
    with aioresponses() as m:
        m.get(API_DISPLAY_MESSAGES_URL, payload=payload)
        assert await client.get_display_messages() == payload


async def test_get_znt_alerts(client, fixture_loader):
    payload = fixture_loader("znt")
    with aioresponses() as m:
        m.get(API_ZNT_URL, payload=payload)
        assert await client.get_znt_alerts() == payload


async def test_get_stops(client, fixture_loader):
    payload = fixture_loader("stops")
    with aioresponses() as m:
        m.get(API_STOPS_URL, payload=payload)
        assert await client.get_stops() == payload


async def test_get_displays(client, fixture_loader):
    payload = fixture_loader("displays")
    with aioresponses() as m:
        m.get(API_DISPLAYS_URL, payload=payload)
        assert await client.get_displays() == payload

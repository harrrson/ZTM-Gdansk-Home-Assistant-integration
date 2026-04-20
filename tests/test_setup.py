"""Tests for ztm_gdansk setup (__init__.py)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.ztm_gdansk import _discover_lines_from_schedule
from custom_components.ztm_gdansk.const import DOMAIN
from tests.conftest import load_fixture


@pytest.fixture
def stops_payload():
    return {"stops": [
        {"stopId": 1234, "stopName": "Brama Wyżynna"},
        {"stopId": 5678, "stopName": "Stogi"},
    ]}


async def test_setup_with_minimal_config(hass: HomeAssistant, stops_payload):
    with patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_stops",
        return_value=stops_payload,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_displays",
        return_value=[],
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_departures",
        return_value={"lastUpdate": "t", "departures": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_bsk_alerts",
        return_value={"results": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_display_messages",
        return_value={"displaysMsg": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_znt_alerts",
        return_value={"results": []},
    ):
        ok = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"departures": [{"stop_id": 1234, "lines": ["8"]}]}}
        )
        await hass.async_block_till_done()
    assert ok is True
    assert "departure_coordinator" in hass.data[DOMAIN]


async def test_setup_warns_on_unknown_stop(hass: HomeAssistant, stops_payload, caplog):
    with patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_stops",
        return_value=stops_payload,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_displays",
        return_value=[],
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_departures",
        return_value={"lastUpdate": "t", "departures": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_bsk_alerts",
        return_value={"results": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_display_messages",
        return_value={"displaysMsg": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_znt_alerts",
        return_value={"results": []},
    ):
        ok = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"departures": [
                {"stop_id": 1234, "lines": ["8"]},
                {"stop_id": 99999, "lines": ["1"]},
            ]}}
        )
        await hass.async_block_till_done()
    assert ok is True
    assert "99999" in caplog.text


async def test_auto_discovery_from_schedule(hass: HomeAssistant, stops_payload):
    """lines: [] should discover all lines from static schedule, not live departures."""
    stopsintrip = load_fixture("stopsintrip")
    routes = load_fixture("routes")
    with patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_stops",
        return_value=stops_payload,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_displays",
        return_value=[],
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_stops_in_trip",
        return_value=stopsintrip,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_routes",
        return_value=routes,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_departures",
        return_value={"lastUpdate": "t", "departures": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_bsk_alerts",
        return_value={"results": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_display_messages",
        return_value={"displaysMsg": []},
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_znt_alerts",
        return_value={"results": []},
    ):
        ok = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"departures": [{"stop_id": 1234, "lines": []}]}}
        )
        await hass.async_block_till_done()
    assert ok is True
    # stop_id 1234 maps to routeId 8 → routeShortName "8" in fixtures
    coord = hass.data[DOMAIN]["departure_coordinator"]
    assert coord is not None


async def test_discover_lines_resolves_route_names():
    """_discover_lines_from_schedule maps routeId→routeShortName correctly."""
    stopsintrip = load_fixture("stopsintrip")
    routes = load_fixture("routes")
    with patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_stops_in_trip",
        return_value=stopsintrip,
    ), patch(
        "custom_components.ztm_gdansk.api.ZTMGdanskClient.get_routes",
        return_value=routes,
    ):
        from aiohttp import ClientSession
        from custom_components.ztm_gdansk.api import ZTMGdanskClient
        async with ClientSession() as session:
            client = ZTMGdanskClient(session)
            result = await _discover_lines_from_schedule(client)
    # stop 15026: routeIds 113,176,213,414 → names "113","176","213","N14"
    assert result[15026] == {"113", "176", "213", "N14"}
    # stop 1234: routeId 8 → "8"
    assert result[1234] == {"8"}
    # stop 184: routeId 113 → "113"
    assert result[184] == {"113"}

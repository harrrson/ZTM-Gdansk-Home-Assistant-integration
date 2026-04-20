"""Tests for ztm_gdansk setup (__init__.py)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.ztm_gdansk.const import DOMAIN


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

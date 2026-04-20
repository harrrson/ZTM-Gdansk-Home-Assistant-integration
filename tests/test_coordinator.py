"""Tests for ZTM Gdańsk coordinators."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ztm_gdansk.api import ZTMApiError, ZTMGdanskClient
from custom_components.ztm_gdansk.coordinator import (
    AlertsCoordinator,
    DepartureCoordinator,
)


@pytest.fixture
def mock_client():
    return AsyncMock(spec=ZTMGdanskClient)


# ---------- DepartureCoordinator ----------

async def test_departure_coordinator_success(hass: HomeAssistant, mock_client):
    async def fake(sid):
        return {"lastUpdate": "t", "departures": [
            {"routeShortName": "8", "estimatedTime": "2026-04-19T22:35:00Z"},
        ]}
    mock_client.get_departures.side_effect = fake
    coord = DepartureCoordinator(
        hass, mock_client, stop_ids=[1234, 5678], scan_interval=timedelta(seconds=60)
    )
    await coord.async_refresh()
    assert 1234 in coord.data
    assert 5678 in coord.data
    assert coord.last_successful_update is not None
    assert coord.consecutive_errors == 0


async def test_departure_coordinator_preserves_data_on_error(hass, mock_client):
    async def fake_ok(sid):
        return {"lastUpdate": "t", "departures": []}
    mock_client.get_departures.side_effect = fake_ok
    coord = DepartureCoordinator(
        hass, mock_client, stop_ids=[1234], scan_interval=timedelta(seconds=60)
    )
    await coord.async_refresh()
    first_update = coord.last_successful_update
    first_data = coord.data

    async def fake_err(sid):
        raise ZTMApiError("boom")
    mock_client.get_departures.side_effect = fake_err
    await coord.async_refresh()
    assert coord.data == first_data
    assert coord.last_successful_update == first_update
    assert coord.consecutive_errors >= 1


async def test_departure_coordinator_backoff(hass, mock_client):
    async def fake_err(sid):
        raise ZTMApiError("boom")
    mock_client.get_departures.side_effect = fake_err
    coord = DepartureCoordinator(
        hass, mock_client, stop_ids=[1234], scan_interval=timedelta(seconds=60)
    )
    for _ in range(3):
        await coord.async_refresh()
    assert coord.update_interval > timedelta(seconds=60)

    async def fake_ok(sid):
        return {"lastUpdate": "t", "departures": []}
    mock_client.get_departures.side_effect = fake_ok
    await coord.async_refresh()
    assert coord.update_interval == timedelta(seconds=60)
    assert coord.consecutive_errors == 0


async def test_departure_coordinator_partial_failure(hass, mock_client):
    async def fake(sid):
        if sid == 9999:
            raise ZTMApiError("boom")
        return {"lastUpdate": "t", "departures": []}
    mock_client.get_departures.side_effect = fake
    coord = DepartureCoordinator(
        hass, mock_client, stop_ids=[1234, 9999], scan_interval=timedelta(seconds=60)
    )
    await coord.async_refresh()
    assert 1234 in coord.data
    assert 9999 not in coord.data
    assert coord.consecutive_errors == 0  # at least one succeeded


# ---------- AlertsCoordinator ----------

async def test_alerts_coordinator_combines_three_sources(hass, mock_client):
    mock_client.get_bsk_alerts.return_value = {
        "metadata": {}, "count": 1,
        "results": [
            {"lineNumbers": ["8"], "title": "Awaria",
             "summary": "Linia 8 nie kursuje", "content": "",
             "publishFrom": "2026-04-20 08:00:00", "publishTo": "2026-04-20 20:00:00",
             "url": ""},
        ],
    }
    mock_client.get_display_messages.return_value = {
        "lastUpdate": "t",
        "displaysMsg": [
            {"displayCode": 701, "displayName": "Hucisko",
             "messagePart1": "PRZYSTANEK NIEOBSŁUGIWANY", "messagePart2": "",
             "startDate": "2026-04-20 08:00:00", "endDate": "2026-05-31 23:59:00",
             "configurationDate": "", "msgType": 1},
        ],
    }
    mock_client.get_znt_alerts.return_value = {
        "metadata": {}, "count": 2,
        "results": [
            {"lineNumbers": ["11"], "title": "Remont",
             "summary": "Linia 11 jedzie objazdem", "content": "",
             "publishFrom": "2026-04-20 08:00:00", "publishTo": "2026-04-27 23:59:00",
             "url": "", "disableAlarm": False},
            {"lineNumbers": [], "title": "Mecz Lechii",
             "summary": "Dodatkowe tramwaje", "content": "",
             "publishFrom": "2026-04-20 08:00:00", "publishTo": "2026-04-20 23:59:00",
             "url": "", "disableAlarm": True},  # MUST be filtered out
        ],
    }
    coord = AlertsCoordinator(
        hass, mock_client, scan_interval=timedelta(seconds=300),
        filter_lines=[], filter_stops=[],
        displays_map={701: [1033, 40155]},
    )
    await coord.async_refresh()
    titles = {a["title"] for a in coord.data}
    # "Mecz Lechii" has disableAlarm=True -> filtered out
    assert titles == {"Awaria", "Remont", "PRZYSTANEK NIEOBSŁUGIWANY"} or titles == {
        "Awaria", "Remont", "Hucisko — PRZYSTANEK NIEOBSŁUGIWANY",
    }
    sources = {a["source"] for a in coord.data}
    assert sources == {"bsk", "display", "znt"}


async def test_alerts_coordinator_deduplicates_across_sources(hass, mock_client):
    # Same alert in bsk and znt — should appear once.
    same = {"lineNumbers": ["8"], "title": "Awaria 8",
            "summary": "Linia 8 nie kursuje", "content": "",
            "publishFrom": "...", "publishTo": "...", "url": ""}
    mock_client.get_bsk_alerts.return_value = {"metadata": {}, "count": 1, "results": [same]}
    mock_client.get_display_messages.return_value = {"lastUpdate": "t", "displaysMsg": []}
    mock_client.get_znt_alerts.return_value = {"metadata": {}, "count": 1,
                                                "results": [{**same, "disableAlarm": False}]}
    coord = AlertsCoordinator(
        hass, mock_client, scan_interval=timedelta(seconds=300),
        filter_lines=[], filter_stops=[], displays_map={},
    )
    await coord.async_refresh()
    assert len(coord.data) == 1


async def test_alerts_coordinator_filters_by_line(hass, mock_client):
    mock_client.get_bsk_alerts.return_value = {"metadata": {}, "count": 2, "results": [
        {"lineNumbers": ["8"], "title": "A", "summary": "", "content": "",
         "publishFrom": "", "publishTo": "", "url": ""},
        {"lineNumbers": ["11"], "title": "B", "summary": "", "content": "",
         "publishFrom": "", "publishTo": "", "url": ""},
    ]}
    mock_client.get_display_messages.return_value = {"lastUpdate": "t", "displaysMsg": []}
    mock_client.get_znt_alerts.return_value = {"metadata": {}, "count": 0, "results": []}
    coord = AlertsCoordinator(
        hass, mock_client, scan_interval=timedelta(seconds=300),
        filter_lines=["8"], filter_stops=[], displays_map={},
    )
    await coord.async_refresh()
    assert {a["title"] for a in coord.data} == {"A"}


async def test_alerts_coordinator_filters_by_stop_via_displays_map(hass, mock_client):
    # displayMessages alert should be matched by stop filter via displays_map lookup.
    mock_client.get_bsk_alerts.return_value = {"metadata": {}, "count": 0, "results": []}
    mock_client.get_display_messages.return_value = {
        "lastUpdate": "t",
        "displaysMsg": [
            {"displayCode": 701, "displayName": "Hucisko",
             "messagePart1": "x", "messagePart2": "",
             "startDate": "", "endDate": "",
             "configurationDate": "", "msgType": 1},
            {"displayCode": 999, "displayName": "Other",  # displayCode not in map
             "messagePart1": "y", "messagePart2": "",
             "startDate": "", "endDate": "",
             "configurationDate": "", "msgType": 1},
        ],
    }
    mock_client.get_znt_alerts.return_value = {"metadata": {}, "count": 0, "results": []}
    coord = AlertsCoordinator(
        hass, mock_client, scan_interval=timedelta(seconds=300),
        filter_lines=[], filter_stops=[1033],   # stop 1033 is in displays_map[701]
        displays_map={701: [1033, 40155]},
    )
    await coord.async_refresh()
    titles = {a["title"] for a in coord.data}
    assert len(coord.data) == 1
    # Exact title format is implementation detail — just confirm the 701 alert made it.
    assert any("Hucisko" in a["title"] or a.get("stops") == [1033, 40155] for a in coord.data)


async def test_alerts_coordinator_no_filters_passes_all(hass, mock_client):
    mock_client.get_bsk_alerts.return_value = {"metadata": {}, "count": 1, "results": [
        {"lineNumbers": [], "title": "X", "summary": "", "content": "",
         "publishFrom": "", "publishTo": "", "url": ""},
    ]}
    mock_client.get_display_messages.return_value = {"lastUpdate": "t", "displaysMsg": []}
    mock_client.get_znt_alerts.return_value = {"metadata": {}, "count": 0, "results": []}
    coord = AlertsCoordinator(
        hass, mock_client, scan_interval=timedelta(seconds=300),
        filter_lines=[], filter_stops=[], displays_map={},
    )
    await coord.async_refresh()
    assert len(coord.data) == 1

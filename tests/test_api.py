"""
Tests for api.py — black-box against spec requirements.

Spec requirements covered:
- get_stops() returns list of stop dicts from date-keyed JSON
- get_routes_for_stop() filters by stopId, excludes passenger=False, natural sort, deduplicates
- get_departures() returns raw departures list; empty list when no departures
- All methods raise ZtmGdanskApiError on HTTP/timeout errors
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ztm_gdansk.api import ZtmGdanskApiClient, ZtmGdanskApiError

from .conftest import (
    DEPARTURES_RESPONSE,
    ROUTES_RESPONSE,
    STOPS_IN_TRIP_RESPONSE,
    STOPS_RESPONSE,
    STOP_CODE,
    STOP_ID,
    STOP_NAME,
)


# ---------------------------------------------------------------------------
# Helpers — build a mock session without touching real aiohttp connectors
# ---------------------------------------------------------------------------


def _response(payload=None, status=200, raise_exc=None):
    """Build an async-context-manager mock that returns a single response."""
    resp = MagicMock()
    if raise_exc:
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=status
        )
    else:
        resp.raise_for_status = MagicMock()
        resp.json = AsyncMock(return_value=payload)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _timeout_response():
    """Simulate a timeout at the context manager level."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _session(*cms):
    """Mock session whose .get() calls return the given context managers in order."""
    session = MagicMock()
    session.get.side_effect = list(cms)
    return session


# ---------------------------------------------------------------------------
# get_stops()
# ---------------------------------------------------------------------------


class TestGetStops:
    async def test_returns_stop_list(self):
        """Spec: get_stops() returns list with stopId, stopName, stopCode, stopDesc."""
        client = ZtmGdanskApiClient(_session(_response(STOPS_RESPONSE)))
        stops = await client.get_stops()

        assert isinstance(stops, list)
        assert len(stops) == 2

    async def test_stop_contains_required_fields(self):
        """Spec: each stop has at minimum stopId, stopName, stopCode, stopDesc."""
        client = ZtmGdanskApiClient(_session(_response(STOPS_RESPONSE)))
        stops = await client.get_stops()

        stop = next(s for s in stops if s["stopId"] == STOP_ID)
        assert stop["stopName"] == STOP_NAME
        assert stop["stopCode"] == STOP_CODE
        assert "stopDesc" in stop

    async def test_filters_out_stops_with_null_name(self):
        """Spec: stops with stopName=None (UNKNOWN external stops) are excluded."""
        response = {
            "lastUpdate": "2026-04-24T20:00:00Z",
            "stops": [
                {"stopId": 1, "stopName": "Valid", "stopCode": "01", "stopDesc": ""},
                {"stopId": 2, "stopName": None, "stopCode": None, "stopDesc": "Ghost"},
            ],
        }
        client = ZtmGdanskApiClient(_session(_response(response)))
        stops = await client.get_stops()

        assert len(stops) == 1
        assert stops[0]["stopName"] == "Valid"

    async def test_calls_stops_url(self):
        """Spec: get_stops() must request URL_STOPS (not a wrong endpoint)."""
        from custom_components.ztm_gdansk.const import URL_STOPS
        session = _session(_response(STOPS_RESPONSE))
        await ZtmGdanskApiClient(session).get_stops()
        assert session.get.call_args[0][0] == URL_STOPS

    async def test_raises_on_http_error(self):
        """Spec: HTTP errors → ZtmGdanskApiError."""
        client = ZtmGdanskApiClient(_session(_response(status=500, raise_exc=True)))
        with pytest.raises(ZtmGdanskApiError):
            await client.get_stops()

    async def test_raises_on_timeout(self):
        """Spec: timeout → ZtmGdanskApiError."""
        client = ZtmGdanskApiClient(_session(_timeout_response()))
        with pytest.raises(ZtmGdanskApiError):
            await client.get_stops()


# ---------------------------------------------------------------------------
# get_routes_for_stop()
# ---------------------------------------------------------------------------


class TestGetRoutesForStop:
    def _client(self, trips=None, routes=None, error_on=None):
        cms = [
            _response(trips or STOPS_IN_TRIP_RESPONSE),
            _response(routes or ROUTES_RESPONSE),
        ]
        if error_on == "trips":
            cms[0] = _response(status=503, raise_exc=True)
        elif error_on == "routes":
            cms[1] = _response(status=503, raise_exc=True)
        # gather() calls both at once; side_effect list must match call order
        session = MagicMock()
        session.get.side_effect = cms
        return ZtmGdanskApiClient(session)

    async def test_returns_only_routes_for_given_stop(self):
        """Spec: only routes where stopId matches are returned."""
        routes = await self._client().get_routes_for_stop(STOP_ID)
        assert "200" not in routes  # routeId 200 → stop 2000

    async def test_excludes_passenger_false(self):
        """Spec: passenger=False records (depot trips) must be excluded."""
        routes = await self._client().get_routes_for_stop(STOP_ID)
        assert "999" not in routes

    async def test_includes_passenger_true(self):
        """Spec: passenger=True records are included."""
        routes = await self._client().get_routes_for_stop(STOP_ID)
        assert "130" in routes

    async def test_includes_passenger_none(self):
        """Spec: passenger=None records are included (not explicitly False)."""
        routes = await self._client().get_routes_for_stop(STOP_ID)
        assert "106" in routes

    async def test_deduplicates_routes(self):
        """Spec: duplicate routeIds (same line via multiple trips) count as one."""
        routes = await self._client().get_routes_for_stop(STOP_ID)
        assert len(routes) == len(set(routes))

    async def test_natural_sort_order(self):
        """Spec: lines sorted naturally — 2 < 10 < N1 < N10."""
        trips = {
            "2026-04-24": {
                "stopsInTrip": [
                    {"routeId": rid, "stopId": STOP_ID, "passenger": True}
                    for rid in [10, 2, 101, 201]
                ]
            }
        }
        routes = {
            "2026-04-24": {
                "routes": [
                    {"routeId": 2, "routeShortName": "2"},
                    {"routeId": 10, "routeShortName": "10"},
                    {"routeId": 101, "routeShortName": "N1"},
                    {"routeId": 201, "routeShortName": "N10"},
                ]
            }
        }
        result = await self._client(trips=trips, routes=routes).get_routes_for_stop(STOP_ID)
        assert result == ["2", "10", "N1", "N10"]

    async def test_unions_routes_across_all_date_keys(self):
        """Spec: weekday-only lines must appear even when queried on a weekend.
        Implementation unions stopsInTrip and routes across all date keys so no
        line is silently dropped because it doesn't run today."""
        trips = {
            "2026-04-26": {  # Sunday — line 176 absent
                "stopsInTrip": [
                    {"routeId": 113, "stopId": STOP_ID, "passenger": True},
                    {"routeId": 213, "stopId": STOP_ID, "passenger": True},
                ]
            },
            "2026-04-28": {  # Monday — line 176 present
                "stopsInTrip": [
                    {"routeId": 113, "stopId": STOP_ID, "passenger": True},
                    {"routeId": 176, "stopId": STOP_ID, "passenger": True},
                ]
            },
        }
        routes = {
            "2026-04-26": {
                "routes": [
                    {"routeId": 113, "routeShortName": "113"},
                    {"routeId": 176, "routeShortName": "176"},
                ]
            },
            "2026-04-28": {
                "routes": [
                    {"routeId": 176, "routeShortName": "176"},
                    {"routeId": 213, "routeShortName": "213"},
                ]
            }
        }
        result = await self._client(trips=trips, routes=routes).get_routes_for_stop(STOP_ID)
        assert "176" in result
        assert "113" in result

    async def test_raises_on_http_error(self):
        """Spec: HTTP error on either static endpoint → ZtmGdanskApiError."""
        with pytest.raises(ZtmGdanskApiError):
            await self._client(error_on="trips").get_routes_for_stop(STOP_ID)


# ---------------------------------------------------------------------------
# get_departures()
# ---------------------------------------------------------------------------


class TestGetDepartures:
    async def test_returns_departures_list(self):
        """Spec: returns raw list from 'departures' key."""
        client = ZtmGdanskApiClient(_session(_response(DEPARTURES_RESPONSE)))
        departures = await client.get_departures(STOP_ID)

        assert isinstance(departures, list)
        assert len(departures) == 2

    async def test_returns_empty_list_when_no_departures(self):
        """Spec: empty departures (e.g. late night) → empty list, no error."""
        client = ZtmGdanskApiClient(
            _session(_response({"lastUpdate": "...", "departures": []}))
        )
        departures = await client.get_departures(STOP_ID)
        assert departures == []

    async def test_departure_contains_required_fields(self):
        """Spec: each departure has routeShortName, headsign, estimatedTime, status."""
        client = ZtmGdanskApiClient(_session(_response(DEPARTURES_RESPONSE)))
        departures = await client.get_departures(STOP_ID)

        d = departures[0]
        for field in ("routeShortName", "headsign", "estimatedTime", "status"):
            assert field in d, f"Missing field: {field}"

    async def test_raises_on_http_error(self):
        """Spec: HTTP error → ZtmGdanskApiError."""
        client = ZtmGdanskApiClient(_session(_response(status=404, raise_exc=True)))
        with pytest.raises(ZtmGdanskApiError):
            await client.get_departures(STOP_ID)

    async def test_sends_stop_id_param(self):
        """Spec: get_departures(stop_id) must pass stopId to URL_DEPARTURES."""
        from custom_components.ztm_gdansk.const import URL_DEPARTURES
        session = _session(_response(DEPARTURES_RESPONSE))
        await ZtmGdanskApiClient(session).get_departures(STOP_ID)
        call = session.get.call_args
        assert call[0][0] == URL_DEPARTURES
        assert call[1]["params"]["stopId"] == STOP_ID

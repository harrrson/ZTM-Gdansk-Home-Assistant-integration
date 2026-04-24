"""Shared fixtures and test data for ZTM Gdańsk integration tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations from the project's custom_components/ dir."""
    yield

from custom_components.ztm_gdansk.const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Canonical test data — mirrors real API response shapes
# ---------------------------------------------------------------------------

STOP_ID = 1016
STOP_NAME = "Dworzec Główny"
STOP_CODE = "07"

STOPS_RESPONSE = {
    "2026-04-24": {
        "stops": [
            {
                "stopId": STOP_ID,
                "stopName": STOP_NAME,
                "stopCode": STOP_CODE,
                "stopDesc": "Centrum",
            },
            {
                "stopId": 2000,
                "stopName": "Wrzeszcz",
                "stopCode": "01",
                "stopDesc": "PKP",
            },
        ]
    }
}

STOPS_IN_TRIP_RESPONSE = {
    "2026-04-24": {
        "stopsInTrip": [
            # included: passenger=True
            {"routeId": 130, "stopId": STOP_ID, "passenger": True},
            # included: passenger=None
            {"routeId": 106, "stopId": STOP_ID, "passenger": None},
            # excluded: passenger=False (depot trip)
            {"routeId": 999, "stopId": STOP_ID, "passenger": False},
            # duplicate routeId — should be deduplicated
            {"routeId": 130, "stopId": STOP_ID, "passenger": True},
            # different stop — should not appear in results for STOP_ID
            {"routeId": 200, "stopId": 2000, "passenger": True},
        ]
    }
}

ROUTES_RESPONSE = {
    "2026-04-24": {
        "routes": [
            {"routeId": 106, "routeShortName": "106"},
            {"routeId": 130, "routeShortName": "130"},
            {"routeId": 200, "routeShortName": "200"},
            {"routeId": 999, "routeShortName": "999"},
        ]
    }
}

DEPARTURE_REALTIME = {
    "routeShortName": "130",
    "headsign": "Dworzec Główny",
    "estimatedTime": "2026-04-24T20:53:39Z",
    "theoreticalTime": "2026-04-24T20:55:00Z",
    "delayInSeconds": -81,
    "status": "REALTIME",
    "vehicleCode": 9052,
}

DEPARTURE_SCHEDULED = {
    "routeShortName": "106",
    "headsign": "Jasień",
    "estimatedTime": "2026-04-24T21:00:00Z",
    "theoreticalTime": "2026-04-24T21:00:00Z",
    "delayInSeconds": None,
    "status": "SCHEDULED",
    "vehicleCode": None,
}

DEPARTURES_RESPONSE = {
    "lastUpdate": "2026-04-24T20:53:00Z",
    "departures": [DEPARTURE_REALTIME, DEPARTURE_SCHEDULED],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STOP_ID: STOP_ID,
            CONF_STOP_NAME: STOP_NAME,
            CONF_STOP_CODE: STOP_CODE,
        },
        options={
            CONF_LINES_FILTER: [],
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_DEPARTURE_COUNT: DEFAULT_DEPARTURE_COUNT,
        },
    )


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.get_stops = AsyncMock(return_value=STOPS_RESPONSE["2026-04-24"]["stops"])
    client.get_routes_for_stop = AsyncMock(return_value=["106", "130"])
    client.get_departures = AsyncMock(
        return_value=DEPARTURES_RESPONSE["departures"]
    )
    return client

"""
Tests for coordinator.py — black-box against spec requirements.

Spec requirements covered:
- Filters departures by routeShortName when lines_filter is non-empty
- Empty lines_filter → no filtering (all lines pass through)
- Sorts departures by estimatedTime ascending
- Truncates to departure_count
- Maps API fields to spec output format
- delayInSeconds → delay_minutes (rounded); None when null
- Converts UTC timestamps to HA local timezone
- Grace period: first error with no prior data → UpdateFailed
- Grace period: errors 1 and 2 with prior data → returns previous data
- Grace period: 3rd consecutive error → UpdateFailed
- Successful fetch resets the error counter
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ztm_gdansk.api import ZtmGdanskApiError
from custom_components.ztm_gdansk.coordinator import ZtmGdanskCoordinator

from .conftest import DEPARTURE_REALTIME, DEPARTURE_SCHEDULED, STOP_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def coordinator(hass, mock_api_client):
    return ZtmGdanskCoordinator(
        hass=hass,
        api_client=mock_api_client,
        stop_id=STOP_ID,
        lines_filter=[],
        departure_count=5,
        update_interval=60,
    )


# ---------------------------------------------------------------------------
# Output format (spec §DataUpdateCoordinator)
# ---------------------------------------------------------------------------


class TestOutputFormat:
    async def test_maps_fields_to_spec_format(self, coordinator, mock_api_client):
        """Spec: output dict keys are line, headsign, estimated_time,
        scheduled_time, delay_minutes, status, vehicle_id."""
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()

        d = coordinator.data[0]
        assert set(d.keys()) >= {
            "line", "headsign", "estimated_time", "scheduled_time",
            "delay_minutes", "status", "vehicle_id",
        }

    async def test_delay_seconds_converted_to_minutes_rounded(
        self, coordinator, mock_api_client
    ):
        """Spec: delayInSeconds ÷ 60, rounded to int."""
        departure = {**DEPARTURE_REALTIME, "delayInSeconds": -81}  # -81s → -1.35 min → -1
        mock_api_client.get_departures.return_value = [departure]
        await coordinator.async_refresh()

        assert coordinator.data[0]["delay_minutes"] == -1

    async def test_delay_null_becomes_none(self, coordinator, mock_api_client):
        """Spec: delayInSeconds=null → delay_minutes=None (SCHEDULED departures)."""
        mock_api_client.get_departures.return_value = [DEPARTURE_SCHEDULED]
        await coordinator.async_refresh()

        assert coordinator.data[0]["delay_minutes"] is None

    async def test_estimated_time_is_timezone_aware(self, coordinator, mock_api_client):
        """Spec: UTC timestamps converted to local timezone (timezone-aware datetime)."""
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()

        estimated = coordinator.data[0]["estimated_time"]
        assert estimated is not None
        assert estimated.tzinfo is not None

    async def test_vehicle_id_none_when_null(self, coordinator, mock_api_client):
        """Spec: vehicleCode=None → vehicle_id=None."""
        mock_api_client.get_departures.return_value = [DEPARTURE_SCHEDULED]
        await coordinator.async_refresh()

        assert coordinator.data[0]["vehicle_id"] is None


# ---------------------------------------------------------------------------
# Filtering and truncation
# ---------------------------------------------------------------------------


class TestFilteringAndTruncation:
    async def test_empty_lines_filter_returns_all_departures(
        self, hass, mock_api_client
    ):
        """Spec: empty lines_filter = no filtering, all lines pass through."""
        coord = ZtmGdanskCoordinator(
            hass=hass,
            api_client=mock_api_client,
            stop_id=STOP_ID,
            lines_filter=[],
            departure_count=10,
            update_interval=60,
        )
        mock_api_client.get_departures.return_value = [
            DEPARTURE_REALTIME,
            DEPARTURE_SCHEDULED,
        ]
        await coord.async_refresh()

        assert len(coord.data) == 2

    async def test_lines_filter_excludes_non_matching_lines(
        self, hass, mock_api_client
    ):
        """Spec: lines_filter → only departures with matching routeShortName."""
        coord = ZtmGdanskCoordinator(
            hass=hass,
            api_client=mock_api_client,
            stop_id=STOP_ID,
            lines_filter=["130"],
            departure_count=10,
            update_interval=60,
        )
        mock_api_client.get_departures.return_value = [
            DEPARTURE_REALTIME,   # line 130 — should stay
            DEPARTURE_SCHEDULED,  # line 106 — should be filtered out
        ]
        await coord.async_refresh()

        assert len(coord.data) == 1
        assert coord.data[0]["line"] == "130"

    async def test_truncates_to_departure_count(self, hass, mock_api_client):
        """Spec: output truncated to configured departure_count."""
        coord = ZtmGdanskCoordinator(
            hass=hass,
            api_client=mock_api_client,
            stop_id=STOP_ID,
            lines_filter=[],
            departure_count=1,
            update_interval=60,
        )
        mock_api_client.get_departures.return_value = [
            DEPARTURE_REALTIME,
            DEPARTURE_SCHEDULED,
        ]
        await coord.async_refresh()

        assert len(coord.data) == 1

    async def test_sorts_by_estimated_time(self, hass, mock_api_client):
        """Spec: output sorted ascending by estimatedTime."""
        early = {**DEPARTURE_REALTIME, "estimatedTime": "2026-04-24T20:00:00Z"}
        late = {**DEPARTURE_SCHEDULED, "estimatedTime": "2026-04-24T21:00:00Z"}
        coord = ZtmGdanskCoordinator(
            hass=hass,
            api_client=mock_api_client,
            stop_id=STOP_ID,
            lines_filter=[],
            departure_count=10,
            update_interval=60,
        )
        # Intentionally reversed order from API
        mock_api_client.get_departures.return_value = [late, early]
        await coord.async_refresh()

        times = [d["estimated_time"] for d in coord.data]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# Grace period (spec §DataUpdateCoordinator)
# ---------------------------------------------------------------------------


class TestGracePeriod:
    async def test_first_error_with_no_prior_data_marks_unavailable(
        self, coordinator, mock_api_client
    ):
        """Spec: failure on first fetch (no prior data) → sensor becomes unavailable
        (last_update_success=False, not silently swallowed)."""
        mock_api_client.get_departures.side_effect = ZtmGdanskApiError("API down")
        await coordinator.async_refresh()

        assert coordinator.last_update_success is False

    async def test_first_two_errors_after_success_preserve_data_and_availability(
        self, coordinator, mock_api_client
    ):
        """Spec: up to 2 consecutive errors after successful fetch → last known data
        preserved AND sensor stays available (last_update_success=True)."""
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()
        previous_data = coordinator.data

        mock_api_client.get_departures.side_effect = ZtmGdanskApiError("API down")

        # Error 1
        await coordinator.async_refresh()
        assert coordinator.data == previous_data
        assert coordinator.last_update_success is True

        # Error 2
        await coordinator.async_refresh()
        assert coordinator.data == previous_data
        assert coordinator.last_update_success is True

    async def test_third_consecutive_error_marks_unavailable(
        self, coordinator, mock_api_client
    ):
        """Spec: sensor becomes unavailable after 3 consecutive failures."""
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()

        mock_api_client.get_departures.side_effect = ZtmGdanskApiError("API down")
        await coordinator.async_refresh()  # error 1 — grace
        await coordinator.async_refresh()  # error 2 — grace
        await coordinator.async_refresh()  # error 3 — exhausted

        assert coordinator.last_update_success is False

    async def test_successful_fetch_resets_error_counter(
        self, coordinator, mock_api_client
    ):
        """Spec: after recovery the grace counter resets — a fresh 3-error sequence
        begins and the first two errors in it are still forgiven."""
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()

        # Consume one grace slot
        mock_api_client.get_departures.side_effect = ZtmGdanskApiError("blip")
        await coordinator.async_refresh()

        # Recovery
        mock_api_client.get_departures.side_effect = None
        mock_api_client.get_departures.return_value = [DEPARTURE_REALTIME]
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True

        # Start new error sequence — should get 2 more grace slots
        mock_api_client.get_departures.side_effect = ZtmGdanskApiError("blip")
        await coordinator.async_refresh()  # error 1 of new sequence
        await coordinator.async_refresh()  # error 2 of new sequence

        assert coordinator.last_update_success is True  # counter was reset, still in grace

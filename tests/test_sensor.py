"""
Tests for sensor.py — black-box against spec requirements.

Spec requirements covered:
- unique_id = "ztm_gdansk_{stop_id}"
- entity name = "ZTM Gdańsk {stop_name} {stop_code}"
- native_value = minutes to first departure (int ≥ 0)
- native_value = None when departures list is empty
- extra_state_attributes contains all required keys with correct values
- departures in attributes serialized to dicts with ISO-format timestamps
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ztm_gdansk.coordinator import ZtmGdanskCoordinator
from custom_components.ztm_gdansk.sensor import ZtmGdanskSensor
from custom_components.ztm_gdansk.const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
)

from .conftest import STOP_CODE, STOP_ID, STOP_NAME


def _make_sensor(
    coordinator,
    mock_config_entry,
    lines_filter=None,
):
    """Create sensor without HA platform setup."""
    return ZtmGdanskSensor(coordinator, mock_config_entry)


def _mock_coordinator(data):
    coord = MagicMock(spec=ZtmGdanskCoordinator)
    coord.data = data
    return coord


def _future_departure(minutes_from_now: int) -> dict:
    """Build a processed departure dict with estimated_time = now + minutes."""
    est = datetime.now(tz=timezone.utc) + timedelta(minutes=minutes_from_now)
    return {
        "line": "130",
        "headsign": "Dworzec Główny",
        "estimated_time": est,
        "scheduled_time": est,
        "delay_minutes": 0,
        "status": "REALTIME",
        "vehicle_id": 9052,
    }


# ---------------------------------------------------------------------------
# Entity identity
# ---------------------------------------------------------------------------


class TestSensorIdentity:
    def test_unique_id_format(self, mock_config_entry):
        """Spec: unique_id = 'ztm_gdansk_{stop_id}'."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        assert sensor.unique_id == f"ztm_gdansk_{STOP_ID}"

    def test_name_format(self, mock_config_entry):
        """Spec: name = 'ZTM Gdańsk {stop_name} {stop_code}'."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        assert sensor.name == f"ZTM Gdańsk {STOP_NAME} {STOP_CODE}"


# ---------------------------------------------------------------------------
# State (native_value)
# ---------------------------------------------------------------------------


class TestSensorState:
    def test_returns_minutes_to_next_departure(self, mock_config_entry):
        """Spec: state = integer minutes to next departure."""
        departure = _future_departure(10)
        sensor = _make_sensor(_mock_coordinator([departure]), mock_config_entry)

        value = sensor.native_value
        assert isinstance(value, int)
        assert 9 <= value <= 10  # allow 1-minute rounding window

    def test_returns_zero_when_departure_is_past(self, mock_config_entry):
        """Spec: state never goes negative — past departures show 0."""
        past_est = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        departure = {
            "line": "130",
            "headsign": "Dworzec",
            "estimated_time": past_est,
            "scheduled_time": past_est,
            "delay_minutes": 0,
            "status": "REALTIME",
            "vehicle_id": None,
        }
        sensor = _make_sensor(_mock_coordinator([departure]), mock_config_entry)
        assert sensor.native_value == 0

    def test_returns_none_when_no_departures(self, mock_config_entry):
        """Spec: state = None when no departures (e.g. late night)."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        assert sensor.native_value is None

    def test_returns_none_when_coordinator_data_is_none(self, mock_config_entry):
        """Spec: sensor unavailable → state = None."""
        sensor = _make_sensor(_mock_coordinator(None), mock_config_entry)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------


class TestSensorAttributes:
    def test_required_attribute_keys_present(self, mock_config_entry):
        """Spec: attributes must contain stop_name, stop_id, stop_code,
        filtered_lines, departures."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        attrs = sensor.extra_state_attributes
        for key in ("stop_name", "stop_id", "stop_code", "filtered_lines", "departures"):
            assert key in attrs, f"Missing attribute: {key}"

    def test_stop_attributes_match_config(self, mock_config_entry):
        """Spec: stop_name/stop_id/stop_code come from config entry."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        attrs = sensor.extra_state_attributes
        assert attrs["stop_name"] == STOP_NAME
        assert attrs["stop_id"] == STOP_ID
        assert attrs["stop_code"] == STOP_CODE

    def test_filtered_lines_reflects_options(self, hass, mock_config_entry):
        """Spec: filtered_lines = configured lines_filter (empty = all lines)."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from custom_components.ztm_gdansk.const import DOMAIN
        entry_with_filter = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry.data,
            options={
                CONF_LINES_FILTER: ["130", "106"],
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_DEPARTURE_COUNT: DEFAULT_DEPARTURE_COUNT,
            },
        )
        sensor = _make_sensor(_mock_coordinator([]), entry_with_filter)
        assert sensor.extra_state_attributes["filtered_lines"] == ["130", "106"]

    def test_departures_use_iso_string_timestamps(self, mock_config_entry):
        """Spec: estimated_time and scheduled_time in attributes are ISO-8601 strings."""
        departure = _future_departure(10)
        sensor = _make_sensor(_mock_coordinator([departure]), mock_config_entry)
        attrs = sensor.extra_state_attributes
        d = attrs["departures"][0]
        # Must be serializable strings, not datetime objects
        assert isinstance(d["estimated_time"], str)
        assert isinstance(d["scheduled_time"], str)
        # Must be parseable ISO-8601
        datetime.fromisoformat(d["estimated_time"])

    def test_empty_departures_list_when_no_data(self, mock_config_entry):
        """Spec: departures attribute is empty list when coordinator has no data."""
        sensor = _make_sensor(_mock_coordinator([]), mock_config_entry)
        assert sensor.extra_state_attributes["departures"] == []

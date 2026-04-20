"""Tests for ZTMDisruptionBinarySensor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from custom_components.ztm_gdansk.binary_sensor import ZTMDisruptionBinarySensor


def _make_coord(alerts, age_seconds=0):
    coord = MagicMock()
    coord.data = alerts
    coord.last_successful_update = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return coord


def test_unique_id_and_device_class():
    coord = _make_coord([])
    s = ZTMDisruptionBinarySensor(coord, stale_max_age=1500)
    assert s.unique_id == "ztm_gdansk_disruption"
    assert s.device_class == "problem"


def test_state_off_when_no_alerts():
    coord = _make_coord([])
    s = ZTMDisruptionBinarySensor(coord, stale_max_age=1500)
    assert s.is_on is False


def test_state_on_when_alerts_present():
    coord = _make_coord([{"title": "x", "body": "y", "lines": [], "stops": [], "source": "bsk"}])
    s = ZTMDisruptionBinarySensor(coord, stale_max_age=1500)
    assert s.is_on is True


def test_attributes_count_and_alerts():
    alerts = [
        {"title": "A", "body": "x", "lines": [], "stops": [], "source": "bsk"},
        {"title": "B", "body": "y", "lines": [], "stops": [], "source": "display"},
    ]
    coord = _make_coord(alerts, age_seconds=30)
    s = ZTMDisruptionBinarySensor(coord, stale_max_age=1500)
    attrs = s.extra_state_attributes
    assert attrs["count"] == 2
    assert len(attrs["alerts"]) == 2
    assert attrs["data_age_seconds"] == 30


def test_unavailable_after_stale():
    coord = _make_coord([], age_seconds=2000)
    s = ZTMDisruptionBinarySensor(coord, stale_max_age=1500)
    assert s.available is False

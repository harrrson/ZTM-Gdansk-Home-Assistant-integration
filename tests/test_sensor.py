"""Tests for ZTMDepartureSensor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.ztm_gdansk.sensor import ZTMDepartureSensor, slugify_pl


def test_slugify_polish_chars():
    assert slugify_pl("Brama Wyżynna") == "brama_wyzynna"
    assert slugify_pl("Stogi - Pętla") == "stogi_petla"
    assert slugify_pl("ŁĄKOWA") == "lakowa"


def test_sensor_unique_id_and_friendly_name():
    coord = MagicMock()
    coord.data = {1234: {"departures": []}}
    coord.last_successful_update = datetime.now(timezone.utc)
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="Brama Wyżynna",
        line="8", next_count=5, stale_max_age=600,
    )
    assert sensor.unique_id == "ztm_gdansk_1234_8"
    assert "Brama Wyżynna" in sensor.name
    assert "linia 8" in sensor.name


def _make_coord(stop_id, departures, age_seconds=0):
    coord = MagicMock()
    coord.data = {stop_id: {"departures": departures}}
    coord.last_successful_update = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return coord


def test_sensor_state_returns_next_estimated_for_line():
    deps = [
        {"routeShortName": "8", "estimatedTime": "2026-04-19T22:35:00+02:00",
         "theoreticalTime": "2026-04-19T22:34:00+02:00", "headsign": "Stogi"},
        {"routeShortName": "11", "estimatedTime": "2026-04-19T22:36:00+02:00",
         "theoreticalTime": "2026-04-19T22:36:00+02:00", "headsign": "Migowo"},
        {"routeShortName": "8", "estimatedTime": "2026-04-19T22:45:00+02:00",
         "theoreticalTime": "2026-04-19T22:44:00+02:00", "headsign": "Stogi"},
    ]
    coord = _make_coord(1234, deps)
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="X", line="8", next_count=5, stale_max_age=600,
    )
    assert sensor.native_value.isoformat() == "2026-04-19T22:35:00+02:00"


def test_sensor_state_none_when_no_departures_for_line():
    coord = _make_coord(1234, [
        {"routeShortName": "11", "estimatedTime": "2026-04-19T22:36:00+02:00",
         "theoreticalTime": "2026-04-19T22:36:00+02:00", "headsign": "Migowo"},
    ])
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="X", line="8", next_count=5, stale_max_age=600,
    )
    assert sensor.native_value is None


def test_sensor_attributes_include_next_departures_capped_at_n():
    deps = [
        {"routeShortName": "8", "estimatedTime": f"2026-04-19T22:{30+i:02d}:00+02:00",
         "theoreticalTime": f"2026-04-19T22:{30+i:02d}:00+02:00",
         "headsign": "Stogi"}
        for i in range(8)
    ]
    coord = _make_coord(1234, deps)
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="X", line="8", next_count=3, stale_max_age=600,
    )
    attrs = sensor.extra_state_attributes
    assert len(attrs["next_departures"]) == 3
    assert attrs["line"] == "8"
    assert attrs["stop_id"] == 1234


def test_sensor_unavailable_after_stale_threshold():
    coord = _make_coord(1234, [], age_seconds=700)
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="X", line="8", next_count=5, stale_max_age=600,
    )
    assert sensor.available is False


def test_sensor_available_when_fresh():
    coord = _make_coord(1234, [
        {"routeShortName": "8", "estimatedTime": "2026-04-19T22:35:00+02:00",
         "theoreticalTime": "2026-04-19T22:34:00+02:00", "headsign": "Stogi"},
    ], age_seconds=10)
    sensor = ZTMDepartureSensor(
        coord, stop_id=1234, stop_name="X", line="8", next_count=5, stale_max_age=600,
    )
    assert sensor.available is True

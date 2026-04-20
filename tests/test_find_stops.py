"""Tests for find_stops CLI helper."""
from __future__ import annotations

from custom_components.ztm_gdansk.tools.find_stops import filter_stops, format_row


def test_filter_case_insensitive_polish():
    stops = [
        {"id": 1, "name": "Brama Wyżynna"},
        {"id": 2, "name": "Stogi Plaża"},
        {"id": 3, "name": "Brama Oliwska"},
    ]
    res = filter_stops(stops, "brama")
    assert {s["id"] for s in res} == {1, 3}

    res = filter_stops(stops, "wyzynna")  # without diacritics
    assert {s["id"] for s in res} == {1}


def test_format_row():
    assert format_row({"id": 1234, "name": "Brama Wyżynna"}).startswith("1234")

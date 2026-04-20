"""Tests for YAML config schema."""
import pytest
import voluptuous as vol

from custom_components.ztm_gdansk.config_schema import CONFIG_SCHEMA
from custom_components.ztm_gdansk.const import DOMAIN


def _wrap(domain_config: dict) -> dict:
    return {DOMAIN: domain_config}


def test_minimal_config_accepted():
    config = _wrap({"departures": [{"stop_id": 1234}]})
    result = CONFIG_SCHEMA(config)
    domain = result[DOMAIN]
    assert domain["scan_interval"] == 60
    assert domain["next_departures_count"] == 5
    assert domain["stale_data_max_age"] == 600
    assert domain["alerts"]["enabled"] is True
    assert domain["alerts"]["scan_interval"] == 300
    assert domain["alerts"]["filter_lines"] == []
    assert domain["alerts"]["filter_stops"] == []
    assert domain["departures"][0]["stop_id"] == 1234
    assert domain["departures"][0]["lines"] == []


def test_empty_departures_rejected():
    with pytest.raises(vol.Invalid) as exc:
        CONFIG_SCHEMA(_wrap({"departures": []}))
    assert "departures" in str(exc.value).lower()


def test_scan_interval_below_minimum_rejected():
    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(_wrap({
            "scan_interval": 5,
            "departures": [{"stop_id": 1}],
        }))


def test_lines_normalized_to_strings():
    result = CONFIG_SCHEMA(_wrap({
        "departures": [{"stop_id": 1234, "lines": [8, "11", "N1"]}],
    }))
    assert result[DOMAIN]["departures"][0]["lines"] == ["8", "11", "N1"]


def test_negative_stop_id_rejected():
    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(_wrap({"departures": [{"stop_id": -1}]}))


def test_alerts_disabled_explicitly():
    result = CONFIG_SCHEMA(_wrap({
        "departures": [{"stop_id": 1}],
        "alerts": {"enabled": False},
    }))
    assert result[DOMAIN]["alerts"]["enabled"] is False

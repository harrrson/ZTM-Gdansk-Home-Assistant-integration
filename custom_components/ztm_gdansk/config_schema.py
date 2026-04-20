"""YAML configuration schema for ZTM Gdańsk integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ALERTS,
    CONF_ALERTS_ENABLED,
    CONF_ALERTS_FILTER_LINES,
    CONF_ALERTS_FILTER_STOPS,
    CONF_DEPARTURES,
    CONF_LINES,
    CONF_NEXT_DEPARTURES_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_STALE_DATA_MAX_AGE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_ALERTS_SCAN_INTERVAL,
    DEFAULT_NEXT_DEPARTURES_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_DATA_MAX_AGE,
    DOMAIN,
    MAX_NEXT_DEPARTURES_COUNT,
    MIN_ALERTS_SCAN_INTERVAL,
    MIN_NEXT_DEPARTURES_COUNT,
    MIN_SCAN_INTERVAL,
)


def _line_to_str(value: object) -> str:
    if isinstance(value, (str, int)):
        return str(value)
    raise vol.Invalid("Numer linii musi być liczbą lub łańcuchem znaków")


def _positive_int(value: object) -> int:
    n = int(value)
    if n <= 0:
        raise vol.Invalid("stop_id musi być dodatnią liczbą całkowitą")
    return n


_LINES_SCHEMA = vol.All(cv.ensure_list, [_line_to_str])

_DEPARTURE_ENTRY_SCHEMA = vol.Schema({
    vol.Required(CONF_STOP_ID): _positive_int,
    vol.Optional(CONF_STOP_NAME): cv.string,
    vol.Optional(CONF_LINES, default=list): _LINES_SCHEMA,
})

_ALERTS_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALERTS_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_ALERTS_SCAN_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=MIN_ALERTS_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_ALERTS_FILTER_LINES, default=list): _LINES_SCHEMA,
    vol.Optional(CONF_ALERTS_FILTER_STOPS, default=list): vol.All(
        cv.ensure_list, [_positive_int]
    ),
})


def _non_empty_departures(value: list) -> list:
    if not value:
        raise vol.Invalid(
            "Sekcja `departures` musi zawierać co najmniej jeden przystanek"
        )
    return value


_DOMAIN_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_NEXT_DEPARTURES_COUNT, default=DEFAULT_NEXT_DEPARTURES_COUNT): vol.All(
        cv.positive_int,
        vol.Range(min=MIN_NEXT_DEPARTURES_COUNT, max=MAX_NEXT_DEPARTURES_COUNT),
    ),
    vol.Optional(CONF_STALE_DATA_MAX_AGE, default=DEFAULT_STALE_DATA_MAX_AGE): cv.positive_int,
    vol.Optional(CONF_ALERTS, default=dict): _ALERTS_SCHEMA,
    vol.Required(CONF_DEPARTURES): vol.All(cv.ensure_list, _non_empty_departures, [_DEPARTURE_ENTRY_SCHEMA]),
})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: _DOMAIN_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)

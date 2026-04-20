"""ZTM Gdańsk integration bootstrap."""
from __future__ import annotations

import asyncio
import difflib
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .api import ZTMApiError, ZTMGdanskClient
from .config_schema import CONFIG_SCHEMA  # noqa: F401 — re-exported for HA
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
    DOMAIN,
)
from .coordinator import AlertsCoordinator, DepartureCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    domain_config = config.get(DOMAIN)
    if not domain_config:
        return True

    session = async_get_clientsession(hass)
    client = ZTMGdanskClient(session)

    # Validate stop IDs against API
    try:
        all_stops_raw = await client.get_stops()
    except ZTMApiError as err:
        _LOGGER.warning(
            "Nie udało się pobrać listy przystanków ZTM przy starcie (%s) — "
            "kontynuuję bez walidacji stop_id", err,
        )
        all_stops_raw = []

    stop_index = _build_stop_index(all_stops_raw)

    # Fetch display code → stop IDs mapping for alert enrichment (ADDENDUM §F)
    try:
        displays_raw = await client.get_displays()
    except ZTMApiError as err:
        _LOGGER.warning(
            "Nie udało się pobrać mapowania tablic informacyjnych ZTM (%s) — "
            "filtrowanie alertów po przystankach będzie ograniczone", err,
        )
        displays_raw = []

    displays_map = _build_displays_map(displays_raw)

    valid_entries: list[dict[str, Any]] = []
    for entry in domain_config[CONF_DEPARTURES]:
        sid = entry[CONF_STOP_ID]
        api_name = stop_index.get(sid)
        if api_name is None and stop_index:
            suggestions = _suggest_names(sid, stop_index)
            _LOGGER.warning(
                "Stop ID %s nie istnieje w API ZTM. Czy chodziło o: %s? — pomijam ten wpis.",
                sid, ", ".join(suggestions) or "brak sugestii",
            )
            continue
        stop_name = entry.get(CONF_STOP_NAME) or api_name or f"stop {sid}"
        valid_entries.append({
            CONF_STOP_ID: sid,
            CONF_STOP_NAME: stop_name,
            CONF_LINES: entry[CONF_LINES],  # may be empty -> resolve later
        })

    if not valid_entries:
        _LOGGER.error(
            "Żaden ze skonfigurowanych przystanków nie został rozpoznany — integracja nie startuje"
        )
        return False

    # Resolve "all lines from stop" entries via schedule data (not live departures)
    needs_discovery = [e for e in valid_entries if not e[CONF_LINES]]
    if needs_discovery:
        stop_lines_map = await _discover_lines_from_schedule(client)
        for entry in needs_discovery:
            sid = entry[CONF_STOP_ID]
            entry[CONF_LINES] = sorted(stop_lines_map.get(sid, []))
            if not entry[CONF_LINES]:
                _LOGGER.warning(
                    "Nie udało się wykryć linii dla stop_id=%s ze statycznego rozkładu — "
                    "podaj `lines:` jawnie", sid,
                )

    departure_coord = DepartureCoordinator(
        hass, client,
        stop_ids=[e[CONF_STOP_ID] for e in valid_entries],
        scan_interval=timedelta(seconds=domain_config[CONF_SCAN_INTERVAL]),
    )
    await departure_coord.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["departure_coordinator"] = departure_coord
    hass.data[DOMAIN]["next_departures_count"] = domain_config[CONF_NEXT_DEPARTURES_COUNT]
    hass.data[DOMAIN]["stale_data_max_age"] = domain_config[CONF_STALE_DATA_MAX_AGE]

    alerts_cfg = domain_config[CONF_ALERTS]
    if alerts_cfg[CONF_ALERTS_ENABLED]:
        # ADDENDUM §F: pass displays_map to AlertsCoordinator
        alerts_coord = AlertsCoordinator(
            hass, client,
            scan_interval=timedelta(seconds=alerts_cfg[CONF_SCAN_INTERVAL]),
            filter_lines=alerts_cfg[CONF_ALERTS_FILTER_LINES],
            filter_stops=alerts_cfg[CONF_ALERTS_FILTER_STOPS],
            displays_map=displays_map,
        )
        await alerts_coord.async_refresh()
        hass.data[DOMAIN]["alerts_coordinator"] = alerts_coord
        hass.data[DOMAIN]["alerts_stale_max_age"] = alerts_cfg[CONF_SCAN_INTERVAL] * 5

    hass.async_create_task(
        async_load_platform(
            hass, "sensor", DOMAIN,
            {"entries": valid_entries},
            config,
        )
    )
    if alerts_cfg[CONF_ALERTS_ENABLED]:
        hass.async_create_task(
            async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
        )

    return True


async def _discover_lines_from_schedule(client: ZTMGdanskClient) -> dict[int, set[str]]:
    """Build {stopId: set(routeShortName)} from static schedule data.

    Fetches stopsintrip.json (~37 MB) and routes.json once at startup.
    Only called when at least one departure entry uses lines: [].
    """
    try:
        raw_trips, raw_routes = await asyncio.gather(
            client.get_stops_in_trip(),
            client.get_routes(),
        )
    except ZTMApiError as err:
        _LOGGER.warning(
            "Nie udało się pobrać danych rozkładu do wykrywania linii (%s) — "
            "auto-discovery niedostępne", err,
        )
        return {}

    route_name_map: dict[int, str] = {}
    if isinstance(raw_routes, dict):
        for date_block in raw_routes.values():
            if isinstance(date_block, dict):
                for route in date_block.get("routes") or []:
                    rid = route.get("routeId")
                    name = route.get("routeShortName")
                    if isinstance(rid, int) and isinstance(name, str):
                        route_name_map[rid] = name
                break

    stop_lines: dict[int, set[str]] = {}
    if isinstance(raw_trips, dict):
        for date_block in raw_trips.values():
            if isinstance(date_block, dict):
                for item in date_block.get("stopsInTrip") or []:
                    sid = item.get("stopId")
                    rid = item.get("routeId")
                    if isinstance(sid, int) and isinstance(rid, int):
                        name = route_name_map.get(rid, str(rid))
                        stop_lines.setdefault(sid, set()).add(name)
                break

    return stop_lines


def _build_stop_index(raw: Any) -> dict[int, str]:
    """Normalize the API stops payload to {stop_id: name}.

    Handles both a bare list and the real dict-with-stops shape per ADDENDUM §C.
    """
    out: dict[int, str] = {}
    items = (
        raw
        if isinstance(raw, list)
        else (raw.get("stops") if isinstance(raw, dict) else None) or []
    )
    for it in items:
        sid = it.get("stopId") or it.get("stop_id") or it.get("id")
        name = it.get("stopName") or it.get("stop_name") or it.get("name")
        if isinstance(sid, int) and isinstance(name, str):
            out[sid] = name
    return out


def _build_displays_map(raw: Any) -> dict[int, list[int]]:
    """Build {displayCode: [stopId, ...]} mapping from the displays API response.

    Handles a bare list or a dict-with-list shape. Filters out zero stop IDs
    (unused slots per ADDENDUM §F).
    """
    out: dict[int, list[int]] = {}
    items = (
        raw
        if isinstance(raw, list)
        else (raw.get("displays") if isinstance(raw, dict) else None) or []
    )
    for it in items:
        code = it.get("displayCode")
        if not isinstance(code, int):
            continue
        stops = [
            it[slot]
            for slot in ("idStop1", "idStop2", "idStop3", "idStop4")
            if isinstance(it.get(slot), int) and it[slot]
        ]
        out[code] = stops
    return out


def _suggest_names(sid: int, stop_index: dict[int, str], k: int = 3) -> list[str]:
    """Suggest the k most-similar stop IDs (by string distance)."""
    candidates = [str(s) for s in stop_index]
    matches = difflib.get_close_matches(str(sid), candidates, n=k, cutoff=0.5)
    return [f"{m} ({stop_index[int(m)]})" for m in matches if int(m) in stop_index]

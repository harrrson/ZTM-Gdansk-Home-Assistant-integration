"""ZTM Gdańsk API client."""
from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Any

import aiohttp

from .const import URL_DEPARTURES, URL_ROUTES, URL_STOPS, URL_STOPS_IN_TRIP

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class ZtmGdanskApiError(Exception):
    """Raised on API communication or parsing errors."""


class ZtmGdanskApiClient:
    """HTTP client for the ZTM Gdańsk TRISTAR API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get_json(self, url: str, params: dict | None = None) -> Any:
        try:
            async with self._session.get(
                url, params=params, timeout=REQUEST_TIMEOUT
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise ZtmGdanskApiError(f"Timeout fetching {url}") from err
        except aiohttp.ClientResponseError as err:
            raise ZtmGdanskApiError(f"HTTP {err.status} fetching {url}") from err
        except aiohttp.ClientError as err:
            raise ZtmGdanskApiError(f"Client error fetching {url}: {err}") from err

    async def get_stops(self) -> list[dict]:
        """Return list of stops with stopId, stopName, stopCode, stopDesc."""
        data = await self._get_json(URL_STOPS)
        try:
            return [s for s in data["stops"] if s.get("stopName")]
        except (KeyError, TypeError) as err:
            raise ZtmGdanskApiError(f"Unexpected stops.json structure: {err}") from err

    async def get_routes_for_stop(self, stop_id: int) -> list[str]:
        """Return sorted list of routeShortName serving given stop."""
        trips_data, routes_data = await asyncio.gather(
            self._get_json(URL_STOPS_IN_TRIP),
            self._get_json(URL_ROUTES),
        )
        try:
            # Union across all date keys so weekday-only lines aren't missed when
            # queried on a weekend or public holiday.
            route_id_to_name: dict[int, str] = {
                rec["routeId"]: rec["routeShortName"]
                for routes_key in routes_data
                for rec in routes_data[routes_key]["routes"]
            }
            route_id_set: set[int] = {
                rec["routeId"]
                for key in trips_data
                for rec in trips_data[key]["stopsInTrip"]
                if rec.get("stopId") == stop_id and rec.get("passenger") is not False
            }
        except (KeyError, StopIteration, TypeError) as err:
            raise ZtmGdanskApiError(f"Unexpected static data structure: {err}") from err

        names = {
            route_id_to_name[rid]
            for rid in route_id_set
            if rid in route_id_to_name
        }
        return sorted(names, key=_natural_sort_key)

    async def get_departures(self, stop_id: int) -> list[dict]:
        """Return raw departures list for given stop."""
        data = await self._get_json(URL_DEPARTURES, params={"stopId": stop_id})
        try:
            return data.get("departures", [])
        except AttributeError as err:
            raise ZtmGdanskApiError(f"Unexpected departures response: {err}") from err


def _natural_sort_key(s: str) -> tuple:
    """Sort key: numeric parts as ints, alphabetic as lowercase strings."""
    parts = re.split(r"(\d+)", s)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)

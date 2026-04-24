"""DataUpdateCoordinator for ZTM Gdańsk."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import as_local, parse_datetime

from .api import ZtmGdanskApiClient, ZtmGdanskApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

GRACE_PERIOD = 3


class ZtmGdanskCoordinator(DataUpdateCoordinator[list[dict]]):
    """Fetches and processes departure data for one stop."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ZtmGdanskApiClient,
        stop_id: int,
        lines_filter: list[str],
        departure_count: int,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{stop_id}",
            update_interval=timedelta(seconds=update_interval),
        )
        self._api = api_client
        self._stop_id = stop_id
        self._lines_filter = lines_filter
        self._departure_count = departure_count
        self._consecutive_errors = 0

    async def _async_update_data(self) -> list[dict]:
        try:
            raw = await self._api.get_departures(self._stop_id)
        except (ZtmGdanskApiError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            self._consecutive_errors += 1
            if self._consecutive_errors < GRACE_PERIOD:
                _LOGGER.warning(
                    "ZTM Gdańsk fetch error (attempt %d/%d): %s",
                    self._consecutive_errors,
                    GRACE_PERIOD,
                    err,
                )
                return self.data or []
            raise UpdateFailed(f"ZTM Gdańsk API unavailable: {err}") from err

        self._consecutive_errors = 0

        if self._lines_filter:
            raw = [d for d in raw if d.get("routeShortName") in self._lines_filter]

        raw = sorted(raw, key=lambda d: d.get("estimatedTime", ""))
        raw = raw[: self._departure_count]

        return [self._process_departure(d) for d in raw]

    def _process_departure(self, d: dict) -> dict:
        estimated = _parse_local(d.get("estimatedTime"))
        scheduled = _parse_local(d.get("theoreticalTime"))

        delay_sec = d.get("delayInSeconds")
        delay_minutes: int | None = None
        if delay_sec is not None:
            delay_minutes = round(delay_sec / 60)

        vehicle = d.get("vehicleCode")
        vehicle_id: int | None = int(vehicle) if vehicle is not None else None

        return {
            "line": d.get("routeShortName"),
            "headsign": d.get("headsign"),
            "estimated_time": estimated,
            "scheduled_time": scheduled,
            "delay_minutes": delay_minutes,
            "status": d.get("status"),
            "vehicle_id": vehicle_id,
        }


def _parse_local(value: str | None):
    """Parse ISO-8601 datetime string and convert to HA local timezone."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    return as_local(dt)

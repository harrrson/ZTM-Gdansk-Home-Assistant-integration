"""Async HTTP client for ZTM Gdansk public APIs."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    API_BSK_URL,
    API_DEPARTURES_URL,
    API_DISPLAY_MESSAGES_URL,
    API_DISPLAYS_URL,
    API_ROUTES_URL,
    API_STOPS_IN_TRIP_URL,
    API_STOPS_URL,
    API_ZNT_URL,
    HTTP_TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class ZTMApiError(Exception):
    """Raised when ZTM API call fails."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status: int | None = None,
        body_snippet: str | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.body_snippet = body_snippet
        full = message
        if url:
            full += f" (url={url}"
            if status is not None:
                full += f", status={status}"
            if body_snippet:
                full += f", body={body_snippet[:200]!r}"
            full += ")"
        super().__init__(full)


class ZTMGdanskClient:
    """Thin async wrapper for ZTM Gdansk JSON endpoints."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._timeout = ClientTimeout(total=HTTP_TIMEOUT_SECONDS)

    async def _get_json(self, url: str, *, timeout: ClientTimeout | None = None) -> Any:
        try:
            async with self._session.get(url, timeout=timeout or self._timeout) as resp:
                if resp.status >= 400:
                    body = (await resp.text())[:500]
                    raise ZTMApiError(
                        "HTTP error", url=url, status=resp.status, body_snippet=body
                    )
                try:
                    return await resp.json(content_type=None)
                except ValueError as exc:
                    body = (await resp.text())[:500]
                    raise ZTMApiError(
                        "Invalid JSON", url=url, status=resp.status, body_snippet=body
                    ) from exc
        except asyncio.TimeoutError as exc:
            raise ZTMApiError("Timeout", url=url) from exc
        except ClientError as exc:
            raise ZTMApiError(f"Network error: {exc}", url=url) from exc

    async def get_departures(self, stop_id: int) -> dict[str, Any]:
        """Return estimated departures for a single stop."""
        return await self._get_json(f"{API_DEPARTURES_URL}?stopId={stop_id}")

    async def get_bsk_alerts(self) -> Any:
        """Return Centrala Ruchu bulletin alerts."""
        return await self._get_json(API_BSK_URL)

    async def get_display_messages(self) -> Any:
        """Return live messages on display boards at stops."""
        return await self._get_json(API_DISPLAY_MESSAGES_URL)

    async def get_znt_alerts(self) -> Any:
        """Return zmiany na trasach route-change alerts."""
        return await self._get_json(API_ZNT_URL)

    async def get_stops(self) -> Any:
        """Return full list of active stops for Gdansk (and wider Tricity)."""
        return await self._get_json(API_STOPS_URL)

    async def get_displays(self) -> Any:
        """Return display-board definitions (maps displayCode to stop IDs)."""
        return await self._get_json(API_DISPLAYS_URL)

    async def get_routes(self) -> Any:
        """Return route (line) definitions keyed by date."""
        return await self._get_json(API_ROUTES_URL)

    async def get_stops_in_trip(self) -> Any:
        """Return stop-in-trip mapping keyed by date (~37 MB)."""
        return await self._get_json(
            API_STOPS_IN_TRIP_URL,
            timeout=ClientTimeout(total=60),
        )

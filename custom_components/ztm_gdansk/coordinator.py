"""DataUpdateCoordinators for the ZTM Gdańsk integration."""
from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ZTMApiError, ZTMGdanskClient
from .const import (
    BACKOFF_ERROR_THRESHOLD,
    BACKOFF_MAX_ALERTS,
    BACKOFF_MAX_DEPARTURES,
    BACKOFF_MULTIPLIER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip() if text else ""


class _BaseCoordinator(DataUpdateCoordinator):
    """Shared backoff + stale-data preservation logic."""

    _max_backoff_seconds: int = 600

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=name,
            update_interval=scan_interval,
        )
        self._base_interval = scan_interval
        self.consecutive_errors = 0
        self.last_successful_update: datetime | None = None

    async def _async_update_data(self) -> Any:
        try:
            data = await self._fetch()
        except ZTMApiError as err:
            self.consecutive_errors += 1
            if self.consecutive_errors == 1:
                _LOGGER.warning("ZTM %s API error: %s", self.name, err)
            else:
                _LOGGER.debug(
                    "ZTM %s API error #%d: %s", self.name, self.consecutive_errors, err
                )
            self._maybe_back_off()
            return self.data  # preserve previous data
        self.consecutive_errors = 0
        self.last_successful_update = _utcnow()
        if self.update_interval != self._base_interval:
            _LOGGER.info(
                "ZTM %s recovered, restoring scan_interval to %s",
                self.name, self._base_interval,
            )
            self.update_interval = self._base_interval
        return data

    async def _fetch(self) -> Any:
        raise NotImplementedError

    def _maybe_back_off(self) -> None:
        if self.consecutive_errors < BACKOFF_ERROR_THRESHOLD:
            return
        new_seconds = min(
            int(self.update_interval.total_seconds() * BACKOFF_MULTIPLIER),
            self._max_backoff_seconds,
        )
        if new_seconds != int(self.update_interval.total_seconds()):
            _LOGGER.info(
                "ZTM %s backing off scan_interval to %ds after %d errors",
                self.name, new_seconds, self.consecutive_errors,
            )
            self.update_interval = timedelta(seconds=new_seconds)


class DepartureCoordinator(_BaseCoordinator):
    """Pulls departures for all configured stops in parallel."""

    _max_backoff_seconds = BACKOFF_MAX_DEPARTURES

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZTMGdanskClient,
        stop_ids: Iterable[int],
        scan_interval: timedelta,
    ) -> None:
        super().__init__(hass, name=f"{DOMAIN}_departures", scan_interval=scan_interval)
        self._client = client
        self._stop_ids = list(stop_ids)

    async def _fetch(self) -> dict[int, dict[str, Any]]:
        results = await asyncio.gather(
            *(self._client.get_departures(sid) for sid in self._stop_ids),
            return_exceptions=True,
        )
        out: dict[int, dict[str, Any]] = {}
        all_failed = True
        for sid, res in zip(self._stop_ids, results):
            if isinstance(res, Exception):
                _LOGGER.debug("Stop %s fetch failed: %s", sid, res)
                if self.data and sid in self.data:
                    out[sid] = self.data[sid]  # preserve prior per-stop data
                continue
            out[sid] = res
            all_failed = False
        if all_failed:
            raise ZTMApiError("All stops failed in this refresh")
        return out


class AlertsCoordinator(_BaseCoordinator):
    """Combines bsk + displayMessages + znt, normalizes, dedupes, filters."""

    _max_backoff_seconds = BACKOFF_MAX_ALERTS

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZTMGdanskClient,
        scan_interval: timedelta,
        filter_lines: list[str],
        filter_stops: list[int],
        displays_map: dict[int, list[int]],
    ) -> None:
        super().__init__(hass, name=f"{DOMAIN}_alerts", scan_interval=scan_interval)
        self._client = client
        self._filter_lines: set[str] = {str(line) for line in filter_lines}
        self._filter_stops: set[int] = set(filter_stops)
        self._displays_map = displays_map

    async def _fetch(self) -> list[dict[str, Any]]:
        results = await asyncio.gather(
            self._client.get_bsk_alerts(),
            self._client.get_display_messages(),
            self._client.get_znt_alerts(),
            return_exceptions=True,
        )
        bsk_raw, disp_raw, znt_raw = results

        combined: list[dict[str, Any]] = []
        for raw, parser in (
            (bsk_raw, self._parse_bsk),
            (disp_raw, self._parse_display_messages),
            (znt_raw, self._parse_znt),
        ):
            if isinstance(raw, Exception):
                _LOGGER.debug("Alert source fetch failed: %s", raw)
                continue
            combined.extend(parser(raw))

        if not combined and all(isinstance(r, Exception) for r in results):
            raise ZTMApiError("All alert sources failed")

        deduped = self._dedupe(combined)
        return [a for a in deduped if self._matches_filter(a)]

    @staticmethod
    def _parse_bsk(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, dict):
            return []
        out: list[dict[str, Any]] = []
        for it in raw.get("results") or []:
            out.append({
                "title": it.get("title") or "",
                "body": it.get("summary") or _strip_html(it.get("content") or ""),
                "valid_from": it.get("publishFrom"),
                "valid_to": it.get("publishTo"),
                "lines": [str(x) for x in (it.get("lineNumbers") or [])],
                "stops": [],
                "source": "bsk",
            })
        return out

    def _parse_display_messages(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, dict):
            return []
        out: list[dict[str, Any]] = []
        for it in raw.get("displaysMsg") or []:
            display_name = it.get("displayName") or ""
            part1 = it.get("messagePart1") or ""
            part2 = it.get("messagePart2") or ""
            body = " ".join(p for p in (part1, part2) if p).strip()
            title = f"{display_name} — {part1}".strip(" —") if part1 else display_name
            display_code = it.get("displayCode")
            stops = (
                [s for s in self._displays_map.get(display_code, []) if s]
                if isinstance(display_code, int)
                else []
            )
            out.append({
                "title": title or "ZTM",
                "body": body,
                "valid_from": it.get("startDate"),
                "valid_to": it.get("endDate"),
                "lines": [],
                "stops": stops,
                "source": "display",
            })
        return out

    @staticmethod
    def _parse_znt(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, dict):
            return []
        out: list[dict[str, Any]] = []
        for it in raw.get("results") or []:
            if it.get("disableAlarm") is True:
                continue  # informational / marketing — not a disruption
            out.append({
                "title": it.get("title") or "",
                "body": it.get("summary") or _strip_html(it.get("content") or ""),
                "valid_from": it.get("publishFrom"),
                "valid_to": it.get("publishTo"),
                "lines": [str(x) for x in (it.get("lineNumbers") or [])],
                "stops": [],
                "source": "znt",
            })
        return out

    @staticmethod
    def _dedupe(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, Any]] = []
        for a in alerts:
            key = (a["title"], a["body"])
            if key in seen:
                continue
            seen.add(key)
            out.append(a)
        return out

    def _matches_filter(self, alert: dict[str, Any]) -> bool:
        if not self._filter_lines and not self._filter_stops:
            return True
        line_match = bool(self._filter_lines & set(alert["lines"]))
        stop_match = bool(self._filter_stops & set(alert["stops"]))
        return line_match or stop_match

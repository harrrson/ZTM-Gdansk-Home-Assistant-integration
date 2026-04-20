"""Departure sensor entity for ZTM Gdańsk."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry  # noqa: F401
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, POLISH_CHAR_MAP
from .coordinator import DepartureCoordinator

_LOGGER = logging.getLogger(__name__)


def slugify_pl(text: str) -> str:
    """Polish-aware slug for entity_id pieces (no external deps)."""
    text = text.translate(POLISH_CHAR_MAP).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class ZTMDepartureSensor(CoordinatorEntity[DepartureCoordinator], SensorEntity):
    """Sensor for next departure of a single line from a single stop."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DepartureCoordinator,
        *,
        stop_id: int,
        stop_name: str,
        line: str,
        next_count: int,
        stale_max_age: int,
    ) -> None:
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop_name = stop_name
        self._line = line
        self._next_count = next_count
        self._stale_max_age = stale_max_age
        self._attr_unique_id = f"{DOMAIN}_{stop_id}_{line}"
        self._attr_name = f"ZTM {stop_name} — linia {line}"
        # Suggested entity_id (HA may rename if collision):
        self.entity_id = f"sensor.ztm_{slugify_pl(stop_name)}_{slugify_pl(line)}"

    def _matching_departures(self) -> list[dict[str, Any]]:
        if not self.coordinator.data:
            return []
        stop_payload = self.coordinator.data.get(self._stop_id)
        if not stop_payload:
            return []
        deps = stop_payload.get("departures") or []
        # Real API field is routeShortName; exposed HA attribute stays "line"
        matching = [d for d in deps if str(d.get("routeShortName")) == self._line]
        matching.sort(key=lambda d: d.get("estimatedTime") or "")
        return matching

    @property
    def native_value(self) -> datetime | None:
        deps = self._matching_departures()
        if not deps:
            return None
        return _parse_iso(deps[0].get("estimatedTime"))

    @property
    def available(self) -> bool:
        if not self.coordinator.last_successful_update:
            return False
        age = (datetime.now(timezone.utc) - self.coordinator.last_successful_update).total_seconds()
        if age > self._stale_max_age:
            return False
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        deps = self._matching_departures()
        next_n = deps[: self._next_count]
        first = deps[0] if deps else {}
        last_update = self.coordinator.last_successful_update
        age_s = (
            int((datetime.now(timezone.utc) - last_update).total_seconds())
            if last_update else None
        )
        next_value = self.native_value
        minutes_until = (
            int((next_value - datetime.now(timezone.utc)).total_seconds() // 60)
            if next_value else None
        )
        delay_minutes = None
        if first:
            est = _parse_iso(first.get("estimatedTime"))
            theo = _parse_iso(first.get("theoreticalTime"))
            if est and theo:
                delay_minutes = int((est - theo).total_seconds() // 60)
        return {
            "line": self._line,
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "direction": first.get("headsign") if first else None,
            "minutes_until": minutes_until,
            "delay_minutes": delay_minutes,
            "theoretical_time": first.get("theoreticalTime") if first else None,
            "vehicle_id": first.get("vehicleId") if first else None,
            "next_departures": [
                {
                    "theoretical": d.get("theoreticalTime"),
                    "estimated": d.get("estimatedTime"),
                    "delay": d.get("delayInSeconds"),
                    "direction": d.get("headsign"),
                    "vehicle_id": d.get("vehicleId"),
                }
                for d in next_n
            ],
            "last_updated": last_update.isoformat() if last_update else None,
            "data_age_seconds": age_s,
        }


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up sensors from a discovery_info dict assembled in __init__.py."""
    if discovery_info is None:
        return
    coordinator: DepartureCoordinator = hass.data[DOMAIN]["departure_coordinator"]
    next_count: int = hass.data[DOMAIN]["next_departures_count"]
    stale_max_age: int = hass.data[DOMAIN]["stale_data_max_age"]
    entries: list[dict[str, Any]] = discovery_info["entries"]

    sensors: list[ZTMDepartureSensor] = []
    for entry in entries:
        for line in entry["lines"]:
            sensors.append(
                ZTMDepartureSensor(
                    coordinator,
                    stop_id=entry["stop_id"],
                    stop_name=entry["stop_name"],
                    line=line,
                    next_count=next_count,
                    stale_max_age=stale_max_age,
                )
            )
    add_entities(sensors)

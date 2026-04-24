"""Sensor entity for ZTM Gdańsk."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now

from .const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import ZtmGdanskCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZtmGdanskCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZtmGdanskSensor(coordinator, entry)])


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


class ZtmGdanskSensor(CoordinatorEntity[ZtmGdanskCoordinator], SensorEntity):
    """Minutes-to-next-departure sensor for one ZTM Gdańsk stop."""

    _attr_icon = "mdi:bus-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self, coordinator: ZtmGdanskCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._stop_id: int = entry.data[CONF_STOP_ID]
        self._stop_name: str = entry.data[CONF_STOP_NAME]
        self._stop_code: str = entry.data[CONF_STOP_CODE]
        self._entry = entry

        self._attr_unique_id = f"ztm_gdansk_{self._stop_id}"
        self._attr_name = f"ZTM Gdańsk {self._stop_name} {self._stop_code}"

    def _options(self) -> dict:
        return self._entry.options

    @property
    def native_value(self) -> int | None:
        departures = self.coordinator.data
        if not departures:
            return None
        estimated = departures[0].get("estimated_time")
        if estimated is None:
            return None
        now = ha_now()
        delta = estimated - now
        minutes = int(delta.total_seconds() / 60)
        return max(minutes, 0)

    @property
    def extra_state_attributes(self) -> dict:
        options = self._options()
        departures = self.coordinator.data or []
        serialized = [_serialize_departure(d) for d in departures]
        return {
            "stop_name": self._stop_name,
            "stop_id": self._stop_id,
            "stop_code": self._stop_code,
            "filtered_lines": options.get(CONF_LINES_FILTER, []),
            "departures": serialized,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._entry.async_on_unload(
            self._entry.add_update_listener(async_update_options)
        )


def _serialize_departure(d: dict) -> dict:
    """Convert datetime objects to ISO strings for HA state attributes."""
    return {
        "line": d.get("line"),
        "headsign": d.get("headsign"),
        "estimated_time": _isoformat(d.get("estimated_time")),
        "scheduled_time": _isoformat(d.get("scheduled_time")),
        "delay_minutes": d.get("delay_minutes"),
        "status": d.get("status"),
        "vehicle_id": d.get("vehicle_id"),
    }


def _isoformat(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()

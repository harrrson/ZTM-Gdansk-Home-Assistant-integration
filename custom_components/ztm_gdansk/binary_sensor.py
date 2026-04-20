"""Disruption binary_sensor for ZTM Gdańsk."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlertsCoordinator

_LOGGER = logging.getLogger(__name__)


class ZTMDisruptionBinarySensor(CoordinatorEntity[AlertsCoordinator], BinarySensorEntity):
    """Single binary_sensor: ON when there is at least one (filtered) ZTM alert."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_unique_id = f"{DOMAIN}_disruption"
    _attr_name = "ZTM zakłócenia"
    _attr_should_poll = False

    def __init__(self, coordinator: AlertsCoordinator, *, stale_max_age: int) -> None:
        super().__init__(coordinator)
        self._stale_max_age = stale_max_age
        self.entity_id = "binary_sensor.ztm_disruption"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_successful_update:
            return False
        age = (datetime.now(timezone.utc) - self.coordinator.last_successful_update).total_seconds()
        return age <= self._stale_max_age

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self.coordinator.last_successful_update
        age = (
            int((datetime.now(timezone.utc) - last).total_seconds()) if last else None
        )
        alerts = list(self.coordinator.data or [])
        return {
            "count": len(alerts),
            "alerts": alerts,
            "last_updated": last.isoformat() if last else None,
            "data_age_seconds": age,
        }


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if discovery_info is None:
        return
    coordinator = hass.data[DOMAIN].get("alerts_coordinator")
    if coordinator is None:
        return
    stale = hass.data[DOMAIN]["alerts_stale_max_age"]
    add_entities([ZTMDisruptionBinarySensor(coordinator, stale_max_age=stale)])

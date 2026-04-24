"""ZTM Gdańsk integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZtmGdanskApiClient
from .const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import ZtmGdanskCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = ZtmGdanskApiClient(session)

    options = entry.options
    coordinator = ZtmGdanskCoordinator(
        hass=hass,
        api_client=api,
        stop_id=entry.data[CONF_STOP_ID],
        lines_filter=options.get(CONF_LINES_FILTER, []),
        departure_count=options.get(CONF_DEPARTURE_COUNT, DEFAULT_DEPARTURE_COUNT),
        update_interval=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded

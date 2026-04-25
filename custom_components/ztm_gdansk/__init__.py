"""ZTM Gdańsk integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
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

_WWW_DIR = Path(__file__).parent / "www"
_CARD_URL = f"/{DOMAIN}/ztm-gdansk-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if hass.http is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, str(_WWW_DIR / "ztm-gdansk-card.js"), cache_headers=False)]
        )
    add_extra_js_url(hass, _CARD_URL)
    return True


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
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded

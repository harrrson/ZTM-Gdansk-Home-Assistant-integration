"""Config Flow for ZTM Gdańsk."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import ZtmGdanskApiClient, ZtmGdanskApiError
from .const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ZtmGdanskConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow — stop selection, line filter, options."""

    VERSION = 1

    def __init__(self) -> None:
        self._stop_id: int | None = None
        self._stop_name: str | None = None
        self._stop_code: str | None = None
        self._lines_filter: list[str] = []
        self._stops: list[dict] | None = None
        self._available_lines: list[str] = []

    def _api(self) -> ZtmGdanskApiClient:
        return ZtmGdanskApiClient(async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if self._stops is None:
            try:
                self._stops = await self._api().get_stops()
            except ZtmGdanskApiError:
                errors["base"] = "cannot_connect"
                self._stops = []

        if user_input is not None and not errors:
            try:
                stop_id = int(user_input[CONF_STOP_ID])
            except (ValueError, TypeError):
                errors[CONF_STOP_ID] = "invalid_stop"
                stop_id = None
            if stop_id is not None:
                stop = next(
                    (s for s in self._stops if s["stopId"] == stop_id), None
                )
                if stop is None:
                    errors[CONF_STOP_ID] = "invalid_stop"
                else:
                    await self.async_set_unique_id(str(stop_id))
                    self._abort_if_unique_id_configured()
                    self._stop_id = stop_id
                    self._stop_name = stop["stopName"]
                    self._stop_code = stop.get("stopCode", "")
                    return await self.async_step_lines()

        options = [
            SelectOptionDict(
                value=str(s["stopId"]),
                label=f"{s['stopName']} ({s.get('stopCode', '')}) — {s.get('stopDesc', '')}",
            )
            for s in self._stops
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if not self._available_lines:
            try:
                self._available_lines = await self._api().get_routes_for_stop(
                    self._stop_id
                )
            except ZtmGdanskApiError:
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            self._lines_filter = user_input.get(CONF_LINES_FILTER, [])
            return await self.async_step_options()

        line_options = [
            SelectOptionDict(value=line, label=line)
            for line in self._available_lines
        ]
        schema = vol.Schema(
            {
                vol.Optional(CONF_LINES_FILTER, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=line_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="lines", data_schema=schema, errors=errors
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._stop_name} ({self._stop_code})",
                data={
                    CONF_STOP_ID: self._stop_id,
                    CONF_STOP_NAME: self._stop_name,
                    CONF_STOP_CODE: self._stop_code,
                },
                options={
                    CONF_LINES_FILTER: self._lines_filter,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_DEPARTURE_COUNT: int(user_input[CONF_DEPARTURE_COUNT]),
                },
            )

        schema = _options_schema(DEFAULT_SCAN_INTERVAL, DEFAULT_DEPARTURE_COUNT)
        return self.async_show_form(step_id="options", data_schema=schema)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ZtmGdanskOptionsFlow:
        return ZtmGdanskOptionsFlow()


class ZtmGdanskOptionsFlow(config_entries.OptionsFlow):
    """Options Flow — change line filter and polling options."""

    def __init__(self) -> None:
        self._available_lines: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if not self._available_lines:
            api = ZtmGdanskApiClient(async_get_clientsession(self.hass))
            try:
                self._available_lines = await api.get_routes_for_stop(
                    self.config_entry.data[CONF_STOP_ID]
                )
            except ZtmGdanskApiError:
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            return self.async_create_entry(
                data={
                    CONF_LINES_FILTER: user_input.get(CONF_LINES_FILTER, []),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_DEPARTURE_COUNT: int(user_input[CONF_DEPARTURE_COUNT]),
                }
            )

        current = self.config_entry.options
        line_options = [
            SelectOptionDict(value=line, label=line)
            for line in self._available_lines
        ]
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LINES_FILTER,
                    default=current.get(CONF_LINES_FILTER, []),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=line_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                **_options_schema(
                    current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    current.get(CONF_DEPARTURE_COUNT, DEFAULT_DEPARTURE_COUNT),
                ).schema,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )


def _options_schema(scan_interval: int, departure_count: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=3600,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_DEPARTURE_COUNT, default=departure_count
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=50,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )

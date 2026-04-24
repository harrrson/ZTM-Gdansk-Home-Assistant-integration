"""
Tests for config_flow.py — black-box against spec requirements.

Spec requirements covered:
- Three-step flow: user → lines → options → creates config entry
- Entry data contains stop_id, stop_name, stop_code (immutable)
- Entry options contains lines_filter, scan_interval, departure_count (editable)
- Duplicate stop_id aborts the flow
- API error during stop list fetch → form re-shown with error
- OptionsFlow updates options (without re-adding the integration)
- Entry title = "{stop_name} ({stop_code})"
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import InvalidData

from custom_components.ztm_gdansk.const import (
    CONF_DEPARTURE_COUNT,
    CONF_LINES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

from .conftest import STOP_CODE, STOP_ID, STOP_NAME, STOPS_RESPONSE


MOCK_STOPS = STOPS_RESPONSE["2026-04-24"]["stops"]
MOCK_LINES = ["106", "130"]


def _patch_api(stops=None, lines=None, error=False):
    """Patches ZtmGdanskApiClient AND async_get_clientsession in config_flow.

    Mocking the session prevents aiohttp from creating a real TCPConnector and
    the _run_safe_shutdown_loop daemon thread that the HA test cleanup rejects.
    """
    from custom_components.ztm_gdansk.api import ZtmGdanskApiError

    mock_client = MagicMock()
    if error:
        mock_client.get_stops = AsyncMock(side_effect=ZtmGdanskApiError("API down"))
    else:
        mock_client.get_stops = AsyncMock(return_value=stops or MOCK_STOPS)
        mock_client.get_routes_for_stop = AsyncMock(return_value=lines or MOCK_LINES)

    mock_cls = MagicMock(return_value=mock_client)

    return patch.multiple(
        "custom_components.ztm_gdansk.config_flow",
        ZtmGdanskApiClient=mock_cls,
        async_get_clientsession=MagicMock(return_value=MagicMock()),
    )


def _patch_setup():
    """Skip integration setup so config flow tests don't trigger real API calls."""
    return patch(
        "custom_components.ztm_gdansk.async_setup_entry", return_value=True
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_full_flow(hass, lines_filter=None, scan_interval=60, departure_count=5):
    """Drive through all three steps and return the final result."""
    with _patch_api(), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: str(STOP_ID)}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "lines"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LINES_FILTER: lines_filter or []},
        )
        assert result["type"] == "form"
        assert result["step_id"] == "options"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_DEPARTURE_COUNT: departure_count,
            },
        )
    return result


# ---------------------------------------------------------------------------
# Full flow — entry structure
# ---------------------------------------------------------------------------


class TestConfigFlowEntryStructure:
    async def test_successful_flow_creates_entry(self, hass):
        """Spec: successful flow → type == create_entry."""
        result = await _run_full_flow(hass)
        assert result["type"] == "create_entry"

    async def test_entry_data_contains_stop_identifiers(self, hass):
        """Spec: data (immutable) must have stop_id, stop_name, stop_code."""
        result = await _run_full_flow(hass)
        data = result["data"]
        assert data[CONF_STOP_ID] == STOP_ID
        assert data[CONF_STOP_NAME] == STOP_NAME
        assert data[CONF_STOP_CODE] == STOP_CODE

    async def test_entry_options_contain_editable_settings(self, hass):
        """Spec: options (editable) must have lines_filter, scan_interval, departure_count."""
        result = await _run_full_flow(
            hass, lines_filter=["130"], scan_interval=120, departure_count=3
        )
        opts = result["options"]
        assert opts[CONF_LINES_FILTER] == ["130"]
        assert opts[CONF_SCAN_INTERVAL] == 120
        assert opts[CONF_DEPARTURE_COUNT] == 3

    async def test_entry_title_format(self, hass):
        """Spec: entry title = '{stop_name} ({stop_code})'."""
        result = await _run_full_flow(hass)
        assert result["title"] == f"{STOP_NAME} ({STOP_CODE})"

    async def test_empty_lines_filter_allowed(self, hass):
        """Spec: empty lines_filter = show all lines — must be accepted."""
        result = await _run_full_flow(hass, lines_filter=[])
        assert result["type"] == "create_entry"
        assert result["options"][CONF_LINES_FILTER] == []


# ---------------------------------------------------------------------------
# Duplicate stop prevention
# ---------------------------------------------------------------------------


class TestDuplicatePrevention:
    async def test_duplicate_stop_id_aborts_flow(self, hass):
        """Spec: same stop_id cannot be added twice."""
        await _run_full_flow(hass)

        with _patch_api(), _patch_setup():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_STOP_ID: str(STOP_ID)}
            )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestConfigFlowErrors:
    async def test_api_error_on_stop_fetch_shows_form_with_error(self, hass):
        """Spec: if stop list fetch fails, form is re-shown with cannot_connect error."""
        with _patch_api(error=True):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "base" in result.get("errors", {})

    async def test_scan_interval_below_minimum_rejected(self, hass):
        """Spec: scan_interval must be >= MIN_SCAN_INTERVAL (20s).
        HA framework validates the NumberSelector schema before calling the step handler —
        values below MIN_SCAN_INTERVAL raise InvalidData and are never accepted."""
        with _patch_api(), _patch_setup():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_STOP_ID: str(STOP_ID)}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_LINES_FILTER: []}
            )
            with pytest.raises(InvalidData):
                await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={
                        CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL - 1,
                        CONF_DEPARTURE_COUNT: 5,
                    },
                )


# ---------------------------------------------------------------------------
# Options Flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    async def test_options_flow_updates_options(self, hass):
        """Spec: OptionsFlow allows updating lines_filter and poll settings
        without re-adding the integration."""
        await _run_full_flow(hass)
        entry = hass.config_entries.async_entries(DOMAIN)[0]

        with _patch_api(), _patch_setup():
            result = await hass.config_entries.options.async_init(entry.entry_id)
            assert result["type"] == "form"

            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    CONF_LINES_FILTER: ["130"],
                    CONF_SCAN_INTERVAL: 30,
                    CONF_DEPARTURE_COUNT: 3,
                },
            )

        assert result["type"] == "create_entry"
        assert entry.options[CONF_LINES_FILTER] == ["130"]
        assert entry.options[CONF_SCAN_INTERVAL] == 30
        assert entry.options[CONF_DEPARTURE_COUNT] == 3

    async def test_options_flow_preserves_entry_data(self, hass):
        """Spec: changing options must not alter the immutable data (stop identity)."""
        await _run_full_flow(hass)
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        original_data = dict(entry.data)

        with _patch_api(), _patch_setup():
            result = await hass.config_entries.options.async_init(entry.entry_id)
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    CONF_LINES_FILTER: [],
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_DEPARTURE_COUNT: DEFAULT_DEPARTURE_COUNT,
                },
            )

        assert dict(entry.data) == original_data

"""Pytest fixtures for ZTM Gdańsk integration tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture by filename (without extension)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def fixture_loader():
    """Provide the load_fixture helper as a fixture."""
    return load_fixture


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom_components/* in every test."""
    yield

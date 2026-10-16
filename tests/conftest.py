"""Gemeinsame Fixtures für die Hausarbeit-Tracker-Tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hausarbeit.const import (
    CONF_STATS_DAYS,
    CONF_WEEK_START,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Lädt die Custom-Integration in allen Tests."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Ein Config-Entry für den Haushalt (Standard-Optionen)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hausarbeit",
        options={CONF_WEEK_START: 0, CONF_STATS_DAYS: 90},
    )


@pytest.fixture
async def setup_integration(hass, config_entry):
    """Richtet die Integration ein und liefert (entry, coordinator)."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    return config_entry, coordinator

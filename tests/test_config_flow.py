"""Config- und Options-Flow."""

from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hausarbeit.const import (
    CONF_STATS_DAYS,
    CONF_WEEK_START,
    DOMAIN,
    F_COUNT,
    F_NAME,
    F_PERIOD,
    F_PERSON_ID,
    F_TASK_ID,
    PERIOD_WEEK,
)


# --------------------------------------------------------------------------- #
# Config-Flow
# --------------------------------------------------------------------------- #
async def test_config_flow_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"title": "Zuhause"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_WEEK_START] == 0
    assert result["options"][CONF_STATS_DAYS] == 90


async def test_config_flow_single_instance(hass):
    existing = MockConfigEntry(domain=DOMAIN, options={})
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# --------------------------------------------------------------------------- #
# Options-Flow
# --------------------------------------------------------------------------- #
async def _menu(hass, flow_id, next_step):
    return await hass.config_entries.options.async_configure(flow_id, {"next_step_id": next_step})


async def test_options_settings(setup_integration, hass):
    entry, _coord = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    result = await _menu(hass, result["flow_id"], "settings")
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WEEK_START: 6, CONF_STATS_DAYS: 30}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_WEEK_START] == 6
    assert entry.options[CONF_STATS_DAYS] == 30


async def test_options_person_add(setup_integration, hass):
    entry, coordinator = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _menu(hass, result["flow_id"], "persons")
    assert result["type"] == FlowResultType.MENU
    result = await _menu(hass, result["flow_id"], "person_add")
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {F_NAME: "Hans"})
    # kehrt ins Personen-Menü zurück
    assert result["type"] == FlowResultType.MENU
    names = [p[F_NAME] for p in coordinator.store.persons]
    assert "Hans" in names


async def test_options_task_add(setup_integration, hass):
    entry, coordinator = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _menu(hass, result["flow_id"], "tasks")
    result = await _menu(hass, result["flow_id"], "task_add")
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {F_NAME: "Rasenmähen", "points": 2}
    )
    assert result["type"] == FlowResultType.MENU
    names = [t[F_NAME] for t in coordinator.store.tasks]
    assert "Rasenmähen" in names


async def test_options_target_add_and_upsert(setup_integration, hass):
    entry, coordinator = setup_integration
    p = coordinator.add_person("Ida")
    t = coordinator.add_task("Kehren")

    async def _add_target(count):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await _menu(hass, result["flow_id"], "targets")
        result = await _menu(hass, result["flow_id"], "target_add")
        assert result["type"] == FlowResultType.FORM
        return await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                F_PERSON_ID: p["id"],
                F_TASK_ID: t["id"],
                F_PERIOD: PERIOD_WEEK,
                F_COUNT: count,
            },
        )

    result = await _add_target(2)
    assert result["type"] == FlowResultType.MENU
    assert len(coordinator.store.targets) == 1
    assert coordinator.store.targets[0][F_COUNT] == 2

    # gleiche (Person, Aufgabe, Periode) -> Upsert, kein neuer Eintrag
    await _add_target(7)
    assert len(coordinator.store.targets) == 1
    assert coordinator.store.targets[0][F_COUNT] == 7


async def test_options_target_add_aborts_without_person_and_task(setup_integration, hass):
    entry, _coord = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _menu(hass, result["flow_id"], "targets")
    result = await _menu(hass, result["flow_id"], "target_add")
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "need_person_and_task"


async def test_options_person_remove(setup_integration, hass):
    entry, coordinator = setup_integration
    p = coordinator.add_person("Klaus")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _menu(hass, result["flow_id"], "persons")
    result = await _menu(hass, result["flow_id"], "person_remove")
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"person": p["id"]}
    )
    assert result["type"] == FlowResultType.MENU
    assert coordinator.store.get_person(p["id"]) is None

"""Entity-Namen/IDs, zeitgesteuerte Aktualisierung und Aufräumen der Entity-Registry."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hausarbeit.const import DOMAIN, PERIOD_DAY, PERIOD_WEEK


@pytest.fixture
async def berlin(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")


def _local(*args) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


async def test_entity_ids_names_and_units(setup_integration, hass):
    """Entity-IDs bleiben im bisherigen Schema; Namen/Einheiten kommen aus Übersetzungen."""
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülmaschine")
    coordinator.set_target(p["id"], t["id"], PERIOD_WEEK, 3)
    await hass.async_block_till_done()

    person = hass.states.get("sensor.hausarbeit_anna")
    assert person is not None
    assert person.attributes["friendly_name"] == "Hausarbeit Anna"
    assert person.attributes["unit_of_measurement"] == "tasks"
    assert person.attributes["person_id"] == p["id"]

    target = hass.states.get("sensor.hausarbeit_anna_spulmaschine_week")
    assert target is not None
    assert target.attributes["friendly_name"] == "Hausarbeit Anna · Spülmaschine (week)"
    assert target.attributes["unit_of_measurement"] == "tasks"

    last = hass.states.get("sensor.hausarbeit_spulmaschine_last_done")
    assert last is not None
    assert last.attributes["task_id"] == t["id"]


async def test_rename_person_updates_friendly_name(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    await hass.async_block_till_done()
    coordinator.update_person(p["id"], name="Annika")
    await hass.async_block_till_done()
    # entity_id bleibt, Anzeigename folgt dem neuen Namen
    assert hass.states.get("sensor.hausarbeit_anna").attributes["friendly_name"] == (
        "Hausarbeit Annika"
    )


async def test_midnight_tick_rolls_today_and_day_target(
    hass, berlin, config_entry, freezer: FrozenDateTimeFactory
):
    """Ohne Datenänderung müssen „heute“ und die Tages-Periode um Mitternacht kippen."""
    freezer.move_to(_local(2026, 10, 14, 22, 30))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data

    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Müll")
    tgt = coordinator.set_target(p["id"], t["id"], PERIOD_DAY, 1)
    coordinator.log_execution(p["id"], t["id"])
    await hass.async_block_till_done()

    person = hass.states.get("sensor.hausarbeit_anna")
    assert person.attributes["today"] == 1
    target_id = next(
        s.entity_id
        for s in hass.states.async_all("sensor")
        if s.attributes.get("target_id") == tgt["id"]
    )
    assert hass.states.get(target_id).state == "1"

    # über lokale Mitternacht
    freezer.move_to(_local(2026, 10, 15, 0, 0, 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    person = hass.states.get("sensor.hausarbeit_anna")
    assert person.attributes["today"] == 0
    assert person.attributes["d7"] == 1
    target = hass.states.get(target_id)
    assert target.state == "0"
    assert target.attributes["rest"] == 1
    assert target.attributes["periodenstart"].startswith("2026-10-15T00:00:00")


async def test_hourly_tick_rolls_sliding_window(hass, config_entry, freezer: FrozenDateTimeFactory):
    """Gleitende Fenster (7 Tage) werden spätestens zur vollen Stunde nachgeführt."""
    freezer.move_to(dt_util.parse_datetime("2026-10-01T10:20:00+00:00"))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    p = coordinator.add_person("Ben")
    t = coordinator.add_task("Bad")
    coordinator.log_execution(p["id"], t["id"])
    await hass.async_block_till_done()
    assert hass.states.get("sensor.hausarbeit_ben").attributes["d7"] == 1

    freezer.move_to(dt_util.parse_datetime("2026-10-08T11:00:01+00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.hausarbeit_ben")
    assert state.attributes["d7"] == 0
    assert state.attributes["d30"] == 1


async def test_timer_stops_after_unload(hass, config_entry, freezer: FrozenDateTimeFactory):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)  # darf nicht crashen / keine Listener mehr
    await hass.async_block_till_done()


@pytest.mark.parametrize("kind", ["person", "task", "target"])
async def test_removed_items_leave_no_registry_orphans(setup_integration, hass, kind):
    entry, coordinator = setup_integration
    ent_reg = er.async_get(hass)
    p = coordinator.add_person("Carla")
    t = coordinator.add_task("Fenster")
    tgt = coordinator.set_target(p["id"], t["id"], PERIOD_WEEK, 2)
    await hass.async_block_till_done()
    assert len(er.async_entries_for_config_entry(ent_reg, entry.entry_id)) == 3

    if kind == "person":
        coordinator.remove_person(p["id"])  # entfernt auch die Vorgabe
        gone = {f"{entry.entry_id}_person_{p['id']}", f"{entry.entry_id}_target_{tgt['id']}"}
    elif kind == "task":
        coordinator.remove_task(t["id"])
        gone = {f"{entry.entry_id}_lastdone_{t['id']}", f"{entry.entry_id}_target_{tgt['id']}"}
    else:
        coordinator.remove_target(tgt["id"])
        gone = {f"{entry.entry_id}_target_{tgt['id']}"}
    await hass.async_block_till_done()

    remaining = {e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)}
    assert not remaining & gone
    assert len(remaining) == 3 - len(gone)
    for uid in gone:
        assert ent_reg.async_get_entity_id("sensor", DOMAIN, uid) is None


async def test_legacy_orphans_removed_on_setup(hass, config_entry):
    """Waisen aus älteren Versionen werden beim Start aus der Registry entfernt."""
    config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    orphan = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_person_per_deadbeef",
        config_entry=config_entry,
        suggested_object_id="hausarbeit_ghost",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert ent_reg.async_get(orphan.entity_id) is None


async def test_existing_entity_ids_kept_after_upgrade(hass, config_entry, hass_storage):
    """Registry-Einträge aus 0.1.x (deutsche Namen) behalten ihre entity_id."""
    hass_storage["hausarbeit_data"] = {
        "version": 1,
        "minor_version": 1,
        "key": "hausarbeit_data",
        "data": {
            "persons": [{"id": "per_00000001", "name": "Anna"}],
            "tasks": [{"id": "tsk_00000001", "name": "Spülmaschine", "points": 1}],
            "targets": [],
            "executions": [],
        },
    }
    config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_lastdone_tsk_00000001",
        config_entry=config_entry,
        suggested_object_id="hausarbeit_spulmaschine_zuletzt_erledigt",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert old.entity_id == "sensor.hausarbeit_spulmaschine_zuletzt_erledigt"
    assert hass.states.get(old.entity_id) is not None

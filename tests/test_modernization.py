"""Neuerungen 0.2.0: Admin-Services, übersetzte Fehler, Store-Migration,
Entfernen des Entries, Diagnose, Options-Flow-Selektoren."""

from __future__ import annotations

from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.setup import async_setup_component
import pytest

from custom_components.hausarbeit.const import DOMAIN, STORAGE_KEY
from custom_components.hausarbeit.diagnostics import async_get_config_entry_diagnostics
from custom_components.hausarbeit.validation import is_valid_color

ADMIN_SERVICES = [
    ("remove_person", {"person_id": "per_x"}),
    ("remove_task", {"task_id": "tsk_x"}),
    ("remove_target", {"target_id": "tgt_x"}),
    ("delete_execution", {"execution_id": "exe_x"}),
    ("correct_execution", {"execution_id": "exe_x"}),
    ("add_person", {"name": "X"}),
    ("update_person", {"person_id": "per_x"}),
    ("add_task", {"name": "X"}),
    ("update_task", {"task_id": "tsk_x"}),
    ("set_target", {"person_id": "per_x", "task_id": "tsk_x", "period": "week", "count": 1}),
]


@pytest.mark.parametrize(("service", "data"), ADMIN_SERVICES)
async def test_config_services_require_admin(
    setup_integration, hass, hass_read_only_user, service, data
):
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=Context(user_id=hass_read_only_user.id)
        )


async def test_log_execution_allowed_for_non_admin(setup_integration, hass, hass_read_only_user):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Kind")
    t = coordinator.add_task("Zimmer")
    await hass.services.async_call(
        DOMAIN,
        "log_execution",
        {"person_id": p["id"], "task_id": t["id"]},
        blocking=True,
        context=Context(user_id=hass_read_only_user.id),
    )
    assert len(coordinator.store.executions) == 1


async def test_service_errors_are_translated(setup_integration, hass):
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN, "remove_person", {"person_id": "per_missing"}, blocking=True
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "person_not_found"
    assert exc.value.translation_placeholders == {"id": "per_missing"}


async def test_services_registered_without_entry(hass):
    """Services existieren ab async_setup und melden „nicht geladen“ statt zu fehlen."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "log_execution")
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN, "log_execution", {"person_id": "a", "task_id": "b"}, blocking=True
        )
    assert exc.value.translation_key == "not_loaded"


async def test_services_survive_unload_and_report_not_loaded(setup_integration, hass):
    entry, _coordinator = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "add_person")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_person", {"name": "X"}, blocking=True)


async def test_service_naive_datetime_is_local_time(setup_integration, hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    res = await hass.services.async_call(
        DOMAIN,
        "log_execution",
        {"person_id": p["id"], "task_id": t["id"], "ts": "2026-01-15 08:00:00"},
        blocking=True,
        return_response=True,
    )
    ex = coordinator.store.get_execution(res["execution_id"])
    assert ex["ts"] == "2026-01-15T07:00:00+00:00"  # Winterzeit UTC+1


async def test_store_migration_1_1_normalizes_timestamps(hass, config_entry, hass_storage):
    """Daten aus 0.1.x bleiben vollständig erhalten; Offsets werden zu UTC."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "persons": [{"id": "per_1", "name": "Anna", "color": "#ff0000"}],
            "tasks": [{"id": "tsk_1", "name": "Spülen", "points": 2}],
            "targets": [
                {
                    "id": "tgt_1",
                    "person_id": "per_1",
                    "task_id": "tsk_1",
                    "period": "week",
                    "count": 3,
                }
            ],
            "executions": [
                {
                    "id": "exe_1",
                    "person_id": "per_1",
                    "task_id": "tsk_1",
                    "ts": "2026-10-01T12:30:00+02:00",
                    "note": "x",
                },
                {
                    "id": "exe_2",
                    "person_id": "per_1",
                    "task_id": "tsk_1",
                    "ts": "kaputt",
                    "note": "",
                },
            ],
            "unknown_future_key": {"keep": "ignored"},
        },
    }
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    store = config_entry.runtime_data.store
    assert store.get_person("per_1")["color"] == "#ff0000"
    assert store.get_task("tsk_1")["points"] == 2
    assert store.get_target("tgt_1")["count"] == 3
    assert store.get_execution("exe_1")["ts"] == "2026-10-01T10:30:00+00:00"
    assert store.get_execution("exe_1")["note"] == "x"
    assert store.get_execution("exe_2")["ts"] == "kaputt"  # unangetastet


async def test_remove_entry_deletes_store(hass, config_entry, hass_storage):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    coordinator.add_person("Anna")
    await coordinator.store.async_save_now()
    assert STORAGE_KEY in hass_storage

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY not in hass_storage


async def test_single_config_entry_abort(hass, config_entry):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_diagnostics_redacts_personal_data(setup_integration, hass):
    entry, coordinator = setup_integration
    p = coordinator.add_person("Anna", color="#123456", ha_person_entity="person.anna")
    t = coordinator.add_task("Spülen")
    coordinator.log_execution(p["id"], t["id"], note="geheim")
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "Anna" not in text
    assert "person.anna" not in text
    assert "geheim" not in text
    assert diag["executions"]["count"] == 1
    assert diag["persons"][0]["linked_to_ha_person"] is True
    assert diag["entry"]["options"]["stats_days"] == 90


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("#3f51b5", True),
        ("#fff", True),
        ("teal", True),
        ("rgb(63, 81, 181)", True),
        ("var(--accent-color)", True),
        ("red; background:url(x)", False),
        ("#zzzzzz", False),
        ("", False),
    ],
)
def test_color_validation(value, valid):
    assert is_valid_color(value) is valid


async def _open_person_edit(hass, entry, person_id):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "persons"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "person_edit"}
    )
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"person": person_id}
    )


async def test_options_person_edit_clears_optional_fields(setup_integration, hass):
    entry, coordinator = setup_integration
    p = coordinator.add_person(
        "Anna", icon="mdi:face", color="#ff0000", ha_person_entity="person.anna"
    )
    result = await _open_person_edit(hass, entry, p["id"])
    assert result["step_id"] == "person_edit_form"
    # Nur der Name wird gesendet -> optionale Felder werden geleert
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": "Anna"})
    assert result["type"] == FlowResultType.MENU
    person = coordinator.store.get_person(p["id"])
    assert person["color"] is None
    assert person["ha_person_entity"] is None
    assert person["icon"] is None


async def test_options_person_invalid_color(setup_integration, hass):
    entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    result = await _open_person_edit(hass, entry, p["id"])
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Anna", "color": "red;}"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"color": "invalid_color"}
    assert coordinator.store.get_person(p["id"])["color"] is None


async def test_options_settings_week_start_stored_as_int(setup_integration, hass):
    entry, _coordinator = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    schema_keys = {str(k): k for k in result["data_schema"].schema}
    assert schema_keys["week_start"].default() == "0"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"week_start": "6", "stats_days": 14}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["week_start"] == 6
    assert entry.options["stats_days"] == 14


def test_translations_complete():
    """Alle Sprachdateien haben exakt die Schlüssel von strings.json."""
    import json
    from pathlib import Path

    base = Path(__file__).parent.parent / "custom_components" / DOMAIN

    def keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            out |= keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {f"{prefix}{k}"}
        return out

    reference = keys(json.loads((base / "strings.json").read_text(encoding="utf-8")))
    for file in (base / "translations").glob("*.json"):
        assert keys(json.loads(file.read_text(encoding="utf-8"))) == reference, file.name

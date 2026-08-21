"""Setup, Service-Registrierung und Service-Aufrufe end-to-end."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
import voluptuous as vol

from custom_components.hausarbeit.const import (
    ATTR_EXECUTION_ID,
    ATTR_TARGET_ID,
    DOMAIN,
    F_COUNT,
    F_ID,
    F_NAME,
    F_PERIOD,
    F_PERSON_ID,
    F_TASK_ID,
    F_TIMESTAMP,
    PERIOD_WEEK,
)
from custom_components.hausarbeit.coordinator import (
    HausarbeitCoordinator,
    HausarbeitError,
)

ALL_SERVICES = [
    "log_execution",
    "delete_execution",
    "correct_execution",
    "add_task",
    "update_task",
    "remove_task",
    "add_person",
    "update_person",
    "remove_person",
    "set_target",
    "remove_target",
]


async def test_setup_creates_coordinator(setup_integration, hass):
    entry, coordinator = setup_integration
    assert isinstance(coordinator, HausarbeitCoordinator)
    assert hass.data[DOMAIN][entry.entry_id] is coordinator


async def test_all_services_registered(setup_integration, hass):
    for service in ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, service), service


async def test_add_person_and_task_return_ids(setup_integration, hass):
    p = await hass.services.async_call(
        DOMAIN, "add_person", {F_NAME: "Alice"}, blocking=True, return_response=True
    )
    assert p[F_ID].startswith("per_")
    t = await hass.services.async_call(
        DOMAIN, "add_task", {F_NAME: "Spülen"}, blocking=True, return_response=True
    )
    assert t[F_ID].startswith("tsk_")

    _entry, coordinator = setup_integration
    assert coordinator.store.get_person(p[F_ID]) is not None
    assert coordinator.store.get_task(t[F_ID]) is not None


async def test_log_execution_service_creates_execution(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Bob")
    t = coordinator.add_task("Müll")
    res = await hass.services.async_call(
        DOMAIN,
        "log_execution",
        {F_PERSON_ID: p[F_ID], F_TASK_ID: t[F_ID]},
        blocking=True,
        return_response=True,
    )
    assert ATTR_EXECUTION_ID in res
    assert res[ATTR_EXECUTION_ID].startswith("exe_")
    assert len(coordinator.store.executions) == 1


async def test_set_target_delete_and_correct_flow(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Carla")
    t = coordinator.add_task("Wischen")

    tgt = await hass.services.async_call(
        DOMAIN,
        "set_target",
        {F_PERSON_ID: p[F_ID], F_TASK_ID: t[F_ID], F_PERIOD: PERIOD_WEEK, F_COUNT: 3},
        blocking=True,
        return_response=True,
    )
    assert tgt[ATTR_TARGET_ID].startswith("tgt_")
    assert len(coordinator.store.targets) == 1

    ex = coordinator.log_execution(p[F_ID], t[F_ID])
    # correct: Notiz ändern
    await hass.services.async_call(
        DOMAIN,
        "correct_execution",
        {ATTR_EXECUTION_ID: ex[F_ID], "note": "korrigiert"},
        blocking=True,
    )
    assert coordinator.store.get_execution(ex[F_ID])["note"] == "korrigiert"
    # delete
    await hass.services.async_call(
        DOMAIN, "delete_execution", {ATTR_EXECUTION_ID: ex[F_ID]}, blocking=True
    )
    assert len(coordinator.store.executions) == 0

    # remove target / task / person
    await hass.services.async_call(
        DOMAIN, "remove_target", {ATTR_TARGET_ID: tgt[ATTR_TARGET_ID]}, blocking=True
    )
    assert len(coordinator.store.targets) == 0
    await hass.services.async_call(DOMAIN, "remove_task", {F_TASK_ID: t[F_ID]}, blocking=True)
    assert coordinator.store.get_task(t[F_ID]) is None
    await hass.services.async_call(DOMAIN, "remove_person", {F_PERSON_ID: p[F_ID]}, blocking=True)
    assert coordinator.store.get_person(p[F_ID]) is None


async def test_log_execution_unknown_person_raises(setup_integration, hass):
    _entry, coordinator = setup_integration
    t = coordinator.add_task("Kochen")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "log_execution",
            {F_PERSON_ID: "per_unknown", F_TASK_ID: t[F_ID]},
            blocking=True,
            return_response=True,
        )


async def test_log_execution_unknown_task_raises(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Dora")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "log_execution",
            {F_PERSON_ID: p[F_ID], F_TASK_ID: "tsk_unknown"},
            blocking=True,
            return_response=True,
        )


async def test_set_target_count_zero_raises(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Emil")
    t = coordinator.add_task("Staubsaugen")
    # Schema (Range min=1) ODER Coordinator lehnt count<=0 ab.
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call(
            DOMAIN,
            "set_target",
            {F_PERSON_ID: p[F_ID], F_TASK_ID: t[F_ID], F_PERIOD: PERIOD_WEEK, F_COUNT: 0},
            blocking=True,
            return_response=True,
        )
    # direkt am Coordinator ist es ein HausarbeitError
    with pytest.raises(HausarbeitError):
        coordinator.set_target(p[F_ID], t[F_ID], PERIOD_WEEK, 0)


async def test_set_target_upsert(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Frida")
    t = coordinator.add_task("Bad putzen")
    a = coordinator.set_target(p[F_ID], t[F_ID], PERIOD_WEEK, 2)
    b = coordinator.set_target(p[F_ID], t[F_ID], PERIOD_WEEK, 5)
    # gleicher Eintrag, nur count geändert
    assert len(coordinator.store.targets) == 1
    assert a[F_ID] == b[F_ID]
    assert coordinator.store.get_target(a[F_ID])[F_COUNT] == 5


async def test_log_execution_with_past_ts_via_service(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Gustav")
    t = coordinator.add_task("Fenster")
    past = dt_util.utcnow() - timedelta(days=10)
    res = await hass.services.async_call(
        DOMAIN,
        "log_execution",
        {F_PERSON_ID: p[F_ID], F_TASK_ID: t[F_ID], F_TIMESTAMP: past},
        blocking=True,
        return_response=True,
    )
    ex = coordinator.store.get_execution(res[ATTR_EXECUTION_ID])
    assert ex is not None
    assert ex[F_TIMESTAMP].startswith(past.strftime("%Y-%m-%d"))

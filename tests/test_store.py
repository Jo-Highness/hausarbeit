"""Persistenter Store: Migration und robustes Laden."""
from __future__ import annotations

import pytest

from custom_components.hausarbeit.const import (
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_MINOR_VERSION,
    STORE_PERSONS,
    STORE_TASKS,
    STORE_TARGETS,
    STORE_EXECUTIONS,
)
from custom_components.hausarbeit.store import (
    HausarbeitStore,
    HausarbeitMigratableStore,
    new_id,
)

ALL_KEYS = (STORE_PERSONS, STORE_TASKS, STORE_TARGETS, STORE_EXECUTIONS)


def test_new_id_prefix():
    ident = new_id("per_")
    assert ident.startswith("per_")
    assert len(ident) == len("per_") + 8


async def test_migrate_fills_missing_keys(hass):
    store = HausarbeitMigratableStore(
        hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
    )
    old = {STORE_PERSONS: [{"id": "per_1"}]}  # nur Personen vorhanden
    migrated = await store._async_migrate_func(1, 1, old)
    for key in ALL_KEYS:
        assert isinstance(migrated[key], list)
    assert migrated[STORE_PERSONS] == [{"id": "per_1"}]
    assert migrated[STORE_TASKS] == []
    assert migrated[STORE_TARGETS] == []
    assert migrated[STORE_EXECUTIONS] == []


async def test_migrate_ignores_non_list_and_non_dict(hass):
    store = HausarbeitMigratableStore(
        hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
    )
    migrated = await store._async_migrate_func(1, 1, {STORE_TASKS: "kaputt"})
    assert migrated[STORE_TASKS] == []
    migrated2 = await store._async_migrate_func(1, 1, None)
    for key in ALL_KEYS:
        assert migrated2[key] == []


async def test_async_load_empty_store(hass):
    store = HausarbeitStore(hass)
    await store.async_load()
    assert store.persons == []
    assert store.tasks == []
    assert store.targets == []
    assert store.executions == []


async def test_store_crud_roundtrip(hass):
    store = HausarbeitStore(hass)
    await store.async_load()
    store.add(STORE_PERSONS, {"id": "per_1", "name": "Alice"})
    assert store.get_person("per_1")["name"] == "Alice"

    updated = store.update(store.persons, "per_1", {"name": "Alicia"})
    assert updated["name"] == "Alicia"
    assert store.update(store.persons, "per_x", {"name": "X"}) is None

    assert store.remove(store.persons, "per_1") is True
    assert store.remove(store.persons, "per_1") is False

    store.replace_all(STORE_TASKS, [{"id": "tsk_1"}])
    assert len(store.tasks) == 1

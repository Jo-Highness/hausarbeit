"""Diagnose-Daten (Einstellungen → Geräte & Dienste → Hausarbeit-Tracker → Diagnose).

Enthält nur Struktur- und Zähldaten. Namen von Personen, Farben, Verknüpfungen zu
person.*-Entitäten, Notizen und HA-Benutzer-IDs werden geschwärzt bzw. weggelassen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    F_ACTIVE,
    F_COLOR,
    F_COUNT,
    F_HA_PERSON,
    F_ID,
    F_NAME,
    F_PERIOD,
    F_PERSON_ID,
    F_POINTS,
    F_TASK_ID,
    F_TIMESTAMP,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    VERSION,
)
from .targets import parse_ts

if TYPE_CHECKING:
    from . import HausarbeitConfigEntry

TO_REDACT = {F_NAME, F_COLOR, F_HA_PERSON, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HausarbeitConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    store = coordinator.store

    timestamps = [
        ts for ex in store.executions if (ts := parse_ts(ex.get(F_TIMESTAMP, ""))) is not None
    ]
    unparsable = len(store.executions) - len(timestamps)
    person_ids = {p.get(F_ID) for p in store.persons}
    task_ids = {t.get(F_ID) for t in store.tasks}

    return {
        "version": VERSION,
        "storage_version": f"{STORAGE_VERSION}.{STORAGE_MINOR_VERSION}",
        "entry": async_redact_data(
            {"title": entry.title, "options": dict(entry.options)}, TO_REDACT
        ),
        "persons": [
            async_redact_data(
                {**person, "linked_to_ha_person": bool(person.get(F_HA_PERSON))}, TO_REDACT
            )
            for person in store.persons
        ],
        "tasks": [
            {
                F_ID: task.get(F_ID),
                F_POINTS: task.get(F_POINTS),
                F_ACTIVE: task.get(F_ACTIVE),
            }
            for task in store.tasks
        ],
        "targets": [
            {
                F_ID: target.get(F_ID),
                F_PERSON_ID: target.get(F_PERSON_ID),
                F_TASK_ID: target.get(F_TASK_ID),
                F_PERIOD: target.get(F_PERIOD),
                F_COUNT: target.get(F_COUNT),
            }
            for target in store.targets
        ],
        "executions": {
            "count": len(store.executions),
            "unparsable_timestamps": unparsable,
            "orphaned_person": sum(
                1 for ex in store.executions if ex.get(F_PERSON_ID) not in person_ids
            ),
            "orphaned_task": sum(1 for ex in store.executions if ex.get(F_TASK_ID) not in task_ids),
            "first": min(timestamps).isoformat() if timestamps else None,
            "last": max(timestamps).isoformat() if timestamps else None,
        },
    }

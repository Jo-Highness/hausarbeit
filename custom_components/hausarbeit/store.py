"""Persistente Speicherung für den Hausarbeit-Tracker.

Nutzt homeassistant.helpers.storage.Store (versioniert, mit Migrationspfad).
Das Ausführungs-Log kann groß werden, daher wird effizient (debounced) gespeichert
und der Event-Loop nie blockiert. Diese Klasse hält die Daten im Speicher und bietet
CRUD-Operationen; die *fachliche* Logik (Perioden/Statistik) liegt in targets.py.
"""

from __future__ import annotations

from datetime import UTC
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    F_TIMESTAMP,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    STORE_EXECUTIONS,
    STORE_PERSONS,
    STORE_TARGETS,
    STORE_TASKS,
)
from .targets import parse_ts

SAVE_DELAY = 2  # Sekunden Debounce für Schreibvorgänge


def new_id(prefix: str) -> str:
    """Kurze, stabile ID: <prefix> + 8 Hex-Zeichen aus uuid4."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _empty_data() -> dict[str, list]:
    return {
        STORE_PERSONS: [],
        STORE_TASKS: [],
        STORE_TARGETS: [],
        STORE_EXECUTIONS: [],
    }


class HausarbeitMigratableStore(Store):
    """Store mit Migrationspfad für zukünftige Schema-Änderungen."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict
    ) -> dict:
        # v1 ist die erste Version — nichts zu migrieren. Fehlende Schlüssel ergänzen,
        # damit ältere/teilweise Daten robust geladen werden.
        data = _empty_data()
        if isinstance(old_data, dict):
            for key in (STORE_PERSONS, STORE_TASKS, STORE_TARGETS, STORE_EXECUTIONS):
                if isinstance(old_data.get(key), list):
                    data[key] = old_data[key]
        if old_major_version == 1 and old_minor_version < 2:
            # 1.2: Zeitstempel einheitlich als UTC speichern (ältere Versionen haben
            # Offsets wie +02:00 unverändert übernommen). Gleicher Zeitpunkt, nur
            # normalisierte Darstellung — unlesbare Werte bleiben unangetastet.
            for execution in data[STORE_EXECUTIONS]:
                if not isinstance(execution, dict):
                    continue
                parsed = parse_ts(execution.get(F_TIMESTAMP, ""))
                if parsed is not None:
                    execution[F_TIMESTAMP] = parsed.astimezone(UTC).isoformat()
        return data


class HausarbeitStore:
    """Hält die Daten im Speicher und persistiert sie debounced."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = HausarbeitMigratableStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self.data: dict[str, list] = _empty_data()

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        if loaded is None:
            self.data = _empty_data()
            return
        # Robust: fehlende Top-Level-Listen ergänzen.
        data = _empty_data()
        for key in (STORE_PERSONS, STORE_TASKS, STORE_TARGETS, STORE_EXECUTIONS):
            if isinstance(loaded.get(key), list):
                data[key] = loaded[key]
        self.data = data

    def _schedule_save(self) -> None:
        """Nicht-blockierendes, gebündeltes Speichern."""
        self._store.async_delay_save(lambda: self.data, SAVE_DELAY)

    async def async_save_now(self) -> None:
        await self._store.async_save(self.data)

    async def async_remove(self) -> None:
        """Gespeicherte Datei löschen (beim Entfernen der Integration)."""
        await self._store.async_remove()

    # -- Zugriff -----------------------------------------------------------
    @property
    def persons(self) -> list[dict]:
        return self.data[STORE_PERSONS]

    @property
    def tasks(self) -> list[dict]:
        return self.data[STORE_TASKS]

    @property
    def targets(self) -> list[dict]:
        return self.data[STORE_TARGETS]

    @property
    def executions(self) -> list[dict]:
        return self.data[STORE_EXECUTIONS]

    def _find(self, collection: list[dict], item_id: str) -> dict | None:
        return next((x for x in collection if x.get("id") == item_id), None)

    def get_person(self, person_id: str) -> dict | None:
        return self._find(self.persons, person_id)

    def get_task(self, task_id: str) -> dict | None:
        return self._find(self.tasks, task_id)

    def get_target(self, target_id: str) -> dict | None:
        return self._find(self.targets, target_id)

    def get_execution(self, execution_id: str) -> dict | None:
        return self._find(self.executions, execution_id)

    # -- Generisches CRUD --------------------------------------------------
    def add(self, collection_key: str, item: dict) -> dict:
        self.data[collection_key].append(item)
        self._schedule_save()
        return item

    def update(self, collection: list[dict], item_id: str, changes: dict) -> dict | None:
        # Setzt ALLE übergebenen Schlüssel (auch None/"" -> Feld leeren). Nur Schlüssel,
        # die NICHT im dict stehen, bleiben unverändert. Die Aufrufer (Coordinator/
        # Services) entscheiden bewusst, welche Felder im dict landen.
        item = self._find(collection, item_id)
        if item is None:
            return None
        for key, value in changes.items():
            if key in ("id", "created"):
                continue  # unveränderliche Felder schützen
            item[key] = value
        self._schedule_save()
        return item

    def remove(self, collection: list[dict], item_id: str) -> bool:
        item = self._find(collection, item_id)
        if item is None:
            return False
        collection.remove(item)
        self._schedule_save()
        return True

    def replace_all(self, collection_key: str, items: list[dict]) -> None:
        self.data[collection_key] = items
        self._schedule_save()

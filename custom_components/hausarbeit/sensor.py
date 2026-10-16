"""Sensor-Entitäten des Hausarbeit-Trackers.

Dynamisch: pro Person ein Sensor (Ausführungen im Statistik-Zeitraum + Aufschlüsselung),
pro Soll-Vorgabe ein Sensor (Ist der laufenden Periode + Soll/Rest/Erfüllungsgrad),
pro Aufgabe ein „zuletzt erledigt"-Sensor. Entitäten werden bei Datenänderungen
(Signal) hinzugefügt bzw. samt Entity-Registry-Eintrag entfernt — kein Neustart nötig.
Zusätzlich aktualisiert der stündliche Tick des Coordinators die zeitabhängigen Werte.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    F_ICON,
    F_ID,
    F_PERIOD,
    F_PERSON_ID,
    F_TASK_ID,
    MANUFACTURER,
    MODEL,
    NAME,
    PERIOD_WEEK,
    PERIODS,
    VERSION,
)
from .coordinator import HausarbeitCoordinator
from .targets import count_executions, evaluate_target, parse_ts

if TYPE_CHECKING:
    from . import HausarbeitConfigEntry

# Unique-ID-Bausteine (NICHT ändern — bestehende Entitäten hängen daran):
#   <entry_id>_person_<per_id>, <entry_id>_target_<tgt_id>, <entry_id>_lastdone_<tsk_id>
_KIND_PERSON = "person"
_KIND_TARGET = "target"
_KIND_LASTDONE = "lastdone"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HausarbeitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: dict[str, _BaseSensor] = {}
    ent_reg = er.async_get(hass)

    def _wanted_keys() -> dict[str, tuple[str, str]]:
        wanted: dict[str, tuple[str, str]] = {}
        for person in coordinator.store.persons:
            wanted[f"{_KIND_PERSON}_{person[F_ID]}"] = (_KIND_PERSON, person[F_ID])
        for target in coordinator.store.targets:
            wanted[f"{_KIND_TARGET}_{target[F_ID]}"] = (_KIND_TARGET, target[F_ID])
        for task in coordinator.store.tasks:
            wanted[f"{_KIND_LASTDONE}_{task[F_ID]}"] = (_KIND_LASTDONE, task[F_ID])
        return wanted

    def _create(kind: str, item_id: str) -> _BaseSensor:
        if kind == _KIND_PERSON:
            return PersonSensor(coordinator, entry, item_id)
        if kind == _KIND_TARGET:
            return TargetSensor(coordinator, entry, item_id)
        return TaskLastDoneSensor(coordinator, entry, item_id)

    @callback
    def _remove_entity(entity: _BaseSensor) -> None:
        """Entität entfernen — inklusive Entity-Registry-Eintrag (keine Waisen)."""
        if entity.registry_entry is not None and ent_reg.async_get(entity.entity_id):
            # Das Löschen des Registry-Eintrags entfernt auch die laufende Entität.
            ent_reg.async_remove(entity.entity_id)
        elif entity.hass is not None:
            entry.async_create_background_task(
                hass,
                entity.async_remove(force_remove=True),
                f"{DOMAIN}_remove_{entity.unique_id}",
            )

    @callback
    def _remove_orphaned_registry_entries(wanted: dict[str, tuple[str, str]]) -> None:
        """Registry-Einträge entfernen, deren Person/Aufgabe/Vorgabe nicht mehr existiert.

        Räumt Waisen auf, die ältere Versionen beim Löschen hinterlassen haben.
        """
        prefix = f"{entry.entry_id}_"
        for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if reg_entry.domain != "sensor" or not reg_entry.unique_id.startswith(prefix):
                continue
            key = reg_entry.unique_id[len(prefix) :]
            if key not in wanted:
                ent_reg.async_remove(reg_entry.entity_id)

    @callback
    def _reconcile() -> None:
        wanted = _wanted_keys()

        for key in [k for k in known if k not in wanted]:
            _remove_entity(known.pop(key))

        # Bereits bekannte Entitäten genau EINMAL aktualisieren (vor dem Hinzufügen
        # neuer — die schreiben ihren Zustand beim Hinzufügen selbst).
        for entity in known.values():
            if entity.hass is not None:
                entity.async_refresh()

        new_entities: list[_BaseSensor] = []
        for key, (kind, item_id) in wanted.items():
            if key not in known:
                entity = _create(kind, item_id)
                known[key] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    _remove_orphaned_registry_entries(_wanted_keys())
    _reconcile()
    entry.async_on_unload(async_dispatcher_connect(hass, coordinator.signal, _reconcile))


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: HausarbeitCoordinator, entry: HausarbeitConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def async_refresh(self) -> None:
        """Zustand neu schreiben (Datenänderung oder Zeit-Tick).

        Der Name hängt über ``translation_placeholders`` an Personen-/Aufgabennamen,
        die umbenannt werden können. Home Assistant cached ``name`` je Entität, daher
        wird der Cache vor dem Schreiben verworfen.
        """
        self.__dict__.pop("name", None)
        self.async_write_ha_state()


class PersonSensor(_BaseSensor):
    """Ausführungen einer Person im Statistik-Zeitraum (Anzahl, nicht Punkte)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "person"

    def __init__(self, coordinator, entry, person_id: str) -> None:
        super().__init__(coordinator, entry)
        self._person_id = person_id
        self._attr_unique_id = f"{entry.entry_id}_{_KIND_PERSON}_{person_id}"

    @property
    def translation_placeholders(self) -> Mapping[str, str]:
        return {"person": self.coordinator.person_name(self._person_id)}

    @property
    def available(self) -> bool:
        return self.coordinator.store.get_person(self._person_id) is not None

    @property
    def icon(self) -> str | None:
        person = self.coordinator.store.get_person(self._person_id)
        return (person or {}).get(F_ICON) or None  # Fallback: icons.json

    def _window_start(self) -> tuple[datetime, datetime]:
        now = self.coordinator._now()
        return now, now - timedelta(days=self.coordinator.stats_days)

    @property
    def native_value(self) -> int:
        _now, start = self._window_start()
        return count_executions(
            self.coordinator.store.executions, self._person_id, None, start, None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now, start = self._window_start()
        windows = self.coordinator.person_windows(self._person_id, now)
        return {
            "person_id": self._person_id,
            "stats_days": self.coordinator.stats_days,
            "breakdown": self.coordinator.person_breakdown(self._person_id, start, None),
            **windows,
        }


class TargetSensor(_BaseSensor):
    """Ist/Soll einer Soll-Vorgabe für die laufende Periode."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, target_id: str) -> None:
        super().__init__(coordinator, entry)
        self._target_id = target_id
        self._attr_unique_id = f"{entry.entry_id}_{_KIND_TARGET}_{target_id}"
        target = coordinator.store.get_target(target_id) or {}
        period = target.get(F_PERIOD, PERIOD_WEEK)
        # Die Periode einer Vorgabe ist fest (andere Periode = neue Vorgabe), daher
        # pro Periode ein eigener Übersetzungsschlüssel ("Woche"/"week"/"semana").
        self._attr_translation_key = (
            f"target_{period}" if period in PERIODS else f"target_{PERIOD_WEEK}"
        )

    def _eval(self) -> dict | None:
        target = self.coordinator.store.get_target(self._target_id)
        if target is None:
            return None
        ev = evaluate_target(
            target,
            self.coordinator.store.executions,
            self.coordinator._now(),
            self.coordinator.week_start,
        )
        ev["person_name"] = self.coordinator.person_name(target.get(F_PERSON_ID))
        ev["task_name"] = self.coordinator.task_name(target.get(F_TASK_ID))
        return ev

    @property
    def translation_placeholders(self) -> Mapping[str, str]:
        target = self.coordinator.store.get_target(self._target_id) or {}
        return {
            "person": self.coordinator.person_name(target.get(F_PERSON_ID, "")),
            "task": self.coordinator.task_name(target.get(F_TASK_ID, "")),
        }

    @property
    def available(self) -> bool:
        return self.coordinator.store.get_target(self._target_id) is not None

    @property
    def native_value(self) -> int | None:
        ev = self._eval()
        return ev["ist"] if ev else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ev = self._eval()
        if not ev:
            return {}
        # Attributnamen sind öffentlich (Automationen/Templates) — nicht umbenennen.
        return {
            "target_id": self._target_id,
            "soll": ev["count"],
            "ist": ev["ist"],
            "rest": ev["rest"],
            "erfuellungsgrad": ev["percent"],
            "im_soll": ev["on_track"],
            "periode": ev[F_PERIOD],
            "periodenstart": ev["period_start"],
            "periodenende": ev["period_end"],
            "person_id": ev[F_PERSON_ID],
            "task_id": ev[F_TASK_ID],
        }


class TaskLastDoneSensor(_BaseSensor):
    """Zeitpunkt, zu dem eine Aufgabe zuletzt erledigt wurde."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_done"

    def __init__(self, coordinator, entry, task_id: str) -> None:
        super().__init__(coordinator, entry)
        self._task_id = task_id
        self._attr_unique_id = f"{entry.entry_id}_{_KIND_LASTDONE}_{task_id}"

    @property
    def translation_placeholders(self) -> Mapping[str, str]:
        return {"task": self.coordinator.task_name(self._task_id)}

    @property
    def available(self) -> bool:
        return self.coordinator.store.get_task(self._task_id) is not None

    @property
    def icon(self) -> str | None:
        task = self.coordinator.store.get_task(self._task_id)
        return (task or {}).get(F_ICON) or None  # Fallback: icons.json

    @property
    def native_value(self) -> datetime | None:
        info = self.coordinator.last_done(self._task_id)
        if not info:
            return None
        return parse_ts(info.get("ts", ""))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.last_done(self._task_id)
        if not info:
            return {"task_id": self._task_id}
        return {
            "task_id": self._task_id,
            "person_id": info.get(F_PERSON_ID),
            "person_name": info.get("person_name"),
        }

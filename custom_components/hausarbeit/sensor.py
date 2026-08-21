"""Sensor-Entitäten des Hausarbeit-Trackers.

Dynamisch: pro Person ein Sensor (Ausführungen im Statistik-Zeitraum + Aufschlüsselung),
pro Soll-Vorgabe ein Sensor (Ist der laufenden Periode + Soll/Rest/Erfüllungsgrad),
pro Aufgabe ein „zuletzt erledigt"-Sensor. Entitäten werden bei Datenänderungen
(Signal) hinzugefügt/entfernt — kein Neustart nötig.
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    VERSION,
)
from .coordinator import HausarbeitCoordinator
from .targets import parse_ts


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HausarbeitCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: dict[str, SensorEntity] = {}

    @callback
    def _reconcile() -> None:
        wanted: dict[str, SensorEntity] = {}
        for person in coordinator.store.persons:
            uid = f"person_{person[F_ID]}"
            wanted[uid] = known.get(uid) or PersonSensor(coordinator, entry, person[F_ID])
        for target in coordinator.store.targets:
            uid = f"target_{target[F_ID]}"
            wanted[uid] = known.get(uid) or TargetSensor(coordinator, entry, target[F_ID])
        for task in coordinator.store.tasks:
            uid = f"lastdone_{task[F_ID]}"
            wanted[uid] = known.get(uid) or TaskLastDoneSensor(coordinator, entry, task[F_ID])

        new_entities = [e for uid, e in wanted.items() if uid not in known]
        removed = [uid for uid in known if uid not in wanted]

        for uid in removed:
            entity = known.pop(uid)
            hass.async_create_task(entity.async_remove(force_remove=True))

        if new_entities:
            for uid, entity in wanted.items():
                if uid not in known:
                    known[uid] = entity
            async_add_entities(new_entities)

        # existierende Entitäten aktualisieren
        for entity in known.values():
            if entity.hass is not None:
                entity.async_write_ha_state()

    _reconcile()
    entry.async_on_unload(async_dispatcher_connect(hass, coordinator.signal, _reconcile))


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: HausarbeitCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.coordinator.signal, self.async_write_ha_state)
        )


class PersonSensor(_BaseSensor):
    """Ausführungen einer Person im Statistik-Zeitraum."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Aufgaben"

    def __init__(self, coordinator, entry, person_id: str) -> None:
        super().__init__(coordinator, entry)
        self._person_id = person_id
        self._attr_unique_id = f"{entry.entry_id}_person_{person_id}"

    @property
    def available(self) -> bool:
        return self.coordinator.store.get_person(self._person_id) is not None

    @property
    def name(self) -> str:
        return self.coordinator.person_name(self._person_id)

    @property
    def icon(self) -> str:
        person = self.coordinator.store.get_person(self._person_id)
        return (person or {}).get(F_ICON) or "mdi:account"

    @property
    def native_value(self) -> int:
        now = self.coordinator._now()
        start = now - timedelta(days=self.coordinator.stats_days)
        from .targets import count_executions

        return count_executions(
            self.coordinator.store.executions, self._person_id, None, start, None
        )

    @property
    def extra_state_attributes(self) -> dict:
        now = self.coordinator._now()
        start = now - timedelta(days=self.coordinator.stats_days)
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
    _attr_native_unit_of_measurement = "Aufgaben"
    _attr_icon = "mdi:target"

    def __init__(self, coordinator, entry, target_id: str) -> None:
        super().__init__(coordinator, entry)
        self._target_id = target_id
        self._attr_unique_id = f"{entry.entry_id}_target_{target_id}"

    def _eval(self) -> dict | None:
        target = self.coordinator.store.get_target(self._target_id)
        if target is None:
            return None
        from .targets import evaluate_target

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
    def available(self) -> bool:
        return self.coordinator.store.get_target(self._target_id) is not None

    @property
    def name(self) -> str:
        ev = self._eval()
        if not ev:
            return "Soll-Vorgabe"
        return f"{ev['person_name']} · {ev['task_name']} ({ev[F_PERIOD]})"

    @property
    def native_value(self) -> int | None:
        ev = self._eval()
        return ev["ist"] if ev else None

    @property
    def extra_state_attributes(self) -> dict:
        ev = self._eval()
        if not ev:
            return {}
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

    def __init__(self, coordinator, entry, task_id: str) -> None:
        super().__init__(coordinator, entry)
        self._task_id = task_id
        self._attr_unique_id = f"{entry.entry_id}_lastdone_{task_id}"

    @property
    def available(self) -> bool:
        return self.coordinator.store.get_task(self._task_id) is not None

    @property
    def name(self) -> str:
        return f"{self.coordinator.task_name(self._task_id)} zuletzt erledigt"

    @property
    def icon(self) -> str:
        task = self.coordinator.store.get_task(self._task_id)
        return (task or {}).get(F_ICON) or "mdi:calendar-check"

    @property
    def native_value(self):
        info = self.coordinator.last_done(self._task_id)
        if not info:
            return None
        return parse_ts(info.get("ts", ""))

    @property
    def extra_state_attributes(self) -> dict:
        info = self.coordinator.last_done(self._task_id)
        if not info:
            return {"task_id": self._task_id}
        return {
            "task_id": self._task_id,
            "person_id": info.get(F_PERSON_ID),
            "person_name": info.get("person_name"),
        }

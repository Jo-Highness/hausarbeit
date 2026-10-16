"""Zentrale Steuerung des Hausarbeit-Trackers.

Hält den Store, bietet alle fachlichen Operationen (loggen, korrigieren, CRUD für
Personen/Aufgaben/Soll-Vorgaben) und baut Soll-/Ist- sowie Statistik-Auswertungen.
Bei jeder Änderung wird ein Dispatcher-Signal gesendet, damit Sensoren und die
Lovelace-Karten (WebSocket-Subscriber) sich aktualisieren.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import store as store_mod
from .const import (
    CONF_STATS_DAYS,
    CONF_WEEK_START,
    DEFAULT_STATS_DAYS,
    DEFAULT_WEEK_START,
    EVENT_EXECUTION_LOGGED,
    F_ACTIVE,
    F_CATEGORY,
    F_COLOR,
    F_COUNT,
    F_CREATED,
    F_HA_PERSON,
    F_ICON,
    F_ID,
    F_NAME,
    F_NOTE,
    F_PERIOD,
    F_PERSON_ID,
    F_POINTS,
    F_TASK_ID,
    F_TIMESTAMP,
    F_USER_ID,
    ID_PREFIX_EXECUTION,
    ID_PREFIX_PERSON,
    ID_PREFIX_TARGET,
    ID_PREFIX_TASK,
    MAX_POINTS,
    MIN_POINTS,
    PERIOD_MONTH,
    PERIODS,
    SIGNAL_UPDATE,
    STORE_EXECUTIONS,
    STORE_PERSONS,
    STORE_TARGETS,
    STORE_TASKS,
)
from .targets import (
    count_executions,
    evaluate_target,
    parse_ts,
    period_bounds,
    start_of_day,
    sum_points,
)

_LOGGER = logging.getLogger(__name__)


# Englische Fallback-Texte; die übersetzten Texte stehen unter "exceptions" in
# strings.json / translations/*.json (gleicher Schlüssel).
_ERROR_MESSAGES: dict[str, str] = {
    "person_not_found": "Person {id} not found.",
    "task_not_found": "Task {id} not found.",
    "target_not_found": "Target {id} not found.",
    "execution_not_found": "Execution {id} not found.",
    "empty_person_name": "The person's name must not be empty.",
    "empty_task_name": "The task's name must not be empty.",
    "invalid_points": "Points must be a number between {min} and {max}.",
    "invalid_period": "Invalid period: {period}.",
    "invalid_count": "The target count must be a whole number greater than 0.",
    "invalid_timestamp": "Invalid timestamp: {ts}.",
}


class HausarbeitError(Exception):
    """Fachlicher Fehler (z. B. unbekannte Person/Aufgabe).

    Trägt einen Übersetzungsschlüssel (Abschnitt ``exceptions``) und Platzhalter,
    damit Services übersetzte ``ServiceValidationError`` werfen können.
    """

    def __init__(self, translation_key: str, **placeholders: Any) -> None:
        self.translation_key = translation_key
        self.translation_placeholders = {k: str(v) for k, v in placeholders.items()}
        template = _ERROR_MESSAGES.get(translation_key, translation_key)
        super().__init__(template.format(**self.translation_placeholders))


def _check_name(name: Any, translation_key: str) -> str:
    """Namen trimmen; leer/None ist ungültig (gleiche Regel wie beim Anlegen)."""
    if name is None or not str(name).strip():
        raise HausarbeitError(translation_key)
    return str(name).strip()


def _check_points(points: Any) -> float:
    """Punkte/Gewicht: endliche Zahl in [MIN_POINTS, MAX_POINTS]."""
    try:
        value = float(points)
    except (TypeError, ValueError) as err:
        raise HausarbeitError(
            "invalid_points", min=f"{MIN_POINTS:g}", max=f"{MAX_POINTS:g}"
        ) from err
    if not math.isfinite(value) or not MIN_POINTS <= value <= MAX_POINTS:
        raise HausarbeitError("invalid_points", min=f"{MIN_POINTS:g}", max=f"{MAX_POINTS:g}")
    return value


class HausarbeitCoordinator:
    """Besitzt Daten + Logik für einen Haushalts-Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = store_mod.HausarbeitStore(hass)

    async def async_init(self) -> None:
        await self.store.async_load()

    @callback
    def async_start_timer(self) -> None:
        """Zeitgesteuerte Aktualisierung starten (stündlich, inkl. lokaler Mitternacht).

        Ohne Datenänderung würden „heute"/7/30/90-Tage-Fenster, der Tempo-Wert
        ``im_soll`` und die laufende Periode (Tag/Woche/Monat) sonst veralten.
        Alle Perioden-Grenzen liegen auf lokaler Mitternacht, die gleitenden Fenster
        werden mindestens stündlich nachgeführt. ``async_track_time_change`` arbeitet
        in der lokalen HA-Zeitzone.
        """
        self.entry.async_on_unload(
            async_track_time_change(self.hass, self._async_handle_tick, minute=0, second=0)
        )

    @callback
    def _async_handle_tick(self, _now: datetime) -> None:
        self._notify()

    # -- Optionen ----------------------------------------------------------
    @property
    def week_start(self) -> int:
        return int(self.entry.options.get(CONF_WEEK_START, DEFAULT_WEEK_START))

    @property
    def stats_days(self) -> int:
        return int(self.entry.options.get(CONF_STATS_DAYS, DEFAULT_STATS_DAYS))

    @property
    def signal(self) -> str:
        return f"{SIGNAL_UPDATE}_{self.entry.entry_id}"

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    def _now(self) -> datetime:
        return dt_util.now()  # aware, lokale HA-Zeitzone

    # -- Namens-Helfer -----------------------------------------------------
    def person_name(self, person_id: str) -> str:
        p = self.store.get_person(person_id)
        return p.get(F_NAME, person_id) if p else person_id

    def task_name(self, task_id: str) -> str:
        t = self.store.get_task(task_id)
        return t.get(F_NAME, task_id) if t else task_id

    def _tasks_by_id(self) -> dict[str, dict]:
        return {t[F_ID]: t for t in self.store.tasks}

    # ------------------------------------------------------------------ #
    # Personen
    # ------------------------------------------------------------------ #
    def add_person(
        self,
        name: str,
        icon: str | None = None,
        color: str | None = None,
        ha_person_entity: str | None = None,
    ) -> dict:
        if not name or not str(name).strip():
            raise HausarbeitError("empty_person_name")
        person = {
            F_ID: store_mod.new_id(ID_PREFIX_PERSON),
            F_NAME: str(name).strip(),
            F_ICON: icon,
            F_COLOR: color,
            F_HA_PERSON: ha_person_entity,
            F_CREATED: dt_util.utcnow().isoformat(),
        }
        self.store.add(STORE_PERSONS, person)
        self._notify()
        return person

    def update_person(self, person_id: str, **changes: Any) -> dict:
        if F_NAME in changes:
            changes[F_NAME] = _check_name(changes[F_NAME], "empty_person_name")
        item = self.store.update(self.store.persons, person_id, changes)
        if item is None:
            raise HausarbeitError("person_not_found", id=person_id)
        self._notify()
        return item

    def remove_person(self, person_id: str) -> None:
        if not self.store.remove(self.store.persons, person_id):
            raise HausarbeitError("person_not_found", id=person_id)
        # zugehörige Soll-Vorgaben entfernen (Ausführungs-Log bleibt als Rohdaten erhalten)
        self.store.replace_all(
            STORE_TARGETS,
            [t for t in self.store.targets if t.get(F_PERSON_ID) != person_id],
        )
        self._notify()

    # ------------------------------------------------------------------ #
    # Aufgaben
    # ------------------------------------------------------------------ #
    def add_task(
        self,
        name: str,
        icon: str | None = None,
        category: str | None = None,
        points: float | None = None,
        active: bool | None = None,
    ) -> dict:
        if not name or not str(name).strip():
            raise HausarbeitError("empty_task_name")
        task = {
            F_ID: store_mod.new_id(ID_PREFIX_TASK),
            F_NAME: str(name).strip(),
            F_ICON: icon,
            F_CATEGORY: category,
            F_POINTS: 1 if points is None else _check_points(points),
            F_ACTIVE: True if active is None else bool(active),
            F_CREATED: dt_util.utcnow().isoformat(),
        }
        self.store.add(STORE_TASKS, task)
        self._notify()
        return task

    def update_task(self, task_id: str, **changes: Any) -> dict:
        if F_NAME in changes:
            changes[F_NAME] = _check_name(changes[F_NAME], "empty_task_name")
        if changes.get(F_POINTS) is not None:
            changes[F_POINTS] = _check_points(changes[F_POINTS])
        item = self.store.update(self.store.tasks, task_id, changes)
        if item is None:
            raise HausarbeitError("task_not_found", id=task_id)
        self._notify()
        return item

    def remove_task(self, task_id: str) -> None:
        if not self.store.remove(self.store.tasks, task_id):
            raise HausarbeitError("task_not_found", id=task_id)
        self.store.replace_all(
            STORE_TARGETS,
            [t for t in self.store.targets if t.get(F_TASK_ID) != task_id],
        )
        self._notify()

    # ------------------------------------------------------------------ #
    # Soll-Vorgaben (Targets) — genau eine je (Person, Aufgabe, Periode)
    # ------------------------------------------------------------------ #
    def set_target(self, person_id: str, task_id: str, period: str, count: int) -> dict:
        if self.store.get_person(person_id) is None:
            raise HausarbeitError("person_not_found", id=person_id)
        if self.store.get_task(task_id) is None:
            raise HausarbeitError("task_not_found", id=task_id)
        if period not in PERIODS:
            raise HausarbeitError("invalid_period", period=period)
        try:
            count = int(count)
        except (TypeError, ValueError) as err:
            raise HausarbeitError("invalid_count") from err
        if count <= 0:
            raise HausarbeitError("invalid_count")

        existing = next(
            (
                t
                for t in self.store.targets
                if t.get(F_PERSON_ID) == person_id
                and t.get(F_TASK_ID) == task_id
                and t.get(F_PERIOD) == period
            ),
            None,
        )
        if existing is not None:
            existing[F_COUNT] = count
            self.store._schedule_save()
            self._notify()
            return existing

        target = {
            F_ID: store_mod.new_id(ID_PREFIX_TARGET),
            F_PERSON_ID: person_id,
            F_TASK_ID: task_id,
            F_PERIOD: period,
            F_COUNT: count,
            F_CREATED: dt_util.utcnow().isoformat(),
        }
        self.store.add(STORE_TARGETS, target)
        self._notify()
        return target

    def remove_target(self, target_id: str) -> None:
        if not self.store.remove(self.store.targets, target_id):
            raise HausarbeitError("target_not_found", id=target_id)
        self._notify()

    # ------------------------------------------------------------------ #
    # Ausführungen (Log)
    # ------------------------------------------------------------------ #
    def _normalize_ts(self, ts: Any) -> str:
        """Beliebigen Zeitpunkt -> ISO-8601 in UTC (aware).

        Zeitpunkte ohne Zeitzone (z. B. aus dem Datetime-Selektor der Services oder
        ``2026-10-16T08:00`` per WebSocket) gelten als *lokale* HA-Zeit; Offsets wie
        ``+02:00`` werden nach UTC umgerechnet, damit alle gespeicherten Werte gleich
        aufgebaut sind.
        """
        if ts is None:
            return dt_util.utcnow().isoformat()
        local_tz = dt_util.get_default_time_zone()
        if isinstance(ts, datetime):
            parsed: datetime | None = ts if ts.tzinfo else ts.replace(tzinfo=local_tz)
        else:
            parsed = parse_ts(str(ts), default_tz=local_tz)
        if parsed is None:
            raise HausarbeitError("invalid_timestamp", ts=ts)
        return dt_util.as_utc(parsed).isoformat()

    def log_execution(
        self,
        person_id: str,
        task_id: str,
        ts: Any = None,
        note: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if self.store.get_person(person_id) is None:
            raise HausarbeitError("person_not_found", id=person_id)
        if self.store.get_task(task_id) is None:
            raise HausarbeitError("task_not_found", id=task_id)
        execution = {
            F_ID: store_mod.new_id(ID_PREFIX_EXECUTION),
            F_PERSON_ID: person_id,
            F_TASK_ID: task_id,
            F_TIMESTAMP: self._normalize_ts(ts),
            F_NOTE: (note or "").strip(),
        }
        if user_id:
            execution[F_USER_ID] = user_id
        self.store.add(STORE_EXECUTIONS, execution)
        self.hass.bus.async_fire(
            EVENT_EXECUTION_LOGGED,
            {
                "execution_id": execution[F_ID],
                F_PERSON_ID: person_id,
                "person_name": self.person_name(person_id),
                F_TASK_ID: task_id,
                "task_name": self.task_name(task_id),
                F_TIMESTAMP: execution[F_TIMESTAMP],
            },
        )
        self._notify()
        return execution

    def delete_execution(self, execution_id: str) -> None:
        if not self.store.remove(self.store.executions, execution_id):
            raise HausarbeitError("execution_not_found", id=execution_id)
        self._notify()

    def correct_execution(
        self,
        execution_id: str,
        person_id: str | None = None,
        task_id: str | None = None,
        ts: Any = None,
        note: str | None = None,
    ) -> dict:
        execution = self.store.get_execution(execution_id)
        if execution is None:
            raise HausarbeitError("execution_not_found", id=execution_id)
        if person_id is not None:
            if self.store.get_person(person_id) is None:
                raise HausarbeitError("person_not_found", id=person_id)
            execution[F_PERSON_ID] = person_id
        if task_id is not None:
            if self.store.get_task(task_id) is None:
                raise HausarbeitError("task_not_found", id=task_id)
            execution[F_TASK_ID] = task_id
        if ts is not None:
            execution[F_TIMESTAMP] = self._normalize_ts(ts)
        if note is not None:
            execution[F_NOTE] = str(note).strip()
        self.store._schedule_save()
        self._notify()
        return execution

    # ------------------------------------------------------------------ #
    # Auswertungen für Sensoren / WebSocket
    # ------------------------------------------------------------------ #
    def evaluate_targets(self) -> list[dict]:
        now = self._now()
        out: list[dict] = []
        for target in self.store.targets:
            ev = evaluate_target(target, self.store.executions, now, self.week_start)
            ev["person_name"] = self.person_name(target.get(F_PERSON_ID))
            ev["task_name"] = self.task_name(target.get(F_TASK_ID))
            out.append(ev)
        return out

    def person_breakdown(
        self, person_id: str, start: datetime | None, end: datetime | None
    ) -> dict[str, int]:
        """Aufschlüsselung {task_name: anzahl} für eine Person im Zeitfenster."""
        result: dict[str, int] = {}
        for ex in self.store.executions:
            if ex.get(F_PERSON_ID) != person_id:
                continue
            ts = parse_ts(ex.get(F_TIMESTAMP, ""))
            if ts is None:
                continue
            if start is not None and ts < start:
                continue
            if end is not None and ts >= end:
                continue
            name = self.task_name(ex.get(F_TASK_ID))
            result[name] = result.get(name, 0) + 1
        return result

    def person_windows(self, person_id: str, now: datetime) -> dict[str, int]:
        """Zählungen für today/7d/30d/90d/current_month/total."""
        tasks_by_id = self._tasks_by_id()
        ex = self.store.executions
        today = start_of_day(now)
        month_start, _ = period_bounds(now, PERIOD_MONTH, self.week_start)
        return {
            "today": count_executions(ex, person_id, None, today, None),
            "d7": count_executions(ex, person_id, None, now - timedelta(days=7), None),
            "d30": count_executions(ex, person_id, None, now - timedelta(days=30), None),
            "d90": count_executions(ex, person_id, None, now - timedelta(days=90), None),
            "current_month": count_executions(ex, person_id, None, month_start, None),
            "total": count_executions(ex, person_id, None, None, None),
            "points_total": int(sum_points(ex, tasks_by_id, person_id, None, None)),
        }

    def build_stats(self, days: int | None = None) -> dict:
        now = self._now()
        days = self.stats_days if days is None else int(days)
        start = now - timedelta(days=days)
        tasks_by_id = self._tasks_by_id()
        ex = self.store.executions

        # Zähler je (existierender) Person zuerst; total = deren Summe, damit
        # share_percent sich zu 100 % summiert und total == Σ per_task.count bleibt —
        # auch wenn nach dem Löschen einer Person verwaiste Ausführungen im Log liegen.
        person_counts: dict[str, int] = {}
        person_points: dict[str, float] = {}
        for person in self.store.persons:
            pid = person[F_ID]
            person_counts[pid] = count_executions(ex, pid, None, start, None)
            person_points[pid] = sum_points(ex, tasks_by_id, pid, start, None)
        total_in_window = sum(person_counts.values())

        ranking = []
        for person in self.store.persons:
            pid = person[F_ID]
            cnt = person_counts[pid]
            ranking.append(
                {
                    F_PERSON_ID: pid,
                    "person_name": person.get(F_NAME, pid),
                    "count": cnt,
                    "points": round(person_points[pid], 1),
                    "share_percent": round((cnt / total_in_window) * 100, 1)
                    if total_in_window
                    else 0.0,
                }
            )
        ranking.sort(key=lambda r: (r["count"], r["points"]), reverse=True)

        per_task = []
        for task in self.store.tasks:
            tid = task[F_ID]
            per_person = []
            task_total = 0
            for person in self.store.persons:
                pid = person[F_ID]
                c = count_executions(ex, pid, tid, start, None)
                task_total += c
                if c:
                    per_person.append(
                        {
                            F_PERSON_ID: pid,
                            "person_name": person.get(F_NAME, pid),
                            "count": c,
                        }
                    )
            per_task.append(
                {
                    F_TASK_ID: tid,
                    "task_name": task.get(F_NAME, tid),
                    "count": task_total,
                    "per_person": per_person,
                }
            )
        per_task.sort(key=lambda t: t["count"], reverse=True)

        per_person = []
        for person in self.store.persons:
            windows = self.person_windows(person[F_ID], now)
            per_person.append(
                {
                    F_PERSON_ID: person[F_ID],
                    "person_name": person.get(F_NAME, person[F_ID]),
                    **windows,
                }
            )

        return {
            "days": days,
            "start": start.isoformat(),
            "end": now.isoformat(),
            "total": total_in_window,
            "ranking": ranking,
            "per_task": per_task,
            "per_person": per_person,
            "targets": self.evaluate_targets(),
        }

    def last_done(self, task_id: str) -> dict | None:
        """Zuletzt-erledigt-Info für eine Aufgabe (Person + Zeitpunkt)."""
        latest: dict | None = None
        latest_ts: datetime | None = None
        for ex in self.store.executions:
            if ex.get(F_TASK_ID) != task_id:
                continue
            ts = parse_ts(ex.get(F_TIMESTAMP, ""))
            if ts is None:
                continue
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
                latest = ex
        if latest is None:
            return None
        return {
            F_PERSON_ID: latest.get(F_PERSON_ID),
            "person_name": self.person_name(latest.get(F_PERSON_ID)),
            F_TIMESTAMP: latest.get(F_TIMESTAMP),
        }

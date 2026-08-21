"""Reine Berechnungslogik: Perioden-Grenzen, Soll-/Ist-Auswertung, Statistik.

Bewusst frei von Home-Assistant-Abhängigkeiten (nur datetime), damit alles ohne
laufendes HA unit-testbar ist. Alle Funktionen arbeiten mit *aware* datetimes.
Ausführungs-Zeitstempel werden als ISO-8601 (UTC, "Z") gespeichert; Perioden-Grenzen
werden in der lokalen HA-Zeitzone gebildet — der Vergleich funktioniert korrekt, weil
Python aware-datetimes zeitzonenübergreifend vergleicht.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .const import (
    F_COUNT,
    F_ID,
    F_PERIOD,
    F_PERSON_ID,
    F_POINTS,
    F_TASK_ID,
    F_TIMESTAMP,
    PERIOD_DAY,
    PERIOD_MONTH,
    PERIOD_WEEK,
)


def parse_ts(value: str) -> datetime | None:
    """ISO-8601 -> aware datetime (UTC). Gibt None bei Unparsebarem."""
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def start_of_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def period_bounds(now: datetime, period: str, week_start: int = 0) -> tuple[datetime, datetime]:
    """(start, end) der Periode, die `now` (aware, lokal) enthält.

    - day:   Kalendertag [00:00, +1 Tag)
    - week:  konfigurierbarer Wochenstart (0=Montag … 6=Sonntag), [start, +7 Tage)
    - month: Kalendermonat [1., 00:00, 1. des Folgemonats)
    end ist exklusiv.
    """
    day = start_of_day(now)
    if period == PERIOD_DAY:
        return day, day + timedelta(days=1)
    if period == PERIOD_WEEK:
        delta = (now.weekday() - week_start) % 7
        start = day - timedelta(days=delta)
        return start, start + timedelta(days=7)
    if period == PERIOD_MONTH:
        start = day.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    raise ValueError(f"Unbekannter Perioden-Typ: {period}")


def previous_period_bounds(
    now: datetime, period: str, week_start: int = 0
) -> tuple[datetime, datetime]:
    """Grenzen der VORHERIGEN abgeschlossenen Periode."""
    start, _end = period_bounds(now, period, week_start)
    # Ein Zeitpunkt kurz vor dem aktuellen Start liegt in der Vorperiode.
    prev_ref = start - timedelta(seconds=1)
    return period_bounds(prev_ref, period, week_start)


def count_executions(
    executions: list[dict],
    person_id: str | None,
    task_id: str | None,
    start: datetime | None,
    end: datetime | None,
) -> int:
    """Anzahl passender Ausführungen im halboffenen Intervall [start, end)."""
    total = 0
    for ex in executions:
        if person_id is not None and ex.get(F_PERSON_ID) != person_id:
            continue
        if task_id is not None and ex.get(F_TASK_ID) != task_id:
            continue
        ts = parse_ts(ex.get(F_TIMESTAMP, ""))
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts >= end:
            continue
        total += 1
    return total


def sum_points(
    executions: list[dict],
    tasks_by_id: dict[str, dict],
    person_id: str | None,
    start: datetime | None,
    end: datetime | None,
) -> float:
    """Summe der Punkte (Gewicht je Aufgabe, Default 1) passender Ausführungen."""
    total = 0.0
    for ex in executions:
        if person_id is not None and ex.get(F_PERSON_ID) != person_id:
            continue
        ts = parse_ts(ex.get(F_TIMESTAMP, ""))
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts >= end:
            continue
        task = tasks_by_id.get(ex.get(F_TASK_ID))
        pts = task.get(F_POINTS, 1) if task else 1
        try:
            total += float(pts)
        except (TypeError, ValueError):
            total += 1.0
    return total


def evaluate_target(
    target: dict,
    executions: list[dict],
    now: datetime,
    week_start: int = 0,
) -> dict:
    """Ist/Soll/Rest/Erfüllungsgrad der LAUFENDEN Periode für eine Vorgabe.

    on_track = die Person hält das nötige Tempo (Ist >= anteilig erwartetem Soll bis
    jetzt). Bei erfülltem Soll (Rest == 0) immer True.
    """
    period = target.get(F_PERIOD, PERIOD_WEEK)
    count = int(target.get(F_COUNT, 0) or 0)
    start, end = period_bounds(now, period, week_start)
    ist = count_executions(executions, target.get(F_PERSON_ID), target.get(F_TASK_ID), start, end)
    rest = max(0, count - ist)
    percent = round((ist / count) * 100, 1) if count > 0 else 100.0

    # Tempo-basiertes on_track
    total_span = (end - start).total_seconds()
    elapsed = max(0.0, min(1.0, (now - start).total_seconds() / total_span)) if total_span else 1.0
    required_so_far = count * elapsed
    on_track = (rest == 0) or (ist + 1e-9 >= required_so_far)

    return {
        F_ID: target.get(F_ID),
        F_PERSON_ID: target.get(F_PERSON_ID),
        F_TASK_ID: target.get(F_TASK_ID),
        F_PERIOD: period,
        F_COUNT: count,
        "ist": ist,
        "rest": rest,
        "percent": percent,
        "on_track": on_track,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }

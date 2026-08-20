"""Reine Berechnungslogik (targets.py) — ohne laufendes Home Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from custom_components.hausarbeit.const import (
    PERIOD_DAY,
    PERIOD_WEEK,
    PERIOD_MONTH,
    F_ID,
    F_PERSON_ID,
    F_TASK_ID,
    F_PERIOD,
    F_COUNT,
    F_TIMESTAMP,
    F_POINTS,
)
from custom_components.hausarbeit.targets import (
    parse_ts,
    start_of_day,
    period_bounds,
    previous_period_bounds,
    count_executions,
    sum_points,
    evaluate_target,
)

BERLIN = ZoneInfo("Europe/Berlin")


def dt(y, m, d, h=0, mi=0, s=0):
    return datetime(y, m, d, h, mi, s, tzinfo=BERLIN)


def _ex(person, task, ts: datetime):
    return {F_PERSON_ID: person, F_TASK_ID: task, F_TIMESTAMP: ts.isoformat()}


# --------------------------------------------------------------------------- #
# parse_ts
# --------------------------------------------------------------------------- #
def test_parse_ts_z_suffix():
    d = parse_ts("2026-01-01T00:00:00Z")
    assert d == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert d.tzinfo is not None


def test_parse_ts_offset():
    d = parse_ts("2026-01-01T00:00:00+00:00")
    assert d == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_parse_ts_naive_becomes_utc():
    d = parse_ts("2026-01-01T12:00:00")
    assert d.tzinfo is timezone.utc


def test_parse_ts_none_and_empty():
    assert parse_ts(None) is None
    assert parse_ts("") is None
    assert parse_ts("kein-datum") is None


# --------------------------------------------------------------------------- #
# period_bounds — day
# --------------------------------------------------------------------------- #
def test_period_bounds_day():
    now = dt(2026, 1, 15, 14, 30)
    start, end = period_bounds(now, PERIOD_DAY)
    assert start == dt(2026, 1, 15, 0, 0)
    assert end == dt(2026, 1, 16, 0, 0)
    # end exklusiv
    assert start <= now < end


def test_period_bounds_day_month_end():
    now = dt(2026, 1, 31, 23, 59)
    start, end = period_bounds(now, PERIOD_DAY)
    assert start == dt(2026, 1, 31, 0, 0)
    assert end == dt(2026, 2, 1, 0, 0)


# --------------------------------------------------------------------------- #
# period_bounds — week (Wochenstart 0 = Montag, 6 = Sonntag)
# --------------------------------------------------------------------------- #
def test_period_bounds_week_monday_start():
    # 2026-01-15 ist ein Donnerstag (weekday 3)
    now = dt(2026, 1, 15, 8, 0)
    assert now.weekday() == 3
    start, end = period_bounds(now, PERIOD_WEEK, week_start=0)
    assert start == dt(2026, 1, 12, 0, 0)   # Montag
    assert end == dt(2026, 1, 19, 0, 0)     # Montag darauf, exklusiv
    assert (end - start) == timedelta(days=7)


def test_period_bounds_week_sunday_start():
    now = dt(2026, 1, 15, 8, 0)
    start, end = period_bounds(now, PERIOD_WEEK, week_start=6)
    assert start == dt(2026, 1, 11, 0, 0)   # Sonntag
    assert end == dt(2026, 1, 18, 0, 0)
    assert start.weekday() == 6


def test_period_bounds_week_on_start_day():
    # now genau am Wochenstart -> start == Kalendertag
    now = dt(2026, 1, 12, 9, 0)  # Montag
    start, end = period_bounds(now, PERIOD_WEEK, week_start=0)
    assert start == dt(2026, 1, 12, 0, 0)
    assert end == dt(2026, 1, 19, 0, 0)


# --------------------------------------------------------------------------- #
# period_bounds — month (inkl. Jahreswechsel)
# --------------------------------------------------------------------------- #
def test_period_bounds_month():
    now = dt(2026, 1, 15, 12, 0)
    start, end = period_bounds(now, PERIOD_MONTH)
    assert start == dt(2026, 1, 1, 0, 0)
    assert end == dt(2026, 2, 1, 0, 0)


def test_period_bounds_month_december_year_rollover():
    now = dt(2025, 12, 20, 12, 0)
    start, end = period_bounds(now, PERIOD_MONTH)
    assert start == dt(2025, 12, 1, 0, 0)
    assert end == dt(2026, 1, 1, 0, 0)


def test_period_bounds_unknown_raises():
    with pytest.raises(ValueError):
        period_bounds(dt(2026, 1, 1), "jahrzehnt")


def test_start_of_day():
    assert start_of_day(dt(2026, 5, 6, 23, 59, 59)) == dt(2026, 5, 6, 0, 0, 0)


# --------------------------------------------------------------------------- #
# previous_period_bounds
# --------------------------------------------------------------------------- #
def test_previous_period_bounds_day():
    now = dt(2026, 1, 15, 14, 0)
    start, end = previous_period_bounds(now, PERIOD_DAY)
    assert start == dt(2026, 1, 14, 0, 0)
    assert end == dt(2026, 1, 15, 0, 0)


def test_previous_period_bounds_week():
    now = dt(2026, 1, 15, 8, 0)
    start, end = previous_period_bounds(now, PERIOD_WEEK, week_start=0)
    assert start == dt(2026, 1, 5, 0, 0)    # Montag der Vorwoche
    assert end == dt(2026, 1, 12, 0, 0)


def test_previous_period_bounds_month_year_rollover():
    now = dt(2026, 1, 15, 8, 0)
    start, end = previous_period_bounds(now, PERIOD_MONTH)
    assert start == dt(2025, 12, 1, 0, 0)
    assert end == dt(2026, 1, 1, 0, 0)


# --------------------------------------------------------------------------- #
# count_executions — Grenzfälle start (inkl.) / end (exkl.)
# --------------------------------------------------------------------------- #
def test_count_executions_boundaries():
    start = dt(2026, 1, 15, 0, 0)
    end = dt(2026, 1, 16, 0, 0)
    executions = [
        _ex("p1", "t1", start - timedelta(seconds=1)),  # vor start -> raus
        _ex("p1", "t1", start),                          # genau start -> rein
        _ex("p1", "t1", dt(2026, 1, 15, 12, 0)),         # mittig -> rein
        _ex("p1", "t1", end - timedelta(seconds=1)),     # kurz vor end -> rein
        _ex("p1", "t1", end),                            # genau end -> raus (exklusiv)
    ]
    assert count_executions(executions, "p1", "t1", start, end) == 3


def test_count_executions_person_task_filter():
    start = dt(2026, 1, 15, 0, 0)
    end = dt(2026, 1, 16, 0, 0)
    executions = [
        _ex("p1", "t1", dt(2026, 1, 15, 6)),
        _ex("p2", "t1", dt(2026, 1, 15, 7)),
        _ex("p1", "t2", dt(2026, 1, 15, 8)),
    ]
    assert count_executions(executions, "p1", None, start, end) == 2
    assert count_executions(executions, None, "t1", start, end) == 2
    assert count_executions(executions, "p1", "t1", start, end) == 1
    assert count_executions(executions, None, None, start, end) == 3


def test_count_executions_ignores_unparseable_ts():
    executions = [{F_PERSON_ID: "p1", F_TASK_ID: "t1", F_TIMESTAMP: "kaputt"}]
    assert count_executions(executions, "p1", "t1", None, None) == 0


def test_count_executions_open_bounds():
    executions = [_ex("p1", "t1", dt(2026, 1, 1)), _ex("p1", "t1", dt(2026, 6, 1))]
    assert count_executions(executions, "p1", "t1", None, None) == 2


# --------------------------------------------------------------------------- #
# sum_points — Gewichtung je Aufgabe (Default 1)
# --------------------------------------------------------------------------- #
def test_sum_points_weighting():
    tasks_by_id = {
        "t1": {F_ID: "t1", F_POINTS: 3},
        "t2": {F_ID: "t2"},  # kein points -> Default 1
    }
    executions = [
        _ex("p1", "t1", dt(2026, 1, 15, 6)),
        _ex("p1", "t2", dt(2026, 1, 15, 7)),
        _ex("p1", "t2", dt(2026, 1, 15, 8)),
    ]
    # 3 + 1 + 1 = 5
    assert sum_points(executions, tasks_by_id, "p1", None, None) == 5.0


def test_sum_points_unknown_task_defaults_to_one():
    executions = [_ex("p1", "tX", dt(2026, 1, 15, 6))]
    assert sum_points(executions, {}, "p1", None, None) == 1.0


def test_sum_points_bad_points_value_defaults_to_one():
    tasks_by_id = {"t1": {F_ID: "t1", F_POINTS: "abc"}}
    executions = [_ex("p1", "t1", dt(2026, 1, 15, 6))]
    assert sum_points(executions, tasks_by_id, "p1", None, None) == 1.0


# --------------------------------------------------------------------------- #
# evaluate_target — ist/rest/percent/on_track
# --------------------------------------------------------------------------- #
def _target(count, period=PERIOD_WEEK, person="p1", task="t1", tid="tgt_1"):
    return {
        F_ID: tid,
        F_PERSON_ID: person,
        F_TASK_ID: task,
        F_PERIOD: period,
        F_COUNT: count,
    }


def test_evaluate_target_fulfilled_is_on_track():
    now = dt(2026, 1, 15, 12, 0)  # Donnerstag -> Woche Mo 12. – So 18.
    executions = [
        _ex("p1", "t1", dt(2026, 1, 13, 9)),
        _ex("p1", "t1", dt(2026, 1, 14, 9)),
    ]
    ev = evaluate_target(_target(2), executions, now, week_start=0)
    assert ev["ist"] == 2
    assert ev["rest"] == 0
    assert ev["percent"] == 100.0
    assert ev["on_track"] is True


def test_evaluate_target_early_zero_is_on_track():
    # now genau am Perioden-Start (day) -> elapsed 0 -> required 0 -> on_track True
    now = dt(2026, 1, 15, 0, 0)
    ev = evaluate_target(_target(3, period=PERIOD_DAY), [], now, week_start=0)
    assert ev["ist"] == 0
    assert ev["rest"] == 3
    assert ev["percent"] == 0.0
    assert ev["on_track"] is True


def test_evaluate_target_late_zero_not_on_track():
    # spät am Tag, nichts erledigt -> Tempo nicht gehalten
    now = dt(2026, 1, 15, 23, 59)
    ev = evaluate_target(_target(1, period=PERIOD_DAY), [], now, week_start=0)
    assert ev["ist"] == 0
    assert ev["rest"] == 1
    assert ev["on_track"] is False


def test_evaluate_target_percent_and_partial():
    now = dt(2026, 1, 15, 12, 0)
    executions = [_ex("p1", "t1", dt(2026, 1, 13, 9))]
    ev = evaluate_target(_target(4), executions, now, week_start=0)
    assert ev["ist"] == 1
    assert ev["rest"] == 3
    assert ev["percent"] == 25.0


def test_evaluate_target_count_zero_percent_100():
    now = dt(2026, 1, 15, 12, 0)
    ev = evaluate_target(_target(0), [], now, week_start=0)
    assert ev["percent"] == 100.0
    assert ev["rest"] == 0
    assert ev["on_track"] is True


def test_evaluate_target_reports_period_bounds():
    now = dt(2026, 1, 15, 12, 0)
    ev = evaluate_target(_target(1, period=PERIOD_MONTH), [], now, week_start=0)
    assert ev["period_start"].startswith("2026-01-01")
    assert ev["period_end"].startswith("2026-02-01")
    assert ev[F_PERIOD] == PERIOD_MONTH

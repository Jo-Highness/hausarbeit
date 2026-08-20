"""Coordinator-Statistik & Zeitfenster."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util

from custom_components.hausarbeit.const import F_PERSON_ID, F_TASK_ID


async def test_build_stats_ranking_and_shares(setup_integration, hass):
    _entry, coordinator = setup_integration
    alice = coordinator.add_person("Alice")
    bob = coordinator.add_person("Bob")
    spuelen = coordinator.add_task("Spülen")
    muell = coordinator.add_task("Müll")

    # Alice 3, Bob 1
    for _ in range(2):
        coordinator.log_execution(alice["id"], spuelen["id"])
    coordinator.log_execution(alice["id"], muell["id"])
    coordinator.log_execution(bob["id"], muell["id"])

    stats = coordinator.build_stats(days=90)
    assert stats["total"] == 4

    ranking = stats["ranking"]
    assert ranking[0][F_PERSON_ID] == alice["id"]
    assert ranking[0]["count"] == 3
    assert ranking[1][F_PERSON_ID] == bob["id"]
    assert ranking[1]["count"] == 1

    # Anteile summieren sich ~100
    assert round(sum(r["share_percent"] for r in ranking)) == 100

    # per_task
    per_task = {pt[F_TASK_ID]: pt for pt in stats["per_task"]}
    assert per_task[spuelen["id"]]["count"] == 2
    assert per_task[muell["id"]]["count"] == 2

    # per_person Fenster vorhanden
    pp = {p[F_PERSON_ID]: p for p in stats["per_person"]}
    for key in ("today", "d7", "d30", "d90", "current_month", "total"):
        assert key in pp[alice["id"]]
    assert pp[alice["id"]]["total"] == 3


async def test_person_windows_time_buckets(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Zeitreisende")
    t = coordinator.add_task("Kehren")

    now = dt_util.utcnow()
    # jetzt
    coordinator.log_execution(p["id"], t["id"], ts=now)
    # vor 40 Tagen -> in d90, aber nicht d30
    coordinator.log_execution(p["id"], t["id"], ts=now - timedelta(days=40))

    windows = coordinator.person_windows(p["id"], dt_util.now())
    assert windows["total"] == 2
    assert windows["d90"] == 2
    assert windows["d30"] == 1
    assert windows["d7"] == 1


async def test_build_stats_default_days_from_options(setup_integration, hass):
    _entry, coordinator = setup_integration
    stats = coordinator.build_stats()
    assert stats["days"] == coordinator.stats_days == 90


async def test_evaluate_targets_enriches_names(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Nina")
    t = coordinator.add_task("Kochen")
    coordinator.set_target(p["id"], t["id"], "week", 3)
    evs = coordinator.evaluate_targets()
    assert len(evs) == 1
    assert evs[0]["person_name"] == "Nina"
    assert evs[0]["task_name"] == "Kochen"
    assert evs[0]["count"] == 3


async def test_last_done(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Otto")
    t = coordinator.add_task("Fegen")
    now = dt_util.utcnow()
    coordinator.log_execution(p["id"], t["id"], ts=now - timedelta(days=2))
    coordinator.log_execution(p["id"], t["id"], ts=now)  # jüngste
    info = coordinator.last_done(t["id"])
    assert info is not None
    assert info[F_PERSON_ID] == p["id"]
    assert info["person_name"] == "Otto"
    # jüngster Zeitstempel
    assert info["ts"].startswith(now.strftime("%Y-%m-%d"))
    assert coordinator.last_done("tsk_nichtvorhanden") is None

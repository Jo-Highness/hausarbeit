"""WebSocket-API der Karten: Lesen, Loggen, Sortierung, Berechtigungen."""

from __future__ import annotations


async def _ws(hass, hass_ws_client, token=None):
    return await (hass_ws_client(hass, token) if token else hass_ws_client(hass))


async def _call(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def test_read_commands(setup_integration, hass, hass_ws_client):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    coordinator.set_target(p["id"], t["id"], "week", 2)
    client = await _ws(hass, hass_ws_client)

    res = await _call(client, type="hausarbeit/persons")
    assert res["success"] and res["result"]["persons"][0]["id"] == p["id"]
    res = await _call(client, type="hausarbeit/tasks")
    assert res["result"]["tasks"][0]["id"] == t["id"]
    res = await _call(client, type="hausarbeit/targets")
    assert res["result"]["targets"][0]["count"] == 2
    res = await _call(client, type="hausarbeit/stats", days=30)
    assert res["result"]["days"] == 30
    assert res["result"]["ranking"][0]["person_id"] == p["id"]


async def test_log_sorted_by_real_time(setup_integration, hass, hass_ws_client):
    """Sortierung nach Zeitpunkt, nicht nach String (Offsets!)."""
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    # Legacy-Datensätze mit unterschiedlichen Offsets direkt im Store
    coordinator.store.executions.extend(
        [
            # 10:30 UTC
            {
                "id": "exe_a",
                "person_id": p["id"],
                "task_id": t["id"],
                "ts": "2026-10-01T12:30:00+02:00",
            },
            # 11:00 UTC (neuester) — als String „kleiner“ als der erste
            {
                "id": "exe_b",
                "person_id": p["id"],
                "task_id": t["id"],
                "ts": "2026-10-01T11:00:00+00:00",
            },
            # 09:00 UTC
            {"id": "exe_c", "person_id": p["id"], "task_id": t["id"], "ts": "2026-10-01T09:00:00Z"},
        ]
    )
    client = await _ws(hass, hass_ws_client)
    res = await _call(client, type="hausarbeit/log", limit=10)
    assert [e["id"] for e in res["result"]["executions"]] == ["exe_b", "exe_a", "exe_c"]
    assert res["result"]["total"] == 3


async def test_log_execution_normalizes_to_utc(setup_integration, hass, hass_ws_client):
    await hass.config.async_set_time_zone("Europe/Berlin")
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    client = await _ws(hass, hass_ws_client)

    # Offset -> UTC
    res = await _call(
        client,
        type="hausarbeit/log_execution",
        person_id=p["id"],
        task_id=t["id"],
        ts="2026-10-01T12:30:00+02:00",
    )
    assert res["success"]
    assert res["result"]["execution"]["ts"] == "2026-10-01T10:30:00+00:00"

    # ohne Zeitzone -> lokale HA-Zeit (Berlin, Sommerzeit = UTC+2)
    res = await _call(
        client,
        type="hausarbeit/log_execution",
        person_id=p["id"],
        task_id=t["id"],
        ts="2026-10-01T08:00:00",
    )
    assert res["result"]["execution"]["ts"] == "2026-10-01T06:00:00+00:00"

    # unlesbar -> Fehler
    res = await _call(
        client, type="hausarbeit/log_execution", person_id=p["id"], task_id=t["id"], ts="gestern"
    )
    assert not res["success"]
    assert res["error"]["code"] == "invalid_input"


async def test_non_admin_can_log_and_undo_own(
    setup_integration, hass, hass_ws_client, hass_read_only_access_token, hass_read_only_user
):
    """Familienmitglieder (Nicht-Admins) dürfen loggen und ihren eigenen Eintrag zurücknehmen."""
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Kind")
    t = coordinator.add_task("Tisch decken")
    client = await _ws(hass, hass_ws_client, hass_read_only_access_token)

    res = await _call(client, type="hausarbeit/log_execution", person_id=p["id"], task_id=t["id"])
    assert res["success"]
    exe_id = res["result"]["execution_id"]
    assert coordinator.store.get_execution(exe_id)["user_id"] == hass_read_only_user.id

    res = await _call(client, type="hausarbeit/delete_execution", execution_id=exe_id)
    assert res["success"]
    assert coordinator.store.get_execution(exe_id) is None


async def test_non_admin_cannot_delete_foreign_entry(
    setup_integration, hass, hass_ws_client, hass_read_only_access_token
):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    foreign = coordinator.log_execution(p["id"], t["id"])  # z. B. per Automation
    client = await _ws(hass, hass_ws_client, hass_read_only_access_token)

    res = await _call(client, type="hausarbeit/delete_execution", execution_id=foreign["id"])
    assert not res["success"]
    assert res["error"]["code"] == "unauthorized"
    assert coordinator.store.get_execution(foreign["id"]) is not None


async def test_admin_can_delete_any_entry(setup_integration, hass, hass_ws_client):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Anna")
    t = coordinator.add_task("Spülen")
    ex = coordinator.log_execution(p["id"], t["id"])
    client = await _ws(hass, hass_ws_client)
    res = await _call(client, type="hausarbeit/delete_execution", execution_id=ex["id"])
    assert res["success"]
    res = await _call(client, type="hausarbeit/delete_execution", execution_id=ex["id"])
    assert res["error"]["code"] == "not_found"


async def test_subscribe_pushes_updates(setup_integration, hass, hass_ws_client):
    _entry, coordinator = setup_integration
    client = await _ws(hass, hass_ws_client)
    res = await _call(client, type="hausarbeit/subscribe")
    assert res["success"]
    coordinator.add_person("Neu")
    event = await client.receive_json()
    assert event["type"] == "event"
    assert event["event"] == {"event": "updated"}


async def test_not_ready_without_entry(hass, hass_ws_client):
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "hausarbeit", {})
    client = await _ws(hass, hass_ws_client)
    res = await _call(client, type="hausarbeit/persons")
    assert not res["success"]
    assert res["error"]["code"] == "not_ready"

"""WebSocket-API für die Lovelace-Karten.

Lese-Kommandos (persons/tasks/targets/log/stats) und bequeme Aktions-Kommandos
(log_execution/delete_execution), plus ein subscribe-Kommando, das bei jeder
Datenänderung ein {event:"updated"} pusht.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    WS_TASKS,
    WS_PERSONS,
    WS_TARGETS,
    WS_LOG,
    WS_STATS,
    WS_LOG_EXECUTION,
    WS_DELETE_EXECUTION,
    WS_SUBSCRIBE,
    F_PERSON_ID,
    F_TASK_ID,
    F_TIMESTAMP,
    F_NOTE,
    F_ID,
    ATTR_EXECUTION_ID,
)
from .coordinator import HausarbeitCoordinator, HausarbeitError

_REGISTERED = f"{DOMAIN}_ws_registered"


def _coordinator(hass: HomeAssistant) -> HausarbeitCoordinator | None:
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, HausarbeitCoordinator):
            return value
    return None


@callback
def async_register(hass: HomeAssistant) -> None:
    if hass.data.get(_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_persons)
    websocket_api.async_register_command(hass, ws_tasks)
    websocket_api.async_register_command(hass, ws_targets)
    websocket_api.async_register_command(hass, ws_log)
    websocket_api.async_register_command(hass, ws_stats)
    websocket_api.async_register_command(hass, ws_log_execution)
    websocket_api.async_register_command(hass, ws_delete_execution)
    websocket_api.async_register_command(hass, ws_subscribe)
    hass.data[_REGISTERED] = True


def _require(hass, connection, msg) -> HausarbeitCoordinator | None:
    coord = _coordinator(hass)
    if coord is None:
        connection.send_error(msg["id"], "not_ready", "Hausarbeit-Tracker ist nicht eingerichtet.")
        return None
    return coord


@websocket_api.websocket_command({vol.Required("type"): WS_PERSONS})
@callback
def ws_persons(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if coord:
        connection.send_result(msg["id"], {"persons": coord.store.persons})


@websocket_api.websocket_command({vol.Required("type"): WS_TASKS})
@callback
def ws_tasks(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if coord:
        connection.send_result(msg["id"], {"tasks": coord.store.tasks})


@websocket_api.websocket_command({vol.Required("type"): WS_TARGETS})
@callback
def ws_targets(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if coord:
        connection.send_result(msg["id"], {"targets": coord.evaluate_targets()})


@websocket_api.websocket_command({
    vol.Required("type"): WS_LOG,
    vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=100000)),
    vol.Optional(F_PERSON_ID): str,
    vol.Optional(F_TASK_ID): str,
})
@callback
def ws_log(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if not coord:
        return
    person_id = msg.get(F_PERSON_ID)
    task_id = msg.get(F_TASK_ID)
    items = []
    for ex in coord.store.executions:
        if person_id and ex.get(F_PERSON_ID) != person_id:
            continue
        if task_id and ex.get(F_TASK_ID) != task_id:
            continue
        items.append({
            **ex,
            "person_name": coord.person_name(ex.get(F_PERSON_ID)),
            "task_name": coord.task_name(ex.get(F_TASK_ID)),
        })
    total = len(items)
    items.sort(key=lambda e: e.get(F_TIMESTAMP, ""), reverse=True)
    connection.send_result(msg["id"], {"executions": items[: msg["limit"]], "total": total})


@websocket_api.websocket_command({
    vol.Required("type"): WS_STATS,
    vol.Optional("days"): vol.All(int, vol.Range(min=1, max=3650)),
})
@callback
def ws_stats(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if coord:
        connection.send_result(msg["id"], coord.build_stats(msg.get("days")))


@websocket_api.websocket_command({
    vol.Required("type"): WS_LOG_EXECUTION,
    vol.Required(F_PERSON_ID): str,
    vol.Required(F_TASK_ID): str,
    vol.Optional(F_TIMESTAMP): str,
    vol.Optional(F_NOTE): str,
})
@callback
def ws_log_execution(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if not coord:
        return
    try:
        ex = coord.log_execution(
            msg[F_PERSON_ID], msg[F_TASK_ID],
            ts=msg.get(F_TIMESTAMP), note=msg.get(F_NOTE),
        )
    except HausarbeitError as err:
        connection.send_error(msg["id"], "invalid_input", str(err))
        return
    connection.send_result(msg["id"], {ATTR_EXECUTION_ID: ex[F_ID], "execution": ex})


@websocket_api.websocket_command({
    vol.Required("type"): WS_DELETE_EXECUTION,
    vol.Required(ATTR_EXECUTION_ID): str,
})
@callback
def ws_delete_execution(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if not coord:
        return
    try:
        coord.delete_execution(msg[ATTR_EXECUTION_ID])
    except HausarbeitError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({vol.Required("type"): WS_SUBSCRIBE})
@callback
def ws_subscribe(hass, connection, msg) -> None:
    coord = _require(hass, connection, msg)
    if not coord:
        return

    @callback
    def _forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"event": "updated"}))

    unsub = async_dispatcher_connect(hass, coord.signal, _forward)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])

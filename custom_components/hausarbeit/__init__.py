"""Hausarbeit-Tracker — Integration Setup.

Ein Config-Entry pro Haushalt. Registriert Coordinator, Sensor-Plattform, Services,
die WebSocket-API und liefert die drei Lovelace-Karten automatisch als Frontend-
Ressource aus (kein separates HACS-Frontend-Paket nötig).
"""

from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from . import websocket as ws_api
from .const import (
    ATTR_EXECUTION_ID,
    ATTR_TARGET_ID,
    DOMAIN,
    F_ACTIVE,
    F_CATEGORY,
    F_COLOR,
    F_COUNT,
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
    FRONTEND_DIR,
    FRONTEND_URL_BASE,
    LOVELACE_CARDS,
    PERIODS,
    PLATFORMS,
    SERVICE_ADD_PERSON,
    SERVICE_ADD_TASK,
    SERVICE_CORRECT_EXECUTION,
    SERVICE_DELETE_EXECUTION,
    SERVICE_LOG_EXECUTION,
    SERVICE_REMOVE_PERSON,
    SERVICE_REMOVE_TARGET,
    SERVICE_REMOVE_TASK,
    SERVICE_SET_TARGET,
    SERVICE_UPDATE_PERSON,
    SERVICE_UPDATE_TASK,
    VERSION,
)
from .coordinator import HausarbeitCoordinator, HausarbeitError

_LOGGER = logging.getLogger(__name__)

_STATIC_REGISTERED = f"{DOMAIN}_static_registered"
_SERVICES_REGISTERED = f"{DOMAIN}_services_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Entry einrichten."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HausarbeitCoordinator(hass, entry)
    await coordinator.async_init()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await _async_register_frontend(hass)
    ws_api.async_register(hass)
    _async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Entry entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            # letzter Entry -> Services abmelden
            for service in (
                SERVICE_LOG_EXECUTION,
                SERVICE_DELETE_EXECUTION,
                SERVICE_CORRECT_EXECUTION,
                SERVICE_ADD_TASK,
                SERVICE_UPDATE_TASK,
                SERVICE_REMOVE_TASK,
                SERVICE_ADD_PERSON,
                SERVICE_UPDATE_PERSON,
                SERVICE_REMOVE_PERSON,
                SERVICE_SET_TARGET,
                SERVICE_REMOVE_TARGET,
            ):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
            hass.data.pop(_SERVICES_REGISTERED, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bei geänderten Optionen Sensoren neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Karten-JS als statische Ressource ausliefern + automatisch laden."""
    if hass.data.get(_STATIC_REGISTERED):
        return
    # Statische Auslieferung sofort registrieren (http ist eine harte Dependency).
    # Defensiv: scheitert nur in einer minimalen Test-/Headless-Umgebung ohne http.
    try:
        from homeassistant.components.http import StaticPathConfig

        frontend_path = os.path.join(os.path.dirname(__file__), FRONTEND_DIR)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, frontend_path, cache_headers=False)]
        )
        hass.data[_STATIC_REGISTERED] = True
    except Exception as err:
        _LOGGER.warning("Hausarbeit-Frontend-Pfad nicht registrierbar: %s", err)
        return

    # Die Karten-Module erst laden, wenn das frontend-Setup seine Datenstruktur
    # angelegt hat. add_extra_js_url() direkt im async_setup aufzurufen scheitert
    # sonst mit KeyError 'frontend_extra_module_url'. frontend bleibt bewusst nur
    # eine after_dependency (keine harte Dependency), damit die Tests ohne das
    # volle frontend-Setup laufen.
    @callback
    def _register_modules(_hass: HomeAssistant) -> None:
        try:
            from homeassistant.components.frontend import add_extra_js_url

            for filename, _card_type in LOVELACE_CARDS:
                add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{filename}?v={VERSION}")
            _LOGGER.debug("Hausarbeit-Karten registriert unter %s", FRONTEND_URL_BASE)
        except Exception as err:
            _LOGGER.warning("Frontend-Karten konnten nicht registriert werden: %s", err)

    from homeassistant.helpers.start import async_at_start

    async_at_start(hass, _register_modules)


# --------------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------------- #
def _first_coordinator(hass: HomeAssistant) -> HausarbeitCoordinator:
    coordinators = [
        c for c in hass.data.get(DOMAIN, {}).values() if isinstance(c, HausarbeitCoordinator)
    ]
    if not coordinators:
        raise ServiceValidationError("Hausarbeit-Tracker ist nicht eingerichtet.")
    return coordinators[0]


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.data.get(_SERVICES_REGISTERED):
        return

    def coord() -> HausarbeitCoordinator:
        return _first_coordinator(hass)

    # Die Coordinator-Methoden sind nicht-blockierend (nur In-Memory + debounced save),
    # daher direkt im Event-Loop ausführbar.
    def log_execution(call: ServiceCall):
        c = coord()
        ex = c.log_execution(
            call.data[F_PERSON_ID],
            call.data[F_TASK_ID],
            ts=call.data.get(F_TIMESTAMP),
            note=call.data.get(F_NOTE),
        )
        return {ATTR_EXECUTION_ID: ex[F_ID]}

    def delete_execution(call: ServiceCall):
        coord().delete_execution(call.data[ATTR_EXECUTION_ID])

    def correct_execution(call: ServiceCall):
        coord().correct_execution(
            call.data[ATTR_EXECUTION_ID],
            person_id=call.data.get(F_PERSON_ID),
            task_id=call.data.get(F_TASK_ID),
            ts=call.data.get(F_TIMESTAMP),
            note=call.data.get(F_NOTE),
        )

    def add_task(call: ServiceCall):
        t = coord().add_task(
            call.data[F_NAME],
            icon=call.data.get(F_ICON),
            category=call.data.get(F_CATEGORY),
            points=call.data.get(F_POINTS),
            active=call.data.get(F_ACTIVE),
        )
        return {F_ID: t[F_ID]}

    def update_task(call: ServiceCall):
        changes = {
            k: call.data[k]
            for k in (F_NAME, F_ICON, F_CATEGORY, F_POINTS, F_ACTIVE)
            if k in call.data
        }
        coord().update_task(call.data[F_TASK_ID], **changes)

    def remove_task(call: ServiceCall):
        coord().remove_task(call.data[F_TASK_ID])

    def add_person(call: ServiceCall):
        p = coord().add_person(
            call.data[F_NAME],
            icon=call.data.get(F_ICON),
            color=call.data.get(F_COLOR),
            ha_person_entity=call.data.get(F_HA_PERSON),
        )
        return {F_ID: p[F_ID]}

    def update_person(call: ServiceCall):
        changes = {
            k: call.data[k] for k in (F_NAME, F_ICON, F_COLOR, F_HA_PERSON) if k in call.data
        }
        coord().update_person(call.data[F_PERSON_ID], **changes)

    def remove_person(call: ServiceCall):
        coord().remove_person(call.data[F_PERSON_ID])

    def set_target(call: ServiceCall):
        t = coord().set_target(
            call.data[F_PERSON_ID],
            call.data[F_TASK_ID],
            call.data[F_PERIOD],
            call.data[F_COUNT],
        )
        return {ATTR_TARGET_ID: t[F_ID]}

    def remove_target(call: ServiceCall):
        coord().remove_target(call.data[ATTR_TARGET_ID])

    def make(func, returns: bool = False):
        async def handler(call: ServiceCall):
            try:
                result = func(call)
            except HausarbeitError as err:
                raise ServiceValidationError(str(err)) from err
            except HomeAssistantError:
                raise
            except Exception as err:
                raise HomeAssistantError(str(err)) from err
            return result if returns else None

        return handler

    from homeassistant.core import SupportsResponse

    services = [
        (
            SERVICE_LOG_EXECUTION,
            make(log_execution, True),
            vol.Schema(
                {
                    vol.Required(F_PERSON_ID): cv.string,
                    vol.Required(F_TASK_ID): cv.string,
                    vol.Optional(F_TIMESTAMP): cv.datetime,
                    vol.Optional(F_NOTE): cv.string,
                }
            ),
            SupportsResponse.OPTIONAL,
        ),
        (
            SERVICE_DELETE_EXECUTION,
            make(delete_execution),
            vol.Schema(
                {
                    vol.Required(ATTR_EXECUTION_ID): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_CORRECT_EXECUTION,
            make(correct_execution),
            vol.Schema(
                {
                    vol.Required(ATTR_EXECUTION_ID): cv.string,
                    vol.Optional(F_PERSON_ID): cv.string,
                    vol.Optional(F_TASK_ID): cv.string,
                    vol.Optional(F_TIMESTAMP): cv.datetime,
                    vol.Optional(F_NOTE): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_ADD_TASK,
            make(add_task, True),
            vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_CATEGORY): cv.string,
                    vol.Optional(F_POINTS): vol.Coerce(float),
                    vol.Optional(F_ACTIVE): cv.boolean,
                }
            ),
            SupportsResponse.OPTIONAL,
        ),
        (
            SERVICE_UPDATE_TASK,
            make(update_task),
            vol.Schema(
                {
                    vol.Required(F_TASK_ID): cv.string,
                    vol.Optional(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_CATEGORY): cv.string,
                    vol.Optional(F_POINTS): vol.Coerce(float),
                    vol.Optional(F_ACTIVE): cv.boolean,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_REMOVE_TASK,
            make(remove_task),
            vol.Schema(
                {
                    vol.Required(F_TASK_ID): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_ADD_PERSON,
            make(add_person, True),
            vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_COLOR): cv.string,
                    vol.Optional(F_HA_PERSON): cv.string,
                }
            ),
            SupportsResponse.OPTIONAL,
        ),
        (
            SERVICE_UPDATE_PERSON,
            make(update_person),
            vol.Schema(
                {
                    vol.Required(F_PERSON_ID): cv.string,
                    vol.Optional(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_COLOR): cv.string,
                    vol.Optional(F_HA_PERSON): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_REMOVE_PERSON,
            make(remove_person),
            vol.Schema(
                {
                    vol.Required(F_PERSON_ID): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
        (
            SERVICE_SET_TARGET,
            make(set_target, True),
            vol.Schema(
                {
                    vol.Required(F_PERSON_ID): cv.string,
                    vol.Required(F_TASK_ID): cv.string,
                    vol.Required(F_PERIOD): vol.In(PERIODS),
                    vol.Required(F_COUNT): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            SupportsResponse.OPTIONAL,
        ),
        (
            SERVICE_REMOVE_TARGET,
            make(remove_target),
            vol.Schema(
                {
                    vol.Required(ATTR_TARGET_ID): cv.string,
                }
            ),
            SupportsResponse.NONE,
        ),
    ]

    for name, handler, schema, response in services:
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=response
        )

    hass.data[_SERVICES_REGISTERED] = True

"""Hausarbeit-Tracker — Integration Setup.

Genau ein Config-Entry pro Haushalt (``single_config_entry``). Services und die
WebSocket-API werden einmalig in ``async_setup`` registriert und lösen den geladenen
Entry erst beim Aufruf auf. Die drei Lovelace-Karten werden automatisch als
Frontend-Modul ausgeliefert (kein separates HACS-Frontend-Paket nötig).
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import os

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
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
    MAX_POINTS,
    MIN_POINTS,
    PERIODS,
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
from .store import HausarbeitStore
from .validation import color_value

type HausarbeitConfigEntry = ConfigEntry[HausarbeitCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Punkte/Gewicht: gleiche Grenzen wie der Selektor in services.yaml (0..100).
POINTS_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=MIN_POINTS, max=MAX_POINTS))

_LOGGER = logging.getLogger(__name__)

_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Services und WebSocket-Kommandos einmalig registrieren."""
    _async_register_services(hass)
    ws_api.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HausarbeitConfigEntry) -> bool:
    """Config-Entry einrichten."""
    coordinator = HausarbeitCoordinator(hass, entry)
    await coordinator.async_init()
    entry.runtime_data = coordinator

    await _async_register_frontend(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_timer()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausarbeitConfigEntry) -> bool:
    """Config-Entry entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HausarbeitConfigEntry) -> None:
    """Beim Löschen der Integration auch die gespeicherten Daten entfernen.

    Der Store-Schlüssel ``hausarbeit_data`` bleibt aus Kompatibilitätsgründen global
    (es gibt nur einen Entry). Ohne dieses Aufräumen würde eine Neuinstallation die
    alten Personen/Aufgaben/Log-Einträge wieder einlesen.
    """
    await HausarbeitStore(hass).async_remove()


async def _async_update_listener(hass: HomeAssistant, entry: HausarbeitConfigEntry) -> None:
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
def _loaded_coordinator(hass: HomeAssistant) -> HausarbeitCoordinator:
    """Coordinator des geladenen Entries — oder übersetzter Fehler."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")


def _async_register_services(hass: HomeAssistant) -> None:
    def coord() -> HausarbeitCoordinator:
        return _loaded_coordinator(hass)

    # Die Coordinator-Methoden sind nicht-blockierend (nur In-Memory + debounced save),
    # daher direkt im Event-Loop ausführbar.
    def log_execution(call: ServiceCall):
        ex = coord().log_execution(
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

    def make(func: Callable[[ServiceCall], dict | None], returns: bool = False):
        async def handler(call: ServiceCall):
            try:
                result = func(call)
            except HausarbeitError as err:
                raise ServiceValidationError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key=err.translation_key,
                    translation_placeholders=err.translation_placeholders,
                ) from err
            except HomeAssistantError:
                raise
            except Exception as err:
                _LOGGER.exception("Unexpected error in service %s", call.service)
                raise HomeAssistantError(str(err)) from err
            return result if returns else None

        return handler

    # (name, handler, schema, response, admin_only)
    # Erledigungen melden darf jede*r (auch Nicht-Admins, z. B. Kinder per Dashboard-
    # Button). Alles, was Stammdaten ändert oder Log-Einträge löscht/umschreibt, ist
    # Admins vorbehalten — Automationen/Skripte (ohne Benutzer-Kontext) dürfen alles.
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
            False,
        ),
        (
            SERVICE_DELETE_EXECUTION,
            make(delete_execution),
            vol.Schema({vol.Required(ATTR_EXECUTION_ID): cv.string}),
            SupportsResponse.NONE,
            True,
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
            True,
        ),
        (
            SERVICE_ADD_TASK,
            make(add_task, True),
            vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_CATEGORY): cv.string,
                    vol.Optional(F_POINTS): POINTS_SCHEMA,
                    vol.Optional(F_ACTIVE): cv.boolean,
                }
            ),
            SupportsResponse.OPTIONAL,
            True,
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
                    vol.Optional(F_POINTS): POINTS_SCHEMA,
                    vol.Optional(F_ACTIVE): cv.boolean,
                }
            ),
            SupportsResponse.NONE,
            True,
        ),
        (
            SERVICE_REMOVE_TASK,
            make(remove_task),
            vol.Schema({vol.Required(F_TASK_ID): cv.string}),
            SupportsResponse.NONE,
            True,
        ),
        (
            SERVICE_ADD_PERSON,
            make(add_person, True),
            vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_COLOR): color_value,
                    vol.Optional(F_HA_PERSON): cv.string,
                }
            ),
            SupportsResponse.OPTIONAL,
            True,
        ),
        (
            SERVICE_UPDATE_PERSON,
            make(update_person),
            vol.Schema(
                {
                    vol.Required(F_PERSON_ID): cv.string,
                    vol.Optional(F_NAME): cv.string,
                    vol.Optional(F_ICON): cv.string,
                    vol.Optional(F_COLOR): color_value,
                    vol.Optional(F_HA_PERSON): cv.string,
                }
            ),
            SupportsResponse.NONE,
            True,
        ),
        (
            SERVICE_REMOVE_PERSON,
            make(remove_person),
            vol.Schema({vol.Required(F_PERSON_ID): cv.string}),
            SupportsResponse.NONE,
            True,
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
            True,
        ),
        (
            SERVICE_REMOVE_TARGET,
            make(remove_target),
            vol.Schema({vol.Required(ATTR_TARGET_ID): cv.string}),
            SupportsResponse.NONE,
            True,
        ),
    ]

    for name, handler, schema, response, admin_only in services:
        if admin_only:
            async_register_admin_service(
                hass, DOMAIN, name, handler, schema=schema, supports_response=response
            )
        else:
            hass.services.async_register(
                DOMAIN, name, handler, schema=schema, supports_response=response
            )

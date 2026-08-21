"""Config- und Options-Flow für den Hausarbeit-Tracker (UI-First).

Config-Flow: legt genau einen Haushalts-Eintrag an.
Options-Flow: Einstellungen (Wochenstart, Statistik-Zeitraum) UND vollständige
Verwaltung von Personen, Aufgaben und Soll-Vorgaben (anlegen/ändern/entfernen) —
komplett über die HA-Oberfläche, ohne YAML.
"""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_STATS_DAYS,
    CONF_WEEK_START,
    DEFAULT_STATS_DAYS,
    DEFAULT_TITLE,
    DEFAULT_WEEK_START,
    DOMAIN,
    F_ACTIVE,
    F_CATEGORY,
    F_COLOR,
    F_COUNT,
    F_HA_PERSON,
    F_ICON,
    F_ID,
    F_NAME,
    F_PERIOD,
    F_PERSON_ID,
    F_POINTS,
    F_TASK_ID,
    MAX_STATS_DAYS,
    MIN_STATS_DAYS,
    PERIOD_WEEK,
    PERIODS,
)
from .coordinator import HausarbeitCoordinator, HausarbeitError

WEEKDAYS = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}


class HausarbeitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ersteinrichtung — ein Eintrag pro Haushalt."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get("title") or DEFAULT_TITLE,
                data={},
                options={
                    CONF_WEEK_START: DEFAULT_WEEK_START,
                    CONF_STATS_DAYS: DEFAULT_STATS_DAYS,
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("title", default=DEFAULT_TITLE): cv.string}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HausarbeitOptionsFlow()


class HausarbeitOptionsFlow(config_entries.OptionsFlow):
    """Einstellungen + Verwaltung von Personen/Aufgaben/Soll-Vorgaben.

    `config_entry` wird vom Flow-Manager gesetzt (nicht manuell zuweisen — das ist in
    aktuellen HA-Versionen entfernt).
    """

    _selected: str | None = None

    @property
    def _coord(self) -> HausarbeitCoordinator | None:
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    # -- Hauptmenü ---------------------------------------------------------
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "persons", "tasks", "targets"],
        )

    # -- Einstellungen -----------------------------------------------------
    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_WEEK_START: int(user_input[CONF_WEEK_START]),
                    CONF_STATS_DAYS: int(user_input[CONF_STATS_DAYS]),
                },
            )
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WEEK_START, default=opts.get(CONF_WEEK_START, DEFAULT_WEEK_START)
                    ): vol.In(WEEKDAYS),
                    vol.Required(
                        CONF_STATS_DAYS, default=opts.get(CONF_STATS_DAYS, DEFAULT_STATS_DAYS)
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_STATS_DAYS, max=MAX_STATS_DAYS)),
                }
            ),
        )

    # -- Personen ----------------------------------------------------------
    async def async_step_persons(self, user_input=None):
        self._selected = None  # stale Auswahl aus abgebrochenem Edit verwerfen
        return self.async_show_menu(
            step_id="persons",
            menu_options=["person_add", "person_edit", "person_remove"],
        )

    async def async_step_person_add(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._coord.add_person(
                    user_input[F_NAME],
                    icon=user_input.get(F_ICON) or None,
                    color=user_input.get(F_COLOR) or None,
                    ha_person_entity=user_input.get(F_HA_PERSON) or None,
                )
                return await self.async_step_persons()
            except HausarbeitError as err:
                errors["base"] = "invalid"
                self._err = str(err)
        return self.async_show_form(
            step_id="person_add",
            data_schema=vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON, default="mdi:account"): cv.string,
                    vol.Optional(F_COLOR, default=""): cv.string,
                    vol.Optional(F_HA_PERSON, default=""): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_person_edit(self, user_input=None):
        persons = {p[F_ID]: p[F_NAME] for p in self._coord.store.persons}
        if not persons:
            return await self.async_step_persons()
        if user_input is not None and self._selected is None:
            self._selected = user_input["person"]
            return await self.async_step_person_edit_form()
        return self.async_show_form(
            step_id="person_edit",
            data_schema=vol.Schema({vol.Required("person"): vol.In(persons)}),
        )

    async def async_step_person_edit_form(self, user_input=None):
        person = self._coord.store.get_person(self._selected)
        if person is None:
            self._selected = None
            return await self.async_step_persons()
        if user_input is not None:
            self._coord.update_person(
                self._selected,
                name=user_input[F_NAME],
                icon=user_input.get(F_ICON) or None,
                color=user_input.get(F_COLOR) or None,
                ha_person_entity=user_input.get(F_HA_PERSON) or None,
            )
            self._selected = None
            return await self.async_step_persons()
        return self.async_show_form(
            step_id="person_edit_form",
            data_schema=vol.Schema(
                {
                    vol.Required(F_NAME, default=person.get(F_NAME, "")): cv.string,
                    vol.Optional(F_ICON, default=person.get(F_ICON) or "mdi:account"): cv.string,
                    vol.Optional(F_COLOR, default=person.get(F_COLOR) or ""): cv.string,
                    vol.Optional(F_HA_PERSON, default=person.get(F_HA_PERSON) or ""): cv.string,
                }
            ),
        )

    async def async_step_person_remove(self, user_input=None):
        persons = {p[F_ID]: p[F_NAME] for p in self._coord.store.persons}
        if not persons:
            return await self.async_step_persons()
        if user_input is not None:
            self._coord.remove_person(user_input["person"])
            return await self.async_step_persons()
        return self.async_show_form(
            step_id="person_remove",
            data_schema=vol.Schema({vol.Required("person"): vol.In(persons)}),
        )

    # -- Aufgaben ----------------------------------------------------------
    async def async_step_tasks(self, user_input=None):
        self._selected = None  # stale Auswahl aus abgebrochenem Edit verwerfen
        return self.async_show_menu(
            step_id="tasks",
            menu_options=["task_add", "task_edit", "task_remove"],
        )

    async def async_step_task_add(self, user_input=None):
        if user_input is not None:
            self._coord.add_task(
                user_input[F_NAME],
                icon=user_input.get(F_ICON) or None,
                category=user_input.get(F_CATEGORY) or None,
                points=user_input.get(F_POINTS),
                active=user_input.get(F_ACTIVE, True),
            )
            return await self.async_step_tasks()
        return self.async_show_form(
            step_id="task_add",
            data_schema=vol.Schema(
                {
                    vol.Required(F_NAME): cv.string,
                    vol.Optional(F_ICON, default="mdi:broom"): cv.string,
                    vol.Optional(F_CATEGORY, default=""): cv.string,
                    vol.Optional(F_POINTS, default=1): vol.Coerce(float),
                    vol.Optional(F_ACTIVE, default=True): cv.boolean,
                }
            ),
        )

    async def async_step_task_edit(self, user_input=None):
        tasks = {t[F_ID]: t[F_NAME] for t in self._coord.store.tasks}
        if not tasks:
            return await self.async_step_tasks()
        if user_input is not None and self._selected is None:
            self._selected = user_input["task"]
            return await self.async_step_task_edit_form()
        return self.async_show_form(
            step_id="task_edit",
            data_schema=vol.Schema({vol.Required("task"): vol.In(tasks)}),
        )

    async def async_step_task_edit_form(self, user_input=None):
        task = self._coord.store.get_task(self._selected)
        if task is None:
            self._selected = None
            return await self.async_step_tasks()
        if user_input is not None:
            self._coord.update_task(
                self._selected,
                name=user_input[F_NAME],
                icon=user_input.get(F_ICON) or None,
                category=user_input.get(F_CATEGORY) or None,
                points=user_input.get(F_POINTS),
                active=user_input.get(F_ACTIVE),
            )
            self._selected = None
            return await self.async_step_tasks()
        return self.async_show_form(
            step_id="task_edit_form",
            data_schema=vol.Schema(
                {
                    vol.Required(F_NAME, default=task.get(F_NAME, "")): cv.string,
                    vol.Optional(F_ICON, default=task.get(F_ICON) or "mdi:broom"): cv.string,
                    vol.Optional(F_CATEGORY, default=task.get(F_CATEGORY) or ""): cv.string,
                    vol.Optional(F_POINTS, default=task.get(F_POINTS, 1)): vol.Coerce(float),
                    vol.Optional(F_ACTIVE, default=task.get(F_ACTIVE, True)): cv.boolean,
                }
            ),
        )

    async def async_step_task_remove(self, user_input=None):
        tasks = {t[F_ID]: t[F_NAME] for t in self._coord.store.tasks}
        if not tasks:
            return await self.async_step_tasks()
        if user_input is not None:
            self._coord.remove_task(user_input["task"])
            return await self.async_step_tasks()
        return self.async_show_form(
            step_id="task_remove",
            data_schema=vol.Schema({vol.Required("task"): vol.In(tasks)}),
        )

    # -- Soll-Vorgaben -----------------------------------------------------
    async def async_step_targets(self, user_input=None):
        return self.async_show_menu(
            step_id="targets",
            menu_options=["target_add", "target_remove"],
        )

    async def async_step_target_add(self, user_input=None):
        persons = {p[F_ID]: p[F_NAME] for p in self._coord.store.persons}
        tasks = {t[F_ID]: t[F_NAME] for t in self._coord.store.tasks}
        errors = {}
        if not persons or not tasks:
            return self.async_abort(reason="need_person_and_task")
        if user_input is not None:
            try:
                # set_target ist ein Upsert: gleiche (Person, Aufgabe, Periode) => Soll ändern
                self._coord.set_target(
                    user_input[F_PERSON_ID],
                    user_input[F_TASK_ID],
                    user_input[F_PERIOD],
                    user_input[F_COUNT],
                )
                return await self.async_step_targets()
            except HausarbeitError:
                errors["base"] = "invalid"
        return self.async_show_form(
            step_id="target_add",
            data_schema=vol.Schema(
                {
                    vol.Required(F_PERSON_ID): vol.In(persons),
                    vol.Required(F_TASK_ID): vol.In(tasks),
                    vol.Required(F_PERIOD, default=PERIOD_WEEK): vol.In(list(PERIODS)),
                    vol.Required(F_COUNT, default=1): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            errors=errors,
        )

    async def async_step_target_remove(self, user_input=None):
        targets = {}
        for t in self._coord.store.targets:
            label = (
                f"{self._coord.person_name(t[F_PERSON_ID])} · "
                f"{self._coord.task_name(t[F_TASK_ID])} — {t[F_COUNT]}× / {t[F_PERIOD]}"
            )
            targets[t[F_ID]] = label
        if not targets:
            return await self.async_step_targets()
        if user_input is not None:
            self._coord.remove_target(user_input["target"])
            return await self.async_step_targets()
        return self.async_show_form(
            step_id="target_remove",
            data_schema=vol.Schema({vol.Required("target"): vol.In(targets)}),
        )

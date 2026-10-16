"""Config- und Options-Flow für den Hausarbeit-Tracker (UI-First).

Config-Flow: legt genau einen Haushalts-Eintrag an.
Options-Flow: Einstellungen (Wochenstart, Statistik-Zeitraum) UND vollständige
Verwaltung von Personen, Aufgaben und Soll-Vorgaben (anlegen/ändern/entfernen) —
komplett über die HA-Oberfläche, ohne YAML.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    IconSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
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
    MAX_POINTS,
    MAX_STATS_DAYS,
    MIN_POINTS,
    MIN_STATS_DAYS,
    PERIOD_WEEK,
    PERIODS,
)
from .coordinator import HausarbeitCoordinator, HausarbeitError
from .validation import is_valid_color

if TYPE_CHECKING:
    from . import HausarbeitConfigEntry

_WEEK_START_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[str(day) for day in range(7)],
        translation_key="week_start",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
_PERIOD_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(PERIODS),
        translation_key="period",
        mode=SelectSelectorMode.LIST,
    )
)
_STATS_DAYS_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_STATS_DAYS, max=MAX_STATS_DAYS, step=1, mode=NumberSelectorMode.BOX
    )
)
_POINTS_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=MIN_POINTS, max=MAX_POINTS, step=0.5, mode=NumberSelectorMode.BOX)
)
_COUNT_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=1, max=1000, step=1, mode=NumberSelectorMode.BOX)
)
_PERSON_ENTITY_SELECTOR = EntitySelector(EntitySelectorConfig(domain="person"))


def _choice(options: dict[str, str]) -> SelectSelector:
    """Dropdown aus {id: label}."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=k, label=v) for k, v in options.items()],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _person_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Formular Person anlegen/bearbeiten.

    Optionale Felder nutzen ``suggested_value`` statt ``default``, damit sie sich
    im Bearbeiten-Formular wieder leeren lassen.
    """
    return vol.Schema(
        {
            vol.Required(F_NAME, default=defaults.get(F_NAME, vol.UNDEFINED)): TextSelector(),
            vol.Optional(
                F_ICON, description={"suggested_value": defaults.get(F_ICON) or "mdi:account"}
            ): IconSelector(),
            vol.Optional(
                F_COLOR, description={"suggested_value": defaults.get(F_COLOR)}
            ): TextSelector(),
            vol.Optional(
                F_HA_PERSON, description={"suggested_value": defaults.get(F_HA_PERSON)}
            ): _PERSON_ENTITY_SELECTOR,
        }
    )


def _task_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(F_NAME, default=defaults.get(F_NAME, vol.UNDEFINED)): TextSelector(),
            vol.Optional(
                F_ICON, description={"suggested_value": defaults.get(F_ICON) or "mdi:broom"}
            ): IconSelector(),
            vol.Optional(
                F_CATEGORY, description={"suggested_value": defaults.get(F_CATEGORY)}
            ): TextSelector(),
            vol.Optional(F_POINTS, default=defaults.get(F_POINTS, 1)): _POINTS_SELECTOR,
            vol.Optional(F_ACTIVE, default=defaults.get(F_ACTIVE, True)): BooleanSelector(),
        }
    )


def _person_input(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Formulardaten -> Felder (fehlende optionale Felder = leeren) + Feldfehler."""
    errors: dict[str, str] = {}
    color = (user_input.get(F_COLOR) or "").strip() or None
    if color is not None and not is_valid_color(color):
        errors[F_COLOR] = "invalid_color"
    return {
        F_NAME: user_input.get(F_NAME, ""),
        F_ICON: user_input.get(F_ICON) or None,
        F_COLOR: color,
        F_HA_PERSON: user_input.get(F_HA_PERSON) or None,
    }, errors


class HausarbeitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ersteinrichtung — genau ein Eintrag (``single_config_entry`` im Manifest)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
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
            data_schema=vol.Schema({vol.Optional("title", default=DEFAULT_TITLE): TextSelector()}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HausarbeitConfigEntry):
        return HausarbeitOptionsFlow()


class HausarbeitOptionsFlow(config_entries.OptionsFlow):
    """Einstellungen + Verwaltung von Personen/Aufgaben/Soll-Vorgaben.

    `config_entry` wird vom Flow-Manager gesetzt (nicht manuell zuweisen — das ist in
    aktuellen HA-Versionen entfernt).
    """

    _selected: str | None = None

    @property
    def _coord(self) -> HausarbeitCoordinator:
        return self.config_entry.runtime_data

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
                        CONF_WEEK_START,
                        default=str(opts.get(CONF_WEEK_START, DEFAULT_WEEK_START)),
                    ): _WEEK_START_SELECTOR,
                    vol.Required(
                        CONF_STATS_DAYS, default=opts.get(CONF_STATS_DAYS, DEFAULT_STATS_DAYS)
                    ): _STATS_DAYS_SELECTOR,
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
        errors: dict[str, str] = {}
        if user_input is not None:
            fields, errors = _person_input(user_input)
            if not errors:
                try:
                    self._coord.add_person(
                        fields[F_NAME],
                        icon=fields[F_ICON],
                        color=fields[F_COLOR],
                        ha_person_entity=fields[F_HA_PERSON],
                    )
                    return await self.async_step_persons()
                except HausarbeitError:
                    errors["base"] = "invalid"
        return self.async_show_form(
            step_id="person_add",
            data_schema=(
                self.add_suggested_values_to_schema(_person_schema({}), user_input)
                if user_input is not None
                else _person_schema({})
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
            data_schema=vol.Schema({vol.Required("person"): _choice(persons)}),
        )

    async def async_step_person_edit_form(self, user_input=None):
        person = self._coord.store.get_person(self._selected)
        if person is None:
            self._selected = None
            return await self.async_step_persons()
        errors: dict[str, str] = {}
        if user_input is not None:
            fields, errors = _person_input(user_input)
            if not errors:
                try:
                    self._coord.update_person(self._selected, **fields)
                    self._selected = None
                    return await self.async_step_persons()
                except HausarbeitError:
                    errors["base"] = "invalid"
        return self.async_show_form(
            step_id="person_edit_form",
            errors=errors,
            data_schema=_person_schema(person),
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
            data_schema=vol.Schema({vol.Required("person"): _choice(persons)}),
        )

    # -- Aufgaben ----------------------------------------------------------
    async def async_step_tasks(self, user_input=None):
        self._selected = None  # stale Auswahl aus abgebrochenem Edit verwerfen
        return self.async_show_menu(
            step_id="tasks",
            menu_options=["task_add", "task_edit", "task_remove"],
        )

    async def async_step_task_add(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._coord.add_task(
                    user_input.get(F_NAME, ""),
                    icon=user_input.get(F_ICON) or None,
                    category=user_input.get(F_CATEGORY) or None,
                    points=user_input.get(F_POINTS),
                    active=user_input.get(F_ACTIVE, True),
                )
                return await self.async_step_tasks()
            except HausarbeitError:
                errors["base"] = "invalid"
        return self.async_show_form(
            step_id="task_add",
            errors=errors,
            data_schema=_task_schema({}),
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
            data_schema=vol.Schema({vol.Required("task"): _choice(tasks)}),
        )

    async def async_step_task_edit_form(self, user_input=None):
        task = self._coord.store.get_task(self._selected)
        if task is None:
            self._selected = None
            return await self.async_step_tasks()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._coord.update_task(
                    self._selected,
                    name=user_input.get(F_NAME, ""),
                    icon=user_input.get(F_ICON) or None,
                    category=user_input.get(F_CATEGORY) or None,
                    points=user_input.get(F_POINTS),
                    active=user_input.get(F_ACTIVE),
                )
                self._selected = None
                return await self.async_step_tasks()
            except HausarbeitError:
                errors["base"] = "invalid"
        return self.async_show_form(
            step_id="task_edit_form",
            errors=errors,
            data_schema=_task_schema(task),
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
            data_schema=vol.Schema({vol.Required("task"): _choice(tasks)}),
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
                    int(user_input[F_COUNT]),
                )
                return await self.async_step_targets()
            except HausarbeitError:
                errors["base"] = "invalid"
        return self.async_show_form(
            step_id="target_add",
            data_schema=vol.Schema(
                {
                    vol.Required(F_PERSON_ID): _choice(persons),
                    vol.Required(F_TASK_ID): _choice(tasks),
                    vol.Required(F_PERIOD, default=PERIOD_WEEK): _PERIOD_SELECTOR,
                    vol.Required(F_COUNT, default=1): _COUNT_SELECTOR,
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
            data_schema=vol.Schema({vol.Required("target"): _choice(targets)}),
        )

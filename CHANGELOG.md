# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] – 2026-10-16

> Minimum Home Assistant version is now **2025.2.0**. See "Upgrading to 0.2.0" in the README.

### Added

- Sensors refresh **every full hour, including local midnight**, so `today`, the rolling
  7/30/90-day windows, `im_soll` and the current target period no longer go stale when
  nobody logs anything.
- `diagnostics.py` (counts and IDs only; names, colors, linked persons and notes are
  left out).
- `strings.json`; translated service/action texts, entity names, selector options
  (week start, period), form help texts (`data_description`) and error messages in
  English, German and Spanish. `icons.json` for entity and action icons.
- Executions logged via the cards store the logging Home Assistant `user_id`
  (used for the undo permission).
- Tests for the WebSocket API, scheduled updates, entity-registry cleanup, store
  migration, entry removal, permissions and translations; separate `Tests` workflow with
  coverage and a `node --check` syntax check of the Lovelace cards.

### Changed

- **Permissions:** all actions except `log_execution` are now admin-only when called by
  a user (automations/scripts are unaffected). WebSocket `hausarbeit/delete_execution`:
  admins may delete any entry, other users only entries they logged themselves (the
  claim card's undo keeps working for family members).
- Entity names and the unit of measurement are translated (`translation_key`); the unit
  is now `tasks` (was `Aufgaben`). Existing entity IDs are kept; IDs of newly created
  sensors follow the translated name (e.g. `…_woche` instead of `…_week` on German
  systems).
- Options flow uses selectors (dropdowns, icon picker, person entity picker, number
  boxes); optional fields can be cleared; person colors are validated as safe CSS colors.
- Actions and WebSocket commands are registered once in `async_setup`; errors are raised
  as translated `ServiceValidationError`.
- Modernized setup: `entry.runtime_data`, `single_config_entry`, `integration_type:
  service`, `iot_class: calculated`, service device for the sensors.
- `services.yaml` has an English base text.
- Timestamps are stored as UTC; naive timestamps (action datetime selector, WebSocket)
  are interpreted as Home Assistant's local time. Store version 1.2 migrates existing
  entries (same instants, normalized representation).
- README and README.de rewritten (quick start, how to find IDs, accurate entity
  attributes, modern automation syntax). `info.md` removed – HACS renders the README
  (`render_readme: true`). Changelog translated to English.

### Fixed

- Removing a person, task or target left orphaned entries in the entity registry; they
  are now removed, and orphans from older versions are cleaned up on startup.
- Sensors wrote their state twice per update.
- `hausarbeit/log` sorted by timestamp string instead of the actual time (wrong order with
  mixed UTC offsets).
- Removing the integration left the stored data behind, so a reinstall resurrected old
  people, tasks and log entries.
- Minimum Home Assistant version in `hacs.json`/README was too low for the options flow
  in use.
- README examples used wrong attribute names (`Soll`/`Rest`/`Erfüllungsgrad`/`on_track`
  instead of `soll`/`rest`/`erfuellungsgrad`/`im_soll`), wrong time-window names and a
  non-existent entity ID; the FAQ pointed to *Dashboards → Resources*, where the cards
  are not listed.

## [0.1.5] – 2026-10-09

> Note: `const.VERSION` (device firmware version and cache bust of the Lovelace cards) had
> been stuck at 0.1.3 since 0.1.4 and is now in sync with `manifest.json` again.

### Fixed

- `update_person`/`update_task` (services, options flow) accepted an empty name and did
  not trim it – the same rule as when creating now also applies when editing.
- Points/weight were only converted to `float`: negative values, `nan`/`inf` and values
  above 100 were stored. Services, options flow and coordinator now enforce 0–100 (like
  the selector in `services.yaml`).
- Options flow: invalid input in "Add task" and "Edit person/task" now shows the form
  error "invalid" instead of an unhandled error (HTTP 500).

## [0.1.4] – 2026-08-21

### Added

- **Project governance & community files** for HACS readiness: `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1), issue templates
  (bug/feature) and `config.yml`, `PULL_REQUEST_TEMPLATE.md`.
- **Ruff configuration** and a lint/format pass (`ruff check`, `ruff format`) over the
  Python code.
- **CI automation**: Ruff job in CI, `dependabot.yml` (weekly, GitHub Actions),
  `release-drafter.yml` (configuration + workflow).

### Changed

- **README in English as the primary language**; the German version now lives in
  `README.de.md`. Real screenshots (the three Lovelace cards, config flow, entities)
  from a demo instance added.

### Fixed

- **Lovelace cards no longer loaded on current Home Assistant** ("Configuration
  error"). Two causes fixed: (1) the automatic registration of the card modules
  (`add_extra_js_url`) ran in `async_setup` before the `frontend` component had created
  its data structure and failed with `KeyError 'frontend_extra_module_url'` – the calls
  are now deferred via `async_at_start` (`frontend` deliberately stays an
  `after_dependency` so the tests run without the full frontend setup); (2) the cards
  obtained `html`/`css` via `hui-view.prototype`, which current HA versions no longer
  provide – the definition is now deferred until a Lit-capable base
  (`ha-panel-lovelace` / `hui-masonry-view` / `ha-card`) is available. Verified on
  HA 2026.8.

## [0.1.3] – 2026-08-20

### Changed

- **Multilingual, more neutral card picker**: name/description of the three cards in the
  Lovelace card picker now follow the browser/HA language (DE/EN/ES, fallback English).
  The `getStubConfig` default titles were removed – newly added cards automatically use
  the localized default title.

## [0.1.2] – 2026-08-20

### Added

- **Multilingual Lovelace cards**: all three cards (claim/stats/targets) are now available
  in **German, English and Spanish** – the language automatically follows the Home
  Assistant user language (fallback English → German). Periods, date formats and progress
  texts are localized.

## [0.1.1] – 2026-08-20

### Added

- **Brand icon & logo** of the integration (light/dark) – served locally from
  `custom_components/hausarbeit/brand/` (HA brands proxy, from HA 2026.3.0), shown on the
  integration/device page without a `home-assistant/brands` PR.
- **Spanish translation** of the UI (`translations/es.json`) – the UI is now available in
  German, English and Spanish.
- Short description in **English and Spanish** in the README and `info.md`.

### Changed

- Minimum Home Assistant version in the docs corrected to **2024.7.0** (because of
  `StaticPathConfig`).

## [0.1.0] – 2026-08-19

### Added

- First release of the Home Assistant integration **"Hausarbeit-Tracker"**
  (`hausarbeit`) for documenting who did which household chore, and when.
- **Config flow**: one entry per household.
- **Options flow**: global settings **week start** (`week_start`, default Monday) and
  **statistics period** (`stats_days`, default 90 days, 1–3650) plus management of
  people, tasks and targets.
- **Persistent store** (`hausarbeit_data`, `STORAGE_VERSION = 1`) with the top-level
  sections `persons`, `tasks`, `targets`, `executions` and stable IDs
  (`per_` / `tsk_` / `tgt_` / `exe_`); migration path via `async_migrate_func`.
- **Tasks** with name, icon, category, points/weight (default 1) and active flag.
- **People** with name, icon, color and an optional link to a `person.*` entity.
- **Log and backfill completions** (optional timestamp `ts` and note `note`), including
  deleting and correcting.
- **Target/actual tracking** via targets per person and task for the periods
  **day / week / month**.
- **Sensors**: one statistics sensor per person (state = executions in the statistics
  period, attributes per task and time window) and one sensor per target (state =
  actual, attributes target/remaining/completion rate/period start/end/on pace).
- **Services**: `log_execution`, `delete_execution`, `correct_execution`, `add_task`,
  `update_task`, `remove_task`, `add_person`, `update_person`, `remove_person`,
  `set_target`, `remove_target`.
- **WebSocket API**: `hausarbeit/tasks`, `hausarbeit/persons`, `hausarbeit/targets`,
  `hausarbeit/log`, `hausarbeit/stats`, `hausarbeit/log_execution`,
  `hausarbeit/delete_execution`, `hausarbeit/subscribe` (push on data change).
- **Event** `hausarbeit_execution_logged` on the HA event bus for every new execution.
- **Three bundled Lovelace cards** (`hausarbeit-claim-card`,
  `hausarbeit-stats-card`, `hausarbeit-targets-card`), registered automatically as a
  frontend resource.
- **Raw data export** of the execution log via the WebSocket API.
- German translations and documentation (README, HACS info).

[Unreleased]: https://github.com/Jo-Highness/hausarbeit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jo-Highness/hausarbeit/releases/tag/v0.1.0

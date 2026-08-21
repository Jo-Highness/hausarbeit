# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
und dieses Projekt folgt der [Semantischen Versionierung](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Added

- **Projekt-Governance & Community-Dateien** für HACS-Reife: `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1), Issue-Vorlagen
  (Bug/Feature) und `config.yml`, `PULL_REQUEST_TEMPLATE.md`.
- **Ruff-Konfiguration** sowie ein Lint-/Format-Durchlauf (`ruff check`,
  `ruff format`) über den Python-Code.
- **CI-Automatisierung**: Ruff-Job in der CI, `dependabot.yml` (wöchentlich,
  GitHub-Actions), `release-drafter.yml` (Konfiguration + Workflow).

### Changed

- **README auf Englisch als Primärsprache** umgestellt; die deutsche Fassung liegt
  nun in `README.de.md`.

## [0.1.3] – 2026-08-20

### Changed

- **Card-Picker mehrsprachig & neutraler**: Name/Beschreibung der drei Karten im
  Lovelace-Kartenwähler folgen jetzt der Browser-/HA-Sprache (DE/EN/ES, Fallback
  Englisch). Die `getStubConfig`-Standardtitel sind entfernt – neu hinzugefügte Karten
  nutzen automatisch den lokalisierten Standardtitel.

## [0.1.2] – 2026-08-20

### Added

- **Mehrsprachige Lovelace-Karten**: Alle drei Karten (claim/stats/targets) sind nun
  in **Deutsch, Englisch und Spanisch** – die Sprache folgt automatisch der
  Home-Assistant-Nutzersprache (Fallback Englisch → Deutsch). Perioden, Datumsformate
  und Fortschrittstexte werden lokalisiert.

## [0.1.1] – 2026-08-20

### Added

- **Marken-Icon & Logo** der Integration (hell/dunkel) – lokal ausgeliefert über
  `custom_components/hausarbeit/brand/` (HA Brands-Proxy, ab HA 2026.3.0), erscheint auf
  der Integrations-/Geräteseite ohne `home-assistant/brands`-PR.
- **Spanische Übersetzung** der Oberfläche (`translations/es.json`) – die UI gibt es nun
  in Deutsch, Englisch und Spanisch.
- Kurzbeschreibung in **Englisch und Spanisch** in README und `info.md`.

### Changed

- Home-Assistant-Mindestversion in der Doku auf **2024.7.0** korrigiert (wegen
  `StaticPathConfig`).

## [0.1.0] – 2026-08-19

### Added

- Erste Veröffentlichung der Home-Assistant-Integration **„Hausarbeit-Tracker"**
  (`hausarbeit`) zum Dokumentieren, wer wann welche Hausarbeit erledigt hat.
- **Config-Flow**: ein Eintrag pro Haushalt.
- **Options-Flow**: globale Einstellungen **Wochenstart** (`week_start`, Standard Montag)
  und **Statistik-Zeitraum** (`stats_days`, Standard 90 Tage, 1–3650) sowie Verwaltung von
  Personen, Aufgaben und Soll-Vorgaben.
- **Persistenter Store** (`hausarbeit_data`, `STORAGE_VERSION = 1`) mit den Top-Level-
  Bereichen `persons`, `tasks`, `targets`, `executions` und stabilen IDs
  (`per_` / `tsk_` / `tgt_` / `exe_`); Migrationspfad via `async_migrate_func`.
- **Aufgaben** mit Name, Icon, Kategorie, Punkten/Gewicht (Default 1) und Aktiv-Status.
- **Personen** mit Name, Icon, Farbe und optionaler Verknüpfung zu einer `person.*`-
  Entität.
- **Erledigungen loggen und nachtragen** (optionaler Zeitpunkt `ts` und Notiz `note`),
  inklusive Löschen und Korrigieren.
- **Soll-/Ist-Tracking** über Soll-Vorgaben (Targets) je Person und Aufgabe für die
  Perioden **Tag / Woche / Monat**.
- **Sensoren**: je Person ein Statistik-Sensor (State = Ausführungen/Punkte im
  Statistik-Zeitraum, Attribute je Aufgabe und Zeitfenster today/7d/30d/90d/gesamt) sowie
  je Soll-Vorgabe ein Sensor (State = Ist, Attribute Soll/Rest/Erfüllungsgrad/
  Periodenstart/-ende/on_track).
- **Services**: `log_execution`, `delete_execution`, `correct_execution`, `add_task`,
  `update_task`, `remove_task`, `add_person`, `update_person`, `remove_person`,
  `set_target`, `remove_target`.
- **WebSocket-API**: `hausarbeit/tasks`, `hausarbeit/persons`, `hausarbeit/targets`,
  `hausarbeit/log`, `hausarbeit/stats`, `hausarbeit/log_execution`,
  `hausarbeit/delete_execution`, `hausarbeit/subscribe` (Push bei Datenänderung).
- **Event** `hausarbeit_execution_logged` auf dem HA-Event-Bus bei jeder neuen Ausführung.
- **Drei mitgelieferte Lovelace-Karten** (`hausarbeit-claim-card`,
  `hausarbeit-stats-card`, `hausarbeit-targets-card`), die automatisch als Frontend-
  Ressource registriert werden.
- **Rohdaten-Export** des Ausführungs-Logs über die WebSocket-API.
- Deutschsprachige Übersetzungen und Dokumentation (README, HACS-Info).

[Unveröffentlicht]: https://github.com/Jo-Highness/hausarbeit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jo-Highness/hausarbeit/releases/tag/v0.1.0

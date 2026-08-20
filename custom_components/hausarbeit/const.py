"""Zentrale Konstanten & Schnittstellen-Vertrag für die Integration *Hausarbeit-Tracker*.

Diese Datei ist der EINZIGE Ort für IDs, Store-Schema, Service- und WebSocket-Namen.
Backend, Sensoren, WebSocket-API, Tests und die Lovelace-Karten müssen sich exakt an
die hier definierten Namen halten (die Karten spiegeln WS_* / SERVICE_* als String).
"""
from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------------- #
DOMAIN: Final = "hausarbeit"
NAME: Final = "Hausarbeit-Tracker"
VERSION: Final = "0.1.2"   # muss mit manifest.json übereinstimmen (Frontend-Cache-Bust)
MANUFACTURER: Final = "hausarbeit"
MODEL: Final = "Haushalt"

# Ein einzelner Config-Entry pro Haushalt.
DEFAULT_TITLE: Final = "Hausarbeit"

# --------------------------------------------------------------------------- #
# Persistenter Speicher (homeassistant.helpers.storage.Store)
# --------------------------------------------------------------------------- #
STORAGE_KEY: Final = "hausarbeit_data"
STORAGE_VERSION: Final = 1          # Major-Schema-Version (async_migrate_func)
STORAGE_MINOR_VERSION: Final = 1    # Minor-Version für vorwärtskompatible Ergänzungen

# Top-Level-Schlüssel im gespeicherten Dict.
STORE_PERSONS: Final = "persons"
STORE_TASKS: Final = "tasks"
STORE_TARGETS: Final = "targets"
STORE_EXECUTIONS: Final = "executions"

# ID-Präfixe (kurze, stabile IDs: <prefix> + 8 Hex-Zeichen aus uuid4).
ID_PREFIX_PERSON: Final = "per_"
ID_PREFIX_TASK: Final = "tsk_"
ID_PREFIX_TARGET: Final = "tgt_"
ID_PREFIX_EXECUTION: Final = "exe_"

# --------------------------------------------------------------------------- #
# Feld-Namen der Datensätze (Store + Services + WebSocket)
# --------------------------------------------------------------------------- #
# Person
F_ID: Final = "id"
F_NAME: Final = "name"
F_ICON: Final = "icon"
F_COLOR: Final = "color"
F_HA_PERSON: Final = "ha_person_entity"   # optionale Verknüpfung zu person.*
F_CREATED: Final = "created"              # ISO-8601 UTC

# Task (zusätzlich zu F_NAME/F_ICON/F_CREATED)
F_CATEGORY: Final = "category"
F_POINTS: Final = "points"                # Gewicht, Default 1
F_ACTIVE: Final = "active"                # bool, Default True

# Target (Soll-Vorgabe)
F_PERSON_ID: Final = "person_id"
F_TASK_ID: Final = "task_id"
F_PERIOD: Final = "period"                # PERIOD_DAY | PERIOD_WEEK | PERIOD_MONTH
F_COUNT: Final = "count"                  # Soll-Anzahl pro Periode

# Execution (Ausführungs-Ereignis)
F_TIMESTAMP: Final = "ts"                 # ISO-8601 UTC
F_NOTE: Final = "note"

# --------------------------------------------------------------------------- #
# Perioden-Typen
# --------------------------------------------------------------------------- #
PERIOD_DAY: Final = "day"
PERIOD_WEEK: Final = "week"
PERIOD_MONTH: Final = "month"
PERIODS: Final = (PERIOD_DAY, PERIOD_WEEK, PERIOD_MONTH)

# --------------------------------------------------------------------------- #
# Config-/Options-Flow
# --------------------------------------------------------------------------- #
CONF_WEEK_START: Final = "week_start"      # 0=Montag … 6=Sonntag (Python weekday())
CONF_STATS_DAYS: Final = "stats_days"      # Standard-Statistikzeitraum in Tagen

DEFAULT_WEEK_START: Final = 0               # Montag
DEFAULT_STATS_DAYS: Final = 90
MIN_STATS_DAYS: Final = 1
MAX_STATS_DAYS: Final = 3650

# --------------------------------------------------------------------------- #
# Services (siehe services.yaml) — Domain ist DOMAIN
# --------------------------------------------------------------------------- #
SERVICE_LOG_EXECUTION: Final = "log_execution"
SERVICE_DELETE_EXECUTION: Final = "delete_execution"
SERVICE_CORRECT_EXECUTION: Final = "correct_execution"
SERVICE_ADD_TASK: Final = "add_task"
SERVICE_UPDATE_TASK: Final = "update_task"
SERVICE_REMOVE_TASK: Final = "remove_task"
SERVICE_ADD_PERSON: Final = "add_person"
SERVICE_UPDATE_PERSON: Final = "update_person"
SERVICE_REMOVE_PERSON: Final = "remove_person"
SERVICE_SET_TARGET: Final = "set_target"
SERVICE_REMOVE_TARGET: Final = "remove_target"

# Service-Feldnamen (zusätzlich zu den F_*-Feldern oben)
ATTR_EXECUTION_ID: Final = "execution_id"
ATTR_TARGET_ID: Final = "target_id"

# --------------------------------------------------------------------------- #
# WebSocket-API (Typ-Strings, die die Karten senden)
# Lese-Kommandos + bequeme Aktions-Kommandos (liefern IDs/Ergebnis zurück).
# --------------------------------------------------------------------------- #
WS_TASKS: Final = "hausarbeit/tasks"                # Liste Tasks
WS_PERSONS: Final = "hausarbeit/persons"            # Liste Personen
WS_TARGETS: Final = "hausarbeit/targets"            # Targets inkl. Ist/Soll/Rest/%%
WS_LOG: Final = "hausarbeit/log"                    # Ausführungs-Log (Filter/Limit)
WS_STATS: Final = "hausarbeit/stats"               # Aggregierte Statistik (Param days)
WS_LOG_EXECUTION: Final = "hausarbeit/log_execution"   # loggt + liefert execution_id
WS_DELETE_EXECUTION: Final = "hausarbeit/delete_execution"
WS_SUBSCRIBE: Final = "hausarbeit/subscribe"        # Push bei Datenänderung

# Event-/Dispatcher-Signal bei Datenänderung (Sensoren + WS-Subscriber aktualisieren)
SIGNAL_UPDATE: Final = f"{DOMAIN}_updated"

# Event, das bei jeder neuen Ausführung auf dem HA-Event-Bus gefeuert wird
EVENT_EXECUTION_LOGGED: Final = f"{DOMAIN}_execution_logged"

# --------------------------------------------------------------------------- #
# Statistik-Zeitfenster (Tage) für die Personen-Sensoren-Aufschlüsselung
# --------------------------------------------------------------------------- #
STAT_WINDOWS_DAYS: Final = {
    "today": 0,        # Sonderfall: seit lokalem Kalendertag-Beginn
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,       # gesamt
}

# --------------------------------------------------------------------------- #
# Frontend / Lovelace-Karten
# --------------------------------------------------------------------------- #
FRONTEND_DIR: Final = "frontend"
# (Dateiname, Kartentyp) — werden als /hausarbeit_frontend/<datei> ausgeliefert
# und per add_extra_js_url automatisch geladen.
LOVELACE_CARDS: Final = (
    ("hausarbeit-claim-card.js", "hausarbeit-claim-card"),
    ("hausarbeit-stats-card.js", "hausarbeit-stats-card"),
    ("hausarbeit-targets-card.js", "hausarbeit-targets-card"),
)
FRONTEND_URL_BASE: Final = "/hausarbeit_frontend"

# hass.data-Struktur:  hass.data[DOMAIN][entry_id] = HausarbeitCoordinator
PLATFORMS: Final = ["sensor"]

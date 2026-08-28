# Requirements — Hausarbeit-Tracker (Clean-Room)

> Code-unabhaengiges Anforderungsdokument (WAS/WARUM). Ziel: die Integration laesst sich
> allein hieraus als Greenfield neu bauen. Stand: v0.1.4 (2026-08). Bezug: README,
> CHANGELOG, HACS-Readiness-Kampagne.

## 1. Zweck
Eine Home-Assistant-Custom-Integration (HACS-faehig), die dokumentiert, WER WANN WELCHE
Hausarbeit erledigt hat, daraus Statistiken/Rankings bildet und je Person und Aufgabe
ein Soll (z. B. "Anna: Spuelmaschine 3x/Woche") gegen das Ist der laufenden Periode
vergleicht. Vollstaendig lokal (keine Cloud), UI-first (kein YAML noetig), mit drei
mitgelieferten Dashboard-Karten. Zielgruppe: Familien/WGs, die Hausarbeit fair und
nachvollziehbar verteilen wollen.

## 2. Rollen / Nutzer
- **Betreiber** (HA-Admin): richtet den Haushalt ein, pflegt Personen/Aufgaben/Soll-Vorgaben.
- **Haushaltsmitglied**: meldet Erledigungen per Karte (ein Klick), sieht Ranking und
  eigenen Soll-/Ist-Fortschritt.
- **Automationen**: nutzen Services, Sensoren und ein Ereignis, um z. B. zu erinnern oder
  Erledigungen zu melden.

## 3. Datenmodell (fachlich)
Genau EIN Haushalt pro HA-Instanz. Vier Entitaetstypen, alle mit kurzer, stabiler,
praefixierter ID (Person `per_`, Aufgabe `tsk_`, Soll-Vorgabe `tgt_`, Ausfuehrung `exe_`):
- **Person**: Name (Pflicht, nicht leer), optional Icon, Farbe, Verknuepfung zu einer
  bestehenden HA-Personen-Entitaet; Anlagezeitpunkt.
- **Aufgabe**: Name (Pflicht), optional Icon, Kategorie; Punkte/Gewicht (Default 1,
  0..100 in 0,5er-Schritten), aktiv-Flag (Default wahr); Anlagezeitpunkt.
- **Soll-Vorgabe**: Person, Aufgabe, Periode (`day`|`week`|`month`), Soll-Anzahl (>= 1).
  Eindeutig je (Person, Aufgabe, Periode) — erneutes Setzen ist ein Upsert.
- **Ausfuehrung**: Person, Aufgabe, Zeitstempel (UTC, ISO-8601), optionale Notiz.
Regeln: IDs und Anlagezeitpunkt sind unveraenderlich. Loeschen einer Person/Aufgabe
entfernt deren Soll-Vorgaben, das Ausfuehrungs-Log bleibt als Rohdaten erhalten
(verwaiste Eintraege werden in Statistiken nicht mehr gezaehlt).

## 4. Funktionale Anforderungen
- **FR1 Einrichtung**: Anlage des Haushalts ueber den HA-Konfigurationsdialog mit optionalem
  Titel (Default "Hausarbeit"); ein zweiter Eintrag wird abgelehnt (Single Instance).
- **FR2 Optionen**: Wochenstart (0=Montag..6=Sonntag, Default Montag) und Standard-
  Statistikzeitraum in Tagen (1..3650, Default 90) sind ueber den Optionsdialog aenderbar;
  Aenderungen wirken ohne Neustart (Reload).
- **FR3 Stammdaten per UI**: Der Optionsdialog bietet Menues zum Anlegen/Aendern/Entfernen
  von Personen und Aufgaben sowie Setzen/Entfernen von Soll-Vorgaben (Auswahl per
  Dropdown); Soll-Vorgabe ist erst moeglich, wenn mind. eine Person und eine Aufgabe
  existieren.
- **FR4 Erledigung loggen**: Eine Ausfuehrung wird mit Person + Aufgabe erfasst; Zeitpunkt
  optional (Default jetzt, sonst Nachtragen in die Vergangenheit), Notiz optional.
  Unbekannte Person/Aufgabe wird abgelehnt. Rueckgabe der neuen Ausfuehrungs-ID.
- **FR5 Korrektur/Loeschung**: Jede Ausfuehrung kann in Person, Aufgabe, Zeitpunkt oder
  Notiz korrigiert oder geloescht werden.
- **FR6 Ereignis**: Bei jeder neuen Ausfuehrung wird ein HA-Ereignis
  `hausarbeit_execution_logged` mit Ausfuehrungs-ID, Person (ID+Name), Aufgabe (ID+Name)
  und Zeitstempel gefeuert.
- **FR7 Services**: Alle Stammdaten- und Log-Operationen sind als HA-Services der Domain
  `hausarbeit` verfuegbar: log_execution, delete_execution, correct_execution, add_task,
  update_task, remove_task, add_person, update_person, remove_person, set_target,
  remove_target. Anlegende Services liefern optional die erzeugte ID zurueck; fachliche
  Fehler erscheinen als Validierungsfehler in der UI.
- **FR8 Perioden**: Tag = lokaler Kalendertag; Woche = 7 Tage ab konfiguriertem
  Wochenstart; Monat = Kalendermonat (inkl. Jahreswechsel). Grenzen halboffen [Start, Ende).
  Berechnung in der HA-Zeitzone, Zeitstempel intern in UTC.
- **FR9 Soll-/Ist-Auswertung** je Soll-Vorgabe fuer die LAUFENDE Periode: Ist (Anzahl),
  Rest (Soll-Ist, min. 0), Erfuellungsgrad in % (1 Nachkommastelle; bei Soll 0 = 100),
  Periodenstart/-ende, `on_track` = Soll erfuellt ODER Ist >= anteilig zur verstrichenen
  Periodenzeit erwartetes Soll.
- **FR10 Statistik** ueber einen Zeitraum in Tagen (Default = Option): Gesamtzahl;
  Ranking der Personen nach Anzahl, dann Punkten (Punkte = Summe der Aufgabengewichte,
  unbekannte/ungueltige Gewichte zaehlen 1), Anteil in % (summiert sich zu 100);
  Aufschluesselung je Aufgabe (gesamt + je Person, absteigend); je Person Zeitfenster
  heute (seit lokalem Tagesbeginn) / 7 / 30 / 90 Tage / laufender Monat / gesamt /
  Punkte gesamt; plus alle Soll-Auswertungen.
- **FR11 Sensoren** (dynamisch, ohne Neustart bei Datenaenderung angelegt/entfernt, an
  EINEM Geraet "Haushalt" haengend, stabile unique_ids aus Datensatz-ID):
  - je Person: Zustand = Ausfuehrungen im Statistikzeitraum; Attribute Person-ID,
    Statistiktage, Aufschluesselung je Aufgabe, Zeitfenster aus FR10; Icon der Person.
  - je Soll-Vorgabe: Zustand = Ist der laufenden Periode; Attribute Soll, Ist, Rest,
    Erfuellungsgrad, im_soll, Periode, Periodenstart/-ende, Person-/Aufgaben-ID;
    Name "Person · Aufgabe (Periode)".
  - je Aufgabe: Diagnose-Sensor "zuletzt erledigt" (Zeitstempel-Typ) mit Person als Attribut.
  Sensoren einer geloeschten Person/Aufgabe/Vorgabe werden entfernt.
- **FR12 WebSocket-API** (fuer Karten und Export) mit den Kommandos `hausarbeit/persons`,
  `/tasks`, `/targets` (mit Auswertung), `/log` (Filter Person/Aufgabe, Limit 1..100000,
  Default 100, neueste zuerst, Namen angereichert, Gesamtzahl), `/stats` (Parameter days),
  `/log_execution`, `/delete_execution`, `/subscribe` (Push "updated" bei jeder
  Datenaenderung). Ohne eingerichteten Haushalt: Fehler "not_ready".
- **FR13 Lovelace-Karten**, von der Integration selbst als Frontend-Ressource ausgeliefert
  und automatisch geladen (kein separates Frontend-Paket, Cache-Bust per Version):
  - Claim-Karte: Person waehlen (Chip), Aufgabe antippen = loggen; bei nur einer Person
    genuegt der Aufgabenklick; optional Datum/Zeit + Notiz zum Nachtragen; Undo der
    zuletzt geloggten Ausfuehrung; Optionen: Titel, Personen-/Aufgabenfilter, show_note,
    Spaltenzahl.
  - Stats-Karte: Ranking und Aufschluesselung je Aufgabe, Zeitraum umschaltbar
    (7/30/90 Tage), Startansicht ranking|tasks.
  - Targets-Karte: Fortschrittsbalken je Soll-Vorgabe der laufenden Periode; Filter
    Person und Periode.
  Alle Karten aktualisieren sich live ueber subscribe und erscheinen im Kartenwaehler.
- **FR14 Mehrsprachigkeit**: Backend-Uebersetzungen (Config-/Optionsdialog) und Karten
  in Deutsch, Englisch, Spanisch; Karten folgen der HA-Nutzersprache (Fallback EN → DE).
- **FR15 Branding**: Icon/Logo werden von der Integration selbst mitgeliefert (hell/dunkel).

## 5. Nicht-funktionale Anforderungen
- **NFR1 Lokal/offline**: Keine externe Kommunikation, keine Python-Abhaengigkeiten ueber
  HA hinaus; IoT-Klasse local_push.
- **NFR2 Persistenz**: Daten im versionierten HA-Storage (Schluessel `hausarbeit_data`,
  Major/Minor-Version, Migrationspfad; fehlende Top-Level-Listen werden beim Laden
  ergaenzt). Schreiben gebuendelt/verzoegert (ca. 2 s), Event-Loop wird nie blockiert.
- **NFR3 Konsistenz**: Jede Datenaenderung benachrichtigt Sensoren und WS-Abonnenten
  ueber genau ein internes Signal; Sensoren pollen nicht.
- **NFR4 Kompatibilitaet**: HA >= 2024.7.0; verifiziert bis 2026.8. Karten benutzen das
  von HA geladene Lit (kein Build, kein CDN) und warten robust, bis eine Lit-faehige
  Basis verfuegbar ist; Registrierung der Karten-Module erst nach HA-Start.
- **NFR5 Testbarkeit**: Perioden-/Statistiklogik frei von HA-Abhaengigkeiten und unit-
  testbar; Integrationstests fuer Setup, Services, Sensoren, Config-/Options-Flow und
  Store (>= 60 Tests, CI gruen: hassfest, HACS-Validierung, Ruff).
- **NFR6 HACS-Reife**: hacs.json, manifest mit Version/Codeowner/Issue-Tracker,
  README (EN primaer, DE-Fassung), CHANGELOG (Keep a Changelog, SemVer), CONTRIBUTING,
  SECURITY, CODE_OF_CONDUCT, Issue-/PR-Vorlagen, Release-Drafter, Dependabot.
- **NFR7 Robustheit**: Unparsebare Zeitstempel werden in Auswertungen ignoriert, nie
  Abbruch; unbekannte Perioden-Typen sind ein Fehler; Services/WS liefern fachliche
  Fehlermeldungen statt Tracebacks.

## 6. Schnittstellen
- **HA Config-/Options-Flow**: Ersteinrichtung + Menue (Einstellungen / Personen /
  Aufgaben / Soll-Vorgaben).
- **HA Services** Domain `hausarbeit` (siehe FR7), mit services.yaml-Beschreibung und
  Selektoren (Datum/Zeit, Icon, Entitaet person.*, Zahl, Auswahl).
- **HA Event-Bus**: `hausarbeit_execution_logged` (FR6).
- **HA Sensor-Plattform**: Personen-, Soll- und Zuletzt-erledigt-Sensoren (FR11).
- **WebSocket-API** `hausarbeit/*` (FR12) — einziger Kanal der Karten.
- **Statische Frontend-Route** `/hausarbeit_frontend/<karte>.js?v=<version>`.
- **Storage**: HA-Store `hausarbeit_data` v1.

## 7. Konfiguration
| Option | Bedeutung | Default | Bereich |
|---|---|---|---|
| Titel | Name des Haushalts-Eintrags | Hausarbeit | Text |
| week_start | erster Wochentag fuer Wochenperioden | 0 (Montag) | 0..6 |
| stats_days | Standard-Statistikzeitraum in Tagen | 90 | 1..3650 |
Karten-Optionen siehe FR13. Keine Secrets, keine YAML-Pflicht.

## 8. Akzeptanzkriterien
- **AC1** Nach Installation + Neustart: Integration ueber UI hinzufuegbar, zweiter Versuch
  wird abgewiesen; Optionsdialog zeigt Einstellungen und Stammdaten-Menues.
- **AC2** Person + Aufgabe anlegen (UI oder Service) liefert IDs; Service log_execution
  erzeugt eine Ausfuehrung mit Jetzt-Zeitstempel bzw. uebergebenem Vergangenheits-Zeitpunkt
  und feuert das Ereignis; unbekannte Person/Aufgabe wird abgelehnt.
- **AC3** set_target ist Upsert (gleiche Person/Aufgabe/Periode -> nur Soll aendert
  sich, ID bleibt); count 0 wird abgelehnt; remove_person entfernt zugehoerige
  Soll-Vorgaben, Log bleibt.
- **AC4** Perioden: Wochenstart Montag und Sonntag korrekt, Monatsgrenze inkl. Dezember →
  Januar, Tagesgrenze am Monatsende; Grenzen halboffen.
- **AC5** Soll-Auswertung: erfuellt => on_track; frueh in der Periode mit 0 Ist => on_track;
  spaet in der Periode mit 0 Ist => nicht on_track; Prozent und Rest korrekt.
- **AC6** Statistik: Ranking sortiert nach Anzahl/Punkten, Anteile summieren sich zu 100;
  Punkte gewichten nach Aufgabe; Zeitfenster heute/7/30/90 stimmen.
- **AC7** Sensoren entstehen fuer jede Person/Vorgabe/Aufgabe ohne Neustart und
  verschwinden nach dem Loeschen; Zustand/Attribute entsprechen FR11.
- **AC8** Store: leerer Start liefert leere Listen; Migration ergaenzt fehlende Schluessel
  und ignoriert Nicht-Listen; CRUD-Roundtrip persistiert.
- **AC9** Karten laden auf aktuellem HA ohne "Custom element doesn't exist", zeigen Daten
  in der Nutzersprache und aktualisieren sich live nach einem Log-Vorgang.
- **AC10** CI (hassfest, HACS-Validate, Ruff, pytest) gruen; keine externen Requirements.

## 9. Rationale
- **Ein Haushalt pro Instanz**: HA-Instanz = Haushalt; Mehrfacheintraege wuerden
  Services/WS mehrdeutig machen.
- **Log als append-only Rohdaten** mit expliziter Korrektur/Loeschung: Statistiken bleiben
  jederzeit aus dem Log reproduzierbar; Loeschen von Stammdaten vernichtet keine Historie.
- **Punkte/Gewichte**: unterschiedlich aufwaendige Aufgaben sollen fair vergleichbar sein.
- **on_track tempo-basiert** statt nur Rest: motiviert frueh in der Periode, ohne bereits
  am ersten Tag "rot" zu zeigen.
- **UTC intern, lokale Periodengrenzen**: Zeitzonen-/Sommerzeitwechsel korrekt, Wochen-
  start konfigurierbar wegen unterschiedlicher Gewohnheiten (Mo vs. So).
- **Karten von der Integration ausgeliefert, No-Build-Lit**: eine einzige HACS-
  Installation, keine Build-Pipeline, kein CDN (lokal/offline).
- **WS-API statt Entitaeten als Karten-Kanal**: Karten brauchen Listen und Aggregationen,
  die als Entitaets-Attribute unhandlich waeren; Export der Rohdaten faellt mit ab.
- **UI-first, aber Services vollstaendig**: Automationen und YAML-Nutzer bleiben
  gleichberechtigt.

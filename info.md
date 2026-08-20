<p align="center">
  <img src="custom_components/hausarbeit/brand/logo.png" alt="Hausarbeit-Tracker" width="420">
</p>

# Hausarbeit-Tracker

Dokumentiere, **wer wann welche Hausarbeit** erledigt hat – mit Statistiken, Ranking und
**Soll-/Ist-Tracking pro Person**. Komplett lokal (`local_push`), UI-First und ohne
YAML-Pflicht.

> **🇬🇧 English** — Track **who did which chore, and when**, with statistics, rankings and
> per-person **target vs. actual** tracking. Fully local, UI-first. UI available in DE / EN / ES.
>
> **🇪🇸 Español** — Registra **quién hizo qué tarea del hogar y cuándo**, con estadísticas,
> clasificaciones y seguimiento de **objetivo frente a real** por persona. Totalmente local,
> centrado en la interfaz. Interfaz disponible en DE / EN / ES.

## Highlights

- ✅ **Aufgaben & Personen** frei verwalten (Icon, Kategorie, Punkte/Gewicht, Farbe,
  optionale `person.*`-Verknüpfung).
- 📝 **Claimen & Nachtragen** – Erledigung per Klick loggen oder mit Zeitpunkt und Notiz
  nachtragen.
- 🎯 **Soll/Ist pro Periode** (Tag / Woche / Monat), z. B. „Anna: Spülmaschine 3×/Woche" –
  inkl. Rest, Erfüllungsgrad und „on track".
- 📊 **Statistiken & Ranking** über einen konfigurierbaren Zeitraum (Standard **90 Tage**)
  mit Fenstern heute / 7 / 30 / 90 Tage / gesamt.
- 🗂️ **Rohdaten-Export** des Ausführungs-Logs über die WebSocket-API.
- 🃏 **Drei mitgelieferte Lovelace-Karten** (`hausarbeit-claim-card`,
  `hausarbeit-stats-card`, `hausarbeit-targets-card`) – werden **automatisch als Ressource
  registriert**, keine separate Frontend-Installation nötig.

## Screenshots

> ⚠️ Platzhalter – Bilder folgen (siehe `images/PLACEHOLDER.md`).

![Claim-Karte](./images/claim-card.png)
![Statistik-Karte](./images/stats-card.png)
![Targets-Karte](./images/targets-card.png)

## Kurz-Setup

1. In **HACS** als **benutzerdefiniertes Repository** hinzufügen:
   `https://github.com/Jo-Highness/hausarbeit`, Kategorie **Integration**, installieren.
2. **Home Assistant neu starten**.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen** → „Hausarbeit-Tracker".
4. Über **Konfigurieren** (Options-Flow) Wochenstart (Standard Montag) und
   Statistik-Zeitraum (Standard 90 Tage) sowie **Personen, Aufgaben und Soll-Vorgaben**
   pflegen.
5. Karten ins Dashboard einbauen, z. B. `type: custom:hausarbeit-claim-card`.

**Mindestanforderung:** Home Assistant **2024.4.0+**.

📖 Vollständige Doku, Datenmodell, alle Services und Beispiel-Automationen:
**[README auf GitHub](https://github.com/Jo-Highness/hausarbeit#readme)**

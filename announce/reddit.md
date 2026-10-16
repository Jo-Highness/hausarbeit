**Title:** Hausarbeit-Tracker — a local Home Assistant integration for tracking household chores (who did what, when)

---

I built a small, fully local integration for tracking household chores. It logs **who
completed which chore and when**, keeps statistics and a ranking, and compares **target vs.
actual** per period (day / week / month) — e.g. "Anna: dishwasher 3×/week".

No cloud, no external calls — data stays in Home Assistant's own storage.

**What it does:**

- UI-first setup (config/options flow), no YAML required; actions available for automations.
- Define your own people and tasks (icon, category, points/weight); optionally link a person
  to a `person.*` entity.
- Log a completion instantly or backfill one with a note; undo the last entry.
- Set targets per person/task/period and track actual, remaining, %, and on-track.
- Ships **three Lovelace cards** (log / stats / targets), auto-registered — no separate
  frontend install.
- WebSocket API + dynamic per-person sensors.
- UI in **German, English, and Spanish**.

**Honest caveats:** it's an early **0.x** release, and it's a *tracker*: it records and
reports chores but does **not** assign or enforce them. Docs in English and German.

Min HA **2025.2**, MIT licensed, currently **v0.2.0**. Install via HACS as a custom
repository (once it's accepted into the default store, that step goes away).

Repo: https://github.com/Jo-Highness/hausarbeit

<!-- IMAGE: attach 1–2 screenshots from the repo's images/ folder (claim-card.png / stats-card.png),
     or a short GIF of logging a chore, when posting. -->

Feedback and bug reports welcome.

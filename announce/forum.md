# Hausarbeit-Tracker — a local household-chore tracker (who did which chore, and when)

**Repo:** https://github.com/Jo-Highness/hausarbeit
**License:** MIT · **Minimum Home Assistant:** 2024.7 · **Current version:** 0.1.3

<!-- IMAGE: hero/logo — insert custom_components/hausarbeit/brand/logo.png here (center, ~460px wide) -->

## What it is

**Hausarbeit-Tracker** is a small, fully local integration that answers a simple household
question: *who did which chore, and when?* You log a completed chore per person, and it
keeps statistics and a ranking, and compares **target vs. actual** per period (day / week /
month) — for example "Anna: empty the dishwasher 3×/week".

It is bookkeeping, not automation of the work itself: the integration **records and reports**
who did what. It does **not** assign chores to people or enforce anything automatically.

Everything runs on your instance. There is **no cloud** and no external communication —
data lives in Home Assistant's own storage.

## Features

- **UI-first setup** via a config flow and options flow — no YAML required. Services are
  still available for automations if you want them.
- **People and tasks** you define yourself (name, icon, category, points/weight,
  active/inactive). A person can optionally be linked to an existing `person.*` entity.
- **Log or backfill** a completion: log it immediately, or add one for a different time with
  an optional note. An undo button reverts the most recent entry.
- **Target vs. actual per period** — set how often each person should do each task per day,
  week, or month; sensors expose actual, remaining, percentage, and an on-track indicator.
- **Statistics and ranking** over a configurable window (default 90 days), broken down by
  task and by time window (today / 7 / 30 / 90 days / all).
- **Three bundled Lovelace cards** (see below), registered automatically as a frontend
  resource — no separate frontend install needed.
- **A WebSocket API** and **dynamic per-person sensors** (plus one sensor per target), for
  dashboards, exports, and automations.
- **Multilingual UI: German, English, and Spanish.**

## The three Lovelace cards

- `hausarbeit-claim-card` — buttons to log a completion immediately or backfill one with
  time/note, plus an undo button.
- `hausarbeit-stats-card` — the ranking of people and the breakdown by task / time window.
- `hausarbeit-targets-card` — a progress bar per target for the current period.

<!-- IMAGE: the repo ships screenshots under images/ (claim-card.png, stats-card.png, targets-card.png).
     Insert them here as a 3-up row once captured. A short GIF of logging a chore + undo would fit well too. -->

| Log a completion | Statistics & ranking | Target vs. actual |
|:---:|:---:|:---:|
| ![Claim card](images/claim-card.png) | ![Stats card](images/stats-card.png) | ![Targets card](images/targets-card.png) |

## Installation (HACS)

Not in the default HACS index yet, so add it as a **custom repository**:

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. URL `https://github.com/Jo-Highness/hausarbeit`, category **Integration**.
3. Add, then install; restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → search for "Hausarbeit-Tracker".

Once the repository is accepted into the default HACS store, the custom-repository step
won't be needed anymore.

## Honest limitations

- This is an **early 0.1.x release**. Expect rough edges and possible breaking changes
  before 1.0.
- The **written documentation is fullest in German**. The primary `README.md` is in
  English with a German section; a fuller German write-up lives in `README.de.md`.
- It is a **tracker / bookkeeping tool**. It does not assign or enforce chores — it records
  what people did and reports on it.
- Screenshots in the repo are being finalized; the images above are placeholders until the
  captures are in.

Feedback, bug reports, and ideas are welcome on the issue tracker. Thanks for taking a look.

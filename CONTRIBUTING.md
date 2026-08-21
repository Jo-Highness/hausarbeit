# Contributing to Hausarbeit-Tracker

Thanks for your interest in improving **Hausarbeit-Tracker**, a local
Home Assistant custom integration for tracking who does which household chore,
when, and how it adds up over time. Contributions of all kinds are welcome:
bug reports, feature ideas, documentation, translations, and code.

## Repository layout

```
custom_components/hausarbeit/      # The integration (Python)
├── __init__.py                    # Setup / teardown, service + frontend registration
├── config_flow.py                # Config & options flow
├── const.py                      # Constants
├── coordinator.py                # In-memory state / update coordination
├── sensor.py                     # Sensor platform (per-person + per-target)
├── store.py                      # Persistent storage
├── targets.py                    # Soll/Ist (target vs. actual) logic
├── websocket.py                  # WebSocket API for the cards
├── services.yaml                 # Service definitions
├── manifest.json                 # Integration manifest
├── translations/                 # UI translations (de, en, es)
├── brand/                        # Integration icon/logo assets
└── frontend/                     # Bundled Lovelace cards (plain JavaScript)
    ├── hausarbeit-claim-card.js
    ├── hausarbeit-stats-card.js
    └── hausarbeit-targets-card.js

tests/                            # pytest test suite
```

### Frontend cards

The three Lovelace cards in `custom_components/hausarbeit/frontend/` are plain
ES2020 JavaScript with **no build step**. They reuse the LitElement that Home
Assistant itself loads at runtime (no CDN, no bundler, no npm dependencies).
Edit the `.js` files directly; there is nothing to compile.

## Development environment

You need Python 3.12+ (matching a current Home Assistant release).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install ruff pytest pytest-homeassistant-custom-component
```

## Linting and formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. Before opening a pull request, make sure both pass:

```bash
ruff check .
ruff format --check .
```

To auto-fix and format locally:

```bash
ruff check --fix .
ruff format .
```

## Running the tests

The test suite uses `pytest` together with
[`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component):

```bash
pytest
```

All tests must pass before a pull request can be merged.

## Commit messages

Please follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification. This keeps the history readable and lets the release drafter
categorize changes automatically. Examples:

```
feat: add monthly target period to the targets card
fix: correct week-start handling for stats sensor
docs: document the WebSocket API in the README
ci: run ruff in the validation workflow
chore: bump dependabot schedule to weekly
```

Common types: `feat`, `fix`, `docs`, `ci`, `chore`, `refactor`, `test`, `perf`.

## Pull request process

1. Fork the repository and create a feature branch off `main`.
2. Make your change, keeping commits focused and using Conventional Commits.
3. Run `ruff check .`, `ruff format --check .`, and `pytest` locally.
4. Update the documentation if you change user-facing behavior. If you touch
   user-facing text in `README.md`, update `README.de.md` to match.
5. Add a note to the `## [Unreleased]` section of `CHANGELOG.md`.
6. Open a pull request against `main`, fill in the PR template, and describe
   what changed and why.

A maintainer will review your PR. Please be responsive to feedback; small,
well-scoped PRs are the easiest to review and merge.

Thank you for contributing!

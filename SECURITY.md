# Security Policy

## Supported versions

Only the **latest released version** of Hausarbeit-Tracker receives security
updates. Please make sure you are running the most recent release (via HACS or a
manual update) before reporting an issue.

| Version | Supported |
| ------- | --------- |
| latest  | ✅        |
| older   | ❌        |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/Jo-Highness/hausarbeit/security/advisories/new).
This lets us discuss and fix the issue before any details become public.

Please include, where possible:

- A description of the vulnerability and its impact.
- Steps to reproduce or a proof of concept.
- The affected version and your Home Assistant version.

We aim to acknowledge reports promptly and will keep you informed about progress
toward a fix and disclosure.

## Scope and data handling

Hausarbeit-Tracker is a **local** Home Assistant integration:

- It stores all of its data locally in Home Assistant's own storage
  (`.storage`); nothing is sent to any external server.
- It uses **no cloud services** and requires **no external credentials, API
  keys, or accounts**.
- Its network surface is limited to Home Assistant's own HTTP and WebSocket APIs
  (used by the bundled Lovelace cards).

Because of this, the most relevant security considerations are those of your
Home Assistant instance itself. Keeping Home Assistant and this integration up to
date is the best protection.

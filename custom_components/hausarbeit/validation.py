"""Gemeinsame Eingabe-Validierung (Services + Options-Flow)."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

# Die Karten setzen die Personenfarbe direkt als CSS-Wert (``--chip-accent: <farbe>``).
# Erlaubt sind daher nur unkritische CSS-Farbangaben: Hex (#rgb, #rgba, #rrggbb,
# #rrggbbaa), Farbnamen (``teal``) und Funktionen wie ``rgb(…)``/``hsl(…)``/``var(--…)``
# ohne Zeichen, mit denen man aus dem style-Attribut ausbrechen könnte.
_COLOR_RE = re.compile(
    r"^(#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
    r"|[a-zA-Z]{3,30}"
    r"|(?:rgb|rgba|hsl|hsla|var)\([0-9a-zA-Z\s,.%/+\-]{1,60}\))$"
)


def is_valid_color(value: Any) -> bool:
    """True, wenn ``value`` eine erlaubte CSS-Farbangabe ist."""
    return isinstance(value, str) and bool(_COLOR_RE.match(value.strip()))


def color_value(value: Any) -> str | None:
    """Voluptuous-Validator: leere Eingabe -> None (Farbe entfernen), sonst geprüft."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not is_valid_color(text):
        raise vol.Invalid(f"invalid color: {value!r}")
    return text

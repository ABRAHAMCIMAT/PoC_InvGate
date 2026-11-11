"""Redacción de PII en logs y respuestas."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?[0-9][0-9 .-]{7,}")


def redact(text: str) -> str:
    """Reemplaza emails y teléfonos por marcadores."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text

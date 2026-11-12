"""Redacción de PII en logs y respuestas."""

from __future__ import annotations

import re

# Cada coincidencia solo puede empezar al inicio de un token (lookbehind) y los cuantificadores
# son posesivos (++), así que no hay retroceso: tiempo lineal incluso con entradas hostiles.
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]++@[\w-]++(?:\.[\w-]++)++")

# Racha de dígitos y separadores: una sola clase con cuantificador posesivo, sin anidar.
# Si es un teléfono (8 o más dígitos) se decide en Python, sin regex.
_PHONE_RUN = re.compile(r"(?<![\d+])\+?[\d .-]{8,}+")
_SEPARATORS = " .-"
MIN_PHONE_DIGITS = 8
# Una fecha ISO (AAAA-MM-DD) también tiene 8 dígitos, pero no es un dato personal.
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _phone(match: re.Match[str]) -> str:
    run = match.group(0)
    core = run.strip(_SEPARATORS)
    if sum(c.isdigit() for c in core) < MIN_PHONE_DIGITS or not core.lstrip("+")[:1].isdigit():
        return run
    if _ISO_DATE.fullmatch(core):
        return run
    lead = run[: len(run) - len(run.lstrip(_SEPARATORS))]
    trail = run[len(run.rstrip(_SEPARATORS)) :]
    return f"{lead}[PHONE]{trail}"


def redact(text: str) -> str:
    """Reemplaza emails y teléfonos por marcadores."""
    text = _EMAIL.sub("[EMAIL]", text)
    return _PHONE_RUN.sub(_phone, text)

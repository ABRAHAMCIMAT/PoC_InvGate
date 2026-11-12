"""Redacción de PII en logs y respuestas."""

from __future__ import annotations

import re

# Las regex solo usan clases simples con cuantificador posesivo, sin grupos repetidos, y cada
# coincidencia empieza al inicio de un token: no hay retroceso y el tiempo es lineal incluso
# con entradas hostiles. Lo que no se expresa así (estructura del dominio, número de dígitos)
# se valida en Python.
_EMAIL_CANDIDATE = re.compile(r"(?<![\w.+-])[\w.+-]++@[\w.-]++")

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


def _email(match: re.Match[str]) -> str:
    candidate = match.group(0)
    address = candidate.rstrip(".-")  # un punto final suele cerrar la frase
    domain = address.rpartition("@")[2]
    labels = domain.split(".")
    if len(labels) < 2 or not all(labels):
        return candidate
    return "[EMAIL]" + candidate[len(address) :]


def redact(text: str) -> str:
    """Reemplaza emails y teléfonos por marcadores."""
    text = _EMAIL_CANDIDATE.sub(_email, text)
    return _PHONE_RUN.sub(_phone, text)

"""Redacción de PII en logs y respuestas.

Las dos búsquedas corren en tiempo lineal incluso con entradas hostiles:

- Emails: se recorre el texto por tokens separados por espacios (``\\S+`` nunca retrocede) y
  cada token se valida con Python, sin regex.
- Teléfonos: una sola clase de caracteres con cuantificador posesivo, sin grupos repetidos;
  el número de dígitos se comprueba en Python.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\S+")
_LOCAL_EXTRA = "._+-"
_LABEL_EXTRA = "_-"
# Caracteres que suelen rodear un correo en una frase o en JSON y no forman parte de él.
_WRAPPERS = "\"'()<>[]{},;:!?."

_PHONE_RUN = re.compile(r"(?<![\d+])\+?[\d .-]{8,}+")
_SEPARATORS = " .-"
MIN_PHONE_DIGITS = 8
# Una fecha ISO (AAAA-MM-DD) también tiene 8 dígitos, pero no es un dato personal.
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_email(address: str) -> bool:
    local, at, domain = address.partition("@")
    if not at or not local or "@" in domain:
        return False
    if not all(c.isalnum() or c in _LOCAL_EXTRA for c in local):
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and all(
        label and all(c.isalnum() or c in _LABEL_EXTRA for c in label) for label in labels
    )


def _email_token(match: re.Match[str]) -> str:
    token = match.group(0)
    if "@" not in token:
        return token
    core = token.strip(_WRAPPERS)
    if not core or not _is_email(core):
        return token
    start = token.index(core)
    return f"{token[:start]}[EMAIL]{token[start + len(core) :]}"


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
    text = _TOKEN.sub(_email_token, text)
    return _PHONE_RUN.sub(_phone, text)

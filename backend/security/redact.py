"""Redacción de PII en logs y respuestas."""

from __future__ import annotations

import re

# Cada coincidencia solo puede empezar al inicio de un token (lookbehind) y los cuantificadores
# son posesivos (++), así que no hay retroceso: tiempo lineal incluso con entradas hostiles.
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]++@[\w-]++(?:\.[\w-]++)++")
# Un teléfono empieza y termina en dígito: 8 o más dígitos con separadores sueltos entre ellos.
_PHONE = re.compile(r"(?<![\d+])\+?\d(?:[ .-]?+\d){7,}+")


def redact(text: str) -> str:
    """Reemplaza emails y teléfonos por marcadores."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text

"""Agente de Diagnóstico: causa raíz probable por reglas, o con el LLM si hay uno real."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from backend.llmops.llm import LLM, LLMError

DIAGNOSIS_PROMPT = (
    "Eres el agente de diagnóstico de una mesa de ayuda. En una sola frase en español, indica la "
    "causa raíz más probable del problema descrito y la primera comprobación que debe hacerse."
)


@dataclass(frozen=True)
class Diagnosis:
    cause: str
    confident: bool


# (categoría, palabras clave, causa probable)
RULES: list[tuple[str, tuple[str, ...], str]] = [
    ("acceso", ("bloquead",), "Cuenta bloqueada por intentos fallidos; revisar el estado en el directorio."),
    (
        "acceso",
        ("contrasena", "password", "clave", "olvide"),
        "Contraseña caducada u olvidada; procede autoservicio.",
    ),
    ("acceso", ("vpn",), "Cliente VPN desactualizado o sin segundo factor configurado."),
    (
        "software",
        ("instalar", "licencia", "programa", "aplicacion", "app", "software"),
        "Software fuera del catálogo estándar; requiere licencia y aprobación.",
    ),
    ("hardware", ("enciende", "prende", "bateria", "cargador"), "Fallo de alimentación: batería o cargador."),
    ("hardware", ("pantalla",), "Fallo de pantalla o de su conexión."),
    ("hardware", ("impresora", "imprimir"), "Impresora sin red o cola de impresión bloqueada."),
    ("infraestructura", ("produccion", "servidor", "caido", "todos"), "Caída de un servicio compartido."),
    ("general", ("correo", "outlook", "buzon", "sincroniza"), "Perfil de correo dañado o buzón lleno."),
]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def diagnose(text: str, category: str | None, llm: LLM | None = None) -> Diagnosis:
    """Devuelve la causa probable. `confident` es False si no se pudo determinar."""
    if llm is not None and llm.name != "mock":
        try:
            answer = llm.complete(DIAGNOSIS_PROMPT, text).strip()
        except LLMError:
            answer = ""
        if answer and not llm.degraded:
            return Diagnosis(answer.splitlines()[0][:300], True)
    norm = _norm(text)
    for rule_category, keywords, cause in RULES:
        if (category is None or category == rule_category) and any(k in norm for k in keywords):
            return Diagnosis(cause, True)
    for _, keywords, cause in RULES:
        if any(k in norm for k in keywords):
            return Diagnosis(cause, True)
    return Diagnosis(
        "Causa no determinada con la información recibida; requiere revisión de un agente.", False
    )

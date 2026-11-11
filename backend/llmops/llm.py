"""LLM mock determinista para desarrollo sin credenciales."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLM(ABC):
    """Contrato de un modelo de lenguaje."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Devuelve la respuesta del modelo."""


class MockLLM(LLM):
    """LLM determinista que clasifica por palabras clave."""

    def complete(self, system: str, user: str) -> str:
        text = user.lower()
        if any(k in text for k in ("contraseña", "password", "clave", "acceso")):
            return "categoria=acceso;prioridad=alta;requiere_aprobacion=no"
        if any(k in text for k in ("instalar", "software", "aplicación", "app")):
            return "categoria=software;prioridad=media;requiere_aprobacion=si"
        if any(k in text for k in ("no enciende", "roto", "falla", "error", "caído")):
            return "categoria=hardware;prioridad=alta;requiere_aprobacion=no"
        return "categoria=general;prioridad=media;requiere_aprobacion=no"


def get_llm(provider: str = "mock") -> LLM:
    """Devuelve el LLM configurado. Por ahora solo mock."""
    if provider == "mock":
        return MockLLM()
    raise ValueError(f"LLM_PROVIDER no soportado: {provider}")

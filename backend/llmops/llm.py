"""Modelos de lenguaje: mock determinista y servidores compatibles con OpenAI (Ollama, Jan)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Proveedores que exponen /v1/chat/completions compatible con OpenAI.
OPENAI_COMPATIBLE = {"ollama", "jan", "openai_compatible"}
DEFAULT_MODELS = {"ollama": "llama3.1:8b", "jan": "llama3.1-8b-instruct"}
DEFAULT_URLS = {"ollama": "http://localhost:11434/v1", "jan": "http://localhost:1337/v1"}


class LLMError(Exception):
    """El modelo no respondió o respondió algo inutilizable."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def estimate_tokens(text: str) -> int:
    """Aproximación de ~4 caracteres por token cuando el servidor no informa uso."""
    return max(1, len(text) // 4) if text else 0


class LLM(ABC):
    """Contrato de un modelo de lenguaje."""

    name: str = "llm"
    model: str = ""

    def __init__(self) -> None:
        self.last_usage = Usage()
        self.degraded = False

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Devuelve la respuesta del modelo."""


class MockLLM(LLM):
    """LLM determinista que clasifica por palabras clave."""

    name = "mock"
    model = "mock-keywords"

    def complete(self, system: str, user: str) -> str:
        text = user.lower()
        out = self._classify(text)
        self.last_usage = Usage(estimate_tokens(system + user), estimate_tokens(out))
        return out

    @staticmethod
    def _classify(text: str) -> str:
        if any(k in text for k in ("producción", "produccion", "todos los usuarios", "toda la oficina")):
            return "categoria=infraestructura;prioridad=critica;requiere_aprobacion=no"
        if any(k in text for k in ("contraseña", "password", "clave", "acceso")):
            return "categoria=acceso;prioridad=alta;requiere_aprobacion=no"
        if any(k in text for k in ("instalar", "software", "aplicación", "app", "licencia")):
            return "categoria=software;prioridad=media;requiere_aprobacion=si"
        if any(k in text for k in ("no enciende", "roto", "falla", "error", "caído", "caido")):
            return "categoria=hardware;prioridad=alta;requiere_aprobacion=no"
        return "categoria=general;prioridad=media;requiere_aprobacion=no"


class OpenAICompatibleLLM(LLM):
    """Cliente de /v1/chat/completions (Ollama, Jan, vLLM, LM Studio...)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 30.0,
        name: str = "openai_compatible",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__()
        if not model:
            raise ValueError("LLM_MODEL es obligatorio para un LLM compatible con OpenAI")
        self.name = name
        self.model = model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers, transport=transport
        )

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            resp = self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name} no responde: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"{self.name} devolvió HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Respuesta inesperada de {self.name}") from exc
        usage = body.get("usage") or {}
        self.last_usage = Usage(
            int(usage.get("prompt_tokens") or estimate_tokens(system + user)),
            int(usage.get("completion_tokens") or estimate_tokens(content or "")),
        )
        return str(content or "").strip()


class FallbackLLM(LLM):
    """Usa el LLM principal y, si falla, el mock. Marca `degraded` para el semáforo."""

    def __init__(self, primary: LLM, fallback: LLM | None = None) -> None:
        super().__init__()
        self.primary = primary
        self.fallback = fallback or MockLLM()
        self.name = primary.name
        self.model = primary.model

    def complete(self, system: str, user: str) -> str:
        try:
            out = self.primary.complete(system, user)
            self.degraded = False
            self.name, self.model = self.primary.name, self.primary.model
            self.last_usage = self.primary.last_usage
            return out
        except LLMError as exc:
            logger.warning("LLM principal no disponible, se usa mock: %s", exc)
            out = self.fallback.complete(system, user)
            self.degraded = True
            self.name, self.model = self.fallback.name, self.fallback.model
            self.last_usage = self.fallback.last_usage
            return out


def get_llm(
    provider: str = "mock",
    base_url: str = "",
    model: str = "",
    api_key: str = "",
    timeout: float = 30.0,
) -> LLM:
    """Devuelve el LLM configurado. Los remotos degradan al mock si no responden."""
    if provider == "mock":
        return MockLLM()
    if provider in OPENAI_COMPATIBLE:
        primary = OpenAICompatibleLLM(
            base_url=base_url or DEFAULT_URLS.get(provider, ""),
            model=model or DEFAULT_MODELS.get(provider, ""),
            api_key=api_key,
            timeout=timeout,
            name=provider,
        )
        return FallbackLLM(primary)
    raise ValueError(f"LLM_PROVIDER no soportado: {provider}")

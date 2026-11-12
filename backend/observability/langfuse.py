"""Exportador opcional a Langfuse vía su API pública de ingesta (sin dependencias extra)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.security.redact import redact

logger = logging.getLogger(__name__)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")


class LangfuseExporter:
    """Envía una traza por conversación con un span o generación por agente.

    Solo se activa con LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY. El envío corre en un hilo
    para no añadir latencia al chat, y los errores se registran sin interrumpir el flujo.
    """

    def __init__(
        self,
        host: str,
        public_key: str,
        secret_key: str,
        include_content: bool = False,
        transport: httpx.BaseTransport | None = None,
        background: bool = True,
    ) -> None:
        self.url = host.rstrip("/") + "/api/public/ingestion"
        self.include_content = include_content
        self.background = background
        self._client = httpx.Client(auth=(public_key, secret_key), timeout=10.0, transport=transport)

    def _content(self, text: str) -> str:
        return redact(text) if self.include_content else f"[{len(text)} caracteres omitidos]"

    def build_batch(self, trace: dict[str, Any], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        trace_id = trace["id"]
        batch: list[dict[str, Any]] = [
            {
                "id": uuid.uuid4().hex,
                "timestamp": _iso(trace["start"]),
                "type": "trace-create",
                "body": {
                    "id": trace_id,
                    "name": trace.get("name", "chat"),
                    "timestamp": _iso(trace["start"]),
                    "input": self._content(trace.get("input", "")),
                    "output": self._content(trace.get("output", "")),
                    "metadata": trace.get("metadata", {}),
                    "tags": ["valkiria-invgate"],
                },
            }
        ]
        for step in steps:
            body: dict[str, Any] = {
                "id": uuid.uuid4().hex,
                "traceId": trace_id,
                "name": step["agent"],
                "startTime": _iso(step["start"]),
                "endTime": _iso(step["end"]),
                "output": self._content(step.get("output", "")),
                "level": {"ok": "DEFAULT", "warning": "WARNING", "error": "ERROR"}.get(
                    step["status"], "DEFAULT"
                ),
                "metadata": {"status": step["status"]},
            }
            kind = "span-create"
            if step.get("model"):
                kind = "generation-create"
                body["model"] = step["model"]
                body["usage"] = {
                    "input": step.get("prompt_tokens", 0),
                    "output": step.get("completion_tokens", 0),
                    "unit": "TOKENS",
                }
            batch.append(
                {"id": uuid.uuid4().hex, "timestamp": _iso(step["start"]), "type": kind, "body": body}
            )
        return batch

    def export(self, trace: dict[str, Any], steps: list[dict[str, Any]]) -> None:
        batch = self.build_batch(trace, steps)
        if self.background:
            threading.Thread(target=self._send, args=(batch,), daemon=True).start()
        else:
            self._send(batch)

    def _send(self, batch: list[dict[str, Any]]) -> None:
        try:
            resp = self._client.post(self.url, json={"batch": batch})
            if resp.status_code >= 400:
                logger.warning("Langfuse rechazó la traza: HTTP %s", resp.status_code)
        except httpx.HTTPError as exc:
            logger.warning("No se pudo enviar la traza a Langfuse: %s", exc)

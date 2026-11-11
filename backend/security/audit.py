"""Audit trail append-only en archivo."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from backend.security.redact import redact


class AuditLog:
    """Registro de auditoría append-only con redacción de PII."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def record(self, event: str, actor: str, data: dict[str, Any] | None = None) -> None:
        entry = {
            "ts": time.time(),
            "event": event,
            "actor": actor,
            "data": redact(json.dumps(data or {}, ensure_ascii=False)),
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

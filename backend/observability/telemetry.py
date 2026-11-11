"""Telemetría JSONL modelo-agnóstica."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from backend.security.redact import redact


class Telemetry:
    """Registra eventos de telemetría en JSONL."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def emit(self, event: str, **fields: Any) -> None:
        entry = {"ts": time.time(), "event": event, **fields}
        safe = {k: (redact(v) if isinstance(v, str) else v) for k, v in entry.items()}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(safe, ensure_ascii=False) + "\n")

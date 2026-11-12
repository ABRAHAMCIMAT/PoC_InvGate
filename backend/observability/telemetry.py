"""Telemetría JSONL modelo-agnóstica."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from typing import Any

from backend.security.redact import redact


class Telemetry:
    """Registra eventos de telemetría en JSONL (una línea por evento)."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: str, **fields: Any) -> None:
        entry = {"ts": time.time(), "event": event, **fields}
        safe = {k: (redact(v) if isinstance(v, str) else v) for k, v in entry.items()}
        line = json.dumps(safe, ensure_ascii=False) + "\n"
        with self._lock, open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line)

    def read(self, since: float | None = None) -> Iterator[dict[str, Any]]:
        """Itera los eventos guardados, ignorando líneas corruptas."""
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict) and (since is None or entry.get("ts", 0) >= since):
                    yield entry

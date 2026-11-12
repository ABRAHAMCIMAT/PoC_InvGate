"""Audit trail append-only en archivo, encadenado por hash."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Iterator
from typing import Any

from backend.security.redact import redact

GENESIS = "0" * 64


class AuditLog:
    """Registro de auditoría append-only con redacción de PII.

    Cada entrada guarda el hash de la anterior (`prev`) y el suyo (`hash`), así que borrar o
    editar una línea rompe la cadena y `verify()` lo detecta.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._last = self._tail_hash()

    def _tail_hash(self) -> str:
        last = GENESIS
        for entry in self.read():
            last = entry.get("hash", last)
        return last

    @staticmethod
    def _digest(entry: dict[str, Any]) -> str:
        body = {k: v for k, v in entry.items() if k != "hash"}
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def record(self, event: str, actor: str, data: dict[str, Any] | None = None) -> None:
        with self._lock:
            entry: dict[str, Any] = {
                "ts": time.time(),
                "event": event,
                "actor": actor,
                "data": redact(json.dumps(data or {}, ensure_ascii=False)),
                "prev": self._last,
            }
            entry["hash"] = self._digest(entry)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._last = entry["hash"]

    def read(self) -> Iterator[dict[str, Any]]:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    yield {"corrupt": True}

    def verify(self) -> bool:
        """Comprueba que ninguna entrada se haya editado, borrado o reordenado."""
        prev = GENESIS
        for entry in self.read():
            if entry.get("corrupt") or entry.get("prev") != prev or self._digest(entry) != entry.get("hash"):
                return False
            prev = entry["hash"]
        return True

"""Proveedor simulated: demo persistente en archivo, pensado para aprobaciones en Teams."""

from __future__ import annotations

import itertools
import json
import logging
import os
import threading

from backend.invgate.models import Comment, Incident
from backend.ticketing.demo import DemoProvider

logger = logging.getLogger(__name__)


class SimulatedProvider(DemoProvider):
    """Como el demo, pero guarda tickets y comentarios en un JSON para sobrevivir reinicios.

    Útil para probar aprobaciones en Teams, donde la decisión puede llegar horas después.
    """

    prefix = "SIM"

    def __init__(self, path: str | None = None) -> None:
        super().__init__()
        self.path = path
        self._lock = threading.Lock()
        if path:
            self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer %s: %s", self.path, exc)
            return
        self._incidents = {k: Incident(**v) for k, v in raw.get("incidents", {}).items()}
        self._comments = {k: [Comment(**c) for c in v] for k, v in raw.get("comments", {}).items()}
        self._counter = itertools.count(int(raw.get("counter", 0)) + 1)

    def _changed(self) -> None:
        if not self.path:
            return
        # Se guarda el siguiente valor del contador sin consumirlo.
        nxt = next(self._counter)
        self._counter = itertools.count(nxt)
        data = {
            "counter": nxt - 1,
            "incidents": {k: v.model_dump(mode="json") for k, v in self._incidents.items()},
            "comments": {k: [c.model_dump(mode="json") for c in v] for k, v in self._comments.items()},
        }
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)

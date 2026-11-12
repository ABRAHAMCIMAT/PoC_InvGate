"""Almacén de referencias de conversación de Teams para mensajes proactivos."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from botbuilder.schema import ConversationReference

logger = logging.getLogger(__name__)

DEFAULT_KEY = "default"


class ReferenceStore:
    """Guarda la conversación 1:1 de cada usuario con el bot, por id de Teams, AAD y correo.

    El bot solo puede escribir a alguien que ya le habló (o lo instaló). La primera persona
    que lo hace queda también como `default`, para el PoC con un único manager.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self._refs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    self._refs = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("No se pudo leer %s: %s", path, exc)

    def save(self, reference: ConversationReference, *keys: str | None) -> None:
        data = reference.serialize()
        with self._lock:
            for key in {k.strip().lower() for k in keys if k}:
                self._refs[key] = data
            self._refs.setdefault(DEFAULT_KEY, data)
            self._flush()

    def get(self, *keys: str | None) -> ConversationReference | None:
        for key in [*(k for k in keys if k), DEFAULT_KEY]:
            data = self._refs.get(key.strip().lower())
            if data:
                return ConversationReference.deserialize(data)
        return None

    def _flush(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._refs, fh)
        os.replace(tmp, self.path)

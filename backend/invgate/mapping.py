"""Mapeo de campos y valores entre el dominio del PoC e InvGate."""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.invgate.models import Incident

logger = logging.getLogger(__name__)


def _load_json(raw: str, name: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("%s no es JSON válido; se ignora", name)
        return None


class FieldMapper:
    """Traduce nombres de campo del dominio a los de InvGate.

    `INVGATE_FIELD_MAP` es un JSON del tipo:
    {"title": "title", "description": "description", "category": "category_id"}
    Se combina con `defaults`; lo configurado tiene prioridad.
    """

    def __init__(self, raw: str = "", defaults: dict[str, str] | None = None) -> None:
        self._map: dict[str, str] = dict(defaults or {})
        parsed = _load_json(raw, "INVGATE_FIELD_MAP")
        if isinstance(parsed, dict):
            self._map.update({str(k): str(v) for k, v in parsed.items()})

    def to_invgate(self, field: str) -> str:
        return self._map.get(field, field)

    def from_invgate(self, field: str) -> str:
        for domain, invgate in self._map.items():
            if invgate == field:
                return domain
        return field

    def map_payload(self, incident: Incident) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for domain, value in incident.model_dump(mode="json", exclude_none=True).items():
            if domain in {"id", "number", "created_at", "updated_at", "extra"}:
                continue
            payload[self.to_invgate(domain)] = value
        payload.update(incident.extra)
        return payload


class ValueMapper:
    """Traduce valores del dominio a los de InvGate.

    `INVGATE_VALUE_MAP` es un JSON del tipo:
    {"priority": {"alta": "3", "media": "2", "baja": "1"}, "category": {"acceso": "12"}}
    Se combina por campo con `defaults`; lo configurado tiene prioridad.
    """

    def __init__(self, raw: str = "", defaults: dict[str, dict[str, str]] | None = None) -> None:
        self._map: dict[str, dict[str, str]] = {k: dict(v) for k, v in (defaults or {}).items()}
        parsed = _load_json(raw, "INVGATE_VALUE_MAP")
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if isinstance(v, dict):
                    self._map.setdefault(str(k), {}).update({str(kk): str(vv) for kk, vv in v.items()})

    def to_invgate(self, field: str, value: Any) -> Any:
        mapping = self._map.get(field)
        if mapping and str(value) in mapping:
            return mapping[str(value)]
        return value

    def from_invgate(self, field: str, value: Any) -> Any:
        mapping = self._map.get(field)
        if mapping and value is not None:
            for domain, invgate in mapping.items():
                if invgate == str(value):
                    return domain
        return value

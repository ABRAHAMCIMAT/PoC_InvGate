"""Mapeo de campos y valores entre el dominio del PoC e InvGate."""

from __future__ import annotations

import json
from typing import Any

from backend.invgate.models import Incident


class FieldMapper:
    """Traduce nombres de campo del dominio a los de InvGate.

    `INVGATE_FIELD_MAP` es un JSON del tipo:
    {"title": "title", "description": "description", "category": "category"}
    """

    def __init__(self, raw: str = "") -> None:
        self._map: dict[str, str] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    self._map = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                self._map = {}

    def to_invgate(self, field: str) -> str:
        return self._map.get(field, field)

    def from_invgate(self, field: str) -> str:
        for domain, invgate in self._map.items():
            if invgate == field:
                return domain
        return field

    def map_payload(self, incident: Incident) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for domain, value in incident.model_dump(exclude_none=True).items():
            if domain in {"id", "number", "created_at", "updated_at", "extra"}:
                continue
            payload[self.to_invgate(domain)] = value
        payload.update(incident.extra)
        return payload


class ValueMapper:
    """Traduce valores del dominio a los de InvGate.

    `INVGATE_VALUE_MAP` es un JSON del tipo:
    {"priority": {"alta": "high", "media": "medium", "baja": "low"}}
    """

    def __init__(self, raw: str = "") -> None:
        self._map: dict[str, dict[str, str]] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    self._map = {
                        str(k): {str(kk): str(vv) for kk, vv in v.items()}
                        for k, v in parsed.items()
                        if isinstance(v, dict)
                    }
            except json.JSONDecodeError:
                self._map = {}

    def to_invgate(self, field: str, value: Any) -> Any:
        mapping = self._map.get(field)
        if mapping and value in mapping:
            return mapping[value]
        return value

    def from_invgate(self, field: str, value: Any) -> Any:
        mapping = self._map.get(field)
        if mapping:
            for domain, invgate in mapping.items():
                if invgate == value:
                    return domain
        return value

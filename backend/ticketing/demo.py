"""Proveedor demo en memoria (sin credenciales)."""

from __future__ import annotations

import itertools
import time

from backend.invgate.models import Comment, Incident
from backend.ticketing.base import TicketingProvider


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class DemoProvider(TicketingProvider):
    """Proveedor en memoria para desarrollo y pruebas sin InvGate."""

    prefix = "DEMO"

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._comments: dict[str, list[Comment]] = {}
        self._counter = itertools.count(1)

    def create_incident(self, incident: Incident) -> Incident:
        incident_id = f"{self.prefix}-{next(self._counter):04d}"
        now = _now()
        created = incident.model_copy(
            update={"id": incident_id, "number": incident_id, "created_at": now, "updated_at": now}
        )
        self._incidents[incident_id] = created
        self._comments[incident_id] = []
        self._changed()
        return created

    def get_incident(self, incident_id: str) -> Incident:
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"Incidente no encontrado: {incident_id}")
        return incident

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        current = self.get_incident(incident_id)
        changes = incident.model_dump(exclude_none=True, exclude={"id", "number", "created_at"})
        updated = current.model_copy(update={**changes, "updated_at": _now()})
        self._incidents[incident_id] = updated
        self._changed()
        return updated

    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        self.get_incident(incident_id)
        comment = Comment(
            id=f"C-{next(self._counter):04d}",
            incident_id=incident_id,
            body=body,
            author=author,
            created_at=_now(),
        )
        self._comments.setdefault(incident_id, []).append(comment)
        self._changed()
        return comment

    def list_comments(self, incident_id: str) -> list[Comment]:
        self.get_incident(incident_id)
        return list(self._comments.get(incident_id, []))

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        return list(self._incidents.values())[:limit]

    def _changed(self) -> None:
        """Gancho para proveedores que persisten (simulated)."""

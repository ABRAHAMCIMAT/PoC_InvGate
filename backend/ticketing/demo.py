"""Proveedor demo en memoria (sin credenciales)."""

from __future__ import annotations

import itertools
import time

from backend.invgate.models import Comment, Incident
from backend.ticketing.base import TicketingProvider


class DemoProvider(TicketingProvider):
    """Proveedor en memoria para desarrollo y pruebas sin InvGate."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._comments: dict[str, list[Comment]] = {}
        self._counter = itertools.count(1)

    def create_incident(self, incident: Incident) -> Incident:
        incident_id = f"DEMO-{next(self._counter):04d}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        created = incident.model_copy(
            update={"id": incident_id, "number": incident_id, "created_at": now, "updated_at": now}
        )
        self._incidents[incident_id] = created
        self._comments[incident_id] = []
        return created

    def get_incident(self, incident_id: str) -> Incident:
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"Incidente no encontrado: {incident_id}")
        return incident

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        current = self.get_incident(incident_id)
        updated = current.model_copy(update=incident.model_dump(exclude_none=True))
        updated.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._incidents[incident_id] = updated
        return updated

    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        self.get_incident(incident_id)
        comment = Comment(
            id=f"C-{next(self._counter):04d}",
            incident_id=incident_id,
            body=body,
            author=author,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._comments.setdefault(incident_id, []).append(comment)
        return comment

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        return list(self._incidents.values())[:limit]

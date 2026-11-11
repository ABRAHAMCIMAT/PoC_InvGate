"""Proveedor InvGate real que envuelve el cliente HTTP."""

from __future__ import annotations

from backend.invgate.client import InvGateClient
from backend.invgate.models import Comment, Incident
from backend.ticketing.base import TicketingProvider


class InvGateProvider(TicketingProvider):
    """Proveedor de ticketing sobre la API real de InvGate."""

    def __init__(self, client: InvGateClient) -> None:
        self._client = client

    def create_incident(self, incident: Incident) -> Incident:
        return self._client.create_incident(incident)

    def get_incident(self, incident_id: str) -> Incident:
        return self._client.get_incident(incident_id)

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        return self._client.update_incident(incident_id, incident)

    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        return self._client.add_comment(incident_id, body, author)

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        return self._client.list_incidents(limit)

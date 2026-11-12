"""Proveedor InvGate real que envuelve el cliente HTTP."""

from __future__ import annotations

from backend.invgate.client import InvGateClient
from backend.invgate.models import Comment, Incident
from backend.ticketing.base import TicketingProvider


class InvGateProvider(TicketingProvider):
    """Proveedor de ticketing sobre la API real de InvGate, con aprobaciones nativas."""

    def __init__(self, client: InvGateClient, author_id: str = "") -> None:
        self._client = client
        self.author_id = author_id

    def create_incident(self, incident: Incident) -> Incident:
        return self._client.create_incident(incident)

    def get_incident(self, incident_id: str) -> Incident:
        return self._client.get_incident(incident_id)

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        return self._client.update_incident(incident_id, incident)

    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        # En InvGate el autor debe ser un id de usuario; los nombres libres se ignoran.
        author_id = author if author and author.isdigit() else (self.author_id or None)
        return self._client.add_comment(incident_id, body, author_id)

    def list_comments(self, incident_id: str) -> list[Comment]:
        return self._client.list_comments(incident_id)

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        return self._client.list_incidents(limit)

    def request_approval(self, incident_id: str, approver: str, description: str) -> str | None:
        """Crea una aprobación espontánea y devuelve su approval_id."""
        if not approver:
            raise ValueError("POC_MANAGER_INVGATE_ID es obligatorio para aprobaciones en InvGate")
        self._client.request_approval(incident_id, approver, description, self.author_id or approver)
        pending = self._client.list_approvals(incident_id, only_pending=True)
        if not pending:
            return None
        latest = max(pending, key=lambda a: int(str(a.get("id", 0))) if str(a.get("id", "")).isdigit() else 0)
        return str(latest.get("id")) if latest.get("id") is not None else None

    def resolve_approval(
        self,
        incident_id: str,
        approval_ref: str | None,
        approved: bool,
        voter: str,
        note: str | None = None,
    ) -> None:
        """Vota en la aprobación nativa (PUT /incident.approval.accept|reject)."""
        approval_id = approval_ref
        if approval_id is None:
            pending = self._client.list_approvals(incident_id, only_pending=True)
            if not pending:
                raise LookupError(f"El incidente {incident_id} no tiene aprobaciones pendientes en InvGate")
            approval_id = str(pending[-1].get("id"))
        if approved:
            self._client.accept_approval(approval_id, voter, note)
        else:
            self._client.reject_approval(approval_id, voter, note)

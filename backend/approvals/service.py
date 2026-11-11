"""Servicio de aprobaciones con TTL y decisión única."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.invgate.models import Incident
from backend.ticketing.base import TicketingProvider


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    id: str
    incident_id: str
    manager_name: str
    manager_email: str
    reason: str
    created_at: float = field(default_factory=time.time)
    ttl_hours: int = 72
    decision: ApprovalDecision | None = None
    note: str | None = None
    decided_by: str | None = None
    decided_at: float | None = None

    @property
    def expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_hours * 3600

    @property
    def decided(self) -> bool:
        return self.decision is not None


class ApprovalService:
    """Gestiona aprobaciones: disparo, resolución y sincronización con InvGate."""

    def __init__(self, provider: TicketingProvider, ttl_hours: int = 72) -> None:
        self.provider = provider
        self.ttl_hours = ttl_hours
        self._requests: dict[str, ApprovalRequest] = {}

    def request_approval(
        self,
        incident: Incident,
        manager_name: str,
        manager_email: str,
        reason: str,
    ) -> ApprovalRequest:
        if not incident.id:
            raise ValueError("El incidente debe tener id para solicitar aprobación")
        req = ApprovalRequest(
            id=f"APR-{int(time.time())}",
            incident_id=incident.id,
            manager_name=manager_name,
            manager_email=manager_email,
            reason=reason,
            ttl_hours=self.ttl_hours,
        )
        self._requests[req.id] = req
        return req

    def decide(
        self,
        approval_id: str,
        decision: ApprovalDecision,
        user_id: str,
        note: str | None = None,
    ) -> ApprovalRequest:
        req = self._requests.get(approval_id)
        if req is None:
            raise KeyError(f"Aprobación no encontrada: {approval_id}")
        if req.expired:
            raise TimeoutError(f"Aprobación {approval_id} expiró")
        if req.decided:
            # Segundo clic ignorado: la decisión ya existe.
            return req
        req.decision = decision
        req.note = note
        req.decided_by = user_id
        req.decided_at = time.time()
        # Sincronizar con InvGate (aceptar/rechazar).
        incident = self.provider.get_incident(req.incident_id)
        if decision == ApprovalDecision.APPROVED:
            incident = incident.model_copy(update={"status": "in_progress"})
        else:
            incident = incident.model_copy(update={"status": "cancelled"})
        self.provider.update_incident(req.incident_id, incident)
        return req

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._requests[approval_id]

    def list(self) -> list[ApprovalRequest]:
        return list(self._requests.values())

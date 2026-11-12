"""Servicio de aprobaciones con TTL, decisión única y sincronización con el ticketing."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from backend.invgate.models import Incident
from backend.ticketing.base import TicketingProvider

logger = logging.getLogger(__name__)


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalForbiddenError(PermissionError):
    """Quien vota no es el manager asignado."""


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
    external_id: str | None = None
    manager_teams_id: str | None = None

    @property
    def expired(self) -> bool:
        return not self.decided and time.time() > self.created_at + self.ttl_hours * 3600

    @property
    def decided(self) -> bool:
        return self.decision is not None

    @property
    def status(self) -> str:
        if self.decision is not None:
            return self.decision.value
        return "expired" if self.expired else "pending"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "status": self.status,
            "manager_name": self.manager_name,
            "reason": self.reason,
            "note": self.note,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "created_at": self.created_at,
            "expires_at": self.created_at + self.ttl_hours * 3600,
            "external_id": self.external_id,
        }


Listener = Callable[[str, ApprovalRequest], None]


class ApprovalService:
    """Gestiona aprobaciones: disparo, notificación, resolución y sincronización.

    - Solo el manager asignado decide: por correo (`manager_email`) o por su id de Teams.
    - El segundo clic se ignora: la primera decisión válida queda fija.
    - La decisión se registra en el proveedor (aprobación nativa en InvGate) antes de darse
      por buena; si la sincronización falla, la aprobación sigue pendiente.
    """

    def __init__(
        self,
        provider: TicketingProvider,
        ttl_hours: int = 72,
        *,
        manager_name: str = "",
        manager_email: str = "",
        manager_invgate_id: str = "",
        manager_teams_id: str = "",
        store_path: str | None = None,
    ) -> None:
        self.provider = provider
        self.ttl_hours = ttl_hours
        self.manager_name = manager_name
        self.manager_email = manager_email
        self.manager_invgate_id = manager_invgate_id
        self.manager_teams_id = manager_teams_id
        self.store_path = store_path
        self._requests: dict[str, ApprovalRequest] = {}
        self._listeners: list[Listener] = []
        self._lock = threading.RLock()
        self._load()

    # ------------------------------------------------------------- Eventos
    def subscribe(self, listener: Listener) -> None:
        """`listener(evento, req)` con evento `requested` o `decided`."""
        self._listeners.append(listener)

    def _emit(self, event: str, req: ApprovalRequest) -> None:
        for listener in self._listeners:
            try:
                listener(event, req)
            except Exception:
                logger.exception("Listener de aprobaciones falló en %s", event)

    # --------------------------------------------------------------- API
    def request_approval(
        self,
        incident: Incident,
        manager_name: str | None = None,
        manager_email: str | None = None,
        reason: str = "",
    ) -> ApprovalRequest:
        if not incident.id:
            raise ValueError("El incidente debe tener id para solicitar aprobación")
        name = manager_name if manager_name is not None else self.manager_name
        email = manager_email if manager_email is not None else self.manager_email
        approver = self.manager_invgate_id or email or name or "manager"
        external_id = self.provider.request_approval(incident.id, approver, reason or incident.title)
        req = ApprovalRequest(
            id=f"APR-{uuid.uuid4().hex[:10]}",
            incident_id=incident.id,
            manager_name=name,
            manager_email=email,
            reason=reason or incident.title,
            ttl_hours=self.ttl_hours,
            external_id=external_id,
            manager_teams_id=self.manager_teams_id or None,
        )
        with self._lock:
            self._requests[req.id] = req
            self._save()
        self._emit("requested", req)
        return req

    def is_manager(self, req: ApprovalRequest, user_id: str | None, user_email: str | None) -> bool:
        """True si quien vota es el manager asignado. Sin manager configurado, cualquiera decide."""
        if not req.manager_email and not req.manager_teams_id:
            return True
        if (
            req.manager_email
            and user_email
            and user_email.strip().lower() == req.manager_email.strip().lower()
        ):
            return True
        return bool(req.manager_teams_id and user_id and user_id == req.manager_teams_id)

    def decide(
        self,
        approval_id: str,
        decision: ApprovalDecision,
        user_id: str,
        note: str | None = None,
        user_email: str | None = None,
    ) -> ApprovalRequest:
        with self._lock:
            req = self._requests.get(approval_id)
            if req is None:
                raise KeyError(f"Aprobación no encontrada: {approval_id}")
            if req.decided:
                # Segundo clic ignorado: la decisión ya existe.
                return req
            if req.expired:
                raise TimeoutError(f"Aprobación {approval_id} expiró")
            if not self.is_manager(req, user_id, user_email):
                raise ApprovalForbiddenError(f"{user_email or user_id} no es el manager de {approval_id}")
            note = (note or "").strip() or None
            voter = self.manager_invgate_id or user_email or user_id
            self.provider.resolve_approval(
                req.incident_id, req.external_id, decision == ApprovalDecision.APPROVED, voter, note
            )
            req.decision = decision
            req.note = note
            req.decided_by = user_email or user_id
            req.decided_at = time.time()
            self._save()
        self._emit("decided", req)
        return req

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._requests[approval_id]

    def list(self) -> list[ApprovalRequest]:
        return list(self._requests.values())

    # -------------------------------------------------------- Persistencia
    def _load(self) -> None:
        if not self.store_path or not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer %s: %s", self.store_path, exc)
            return
        for item in raw:
            decision = item.get("decision")
            item["decision"] = ApprovalDecision(decision) if decision else None
            req = ApprovalRequest(**item)
            self._requests[req.id] = req

    def _save(self) -> None:
        if not self.store_path:
            return
        data = []
        for req in self._requests.values():
            item = asdict(req)
            item["decision"] = req.decision.value if req.decision else None
            data.append(item)
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        tmp = f"{self.store_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, self.store_path)

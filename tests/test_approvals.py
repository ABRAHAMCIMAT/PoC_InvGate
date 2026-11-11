"""Pruebas del servicio de aprobaciones."""

from __future__ import annotations

import pytest

from backend.approvals.service import ApprovalDecision, ApprovalService
from backend.invgate.models import Incident
from backend.ticketing.demo import DemoProvider


def _service() -> tuple[ApprovalService, DemoProvider]:
    provider = DemoProvider()
    return ApprovalService(provider, ttl_hours=72), provider


def test_request_and_approve() -> None:
    service, provider = _service()
    incident = provider.create_incident(Incident(title="Instalar software"))
    req = service.request_approval(incident, "Manager", "m@x.com", "Instalación")
    assert req.decided is False
    decided = service.decide(req.id, ApprovalDecision.APPROVED, "user-1")
    assert decided.decision == ApprovalDecision.APPROVED
    updated = provider.get_incident(incident.id)
    assert updated.status == "in_progress"


def test_second_click_ignored() -> None:
    service, provider = _service()
    incident = provider.create_incident(Incident(title="Instalar"))
    req = service.request_approval(incident, "Manager", "m@x.com", "Instalación")
    service.decide(req.id, ApprovalDecision.APPROVED, "user-1")
    again = service.decide(req.id, ApprovalDecision.REJECTED, "user-1")
    assert again.decision == ApprovalDecision.APPROVED


def test_reject_cancels_ticket() -> None:
    service, provider = _service()
    incident = provider.create_incident(Incident(title="Instalar"))
    req = service.request_approval(incident, "Manager", "m@x.com", "Instalación")
    service.decide(req.id, ApprovalDecision.REJECTED, "user-1")
    updated = provider.get_incident(incident.id)
    assert updated.status == "cancelled"


def test_missing_approval_raises() -> None:
    service, _ = _service()
    with pytest.raises(KeyError):
        service.decide("APR-0", ApprovalDecision.APPROVED, "user-1")

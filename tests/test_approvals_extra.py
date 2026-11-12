"""Pruebas adicionales del servicio de aprobaciones."""

from __future__ import annotations

import pytest

from backend.approvals.service import ApprovalDecision, ApprovalRequest, ApprovalService
from backend.invgate.models import Incident
from backend.ticketing.demo import DemoProvider


def test_request_requires_id() -> None:
    service = ApprovalService(DemoProvider())
    incident = Incident(title="x")
    with pytest.raises(ValueError):
        service.request_approval(incident, "M", "m@x.com", "r")


def test_expired_raises() -> None:
    service = ApprovalService(DemoProvider())
    req = ApprovalRequest(
        id="APR-1",
        incident_id="DEMO-1",
        manager_name="M",
        manager_email="m@x.com",
        reason="r",
        created_at=0,
        ttl_hours=1,
    )
    service._requests[req.id] = req
    with pytest.raises(TimeoutError):
        service.decide("APR-1", ApprovalDecision.APPROVED, "u")


def test_get_and_list() -> None:
    service = ApprovalService(DemoProvider())
    incident = service.provider.create_incident(Incident(title="x"))
    req = service.request_approval(incident, "M", "m@x.com", "r")
    assert service.get(req.id).id == req.id
    assert req.id in [r.id for r in service.list()]

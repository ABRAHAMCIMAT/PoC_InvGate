"""Pruebas de la Adaptive Card de aprobación."""

from __future__ import annotations

from backend.approvals.service import ApprovalRequest
from backend.teams.adaptive_card import build_approval_card


def test_card_has_actions() -> None:
    req = ApprovalRequest(
        id="APR-1",
        incident_id="DEMO-0001",
        manager_name="Manager",
        manager_email="m@x.com",
        reason="Instalación",
    )
    card = build_approval_card(req)
    assert card["type"] == "AdaptiveCard"
    titles = [a["title"] for a in card["actions"]]
    assert "Aprobar" in titles
    assert "Rechazar" in titles
    assert card["actions"][0]["data"]["approval_id"] == "APR-1"

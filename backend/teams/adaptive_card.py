"""Generador de Adaptive Cards para aprobaciones en Teams."""

from __future__ import annotations

from typing import Any

from backend.approvals.service import ApprovalRequest


def build_approval_card(req: ApprovalRequest) -> dict[str, Any]:
    """Construye una Adaptive Card con botones Aprobar/Rechazar."""
    return {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": "Aprobación requerida",
            },
            {
                "type": "TextBlock",
                "text": f"Ticket {req.incident_id}: {req.reason}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Solicitada por {req.manager_name} ({req.manager_email})",
                "isSubtle": True,
                "wrap": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Aprobar",
                "data": {"approval_id": req.id, "decision": "approved"},
            },
            {
                "type": "Action.Submit",
                "title": "Rechazar",
                "data": {"approval_id": req.id, "decision": "rejected"},
            },
        ],
    }

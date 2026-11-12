"""Generador de Adaptive Cards para aprobaciones en Teams."""

from __future__ import annotations

from typing import Any

from backend.approvals.service import ApprovalRequest

NOTE_INPUT_ID = "note"


def build_approval_card(req: ApprovalRequest, open_url: str | None = None) -> dict[str, Any]:
    """Construye la tarjeta con observaciones y botones Aprobar/Rechazar.

    `Action.Submit` vuelve al bot con `approval_id`, `decision` y el texto de `note`.
    Si se da `open_url` (tarjetas enviadas por webhook, que no llegan al bot) se añade un enlace.
    """
    card: dict[str, Any] = {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "size": "Medium", "weight": "Bolder", "text": "Aprobación requerida"},
            {"type": "TextBlock", "text": f"Ticket {req.incident_id}", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": req.reason, "wrap": True},
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Aprobador", "value": req.manager_name or req.manager_email or "Manager"},
                    {"title": "Solicitud", "value": req.id},
                    {"title": "Vence en", "value": f"{req.ttl_hours} h"},
                ],
            },
            {
                "type": "Input.Text",
                "id": NOTE_INPUT_ID,
                "label": "Observaciones (opcional)",
                "placeholder": "Se mostrarán al solicitante",
                "isMultiline": True,
                "maxLength": 500,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Aprobar",
                "style": "positive",
                "data": {"approval_id": req.id, "decision": "approved"},
            },
            {
                "type": "Action.Submit",
                "title": "Rechazar",
                "style": "destructive",
                "data": {"approval_id": req.id, "decision": "rejected"},
            },
        ],
    }
    if open_url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Abrir solicitud", "url": open_url}]
        card["body"] = [b for b in card["body"] if b.get("type") != "Input.Text"]
    return card


def build_result_card(req: ApprovalRequest) -> dict[str, Any]:
    """Tarjeta que reemplaza a la original cuando ya hay decisión (sin botones)."""
    label = (
        "Aprobada" if req.status == "approved" else "Rechazada" if req.status == "rejected" else req.status
    )
    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "size": "Medium", "weight": "Bolder", "text": f"Solicitud {label.lower()}"},
        {"type": "TextBlock", "text": f"Ticket {req.incident_id}: {req.reason}", "wrap": True},
    ]
    if req.note:
        body.append(
            {"type": "TextBlock", "text": f"Observaciones: {req.note}", "wrap": True, "isSubtle": True}
        )
    return {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }

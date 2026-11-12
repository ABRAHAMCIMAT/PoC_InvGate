"""Endpoints de aprobaciones (alternativa web al bot de Teams y consulta de estado)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.approvals.service import ApprovalDecision, ApprovalForbiddenError
from backend.runtime import RuntimeDep
from backend.security.auth import AUTH_RESPONSES, AdminRole, AgentRole

router = APIRouter(prefix="/api/approvals", tags=["approvals"], responses=AUTH_RESPONSES)

APPROVAL_NOT_FOUND = "aprobación no encontrada"
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "La aprobación no existe"}}
DECISION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND,
    403: {"description": "Quien decide no es el manager asignado"},
    409: {"description": "InvGate no tiene una aprobación pendiente para el ticket"},
    410: {"description": "La aprobación venció sin respuesta"},
}


class DecisionRequest(BaseModel):
    decision: ApprovalDecision
    note: str | None = Field(default=None, max_length=500)
    user_email: str | None = Field(default=None, max_length=254)
    user_id: str | None = Field(default=None, max_length=200)


@router.get("")
def list_approvals(_: AgentRole, rt: RuntimeDep) -> list[dict[str, Any]]:
    return [r.as_dict() for r in rt.approvals.list()]


@router.get("/{approval_id}", responses=NOT_FOUND)
def get_approval(approval_id: str, _: AgentRole, rt: RuntimeDep) -> dict[str, Any]:
    try:
        return rt.approvals.get(approval_id).as_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=APPROVAL_NOT_FOUND) from exc


@router.post("/{approval_id}/decision", responses=DECISION_RESPONSES)
def decide(approval_id: str, body: DecisionRequest, role: AdminRole, rt: RuntimeDep) -> dict[str, Any]:
    """Registra la decisión del manager. Un segundo intento devuelve `changed: false`."""
    try:
        before = rt.approvals.get(approval_id).decided
        req = rt.approvals.decide(
            approval_id,
            body.decision,
            body.user_id or f"api:{role}",
            note=body.note,
            user_email=body.user_email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=APPROVAL_NOT_FOUND) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="la aprobación expiró") from exc
    except ApprovalForbiddenError as exc:
        raise HTTPException(status_code=403, detail="solo el manager asignado puede decidir") from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {**req.as_dict(), "changed": not before}

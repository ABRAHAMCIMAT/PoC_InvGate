"""Endpoints de aprobaciones (alternativa web al bot de Teams y consulta de estado)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.approvals.service import ApprovalDecision, ApprovalForbiddenError
from backend.runtime import Runtime, get_runtime
from backend.security.auth import require_role

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    decision: ApprovalDecision
    note: str | None = Field(default=None, max_length=500)
    user_email: str | None = Field(default=None, max_length=254)
    user_id: str | None = Field(default=None, max_length=200)


@router.get("")
def list_approvals(
    _: str = Depends(require_role("agent")), rt: Runtime = Depends(get_runtime)
) -> list[dict[str, Any]]:
    return [r.as_dict() for r in rt.approvals.list()]


@router.get("/{approval_id}")
def get_approval(
    approval_id: str, _: str = Depends(require_role("agent")), rt: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    try:
        return rt.approvals.get(approval_id).as_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="aprobación no encontrada") from exc


@router.post("/{approval_id}/decision")
def decide(
    approval_id: str,
    body: DecisionRequest,
    role: str = Depends(require_role("admin")),
    rt: Runtime = Depends(get_runtime),
) -> dict[str, Any]:
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
        raise HTTPException(status_code=404, detail="aprobación no encontrada") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="la aprobación expiró") from exc
    except ApprovalForbiddenError as exc:
        raise HTTPException(status_code=403, detail="solo el manager asignado puede decidir") from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {**req.as_dict(), "changed": not before}

"""Dashboard de observabilidad y verificación del audit trail."""

from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Query

from backend.observability.metrics import summarize
from backend.runtime import RuntimeDep
from backend.security.auth import AUTH_RESPONSES, AdminRole, AgentRole

router = APIRouter(prefix="/api", tags=["observabilidad"], responses=AUTH_RESPONSES)

MAX_HOURS = 24 * 90


@router.get("/metrics")
def metrics(
    _: AgentRole,
    rt: RuntimeDep,
    hours: Annotated[float | None, Query(gt=0, le=MAX_HOURS)] = None,
) -> dict[str, Any]:
    """Negocio/ITSM, rendimiento, costos y orquestación a partir de la telemetría."""
    since = time.time() - hours * 3600 if hours else None
    return summarize(rt.telemetry.read(since))


@router.get("/audit/verify")
def audit_verify(_: AdminRole, rt: RuntimeDep) -> dict[str, Any]:
    entries = sum(1 for _ in rt.audit.read())
    return {"valid": rt.audit.verify(), "entries": entries}

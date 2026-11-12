"""Dashboard de observabilidad y verificación del audit trail."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.observability.metrics import summarize
from backend.runtime import Runtime, get_runtime
from backend.security.auth import require_role

router = APIRouter(prefix="/api", tags=["observabilidad"])


@router.get("/metrics")
def metrics(
    hours: float | None = Query(default=None, gt=0, le=24 * 90),
    _: str = Depends(require_role("agent")),
    rt: Runtime = Depends(get_runtime),
) -> dict[str, Any]:
    """Negocio/ITSM, rendimiento, costos y orquestación a partir de la telemetría."""
    since = time.time() - hours * 3600 if hours else None
    return summarize(rt.telemetry.read(since))


@router.get("/audit/verify")
def audit_verify(
    _: str = Depends(require_role("admin")), rt: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    entries = sum(1 for _ in rt.audit.read())
    return {"valid": rt.audit.verify(), "entries": entries}

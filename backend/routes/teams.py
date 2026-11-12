"""Endpoint del Bot Framework para el bot de aprobaciones de Teams."""

from __future__ import annotations

import logging
from typing import Any

from botbuilder.schema import Activity
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.runtime import RuntimeDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["teams"])

MESSAGES_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "El token del Bot Framework no es válido"},
    415: {"description": "El cuerpo no es JSON"},
    503: {"description": "TEAMS_BOT_APP_ID sin configurar en producción"},
}


@router.post("/api/messages", responses=MESSAGES_RESPONSES)
async def messages(request: Request, rt: RuntimeDep) -> Response:
    """Recibe actividades de Teams. El adaptador valida el JWT de Microsoft si hay TEAMS_BOT_APP_ID."""
    if rt.settings.is_production and not rt.settings.teams_bot_app_id:
        raise HTTPException(status_code=503, detail="TEAMS_BOT_APP_ID no configurado")
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(status_code=415, detail="se esperaba application/json")
    activity = Activity().deserialize(await request.json())
    auth_header = request.headers.get("Authorization", "")
    try:
        response = await rt.adapter.process_activity(activity, auth_header, rt.bot.on_turn)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="token del Bot Framework no válido") from exc
    if response is not None:
        return JSONResponse(response.body, status_code=response.status)
    return Response(status_code=201)

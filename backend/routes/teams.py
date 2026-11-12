"""Endpoint del Bot Framework para el bot de aprobaciones de Teams."""

from __future__ import annotations

import logging

from botbuilder.schema import Activity
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.runtime import Runtime, get_runtime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["teams"])


@router.post("/api/messages")
async def messages(request: Request, rt: Runtime = Depends(get_runtime)) -> Response:
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

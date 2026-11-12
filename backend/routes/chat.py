"""Endpoints de chat y conversaciones del sistema multiagente."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.models import AgentResult, Conversation
from backend.runtime import Runtime, get_runtime
from backend.security.auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

MAX_MESSAGE = 4000


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=MAX_MESSAGE)
    conversation_id: str | None = None


class EscalateRequest(BaseModel):
    conversation_id: str
    reason: str | None = Field(default=None, max_length=500)


def _summary(conv: Conversation) -> dict[str, Any]:
    return {
        "id": conv.id,
        "ticket_id": conv.ticket_id,
        "category": conv.category,
        "priority": conv.priority,
        "requires_approval": conv.requires_approval,
        "approval_id": conv.approval_id,
        "approved": conv.approved,
        "escalated": conv.escalated,
        "escalation_level": conv.escalation_level,
        "article_id": conv.article_id,
    }


def _approval(rt: Runtime, conv: Conversation) -> dict[str, Any] | None:
    if not conv.approval_id:
        return None
    try:
        return rt.approvals.get(conv.approval_id).as_dict()
    except KeyError:
        return None


def _ticket(rt: Runtime, conv: Conversation) -> dict[str, Any] | None:
    if not conv.ticket_id:
        return None
    try:
        incident = rt.provider.get_incident(conv.ticket_id)
    except Exception as exc:
        logger.info("No se pudo consultar el ticket %s: %s", conv.ticket_id, exc)
        return {"id": conv.ticket_id, "status": None}
    return {
        "id": incident.id,
        "number": incident.number,
        "status": incident.status.value,
        "title": incident.title,
    }


def _validate(req: ChatRequest) -> str:
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message vacío")
    return text


@router.post("/chat")
def chat(
    req: ChatRequest,
    role: str = Depends(require_role("user")),
    rt: Runtime = Depends(get_runtime),
) -> dict[str, Any]:
    text = _validate(req)
    started = time.time()
    orch = rt.orchestrator()
    conv = orch.new_conversation(text)
    rt.conversations[conv.id] = conv
    results = list(orch.run(conv))
    rt.record_chat(conv, results, orch, started, actor=role)
    return {
        "conversation_id": conv.id,
        **{k: v for k, v in _summary(conv).items() if k != "id"},
        "agents": [r.as_dict() for r in results],
        "approval": _approval(rt, conv),
        "reply": conv.messages[-1]["content"],
    }


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest,
    role: str = Depends(require_role("user")),
    rt: Runtime = Depends(get_runtime),
) -> StreamingResponse:
    """SSE: un evento por agente en cuanto termina, y uno final con el resumen."""
    text = _validate(req)
    started = time.time()
    orch = rt.orchestrator()
    conv = orch.new_conversation(text)
    rt.conversations[conv.id] = conv

    def gen() -> Iterator[str]:
        results: list[AgentResult] = []
        yield f"event: start\ndata: {json.dumps({'conversation_id': conv.id})}\n\n"
        for r in orch.run(conv):
            results.append(r)
            yield f"event: agent\ndata: {json.dumps(r.as_dict(), ensure_ascii=False)}\n\n"
        rt.record_chat(conv, results, orch, started, actor=role)
        final = {
            "done": True,
            "conversation_id": conv.id,
            **{k: v for k, v in _summary(conv).items() if k != "id"},
            "approval": _approval(rt, conv),
            "reply": conv.messages[-1]["content"],
        }
        yield f"event: done\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations(
    _: str = Depends(require_role("user")), rt: Runtime = Depends(get_runtime)
) -> list[dict[str, Any]]:
    return [_summary(c) for c in rt.conversations.values()]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, _: str = Depends(require_role("user")), rt: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    conv = rt.conversations.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversación no encontrada")
    return {
        **_summary(conv),
        "messages": conv.messages,
        "approval": _approval(rt, conv),
        "ticket": _ticket(rt, conv),
    }


@router.post("/escalate")
def escalate(
    req: EscalateRequest, role: str = Depends(require_role("agent")), rt: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    conv = rt.conversations.get(req.conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversación no encontrada")
    level = max(conv.escalation_level or 1, 1) + 1 if conv.escalated else 2
    level = min(level, 3)
    conv.escalated, conv.escalation_level = True, level
    conv.messages.append({"role": "assistant", "content": f"Solicitud escalada a Nivel {level}."})
    if conv.ticket_id:
        try:
            rt.provider.add_comment(
                conv.ticket_id, f"Escalado manualmente a Nivel {level}. {req.reason or ''}".strip()
            )
        except Exception as exc:
            logger.warning("No se pudo comentar la escalación: %s", exc)
    rt.audit.record("conversation.escalated", role, {"conversation_id": conv.id, "level": level})
    rt.telemetry.emit("manual_escalation", conversation_id=conv.id, level=level)
    return {"conversation_id": conv.id, "escalated": True, "escalation_level": level}

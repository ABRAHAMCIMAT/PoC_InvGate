"""Endpoints de chat y conversaciones del sistema multiagente."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agents.models import AgentRole, Conversation
from backend.agents.orchestrator import MultiAgentOrchestrator
from backend.llmops.llm import get_llm
from backend.ticketing.factory import get_provider

router = APIRouter(prefix="/api", tags=["chat"])

_conversations: dict[str, Conversation] = {}


def _orchestrator() -> MultiAgentOrchestrator:
    return MultiAgentOrchestrator(get_llm(), get_provider())


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class EscalateRequest(BaseModel):
    conversation_id: str


@router.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message vacío")
    orch = _orchestrator()
    conv, results = orch.handle(req.message)
    _conversations[conv.id] = conv
    return {
        "conversation_id": conv.id,
        "ticket_id": conv.ticket_id,
        "category": conv.category,
        "priority": conv.priority,
        "requires_approval": conv.requires_approval,
        "escalated": conv.escalated,
        "agents": [
            {"role": r.role.value, "output": r.output, "status": r.status} for r in results
        ],
        "reply": conv.messages[-1]["content"],
    }


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message vacío")
    orch = _orchestrator()
    conv, results = orch.handle(req.message)
    _conversations[conv.id] = conv

    def gen() -> Any:
        for r in results:
            yield f"data: {json.dumps({'role': r.role.value, 'output': r.output, 'status': r.status})}\n\n"
        yield f"data: {json.dumps({'done': True, 'conversation_id': conv.id, 'ticket_id': conv.ticket_id})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/conversations")
def list_conversations() -> list[dict[str, Any]]:
    return [
        {
            "id": c.id,
            "ticket_id": c.ticket_id,
            "category": c.category,
            "priority": c.priority,
            "requires_approval": c.requires_approval,
            "approved": c.approved,
            "escalated": c.escalated,
        }
        for c in _conversations.values()
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    conv = _conversations.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversación no encontrada")
    return {
        "id": conv.id,
        "messages": conv.messages,
        "ticket_id": conv.ticket_id,
        "category": conv.category,
        "priority": conv.priority,
        "requires_approval": conv.requires_approval,
        "approved": conv.approved,
        "escalated": conv.escalated,
    }


@router.post("/escalate")
def escalate(req: EscalateRequest) -> dict[str, Any]:
    conv = _conversations.get(req.conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversación no encontrada")
    conv.escalated = True
    conv.messages.append(
        {"role": "assistant", "content": "Solicitud escalada a Nivel 2."}
    )
    return {"conversation_id": conv.id, "escalated": True}

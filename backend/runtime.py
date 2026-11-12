"""Dependencias compartidas de la aplicación (proveedor, aprobaciones, Teams, observabilidad).

Se crean una vez por proceso para que el chat, las aprobaciones y el bot de Teams vean los
mismos tickets. `reset_runtime()` las descarta (pruebas o cambio de configuración).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from fastapi import Depends

from backend.agents.knowledge import KnowledgeBase
from backend.agents.models import AgentResult, Conversation
from backend.agents.orchestrator import MultiAgentOrchestrator
from backend.approvals.service import ApprovalRequest, ApprovalService
from backend.config import Settings, get_settings
from backend.llmops.llm import LLM, get_llm
from backend.observability.langfuse import LangfuseExporter
from backend.observability.telemetry import Telemetry
from backend.security.audit import AuditLog
from backend.security.ratelimit import SlidingWindowLimiter
from backend.teams.bot import ApprovalBot
from backend.teams.notifier import Notifier, NullNotifier, TeamsBotNotifier, WebhookNotifier
from backend.teams.references import ReferenceStore
from backend.ticketing.base import TicketingProvider
from backend.ticketing.factory import get_provider

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    settings: Settings
    provider: TicketingProvider
    approvals: ApprovalService
    telemetry: Telemetry
    audit: AuditLog
    kb: KnowledgeBase
    references: ReferenceStore
    adapter: BotFrameworkAdapter
    bot: ApprovalBot
    notifier: Notifier
    langfuse: LangfuseExporter | None
    limiter: SlidingWindowLimiter | None
    conversations: dict[str, Conversation] = field(default_factory=dict)

    def llm(self) -> LLM:
        s = self.settings
        return get_llm(s.llm_provider, s.llm_base_url, s.llm_model, s.llm_api_key, s.llm_timeout)

    def orchestrator(self) -> MultiAgentOrchestrator:
        return MultiAgentOrchestrator(self.llm(), self.provider, self.approvals, self.kb)

    # ------------------------------------------------------------ Registro
    def record_chat(
        self,
        conv: Conversation,
        results: list[AgentResult],
        orch: MultiAgentOrchestrator,
        started: float,
        actor: str,
    ) -> None:
        """Telemetría por agente y por conversación, auditoría y traza opcional en Langfuse."""
        end = time.time()
        latency_ms = (end - started) * 1000
        prompt = sum(int(r.meta.get("prompt_tokens", 0)) for r in results)
        completion = sum(int(r.meta.get("completion_tokens", 0)) for r in results)
        cost = round((prompt + completion) / 1000 * self.settings.llm_cost_per_1k_tokens, 6)
        model = next((r.meta["model"] for r in results if r.meta.get("model")), orch.llm.model)
        degraded = any(r.meta.get("degraded") for r in results)
        for r in results:
            self.telemetry.emit(
                "agent_step",
                conversation_id=conv.id,
                agent=r.role.value,
                status=r.status,
                latency_ms=round(r.latency_ms, 2),
                model=r.meta.get("model"),
                prompt_tokens=r.meta.get("prompt_tokens", 0),
                completion_tokens=r.meta.get("completion_tokens", 0),
            )
        self.telemetry.emit(
            "chat_completed",
            conversation_id=conv.id,
            ticket_id=conv.ticket_id,
            category=conv.category,
            priority=conv.priority,
            requires_approval=conv.requires_approval,
            approval_id=conv.approval_id,
            escalated=conv.escalated,
            escalation_level=conv.escalation_level,
            article_id=conv.article_id,
            latency_ms=round(latency_ms, 2),
            llm_provider=orch.llm.name,
            llm_model=model,
            llm_calls=orch.llm_calls,
            llm_degraded=degraded,
            prompt_tokens=prompt,
            completion_tokens=completion,
            cost_usd=cost,
            statuses=[r.status for r in results],
        )
        self.audit.record(
            "chat.completed",
            actor,
            {"conversation_id": conv.id, "ticket_id": conv.ticket_id, "approval_id": conv.approval_id},
        )
        if self.langfuse is not None:
            t = started
            steps: list[dict[str, Any]] = []
            for r in results:
                steps.append(
                    {
                        "agent": r.role.value,
                        "status": r.status,
                        "start": t,
                        "end": t + r.latency_ms / 1000,
                        "output": r.output,
                        "model": r.meta.get("model"),
                        "prompt_tokens": r.meta.get("prompt_tokens", 0),
                        "completion_tokens": r.meta.get("completion_tokens", 0),
                    }
                )
                t += r.latency_ms / 1000
            self.langfuse.export(
                {
                    "id": conv.id,
                    "name": "chat",
                    "start": started,
                    "input": conv.messages[0]["content"],
                    "output": conv.messages[-1]["content"],
                    "metadata": {
                        "ticket_id": conv.ticket_id,
                        "category": conv.category,
                        "priority": conv.priority,
                    },
                },
                steps,
            )

    def on_approval(self, event: str, req: ApprovalRequest) -> None:
        if event == "requested":
            sent = self.notifier.notify(req)
            self.telemetry.emit(
                "approval_requested", approval_id=req.id, ticket_id=req.incident_id, notified=sent
            )
            self.audit.record(
                "approval.requested", "valkiria", {"approval_id": req.id, "ticket_id": req.incident_id}
            )
        elif event == "decided":
            wait = (req.decided_at or time.time()) - req.created_at
            self.telemetry.emit(
                "approval_decided",
                approval_id=req.id,
                ticket_id=req.incident_id,
                decision=req.status,
                wait_seconds=round(wait, 1),
            )
            self.audit.record(
                "approval.decided",
                req.decided_by or "desconocido",
                {"approval_id": req.id, "decision": req.status, "note": req.note},
            )
            for conv in self.conversations.values():
                if conv.approval_id == req.id:
                    conv.approved = req.status == "approved"


def _notifier(settings: Settings, adapter: BotFrameworkAdapter, refs: ReferenceStore) -> Notifier:
    channel = settings.notify_channel.lower()
    if channel == "teams" and settings.teams_bot_app_id:
        return TeamsBotNotifier(adapter, settings.teams_bot_app_id, refs)
    if channel == "webhook" and settings.teams_workflow_url:
        return WebhookNotifier(settings.teams_workflow_url, settings.public_base_url)
    if channel in {"teams", "webhook"}:
        logger.info("NOTIFY_CHANNEL=%s sin credenciales; las aprobaciones solo se registran", channel)
    return NullNotifier()


def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or get_settings()
    data = settings.data_dir
    provider = get_provider(settings)
    approvals = ApprovalService(
        provider,
        ttl_hours=settings.approval_ttl_hours,
        manager_name=settings.poc_manager_name,
        manager_email=settings.poc_manager_email,
        manager_invgate_id=settings.poc_manager_invgate_id,
        store_path=os.path.join(data, "approvals.json") if settings.ticketing_provider != "demo" else None,
    )
    refs = ReferenceStore(os.path.join(data, "teams_references.json"))
    adapter = BotFrameworkAdapter(
        BotFrameworkAdapterSettings(
            settings.teams_bot_app_id,
            settings.teams_bot_app_password,
            channel_auth_tenant=settings.teams_tenant_id or None,
        )
    )
    langfuse = None
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        langfuse = LangfuseExporter(
            settings.langfuse_host,
            settings.langfuse_public_key,
            settings.langfuse_secret_key,
            include_content=settings.log_user_content,
        )
    limiter = (
        SlidingWindowLimiter(settings.rate_limit_max, settings.rate_limit_window)
        if settings.rate_limit_enabled and settings.rate_limit_max > 0
        else None
    )
    runtime = Runtime(
        settings=settings,
        provider=provider,
        approvals=approvals,
        telemetry=Telemetry(os.path.join(data, "telemetry.jsonl")),
        audit=AuditLog(os.path.join(data, "audit.jsonl")),
        kb=KnowledgeBase.load(),
        references=refs,
        adapter=adapter,
        bot=ApprovalBot(approvals, refs),
        notifier=_notifier(settings, adapter, refs),
        langfuse=langfuse,
        limiter=limiter,
    )
    approvals.subscribe(runtime.on_approval)
    return runtime


@lru_cache
def get_runtime() -> Runtime:
    return build_runtime()


def reset_runtime() -> None:
    get_runtime.cache_clear()


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]

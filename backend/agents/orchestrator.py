"""Orquestador multiagente (Coordinador)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from backend.agents.diagnosis import diagnose
from backend.agents.knowledge import KnowledgeBase
from backend.agents.models import AgentResult, AgentRole, AgentStatus, Conversation
from backend.invgate.models import Incident, IncidentType
from backend.llmops.llm import LLM
from backend.ticketing.base import TicketingProvider

if TYPE_CHECKING:
    from backend.approvals.service import ApprovalService

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = (
    "Eres el agente clasificador de una mesa de ayuda. Responde SOLO con una línea con el formato "
    "categoria=<acceso|software|hardware|infraestructura|general>;"
    "prioridad=<baja|media|alta|critica>;requiere_aprobacion=<si|no>. "
    "Requiere aprobación cualquier instalación de software, licencia o permiso elevado."
)
CATEGORIES = {"acceso", "software", "hardware", "infraestructura", "general"}
PRIORITIES = {"baja", "media", "alta", "critica"}
# Política: además de lo que diga el clasificador, estas categorías siempre se aprueban.
APPROVAL_CATEGORIES = {"software"}
ESCALATION_LEVEL = {"critica": 3, "alta": 2}

OK, WARNING, ERROR = AgentStatus.OK.value, AgentStatus.WARNING.value, AgentStatus.ERROR.value


class MultiAgentOrchestrator:
    """Coordina los 8 agentes para resolver una solicitud.

    `run()` produce los resultados a medida que cada agente termina, para el streaming SSE.
    """

    def __init__(
        self,
        llm: LLM,
        provider: TicketingProvider,
        approvals: ApprovalService | None = None,
        kb: KnowledgeBase | None = None,
    ) -> None:
        self.llm = llm
        self.provider = provider
        self.approvals = approvals
        self.kb = kb or KnowledgeBase.load()
        self.llm_calls = 0

    # ----------------------------------------------------------------- API
    def new_conversation(self, text: str) -> Conversation:
        conv = Conversation(id=uuid.uuid4().hex[:12], created_at=time.time())
        conv.messages.append({"role": "user", "content": text})
        return conv

    def handle(self, text: str) -> tuple[Conversation, list[AgentResult]]:
        conv = self.new_conversation(text)
        return conv, list(self.run(conv))

    def run(self, conv: Conversation) -> Iterator[AgentResult]:
        text = conv.messages[0]["content"]
        state: dict[str, object] = {}
        steps: list[tuple[AgentRole, Callable[[Conversation, str, dict[str, object]], AgentResult]]] = [
            (AgentRole.COORDINATOR, self._coordinator),
            (AgentRole.CLASSIFIER, self._classifier),
            (AgentRole.DIAGNOSIS, self._diagnosis),
            (AgentRole.POLICIES, self._policies),
            (AgentRole.EXECUTION, self._execution),
            (AgentRole.KNOWLEDGE, self._knowledge),
            (AgentRole.FOLLOW_UP, self._follow_up),
            (AgentRole.ESCALATION, self._escalation),
        ]
        for role, step in steps:
            start = time.perf_counter()
            try:
                result = step(conv, text, state)
            except Exception as exc:  # un agente que falla no tumba la conversación
                logger.exception("Agente %s falló", role.value)
                result = AgentResult(role, f"error inesperado: {type(exc).__name__}", ERROR)
            result.latency_ms = (time.perf_counter() - start) * 1000
            yield result
        conv.messages.append({"role": "assistant", "content": self._reply(conv, state)})

    # -------------------------------------------------------------- Agentes
    def _coordinator(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        return AgentResult(AgentRole.COORDINATOR, "solicitud recibida; orquestando 7 agentes")

    def _classifier(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        raw = self.llm.complete(CLASSIFY_PROMPT, text)
        self.llm_calls += 1
        usage = self.llm.last_usage
        parsed = self._parse(raw)
        issues: list[str] = []
        category = parsed.get("categoria", "")
        priority = parsed.get("prioridad", "").replace("í", "i")
        if category not in CATEGORIES:
            issues.append("categoría no reconocida")
            category = "general"
        if priority not in PRIORITIES:
            issues.append("prioridad no reconocida")
            priority = "media"
        conv.category, conv.priority = category, priority
        conv.requires_approval = parsed.get("requiere_aprobacion", "no") in {"si", "sí", "yes", "true"}
        if self.llm.degraded:
            issues.append("LLM no disponible, se usó el clasificador de respaldo")
        meta = {
            "model": self.llm.model,
            "provider": self.llm.name,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "degraded": self.llm.degraded,
        }
        output = f"categoría={category}, prioridad={priority}, aprobación={'sí' if conv.requires_approval else 'no'}"
        if issues:
            return AgentResult(AgentRole.CLASSIFIER, f"{output} ({'; '.join(issues)})", WARNING, meta=meta)
        return AgentResult(AgentRole.CLASSIFIER, output, meta=meta)

    def _diagnosis(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        uses_llm = self.llm.name != "mock"
        result = diagnose(text, conv.category, self.llm if uses_llm else None)
        meta: dict[str, object] = {}
        if uses_llm:
            self.llm_calls += 1
            meta = {
                "model": self.llm.model,
                "prompt_tokens": self.llm.last_usage.prompt_tokens,
                "completion_tokens": self.llm.last_usage.completion_tokens,
            }
        state["diagnosis"] = result.cause
        return AgentResult(AgentRole.DIAGNOSIS, result.cause, OK if result.confident else WARNING, meta=meta)

    def _policies(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        if conv.category in APPROVAL_CATEGORIES and not conv.requires_approval:
            conv.requires_approval = True
            return AgentResult(AgentRole.POLICIES, f"la política exige aprobación para «{conv.category}»")
        if conv.requires_approval:
            return AgentResult(AgentRole.POLICIES, "requiere aprobación del manager")
        return AgentResult(AgentRole.POLICIES, "no requiere aprobación")

    def _execution(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        incident_type = IncidentType.REQUEST if conv.category == "software" else IncidentType.INCIDENT
        description = text
        if state.get("diagnosis"):
            description += f"\n\nDiagnóstico preliminar: {state['diagnosis']}"
        try:
            incident = self.provider.create_incident(
                Incident(
                    title=text[:80],
                    description=description,
                    category=conv.category,
                    priority=conv.priority,
                    type=incident_type,
                )
            )
        except Exception as exc:
            logger.warning("No se pudo crear el ticket: %s", exc)
            state["execution_failed"] = True
            return AgentResult(
                AgentRole.EXECUTION, f"no se pudo crear el ticket ({type(exc).__name__})", ERROR
            )
        conv.ticket_id = incident.id
        state["incident"] = incident
        if not conv.requires_approval:
            return AgentResult(AgentRole.EXECUTION, f"ticket {incident.id} creado")
        if self.approvals is None:
            return AgentResult(
                AgentRole.EXECUTION, f"ticket {incident.id} creado; no hay servicio de aprobaciones", WARNING
            )
        try:
            req = self.approvals.request_approval(incident, reason=text[:200])
        except Exception as exc:
            logger.warning("No se pudo solicitar la aprobación: %s", exc)
            return AgentResult(
                AgentRole.EXECUTION,
                f"ticket {incident.id} creado, pero falló la solicitud de aprobación ({type(exc).__name__})",
                ERROR,
            )
        conv.approval_id = req.id
        who = req.manager_name or req.manager_email or "el manager"
        return AgentResult(
            AgentRole.EXECUTION,
            f"ticket {incident.id} creado; aprobación {req.id} enviada a {who}",
            WARNING,
            meta={"approval_id": req.id},
        )

    def _knowledge(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        article = self.kb.search(text, conv.category)
        if article is None:
            return AgentResult(
                AgentRole.KNOWLEDGE, "no hay artículo aplicable en la base de conocimiento", WARNING
            )
        conv.article_id = article.id
        state["article"] = article
        if conv.ticket_id:
            try:
                self.provider.add_comment(
                    conv.ticket_id, f"Artículo sugerido {article.id}: {article.title}. {article.summary}"
                )
            except Exception as exc:
                logger.warning("No se pudo comentar el artículo en el ticket: %s", exc)
        return AgentResult(AgentRole.KNOWLEDGE, f"artículo sugerido: {article.id} · {article.title}")

    def _follow_up(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        if not conv.ticket_id:
            return AgentResult(AgentRole.FOLLOW_UP, "sin ticket que seguir", ERROR)
        if conv.approval_id:
            return AgentResult(AgentRole.FOLLOW_UP, "en espera de la decisión del manager", WARNING)
        return AgentResult(AgentRole.FOLLOW_UP, f"seguimiento programado para {conv.ticket_id}")

    def _escalation(self, conv: Conversation, text: str, state: dict[str, object]) -> AgentResult:
        level = ESCALATION_LEVEL.get(conv.priority or "")
        reason = f"prioridad {conv.priority}"
        if state.get("execution_failed"):
            level, reason = max(level or 0, 2), "no se pudo crear el ticket"
        if not level:
            return AgentResult(AgentRole.ESCALATION, "sin escalación")
        conv.escalated, conv.escalation_level = True, level
        if conv.ticket_id:
            try:
                self.provider.add_comment(
                    conv.ticket_id, f"Escalado automáticamente a Nivel {level} ({reason})."
                )
            except Exception as exc:
                logger.warning("No se pudo registrar la escalación en el ticket: %s", exc)
        return AgentResult(AgentRole.ESCALATION, f"escalado a Nivel {level} ({reason})", WARNING)

    # ------------------------------------------------------------ Utilidades
    @staticmethod
    def _parse(raw: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for part in raw.replace("\n", ";").split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                result[key.strip().lower()] = value.strip().strip(".").lower()
        return result

    @staticmethod
    def _reply(conv: Conversation, state: dict[str, object]) -> str:
        if not conv.ticket_id:
            return "No pude registrar tu ticket. Tu solicitud se escaló a un agente humano."
        parts = [f"Ticket {conv.ticket_id} creado."]
        if conv.approval_id:
            parts.append(
                "Está esperando la aprobación de tu manager; aquí verás su decisión y sus observaciones."
            )
        if conv.escalated:
            parts.append(f"Se escaló a Nivel {conv.escalation_level}.")
        article = state.get("article")
        if article is not None:
            parts.append(f"Mientras tanto: {getattr(article, 'summary', '')}")
        if not conv.approval_id and not conv.escalated:
            parts.append("Le daremos seguimiento.")
        return " ".join(parts)

"""Orquestador multiagente (Coordinador)."""

from __future__ import annotations

import uuid

from backend.agents.models import AgentResult, AgentRole, Conversation
from backend.invgate.models import Incident
from backend.llmops.llm import LLM
from backend.ticketing.base import TicketingProvider


class MultiAgentOrchestrator:
    """Coordina los 8 agentes para resolver una solicitud."""

    def __init__(self, llm: LLM, provider: TicketingProvider) -> None:
        self.llm = llm
        self.provider = provider

    def _classify(self, text: str) -> dict[str, str]:
        raw = self.llm.complete("Clasifica la solicitud.", text)
        result: dict[str, str] = {}
        for part in raw.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    def handle(self, text: str) -> tuple[Conversation, list[AgentResult]]:
        conv = Conversation(id=uuid.uuid4().hex[:12])
        conv.messages.append({"role": "user", "content": text})
        results: list[AgentResult] = []

        # Clasificador
        classification = self._classify(text)
        conv.category = classification.get("categoria")
        conv.priority = classification.get("prioridad")
        conv.requires_approval = classification.get("requiere_aprobacion") == "si"
        results.append(
            AgentResult(
                AgentRole.CLASSIFIER,
                f"categoría={conv.category}, prioridad={conv.priority}, aprobación={conv.requires_approval}",
            )
        )

        # Diagnóstico
        results.append(AgentResult(AgentRole.DIAGNOSIS, "causa raíz estimada por heurística"))

        # Políticas
        if conv.requires_approval:
            results.append(AgentResult(AgentRole.POLICIES, "requiere aprobación del manager"))
        else:
            results.append(AgentResult(AgentRole.POLICIES, "no requiere aprobación"))

        # Ejecución: crea el ticket
        incident = self.provider.create_incident(
            Incident(title=text[:80], description=text, category=conv.category, priority=conv.priority)
        )
        conv.ticket_id = incident.id
        results.append(AgentResult(AgentRole.EXECUTION, f"ticket {incident.id} creado"))

        # Conocimiento
        results.append(AgentResult(AgentRole.KNOWLEDGE, "artículo sugerido: KB-001"))

        # Seguimiento y escalación
        results.append(AgentResult(AgentRole.FOLLOW_UP, "seguimiento programado"))
        if conv.priority == "alta":
            conv.escalated = True
            results.append(AgentResult(AgentRole.ESCALATION, "escalado a Nivel 2"))
        else:
            results.append(AgentResult(AgentRole.ESCALATION, "sin escalación"))

        conv.messages.append(
            {"role": "assistant", "content": f"Ticket {conv.ticket_id} creado y en seguimiento."}
        )
        return conv, results

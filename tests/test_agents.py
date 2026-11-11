"""Pruebas del orquestador multiagente con LLM mock."""

from __future__ import annotations

from backend.agents.models import AgentRole
from backend.agents.orchestrator import MultiAgentOrchestrator
from backend.llmops.llm import MockLLM
from backend.ticketing.demo import DemoProvider


def test_handle_creates_ticket() -> None:
    provider = DemoProvider()
    orch = MultiAgentOrchestrator(MockLLM(), provider)
    conv, results = orch.handle("No enciende mi laptop")
    assert conv.ticket_id is not None
    assert conv.category == "hardware"
    assert conv.priority == "alta"
    assert conv.escalated is True
    roles = [r.role for r in results]
    assert AgentRole.CLASSIFIER in roles
    assert AgentRole.EXECUTION in roles
    assert AgentRole.ESCALATION in roles


def test_handle_requires_approval() -> None:
    provider = DemoProvider()
    orch = MultiAgentOrchestrator(MockLLM(), provider)
    conv, results = orch.handle("Necesito instalar una aplicación")
    assert conv.requires_approval is True
    assert conv.approved is None
    assert any(r.role == AgentRole.POLICIES for r in results)


def test_handle_general_no_escalation() -> None:
    provider = DemoProvider()
    orch = MultiAgentOrchestrator(MockLLM(), provider)
    conv, _ = orch.handle("Tengo una duda general")
    assert conv.escalated is False

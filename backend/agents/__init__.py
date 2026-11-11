"""Agentes del sistema multiagente."""

from backend.agents.models import AgentResult, AgentRole, Conversation
from backend.agents.orchestrator import MultiAgentOrchestrator

__all__ = ["AgentResult", "AgentRole", "Conversation", "MultiAgentOrchestrator"]

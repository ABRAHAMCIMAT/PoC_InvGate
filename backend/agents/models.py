"""Agentes del sistema multiagente."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentRole(str, Enum):
    COORDINATOR = "coordinador"
    CLASSIFIER = "clasificador"
    DIAGNOSIS = "diagnostico"
    POLICIES = "politicas"
    EXECUTION = "ejecucion"
    KNOWLEDGE = "conocimiento"
    FOLLOW_UP = "seguimiento"
    ESCALATION = "escalacion"


@dataclass
class AgentResult:
    role: AgentRole
    output: str
    status: str = "ok"  # ok | warning | error


@dataclass
class Conversation:
    id: str
    messages: list[dict] = field(default_factory=list)
    ticket_id: str | None = None
    category: str | None = None
    priority: str | None = None
    requires_approval: bool = False
    approved: bool | None = None
    escalated: bool = False

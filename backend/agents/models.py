"""Agentes del sistema multiagente."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    COORDINATOR = "coordinador"
    CLASSIFIER = "clasificador"
    DIAGNOSIS = "diagnostico"
    POLICIES = "politicas"
    EXECUTION = "ejecucion"
    KNOWLEDGE = "conocimiento"
    FOLLOW_UP = "seguimiento"
    ESCALATION = "escalacion"


class AgentStatus(str, Enum):
    """Estado del semáforo: verde, amarillo o rojo."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class AgentResult:
    role: AgentRole
    output: str
    status: str = AgentStatus.OK.value
    latency_ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "output": self.output,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
        }


@dataclass
class Conversation:
    id: str
    messages: list[dict] = field(default_factory=list)
    ticket_id: str | None = None
    category: str | None = None
    priority: str | None = None
    requires_approval: bool = False
    approved: bool | None = None
    approval_id: str | None = None
    escalated: bool = False
    escalation_level: int | None = None
    article_id: str | None = None
    created_at: float = 0.0

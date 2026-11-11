"""Modelos de datos de InvGate Service Management."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class IncidentType(str, Enum):
    INCIDENT = "incident"
    REQUEST = "request"
    PROBLEM = "problem"
    CHANGE = "change"


class Incident(BaseModel):
    """Representación de un incidente/solicitud en InvGate."""

    id: str | None = None
    number: str | None = None
    title: str = Field(..., min_length=1)
    description: str = ""
    status: IncidentStatus = IncidentStatus.NEW
    type: IncidentType = IncidentType.INCIDENT
    category: str | None = None
    priority: str | None = None
    requester: str | None = None
    assignee: str | None = None
    helpdesk: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Comment(BaseModel):
    """Comentario asociado a un incidente."""

    id: str | None = None
    incident_id: str
    body: str = Field(..., min_length=1)
    author: str | None = None
    created_at: str | None = None


class CatalogItem(BaseModel):
    """Elemento de un catálogo de InvGate (prioridades, estados, categorías...)."""

    id: str | None = None
    name: str
    value: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

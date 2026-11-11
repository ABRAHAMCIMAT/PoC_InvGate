"""Proveedores de ticketing (demo, simulated, invgate)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.invgate.models import Comment, Incident


class TicketingProvider(ABC):
    """Contrato común de un proveedor de ticketing."""

    @abstractmethod
    def create_incident(self, incident: Incident) -> Incident:
        """Crea un incidente y devuelve el incidente con su id."""

    @abstractmethod
    def get_incident(self, incident_id: str) -> Incident:
        """Consulta un incidente por id."""

    @abstractmethod
    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        """Actualiza un incidente."""

    @abstractmethod
    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        """Añade un comentario a un incidente."""

    @abstractmethod
    def list_incidents(self, limit: int = 50) -> list[Incident]:
        """Lista incidentes."""

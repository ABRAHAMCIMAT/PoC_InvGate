"""Proveedores de ticketing (demo, simulated, invgate)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.invgate.models import Comment, Incident, IncidentStatus


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

    def list_comments(self, incident_id: str) -> list[Comment]:
        """Lista los comentarios de un incidente (vacío si el proveedor no los guarda)."""
        return []

    # Aprobaciones -----------------------------------------------------------
    # Implementación simulada: deja constancia en el ticket con estado y comentario.
    # El proveedor InvGate la sustituye por las aprobaciones nativas.
    def request_approval(self, incident_id: str, approver: str, description: str) -> str | None:
        """Abre una aprobación sobre el incidente. Devuelve el id externo si existe."""
        current = self.get_incident(incident_id)
        self.update_incident(incident_id, current.model_copy(update={"status": IncidentStatus.WAITING}))
        self.add_comment(incident_id, f"Aprobación solicitada a {approver}: {description}", author="valkiria")
        return None

    def resolve_approval(
        self,
        incident_id: str,
        approval_ref: str | None,
        approved: bool,
        voter: str,
        note: str | None = None,
    ) -> None:
        """Registra la decisión del aprobador en el incidente."""
        status = IncidentStatus.IN_PROGRESS if approved else IncidentStatus.CANCELLED
        current = self.get_incident(incident_id)
        self.update_incident(incident_id, current.model_copy(update={"status": status}))
        label = "aprobada" if approved else "rechazada"
        body = f"Aprobación {label} por {voter}."
        if note:
            body += f" Observaciones: {note}"
        self.add_comment(incident_id, body, author=voter)

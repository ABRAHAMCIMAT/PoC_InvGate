"""Fábrica de proveedores de ticketing según configuración."""

from __future__ import annotations

from backend.config import Settings
from backend.invgate.client import InvGateClient
from backend.ticketing.base import TicketingProvider
from backend.ticketing.demo import DemoProvider
from backend.ticketing.invgate import InvGateProvider
from backend.ticketing.simulated import SimulatedProvider


def get_provider(settings: Settings | None = None) -> TicketingProvider:
    """Devuelve el proveedor configurado por `TICKETING_PROVIDER`."""
    from backend.config import get_settings

    settings = settings or get_settings()
    provider = settings.ticketing_provider
    if provider == "invgate":
        if not settings.invgate_base_url or not settings.invgate_api_token:
            raise ValueError(
                "TICKETING_PROVIDER=invgate requiere INVGATE_BASE_URL e INVGATE_API_TOKEN"
            )
        client = InvGateClient(
            base_url=settings.invgate_base_url,
            api_token=settings.invgate_api_token,
            username=settings.invgate_username,
        )
        return InvGateProvider(client)
    if provider == "simulated":
        return SimulatedProvider()
    return DemoProvider()

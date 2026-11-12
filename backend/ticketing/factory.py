"""Fábrica de proveedores de ticketing según configuración."""

from __future__ import annotations

import json
import os
from typing import Any

from backend.config import Settings
from backend.invgate.client import InvGateClient, OAuth2ClientCredentials
from backend.ticketing.base import TicketingProvider
from backend.ticketing.demo import DemoProvider
from backend.ticketing.invgate import InvGateProvider
from backend.ticketing.simulated import SimulatedProvider


def _defaults(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("INVGATE_DEFAULTS debe ser un objeto JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("INVGATE_DEFAULTS debe ser un objeto JSON")
    return parsed


def build_invgate_client(settings: Settings) -> InvGateClient:
    """Construye el cliente InvGate con API token u OAuth 2.0 client credentials."""
    if not settings.invgate_base_url:
        raise ValueError("TICKETING_PROVIDER=invgate requiere INVGATE_BASE_URL")
    oauth = None
    if settings.invgate_client_id and settings.invgate_client_secret:
        token_url = settings.invgate_oauth_token_url or (
            f"{settings.invgate_base_url.rstrip('/')}/oauth/v2.0/access_token"
        )
        oauth = OAuth2ClientCredentials(token_url, settings.invgate_client_id, settings.invgate_client_secret)
    elif not settings.invgate_api_token:
        raise ValueError(
            "TICKETING_PROVIDER=invgate requiere INVGATE_API_TOKEN o INVGATE_CLIENT_ID + INVGATE_CLIENT_SECRET"
        )
    return InvGateClient(
        base_url=settings.invgate_base_url,
        api_token=settings.invgate_api_token,
        username=settings.invgate_username,
        api_prefix=settings.invgate_api_prefix,
        field_map=settings.invgate_field_map,
        value_map=settings.invgate_value_map,
        defaults=_defaults(settings.invgate_defaults),
        oauth=oauth,
    )


def get_provider(settings: Settings | None = None) -> TicketingProvider:
    """Devuelve el proveedor configurado por `TICKETING_PROVIDER`."""
    from backend.config import get_settings

    settings = settings or get_settings()
    provider = settings.ticketing_provider
    if provider == "invgate":
        return InvGateProvider(build_invgate_client(settings), author_id=settings.invgate_author_id)
    if provider == "simulated":
        return SimulatedProvider(os.path.join(settings.data_dir, "simulated_tickets.json"))
    return DemoProvider()

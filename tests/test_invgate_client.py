"""Pruebas del cliente HTTP de InvGate con respuestas simuladas."""

from __future__ import annotations

import httpx
import pytest

from backend.invgate.client import (
    InvGateAuthError,
    InvGateClient,
    InvGateError,
    InvGateNotFoundError,
)
from backend.invgate.models import Incident


def _client(transport: httpx.MockTransport) -> InvGateClient:
    client = InvGateClient(
        base_url="https://demo.invgate.net",
        api_token="token",
        max_retries=2,
    )
    client._client = httpx.Client(transport=transport, base_url=client.base_url)
    return client


def test_create_incident() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/incident"
        return httpx.Response(200, json={"id": "123", "title": "Hola", "status": "new"})

    client = _client(httpx.MockTransport(handler))
    incident = client.create_incident(Incident(title="Hola"))
    assert incident.id == "123"
    assert incident.title == "Hola"


def test_get_incident_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(InvGateNotFoundError):
        client.get_incident("999")


def test_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(InvGateAuthError):
        client.list_incidents()


def test_retry_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, json={})
        return httpx.Response(200, json=[{"id": "1", "title": "A"}])

    client = _client(httpx.MockTransport(handler))
    incidents = client.list_incidents()
    assert len(incidents) == 1
    assert calls["n"] == 2


def test_exhausts_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(InvGateError):
        client.list_incidents()

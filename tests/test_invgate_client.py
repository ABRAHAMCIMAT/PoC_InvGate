"""Pruebas del cliente HTTP de InvGate con respuestas simuladas."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.invgate.client import (
    InvGateAuthError,
    InvGateClient,
    InvGateError,
    InvGateNotFoundError,
)
from backend.invgate.models import Incident, IncidentStatus, IncidentType


def _client(transport: httpx.MockTransport, **kwargs) -> InvGateClient:
    client = InvGateClient(base_url="https://demo.invgate.net", api_token="token", max_retries=2, **kwargs)
    client._client = httpx.Client(transport=transport, base_url=client.base_url)
    return client


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch) -> None:
    monkeypatch.setattr("backend.invgate.client.time.sleep", lambda d: None)


def test_create_incident_maps_fields_and_defaults() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"info": "ok", "request_id": 123, "status": "OK"})

    client = _client(
        httpx.MockTransport(handler),
        defaults={"creator_id": 1, "customer_id": 2, "category_id": 9},
        value_map='{"category": {"hardware": "40"}}',
    )
    incident = client.create_incident(
        Incident(
            title="Hola", description="desc", category="hardware", priority="alta", type=IncidentType.REQUEST
        )
    )
    assert seen["path"] == "/api/v1/incident"
    body = seen["body"]
    assert body["title"] == "Hola"
    assert body["creator_id"] == 1 and body["customer_id"] == 2
    assert body["category_id"] == "40"  # el mapeo pisa el valor por defecto
    assert body["priority_id"] == "3"
    assert body["type_id"] == "2"
    assert "status_id" not in body
    assert incident.id == "123"


def test_create_without_request_id_fails() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ERROR"})))
    with pytest.raises(InvGateError):
        client.create_incident(Incident(title="x"))


def test_get_incident_parses_invgate_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/incident"
        assert request.url.params["id"] == "55"
        return httpx.Response(
            200,
            json={
                "id": 55,
                "pretty_id": "#55",
                "title": "Sin red",
                "description": "",
                "priority_id": 3,
                "type_id": 1,
                "status_id": 2,
                "category_id": 7,
                "user_id": 10,
                "last_update": "2026-11-12",
                "custom_fields": {},
            },
        )

    client = _client(httpx.MockTransport(handler), value_map='{"status": {"open": "2"}}')
    inc = client.get_incident("55")
    assert inc.id == "55"
    assert inc.number == "#55"
    assert inc.priority == "alta"
    assert inc.type == IncidentType.INCIDENT
    assert inc.status == IncidentStatus.OPEN
    assert inc.category == "7"
    assert inc.updated_at == "2026-11-12"
    assert inc.extra["user_id"] == 10


def test_get_incident_unknown_status_and_type_kept_in_extra() -> None:
    client = _client(
        httpx.MockTransport(lambda r: httpx.Response(200, json=[{"id": 1, "status_id": 99, "type_id": 6}]))
    )
    inc = client.get_incident("1")
    assert inc.status == IncidentStatus.OPEN
    assert inc.extra["status_id"] == 99
    assert inc.extra["type_id"] == 6
    assert inc.title == "Incidente 1"


def test_get_incident_empty_list_not_found() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(InvGateNotFoundError):
        client.get_incident("1")


def test_get_incident_not_found() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(404, json={"error": "not found"})))
    with pytest.raises(InvGateNotFoundError):
        client.get_incident("999")


def test_auth_error() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    with pytest.raises(InvGateAuthError):
        client.list_incidents()


def test_retry_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, json={})
        assert request.url.path == "/api/v1/incidents.last.hour"
        return httpx.Response(200, json={"data": [{"id": "1", "title": "A"}]})

    client = _client(httpx.MockTransport(handler))
    incidents = client.list_incidents()
    assert len(incidents) == 1
    assert calls["n"] == 2


def test_exhausts_retries() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(503, json={})))
    with pytest.raises(InvGateError):
        client.list_incidents()


def test_approval_endpoints() -> None:
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else dict(request.url.params)
        calls.append((request.method, request.url.path, body))
        if request.url.path.endswith("/incident.approval"):
            return httpx.Response(200, json=[{"id": 4, "status": 1}])
        return httpx.Response(200, json={"status": "OK"})

    client = _client(httpx.MockTransport(handler))
    client.request_approval("10", "3", "Instalar", "1")
    assert client.list_approvals("10", only_pending=True) == [{"id": 4, "status": 1}]
    client.accept_approval("4", "3", "ok")
    client.reject_approval("4", "3")
    assert calls[0] == (
        "POST",
        "/api/v1/incident.spontaneous_approval",
        {"request_id": "10", "approval_user_id": "3", "author_id": "1", "description": "Instalar"},
    )
    assert calls[1][1] == "/api/v1/incident.approval"
    assert calls[1][2]["only_pending"] == "true"
    assert calls[2] == (
        "PUT",
        "/api/v1/incident.approval.accept",
        {"approval_id": "4", "user_id": "3", "note": "ok"},
    )
    assert calls[3] == ("PUT", "/api/v1/incident.approval.reject", {"approval_id": "4", "user_id": "3"})


def test_items_helper_shapes() -> None:
    assert InvGateClient._items(None) == []
    assert InvGateClient._items({"requests": [{"id": 1}, 3]}) == [{"id": 1}]
    assert InvGateClient._items({"1": {"id": 1}}) == [{"id": 1}]
    assert InvGateClient._items("x") == []
    assert InvGateClient._extract_id(7) == "7"
    assert InvGateClient._extract_id({}) is None


def test_custom_api_prefix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/custom/incident"
        return httpx.Response(200, json={"id": 1, "title": "x"})

    client = _client(httpx.MockTransport(handler), api_prefix="custom/")
    assert client.get_incident("1").id == "1"

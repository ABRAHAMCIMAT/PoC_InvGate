"""Pruebas adicionales del cliente InvGate (rutas y parámetros de la API v1 documentada)."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.invgate.client import InvGateClient, InvGateError
from backend.invgate.models import Incident


def _client(transport: httpx.MockTransport, **kwargs) -> InvGateClient:
    client = InvGateClient(base_url="https://demo.invgate.net/", api_token="token", max_retries=2, **kwargs)
    client._client = httpx.Client(transport=transport, base_url=client.base_url)
    return client


def test_update_incident_sends_id_in_body() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["method"] = request.url.path, request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "OK"})

    client = _client(httpx.MockTransport(handler))
    inc = client.update_incident("1", Incident(title="Nuevo", status="open", priority="alta"))
    assert seen["path"] == "/api/v1/incident"
    assert seen["method"] == "PUT"
    assert seen["body"]["id"] == "1"
    assert seen["body"]["priority_id"] == "3"
    assert seen["body"]["status_id"] == "open"
    assert inc.id == "1"


def test_add_comment_uses_incident_comment() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "c1", "status": "OK"})

    client = _client(httpx.MockTransport(handler))
    comment = client.add_comment("1", "Hola", author="7")
    assert seen["path"] == "/api/v1/incident.comment"
    assert seen["body"] == {"request_id": "1", "comment": "Hola", "customer_visible": 1, "author_id": "7"}
    assert comment.id == "c1"
    assert comment.incident_id == "1"


def test_add_comment_internal_uses_default_author() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(httpx.MockTransport(handler), defaults={"creator_id": 5})
    client.add_comment("1", "nota", customer_visible=False)
    assert seen["body"]["author_id"] == 5
    assert seen["body"]["customer_visible"] == 0


def test_list_comments_reads_message_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/incident.comment"
        assert request.url.params["request_id"] == "1"
        return httpx.Response(
            200, json=[{"id": 9, "message": "x", "author_id": 3, "created_at": "2026-01-01"}, {"id": 10}]
        )

    client = _client(httpx.MockTransport(handler))
    comments = client.list_comments("1")
    assert len(comments) == 1
    assert comments[0].body == "x"
    assert comments[0].author == "3"


def test_list_catalog_list_and_map() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/categories"):
            return httpx.Response(200, json=[{"id": 1, "name": "Acceso", "parent_category_id": 0}, {"id": 2}])
        return httpx.Response(200, json={"1": "Low", "2": "Medium"})

    client = _client(httpx.MockTransport(handler))
    items = client.list_catalog("categories")
    assert items[0].name == "Acceso"
    assert items[0].extra == {"parent_category_id": 0}
    prios = client.list_catalog("incident.attributes.priority")
    assert [p.name for p in prios] == ["Low", "Medium"]


def test_204_returns_none() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(204)))
    assert client._request("DELETE", "/incident") is None


def test_400_raises() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(400, text="bad request")))
    with pytest.raises(InvGateError):
        client.list_incidents()


def test_http_error_retries(monkeypatch) -> None:
    monkeypatch.setattr("backend.invgate.client.time.sleep", lambda d: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(InvGateError):
        client.list_incidents()
    assert calls["n"] == 2


def test_close() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    client.close()

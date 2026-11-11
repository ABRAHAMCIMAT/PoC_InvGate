"""Pruebas adicionales del cliente InvGate."""

from __future__ import annotations

import httpx
import pytest

from backend.invgate.client import InvGateClient, InvGateError
from backend.invgate.models import Incident


def _client(transport: httpx.MockTransport) -> InvGateClient:
    client = InvGateClient(
        base_url="https://demo.invgate.net/",
        api_token="token",
        max_retries=2,
    )
    client._client = httpx.Client(transport=transport, base_url=client.base_url)
    return client


def test_update_incident() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/incident/1"
        assert request.method == "PUT"
        return httpx.Response(200, json={"id": "1", "title": "Nuevo", "status": "open"})

    client = _client(httpx.MockTransport(handler))
    inc = client.update_incident("1", Incident(title="Nuevo", status="open"))
    assert inc.id == "1"
    assert inc.status.value == "open"


def test_add_comment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/incident/1/comment"
        return httpx.Response(200, json={"id": "c1", "body": "Hola"})

    client = _client(httpx.MockTransport(handler))
    comment = client.add_comment("1", "Hola", author="ana")
    assert comment.id == "c1"
    assert comment.incident_id == "1"


def test_list_comments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "c1", "body": "x"}])

    client = _client(httpx.MockTransport(handler))
    comments = client.list_comments("1")
    assert len(comments) == 1
    assert comments[0].incident_id == "1"


def test_list_catalog() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"name": "Alta"}]})

    client = _client(httpx.MockTransport(handler))
    items = client.list_catalog("priority")
    assert items[0].name == "Alta"


def test_204_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = _client(httpx.MockTransport(handler))
    assert client._request("DELETE", "/incident/1") is None


def test_400_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(InvGateError):
        client.list_incidents()


def test_http_error_retries() -> None:
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

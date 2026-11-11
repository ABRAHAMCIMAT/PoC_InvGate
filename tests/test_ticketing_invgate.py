"""Pruebas del proveedor InvGate real."""

from __future__ import annotations

import httpx

from backend.invgate.client import InvGateClient
from backend.invgate.models import Comment, Incident
from backend.ticketing.invgate import InvGateProvider


def _provider() -> InvGateProvider:
    client = InvGateClient(base_url="https://demo.invgate.net", api_token="t", max_retries=1)
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"id": "1", "title": "x"})),
        base_url=client.base_url,
    )
    return InvGateProvider(client)


def test_provider_create() -> None:
    p = _provider()
    inc = p.create_incident(Incident(title="x"))
    assert inc.id == "1"


def test_provider_get() -> None:
    p = _provider()
    assert p.get_incident("1").id == "1"


def test_provider_update() -> None:
    p = _provider()
    assert p.update_incident("1", Incident(title="x")).id == "1"


def test_provider_add_comment() -> None:
    client = InvGateClient(base_url="https://demo.invgate.net", api_token="t", max_retries=1)
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"id": "c1", "body": "hola"})),
        base_url=client.base_url,
    )
    p = InvGateProvider(client)
    c = p.add_comment("1", "hola")
    assert isinstance(c, Comment)
    assert c.body == "hola"


def test_provider_list() -> None:
    client = InvGateClient(base_url="https://demo.invgate.net", api_token="t", max_retries=1)
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[{"id": "1", "title": "x"}])),
        base_url=client.base_url,
    )
    p = InvGateProvider(client)
    assert len(p.list_incidents()) == 1

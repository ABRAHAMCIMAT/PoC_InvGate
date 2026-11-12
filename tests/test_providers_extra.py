"""Pruebas del proveedor simulated persistente, aprobaciones nativas InvGate, OAuth2 y la fábrica."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.config import Settings
from backend.invgate.client import InvGateAuthError, InvGateClient, OAuth2ClientCredentials
from backend.invgate.models import Incident
from backend.ticketing.base import TicketingProvider
from backend.ticketing.factory import build_invgate_client, get_provider
from backend.ticketing.invgate import InvGateProvider
from backend.ticketing.simulated import SimulatedProvider


def test_simulated_persists_between_instances(tmp_path) -> None:
    path = str(tmp_path / "sim.json")
    p1 = SimulatedProvider(path)
    inc = p1.create_incident(Incident(title="Instalar"))
    p1.add_comment(inc.id, "hola")
    p1.request_approval(inc.id, "Laura", "Instalar")
    p2 = SimulatedProvider(path)
    assert p2.get_incident(inc.id).status.value == "waiting"
    assert [c.body for c in p2.list_comments(inc.id)][0] == "hola"
    nxt = p2.create_incident(Incident(title="otro"))
    assert nxt.id != inc.id
    (tmp_path / "bad.json").write_text("{")
    assert SimulatedProvider(str(tmp_path / "bad.json")).list_incidents() == []
    assert SimulatedProvider().create_incident(Incident(title="x")).id.startswith("SIM-")


def test_base_resolve_approval_rejects_with_note() -> None:
    p = SimulatedProvider()
    inc = p.create_incident(Incident(title="x"))
    p.resolve_approval(inc.id, None, False, "laura", "No hay presupuesto")
    assert p.get_incident(inc.id).status.value == "cancelled"
    assert "No hay presupuesto" in p.list_comments(inc.id)[-1].body
    assert TicketingProvider.list_comments(p, inc.id) == []


class FakeClient:
    def __init__(self, pending=None) -> None:
        self.calls: list[tuple] = []
        self.pending = pending if pending is not None else [{"id": "7"}, {"id": "12"}]

    def request_approval(self, *a):
        self.calls.append(("request", *a))

    def list_approvals(self, incident_id, only_pending=False):
        return self.pending

    def accept_approval(self, *a):
        self.calls.append(("accept", *a))

    def reject_approval(self, *a):
        self.calls.append(("reject", *a))

    def add_comment(self, *a):
        self.calls.append(("comment", *a))

    def list_comments(self, incident_id):
        return []


def test_invgate_provider_native_approvals() -> None:
    client = FakeClient()
    p = InvGateProvider(client, author_id="1")  # type: ignore[arg-type]
    assert p.request_approval("10", "3", "Instalar") == "12"
    assert client.calls[0] == ("request", "10", "3", "Instalar", "1")
    p.resolve_approval("10", "12", True, "3", "ok")
    p.resolve_approval("10", None, False, "3")
    assert client.calls[1:] == [("accept", "12", "3", "ok"), ("reject", "12", "3", None)]
    p.add_comment("10", "x", author="laura")
    p.add_comment("10", "y", author="5")
    assert client.calls[-2:] == [("comment", "10", "x", "1"), ("comment", "10", "y", "5")]
    assert p.list_comments("10") == []
    with pytest.raises(ValueError):
        p.request_approval("10", "", "x")


def test_invgate_provider_without_pending() -> None:
    p = InvGateProvider(FakeClient(pending=[]))  # type: ignore[arg-type]
    assert p.request_approval("10", "3", "x") is None
    with pytest.raises(LookupError):
        p.resolve_approval("10", None, True, "3")
    p2 = InvGateProvider(FakeClient(pending=[{"status": 1}]))  # type: ignore[arg-type]
    assert p2.request_approval("10", "3", "x") is None


def test_oauth_token_cached_and_refreshed(monkeypatch) -> None:
    tokens = iter(["t1", "t2"])
    posts = []

    def fake_post(url, data, timeout):
        posts.append((url, data["grant_type"]))
        return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})

    monkeypatch.setattr("backend.invgate.client.httpx.post", fake_post)
    oauth = OAuth2ClientCredentials("https://x/oauth/token", "id", "secret")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.headers["authorization"] == "Bearer t1" and calls["n"] == 2:
            return httpx.Response(401)
        return httpx.Response(200, json={"id": 1, "title": "x"})

    client = InvGateClient("https://x", oauth=oauth, max_retries=1)
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://x", auth=oauth)
    client.get_incident("1")
    client.get_incident("1")  # 401 -> renueva token y reintenta
    assert posts == [
        ("https://x/oauth/token", "client_credentials"),
        ("https://x/oauth/token", "client_credentials"),
    ]
    assert oauth.token() == "t2"


def test_oauth_errors(monkeypatch) -> None:
    monkeypatch.setattr("backend.invgate.client.httpx.post", lambda *a, **k: httpx.Response(400))
    with pytest.raises(InvGateAuthError):
        OAuth2ClientCredentials("u", "i", "s").token()
    monkeypatch.setattr("backend.invgate.client.httpx.post", lambda *a, **k: httpx.Response(200, json={}))
    with pytest.raises(InvGateAuthError):
        OAuth2ClientCredentials("u", "i", "s").token()


def _settings(**kw) -> Settings:
    base = Settings()
    return base.__class__(**{**base.__dict__, "ticketing_provider": "invgate", **kw})


def test_factory_oauth_and_defaults() -> None:
    client = build_invgate_client(
        _settings(
            invgate_base_url="https://acme.cloud.invgate.net",
            invgate_client_id="cid",
            invgate_client_secret="sec",
            invgate_defaults=json.dumps({"creator_id": 1}),
        )
    )
    assert isinstance(client._client.auth, OAuth2ClientCredentials)
    assert client._client.auth.token_url == "https://acme.cloud.invgate.net/oauth/v2.0/access_token"
    assert client.defaults == {"creator_id": 1}
    custom = build_invgate_client(
        _settings(
            invgate_base_url="https://a",
            invgate_client_id="c",
            invgate_client_secret="s",
            invgate_oauth_token_url="https://a/token",
        )
    )
    assert custom._client.auth.token_url == "https://a/token"


def test_factory_errors() -> None:
    with pytest.raises(ValueError):
        build_invgate_client(_settings())
    with pytest.raises(ValueError):
        build_invgate_client(_settings(invgate_base_url="https://a"))
    for bad in ("{", "[1]"):
        with pytest.raises(ValueError):
            build_invgate_client(
                _settings(invgate_base_url="https://a", invgate_api_token="t", invgate_defaults=bad)
            )
    provider = get_provider(
        _settings(invgate_base_url="https://a", invgate_api_token="t", invgate_author_id="9")
    )
    assert isinstance(provider, InvGateProvider)
    assert provider.author_id == "9"

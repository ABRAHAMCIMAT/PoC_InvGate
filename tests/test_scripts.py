"""Pruebas de los scripts de demo y de validación de InvGate."""

from __future__ import annotations

import random

import httpx

from backend.config import get_settings
from backend.runtime import get_runtime
from scripts import check_invgate, seed_demo_telemetry


def test_seed_populates_metrics(monkeypatch) -> None:
    monkeypatch.setenv("POC_MANAGER_EMAIL", "laura@x.com")
    get_settings.cache_clear()
    stats = seed_demo_telemetry.seed(30, random.Random(1))
    assert stats["conversaciones"] == 30
    from backend.observability.metrics import summarize

    m = summarize(get_runtime().telemetry.read())
    assert m["negocio"]["conversaciones"] == 30
    assert (
        m["negocio"]["aprobaciones"]["solicitadas"]
        == stats["aprobadas"] + stats["rechazadas"] + stats["pendientes"]
    )
    assert seed_demo_telemetry.main(["-n", "2", "--seed", "3"]) == 0


def test_check_invgate_without_config(capsys) -> None:
    assert check_invgate.main([]) == 2
    assert "INVGATE_BASE_URL" in capsys.readouterr().err


def test_check_invgate_against_mock(monkeypatch, capsys) -> None:
    monkeypatch.setenv("INVGATE_BASE_URL", "https://acme.invgate.net")
    monkeypatch.setenv("INVGATE_API_TOKEN", "t")
    monkeypatch.setenv("INVGATE_DEFAULTS", '{"creator_id": 1, "customer_id": 1, "category_id": 1}')
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/helpdesks"):
            return httpx.Response(500)
        if path.endswith("/incident") and request.method == "POST":
            return httpx.Response(200, json={"request_id": 77})
        if path.endswith("/incident") and request.method == "GET":
            return httpx.Response(200, json={"id": 77, "title": "x", "priority_id": 2})
        if path.endswith("/incident.comment"):
            return httpx.Response(200, json=[] if request.method == "GET" else {"id": 1})
        return httpx.Response(200, json={"1": "Low"})

    real = check_invgate.build_invgate_client

    def build(settings):
        client = real(settings)
        client.max_retries = 1
        client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url=client.base_url)
        return client

    monkeypatch.setattr(check_invgate, "build_invgate_client", build)
    monkeypatch.setattr("backend.invgate.client.time.sleep", lambda d: None)
    assert check_invgate.main(["--incident", "77", "--write"]) == 1  # helpdesks falló
    out = capsys.readouterr().out
    assert "✓ POST /incident" in out
    assert "request_id=77" in out
    assert "✕ GET /helpdesks" in out

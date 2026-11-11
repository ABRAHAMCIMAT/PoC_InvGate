"""Pruebas del backoff exponencial del cliente InvGate."""

from __future__ import annotations

import httpx
import pytest

from backend.invgate.client import InvGateClient, InvGateError


def test_backoff_delays_between_retries(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("backend.invgate.client.time.sleep", lambda d: sleeps.append(d))
    monkeypatch.setattr("backend.invgate.client.secrets.randbelow", lambda n: 0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = InvGateClient(base_url="https://demo.invgate.net", api_token="t", max_retries=3)
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url=client.base_url)
    with pytest.raises(InvGateError):
        client.list_incidents()
    assert sleeps == [0.5, 1.0, 2.0]

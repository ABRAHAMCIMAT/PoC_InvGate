"""Pruebas del healthcheck."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.server import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

"""Pruebas de RBAC aplicado a los endpoints de chat."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.server import app


def _client(api_keys: str) -> TestClient:
    settings = Settings(api_keys=api_keys)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_chat_requires_auth_when_keys_set() -> None:
    client = _client("admin-key:admin")
    resp = client.post("/api/chat", json={"message": "Hola"})
    assert resp.status_code == 401


def test_chat_allows_user_role() -> None:
    client = _client("user-key:user,admin-key:admin")
    resp = client.post(
        "/api/chat",
        json={"message": "No enciende mi laptop"},
        headers={"Authorization": "Bearer user-key"},
    )
    assert resp.status_code == 200


def test_escalate_requires_agent_role() -> None:
    client = _client("user-key:user,admin-key:admin")
    resp = client.post(
        "/api/escalate",
        json={"conversation_id": "x"},
        headers={"Authorization": "Bearer user-key"},
    )
    assert resp.status_code == 403


def test_escalate_allows_admin() -> None:
    client = _client("user-key:user,admin-key:admin")
    resp = client.post(
        "/api/escalate",
        json={"conversation_id": "no-existe"},
        headers={"Authorization": "Bearer admin-key"},
    )
    assert resp.status_code == 404

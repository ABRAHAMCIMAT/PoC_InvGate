"""Pruebas de los endpoints de chat."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.server import app


def test_chat_endpoint() -> None:
    client = TestClient(app)
    resp = client.post("/api/chat", json={"message": "No enciende mi laptop"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_id"] is not None
    assert body["category"] == "hardware"
    assert body["escalated"] is True


def test_chat_empty_message() -> None:
    client = TestClient(app)
    resp = client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_conversations_list() -> None:
    client = TestClient(app)
    client.post("/api/chat", json={"message": "Instalar software"})
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_escalate() -> None:
    client = TestClient(app)
    created = client.post("/api/chat", json={"message": "Duda general"}).json()
    conv_id = created["conversation_id"]
    resp = client.post("/api/escalate", json={"conversation_id": conv_id})
    assert resp.status_code == 200
    assert resp.json()["escalated"] is True


def test_escalate_missing() -> None:
    client = TestClient(app)
    resp = client.post("/api/escalate", json={"conversation_id": "no-existe"})
    assert resp.status_code == 404

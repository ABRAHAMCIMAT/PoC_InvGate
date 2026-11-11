"""Pruebas adicionales de los endpoints de chat."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.server import app


def test_chat_stream() -> None:
    client = TestClient(app)
    with client.stream("POST", "/api/chat/stream", json={"message": "No enciende mi laptop"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "data: " in body
    assert "done" in body


def test_chat_stream_empty() -> None:
    client = TestClient(app)
    resp = client.post("/api/chat/stream", json={"message": "  "})
    assert resp.status_code == 400


def test_get_conversation() -> None:
    client = TestClient(app)
    created = client.post("/api/chat", json={"message": "Instalar software"}).json()
    conv_id = created["conversation_id"]
    resp = client.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == conv_id


def test_get_conversation_missing() -> None:
    client = TestClient(app)
    resp = client.get("/api/conversations/no-existe")
    assert resp.status_code == 404

"""Flujo completo por la API: chat -> ticket -> aprobación -> decisión -> observaciones visibles."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.server import app

pytestmark = pytest.mark.e2e


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("POC_MANAGER_NAME", "Laura Manager")
    monkeypatch.setenv("POC_MANAGER_EMAIL", "laura@empresa.com")
    monkeypatch.setenv("NOTIFY_CHANNEL", "none")
    from backend.config import get_settings
    from backend.runtime import reset_runtime

    get_settings.cache_clear()
    reset_runtime()
    return TestClient(app)


def test_approval_round_trip(client: TestClient) -> None:
    chat = client.post("/api/chat", json={"message": "Necesito instalar Figma"}).json()
    assert chat["requires_approval"] is True
    approval_id = chat["approval_id"]
    assert chat["approval"]["status"] == "pending"
    statuses = {a["role"]: a["status"] for a in chat["agents"]}
    assert statuses["ejecucion"] == "warning"
    assert statuses["seguimiento"] == "warning"
    assert len(chat["agents"]) == 8

    listed = client.get("/api/approvals").json()
    assert [a["id"] for a in listed] == [approval_id]
    assert client.get(f"/api/approvals/{approval_id}").json()["manager_name"] == "Laura Manager"

    forbidden = client.post(
        f"/api/approvals/{approval_id}/decision",
        json={"decision": "approved", "user_email": "otro@empresa.com"},
    )
    assert forbidden.status_code == 403

    ok = client.post(
        f"/api/approvals/{approval_id}/decision",
        json={
            "decision": "approved",
            "note": "Usa la licencia del equipo",
            "user_email": "LAURA@empresa.com",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["changed"] is True

    again = client.post(
        f"/api/approvals/{approval_id}/decision",
        json={"decision": "rejected", "user_email": "laura@empresa.com"},
    ).json()
    assert again["changed"] is False
    assert again["status"] == "approved"

    conv = client.get(f"/api/conversations/{chat['conversation_id']}").json()
    assert conv["approved"] is True
    assert conv["approval"]["note"] == "Usa la licencia del equipo"
    assert conv["ticket"]["status"] == "in_progress"

    metrics = client.get("/api/metrics").json()
    assert metrics["negocio"]["aprobaciones"] == {
        "solicitadas": 1,
        "aprobadas": 1,
        "rechazadas": 0,
        "pendientes": 0,
        "espera_media_s": metrics["negocio"]["aprobaciones"]["espera_media_s"],
    }
    assert client.get("/api/audit/verify").json()["valid"] is True


def test_approval_errors(client: TestClient) -> None:
    assert client.get("/api/approvals/APR-x").status_code == 404
    assert client.post("/api/approvals/APR-x/decision", json={"decision": "approved"}).status_code == 404
    chat = client.post("/api/chat", json={"message": "instalar software"}).json()
    from backend.runtime import get_runtime

    get_runtime().approvals.get(chat["approval_id"]).created_at = 0
    expired = client.post(
        f"/api/approvals/{chat['approval_id']}/decision",
        json={"decision": "approved", "user_email": "laura@empresa.com"},
    )
    assert expired.status_code == 410


def test_approval_sync_conflict(client: TestClient, monkeypatch) -> None:
    chat = client.post("/api/chat", json={"message": "instalar software"}).json()
    from backend.runtime import get_runtime

    def missing(*a, **k):
        raise LookupError("sin aprobaciones pendientes")

    monkeypatch.setattr(get_runtime().provider, "resolve_approval", missing)
    resp = client.post(
        f"/api/approvals/{chat['approval_id']}/decision",
        json={"decision": "approved", "user_email": "laura@empresa.com"},
    )
    assert resp.status_code == 409


def test_stream_emits_each_agent(client: TestClient) -> None:
    with client.stream("POST", "/api/chat/stream", json={"message": "Se cayó producción para todos"}) as resp:
        body = "".join(resp.iter_text())
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    agents = [e for e in events if "role" in e]
    assert [a["role"] for a in agents][:2] == ["coordinador", "clasificador"]
    assert len(agents) == 8
    final = events[-1]
    assert final["done"] is True
    assert final["escalation_level"] == 3


def test_manual_escalation_increments_level(client: TestClient) -> None:
    chat = client.post("/api/chat", json={"message": "Tengo una duda"}).json()
    first = client.post(
        "/api/escalate", json={"conversation_id": chat["conversation_id"], "reason": "urgente"}
    )
    assert first.json()["escalation_level"] == 2
    second = client.post("/api/escalate", json={"conversation_id": chat["conversation_id"]})
    assert second.json()["escalation_level"] == 3
    third = client.post("/api/escalate", json={"conversation_id": chat["conversation_id"]})
    assert third.json()["escalation_level"] == 3


def test_frontend_served(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Valkiria" in resp.text
    assert client.get("/dashboard.html").status_code == 200

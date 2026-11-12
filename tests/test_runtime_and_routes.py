"""Pruebas del runtime compartido, el endpoint de Teams y la autenticación en producción."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.runtime import build_runtime, get_runtime, reset_runtime
from backend.teams.notifier import NullNotifier, TeamsBotNotifier, WebhookNotifier


def _settings(**kw) -> Settings:
    base = Settings()
    return base.__class__(**{**base.__dict__, **kw})


def test_notifier_selection(tmp_path) -> None:
    data = str(tmp_path)
    assert isinstance(build_runtime(_settings(data_dir=data)).notifier, NullNotifier)
    teams = build_runtime(_settings(data_dir=data, teams_bot_app_id="app", teams_bot_app_password="pw"))
    assert isinstance(teams.notifier, TeamsBotNotifier)
    hook = build_runtime(
        _settings(data_dir=data, notify_channel="webhook", teams_workflow_url="https://hook")
    )
    assert isinstance(hook.notifier, WebhookNotifier)
    assert isinstance(build_runtime(_settings(data_dir=data, notify_channel="none")).notifier, NullNotifier)
    off = build_runtime(_settings(data_dir=data, rate_limit_max=0))
    assert off.limiter is None


def test_simulated_runtime_persists_approvals(tmp_path) -> None:
    s = _settings(data_dir=str(tmp_path), ticketing_provider="simulated")
    rt = build_runtime(s)
    orch = rt.orchestrator()
    conv, _ = orch.handle("instalar software")
    again = build_runtime(s)
    assert again.approvals.get(conv.approval_id).incident_id == conv.ticket_id
    (tmp_path / "approvals.json").write_text("{")
    assert build_runtime(s).approvals.list() == []


def test_teams_endpoint_handles_activity() -> None:
    from backend.server import app

    client = TestClient(app)
    activity = {
        "type": "message",
        "id": "1",
        "channelId": "emulator",
        "serviceUrl": "https://localhost:9",
        "from": {"id": "u1", "name": "Ana"},
        "recipient": {"id": "bot"},
        "conversation": {"id": "conv1"},
        "text": "hola",
    }
    rt = get_runtime()
    sent = []

    async def fake_send(context, activities):
        sent.extend(activities)
        return []

    rt.adapter.send_activities = fake_send  # type: ignore[method-assign]
    resp = client.post("/api/messages", json=activity)
    assert resp.status_code in (200, 201)
    assert sent
    assert "bot de aprobaciones" in sent[0].text
    assert rt.references.get("u1") is not None
    assert (
        client.post("/api/messages", content="x", headers={"content-type": "text/plain"}).status_code == 415
    )


def test_teams_endpoint_rejects_bad_token(monkeypatch) -> None:
    from backend.server import app

    client = TestClient(app)
    rt = get_runtime()

    async def deny(*a, **k):
        raise PermissionError("bad jwt")

    monkeypatch.setattr(rt.adapter, "process_activity", deny)
    resp = client.post("/api/messages", json={"type": "message"})
    assert resp.status_code == 401


def test_teams_endpoint_invoke_response(monkeypatch) -> None:
    from backend.server import app

    class Invoke:
        status = 200
        body = {"ok": True}

    async def invoke(*a, **k):
        return Invoke()

    monkeypatch.setattr(get_runtime().adapter, "process_activity", invoke)
    resp = TestClient(app).post("/api/messages", json={"type": "invoke"})
    assert resp.json() == {"ok": True}


def test_production_requires_keys_and_bot(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    reset_runtime()
    from backend.server import app

    client = TestClient(app)
    assert client.post("/api/chat", json={"message": "hola"}).status_code == 503
    assert client.post("/api/messages", json={"type": "message"}).status_code == 503


def test_chat_rejects_huge_message() -> None:
    from backend.server import app

    assert TestClient(app).post("/api/chat", json={"message": "x" * 5000}).status_code == 422


def test_conversation_ticket_lookup_failure(monkeypatch) -> None:
    from backend.server import app

    client = TestClient(app)
    chat = client.post("/api/chat", json={"message": "vpn"}).json()
    rt = get_runtime()

    def boom(_):
        raise ConnectionError("x")

    monkeypatch.setattr(rt.provider, "get_incident", boom)
    monkeypatch.setattr(rt.provider, "add_comment", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    body = client.get(f"/api/conversations/{chat['conversation_id']}").json()
    assert body["ticket"] == {"id": chat["ticket_id"], "status": None}
    assert body["approval"] is None
    assert client.post("/api/escalate", json={"conversation_id": chat["conversation_id"]}).status_code == 200


def test_listener_errors_do_not_break(monkeypatch) -> None:
    rt = get_runtime()
    rt.approvals.subscribe(lambda e, r: (_ for _ in ()).throw(RuntimeError("x")))
    conv, _ = rt.orchestrator().handle("instalar software")
    assert conv.approval_id

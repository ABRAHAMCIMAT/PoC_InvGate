"""Pruebas del bot de Teams, el almacén de referencias y los notificadores."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
from botbuilder.core import TurnContext
from botbuilder.core.adapters import TestAdapter
from botbuilder.schema import Activity, ChannelAccount, ConversationAccount, ConversationReference

from backend.approvals.service import ApprovalRequest, ApprovalService
from backend.invgate.models import Incident
from backend.teams.adaptive_card import build_approval_card, build_result_card
from backend.teams.bot import WELCOME, ApprovalBot
from backend.teams.notifier import NullNotifier, TeamsBotNotifier, WebhookNotifier, _run
from backend.teams.references import ReferenceStore
from backend.ticketing.demo import DemoProvider


def _setup(manager_email: str = "", manager_teams_id: str = ""):
    provider = DemoProvider()
    service = ApprovalService(provider, manager_email=manager_email, manager_teams_id=manager_teams_id)
    incident = provider.create_incident(Incident(title="Instalar Figma"))
    req = service.request_approval(incident, reason="Instalar Figma")
    bot = ApprovalBot(service, ReferenceStore())
    adapter = TestAdapter(bot.on_turn)
    return provider, service, req, bot, adapter


def _texts(adapter: TestAdapter) -> list[str]:
    out = []
    while (activity := adapter.get_next_activity()) is not None:
        out.append(activity.text or "")
    return out


def _vote(
    adapter: TestAdapter, value: dict, user_id: str = "user1", reply_to: str | None = None
) -> list[str]:
    activity = Activity(
        type="message",
        value=value,
        from_property=ChannelAccount(id=user_id, name="Ana"),
        reply_to_id=reply_to,
    )
    asyncio.run(adapter.receive_activity(activity))
    return _texts(adapter)


def test_plain_message_gets_welcome_and_stores_reference() -> None:
    _, _, _, bot, adapter = _setup()
    asyncio.run(adapter.receive_activity(Activity(type="message", text="hola")))
    assert _texts(adapter) == [WELCOME]
    assert bot.references.get() is not None


def test_approve_with_note_updates_ticket() -> None:
    provider, service, req, _, adapter = _setup()
    texts = _vote(
        adapter, {"approval_id": req.id, "decision": "approved", "note": "Solo licencia anual"}, reply_to="1"
    )
    assert texts == [f"Aprobación {req.id} aprobada."]
    decided = service.get(req.id)
    assert decided.note == "Solo licencia anual"
    assert provider.get_incident(req.incident_id).status.value == "in_progress"
    assert "Solo licencia anual" in provider.list_comments(req.incident_id)[-1].body


def test_second_click_is_ignored() -> None:
    _, service, req, _, adapter = _setup()
    _vote(adapter, {"approval_id": req.id, "decision": "rejected"})
    texts = _vote(adapter, {"approval_id": req.id, "decision": "approved"})
    assert texts == ["Esta aprobación ya fue resuelta (rejected)."]
    assert service.get(req.id).status == "rejected"


def test_invalid_and_missing() -> None:
    _, _, req, _, adapter = _setup()
    assert _vote(adapter, {"approval_id": req.id, "decision": "tal-vez"}) == ["Decisión no válida."]
    assert _vote(adapter, {"approval_id": "APR-x", "decision": "approved"}) == ["Aprobación no encontrada."]


def test_only_manager_can_decide() -> None:
    _, service, req, _, adapter = _setup(manager_teams_id="manager-1")
    assert _vote(adapter, {"approval_id": req.id, "decision": "approved"}, user_id="otro") == [
        "Solo el manager asignado puede decidir esta aprobación."
    ]
    assert service.get(req.id).status == "pending"
    assert _vote(adapter, {"approval_id": req.id, "decision": "approved"}, user_id="manager-1") == [
        f"Aprobación {req.id} aprobada."
    ]


def test_expired() -> None:
    _, service, req, _, adapter = _setup()
    service.get(req.id).created_at = 0
    assert _vote(adapter, {"approval_id": req.id, "decision": "approved"}) == ["La aprobación expiró."]


def test_sync_failure_keeps_pending(monkeypatch) -> None:
    provider, service, req, _, adapter = _setup()

    def boom(*args, **kwargs):
        raise RuntimeError("InvGate caído")

    monkeypatch.setattr(provider, "resolve_approval", boom)
    texts = _vote(adapter, {"approval_id": req.id, "decision": "approved"})
    assert "No se pudo registrar" in texts[0]
    assert service.get(req.id).status == "pending"


def test_members_added_welcome() -> None:
    _, _, _, _, adapter = _setup()
    activity = Activity(
        type="conversationUpdate",
        members_added=[ChannelAccount(id="manager"), ChannelAccount(id="bot")],
        recipient=ChannelAccount(id="bot"),
    )
    asyncio.run(adapter.receive_activity(activity))
    assert _texts(adapter) == [WELCOME]


def test_send_approval_card() -> None:
    _, _, req, bot, adapter = _setup()

    async def go():
        async def logic(ctx):
            await bot.send_approval(ctx, req.id)

        a = TestAdapter(logic)
        await a.receive_activity(Activity(type="message", text="x"))
        return a.get_next_activity()

    activity = asyncio.run(go())
    assert activity.attachments[0].content["actions"][0]["data"]["approval_id"] == req.id


def test_cards() -> None:
    req = ApprovalRequest(id="APR-1", incident_id="T-1", manager_name="", manager_email="m@x.com", reason="r")
    card = build_approval_card(req)
    assert any(b.get("id") == "note" for b in card["body"])
    link = build_approval_card(req, open_url="https://x/?approval=APR-1")
    assert link["actions"][0]["type"] == "Action.OpenUrl"
    assert not any(b.get("type") == "Input.Text" for b in link["body"])
    req.note = "ok"
    from backend.approvals.service import ApprovalDecision

    req.decision = ApprovalDecision.APPROVED
    result = build_result_card(req)
    assert "aprobada" in result["body"][0]["text"]
    assert "Observaciones: ok" in result["body"][-1]["text"]


def test_reference_store_persists(tmp_path) -> None:
    path = str(tmp_path / "refs.json")
    store = ReferenceStore(path)
    ref = ConversationReference(
        conversation=ConversationAccount(id="c1"), user=ChannelAccount(id="u1"), service_url="https://s"
    )
    store.save(ref, "u1", "Ana@X.com", None)
    again = ReferenceStore(path)
    assert again.get("ana@x.com").conversation.id == "c1"
    assert again.get("desconocido").conversation.id == "c1"  # cae en default
    (tmp_path / "bad.json").write_text("{no json")
    assert ReferenceStore(str(tmp_path / "bad.json")).get() is None


def test_teams_notifier_sends_proactive_card() -> None:
    _, _, req, bot, _ = _setup()
    adapter = TestAdapter(bot.on_turn)
    asyncio.run(adapter.receive_activity(Activity(type="message", text="hola")))
    _texts(adapter)
    notifier = TeamsBotNotifier(adapter, "app-id", bot.references)
    assert notifier.notify(req) is True
    sent = adapter.get_next_activity()
    assert sent.attachments[0].content["type"] == "AdaptiveCard"


def test_teams_notifier_without_reference() -> None:
    _, _, req, _, adapter = _setup()
    assert TeamsBotNotifier(adapter, "app", ReferenceStore()).notify(req) is False


def test_teams_notifier_adapter_error() -> None:
    _, _, req, bot, adapter = _setup()
    asyncio.run(adapter.receive_activity(Activity(type="message", text="hola")))

    class Broken:
        async def continue_conversation(self, *a, **k):
            raise RuntimeError("sin red")

    assert TeamsBotNotifier(Broken(), "app", bot.references).notify(req) is False  # type: ignore[arg-type]


def test_run_inside_running_loop() -> None:
    seen = []

    async def inner():
        seen.append(1)

    async def outer():
        _run(inner())

    asyncio.run(outer())
    assert seen == [1]


def test_webhook_notifier() -> None:
    req = ApprovalRequest(
        id="APR-1", incident_id="T-1", manager_name="M", manager_email="m@x.com", reason="r"
    )
    bodies = []

    def ok(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    assert (
        WebhookNotifier("https://hook", "https://poc", transport=httpx.MockTransport(ok)).notify(req) is True
    )
    assert bodies[0]["attachments"][0]["content"]["actions"][0]["url"] == "https://poc/?approval=APR-1"
    assert WebhookNotifier("https://hook", transport=httpx.MockTransport(ok)).notify(req) is True
    assert bodies[1]["attachments"][0]["content"]["actions"] == []
    bad = WebhookNotifier("https://hook", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert bad.notify(req) is False

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("x")

    assert WebhookNotifier("https://hook", transport=httpx.MockTransport(fail)).notify(req) is False
    assert NullNotifier().notify(req) is False


def _invoke(adapter: TestAdapter, value: dict):
    activity = Activity(
        type="invoke",
        name="adaptiveCard/action",
        value=value,
        from_property=ChannelAccount(id="user1", name="Ana"),
    )
    asyncio.run(adapter.receive_activity(activity))
    return adapter.get_next_activity()


def test_legacy_execute_card_is_replaced_without_buttons() -> None:
    _, _, _, _, adapter = _setup()
    response = _invoke(adapter, {"action": {"type": "Action.Execute", "verb": "approve", "data": {}}})
    assert response.type == "invokeResponse"
    assert response.value.status == 200
    body = response.value.body
    assert body["statusCode"] == 200
    assert body["type"] == "application/vnd.microsoft.card.adaptive"
    card = body["value"]
    assert "actions" not in card
    assert card["body"][0]["text"] == "Tarjeta no vigente"


def test_invoke_with_unsupported_action_is_bad_request() -> None:
    _, _, _, _, adapter = _setup()
    response = _invoke(adapter, {"action": {"type": "Action.Submit"}})
    assert response.value.status == 400


def _context(activity: Activity) -> TurnContext:
    return TurnContext(TestAdapter(lambda ctx: None), activity)


def _teams_activity(**kw) -> Activity:
    return Activity(
        type="message",
        channel_id="msteams",
        from_property=ChannelAccount(id="29:manager", name="Carlos"),
        recipient=ChannelAccount(id="28:bot"),
        conversation=ConversationAccount(id="a:1"),
        service_url="https://smba.trafficmanager.net/amer/",
        **kw,
    )


def test_remember_skips_activity_without_sender_or_recipient() -> None:
    _, _, _, bot, _ = _setup()
    asyncio.run(bot._remember(_context(Activity(type="message", recipient=ChannelAccount(id="bot")))))
    asyncio.run(bot._remember(_context(Activity(type="message", from_property=ChannelAccount(id="u")))))
    assert bot.references.get() is None


def test_email_read_from_teams_member(monkeypatch) -> None:
    _, _, _, bot, _ = _setup()

    async def member(ctx, user_id):
        assert user_id == "29:manager"
        return SimpleNamespace(email="Carlos@Valtre.com", user_principal_name="carlos@valtre.com")

    monkeypatch.setattr("backend.teams.bot.TeamsInfo.get_member", member)
    asyncio.run(bot._remember(_context(_teams_activity(text="hola"))))
    assert "carlos@valtre.com" in bot.references._refs
    assert bot.references.get("carlos@valtre.com").user.id == "29:manager"


def test_email_falls_back_to_user_principal_name(monkeypatch) -> None:
    async def member(ctx, user_id):
        return SimpleNamespace(email=None, user_principal_name="carlos@valtre.com")

    monkeypatch.setattr("backend.teams.bot.TeamsInfo.get_member", member)
    assert asyncio.run(ApprovalBot._email(_context(_teams_activity()))) == "carlos@valtre.com"


def test_email_unavailable_returns_none(monkeypatch) -> None:
    async def member(ctx, user_id):
        raise PermissionError("sin permisos para leer el roster")

    monkeypatch.setattr("backend.teams.bot.TeamsInfo.get_member", member)
    assert asyncio.run(ApprovalBot._email(_context(_teams_activity()))) is None
    # Fuera de Teams ni siquiera se consulta.
    assert asyncio.run(ApprovalBot._email(_context(Activity(type="message", channel_id="webchat")))) is None
    assert asyncio.run(ApprovalBot._email(_context(Activity(type="message", channel_id="msteams")))) is None


def test_card_update_failure_still_confirms_decision(monkeypatch) -> None:
    _, service, req, _, adapter = _setup()

    async def fail(self, activity):
        raise RuntimeError("la tarjeta ya no existe")

    monkeypatch.setattr(TurnContext, "update_activity", fail)
    texts = _vote(adapter, {"approval_id": req.id, "decision": "approved"}, reply_to="card-1")
    assert texts == [f"Aprobación {req.id} aprobada."]
    assert service.get(req.id).status == "approved"


def test_card_replaced_with_result(monkeypatch) -> None:
    _, _, req, _, adapter = _setup()
    updates = []

    async def capture(self, activity):
        updates.append(activity)

    monkeypatch.setattr(TurnContext, "update_activity", capture)
    _vote(
        adapter, {"approval_id": req.id, "decision": "rejected", "note": "Sin presupuesto"}, reply_to="card-1"
    )
    assert updates[0].id == "card-1"
    card = updates[0].attachments[0].content
    assert "actions" not in card
    assert "Sin presupuesto" in json.dumps(card, ensure_ascii=False)

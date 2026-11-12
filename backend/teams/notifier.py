"""Notificación de aprobaciones al manager: bot de Teams proactivo o webhook de Workflows."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from typing import Any, Protocol

import httpx
from botbuilder.core import BotAdapter, CardFactory, MessageFactory, TurnContext

from backend.approvals.service import ApprovalRequest
from backend.teams.adaptive_card import build_approval_card
from backend.teams.references import ReferenceStore

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    def notify(self, req: ApprovalRequest) -> bool: ...


class NullNotifier:
    """No envía nada; deja constancia en el log (NOTIFY_CHANNEL=none)."""

    def notify(self, req: ApprovalRequest) -> bool:
        logger.info("Aprobación %s pendiente para %s (sin canal de notificación)", req.id, req.manager_email)
        return False


def _run(coro: Coroutine[Any, Any, Any]) -> None:
    """Ejecuta la corrutina aunque ya haya un event loop en este hilo."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    errors: list[BaseException] = []

    def target() -> None:
        try:
            asyncio.run(coro)
        except BaseException as exc:  # se relanza en el hilo que llama
            errors.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]


class TeamsBotNotifier:
    """Envía la Adaptive Card al chat 1:1 del manager con el bot (mensaje proactivo)."""

    def __init__(self, adapter: BotAdapter, app_id: str, references: ReferenceStore) -> None:
        self.adapter = adapter
        self.app_id = app_id
        self.references = references

    def notify(self, req: ApprovalRequest) -> bool:
        reference = self.references.get(req.manager_teams_id, req.manager_email)
        if reference is None:
            logger.warning(
                "El manager aún no ha hablado con el bot; no se puede enviar la aprobación %s", req.id
            )
            return False
        card = build_approval_card(req)

        async def callback(turn_context: TurnContext) -> None:
            await turn_context.send_activity(MessageFactory.attachment(CardFactory.adaptive_card(card)))

        try:
            _run(self.adapter.continue_conversation(reference, callback, bot_id=self.app_id))
        except Exception:
            logger.exception("No se pudo enviar la aprobación %s por Teams", req.id)
            return False
        return True


class WebhookNotifier:
    """Publica la tarjeta en un canal mediante un webhook de Teams Workflows (TEAMS_WORKFLOW_URL).

    Los botones de una tarjeta enviada así no llegan al bot, así que solo se incluye un enlace.
    """

    def __init__(
        self, url: str, public_base_url: str = "", transport: httpx.BaseTransport | None = None
    ) -> None:
        self.url = url
        self.public_base_url = public_base_url.rstrip("/")
        self._client = httpx.Client(timeout=10.0, transport=transport)

    def notify(self, req: ApprovalRequest) -> bool:
        link = f"{self.public_base_url}/?approval={req.id}" if self.public_base_url else None
        card = build_approval_card(req, open_url=link) if link else build_approval_card(req)
        if not link:
            card["actions"] = []
        payload = {
            "type": "message",
            "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
        }
        try:
            resp = self._client.post(self.url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Webhook de Teams falló: %s", exc)
            return False
        if resp.status_code >= 400:
            logger.warning("Webhook de Teams devolvió HTTP %s", resp.status_code)
            return False
        return True

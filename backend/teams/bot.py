"""Bot de Microsoft Teams para aprobaciones."""

from __future__ import annotations

import logging

from botbuilder.core import (
    ActivityHandler,
    CardFactory,
    MessageFactory,
    TurnContext,
)

from backend.approvals.service import ApprovalDecision, ApprovalService
from backend.teams.adaptive_card import build_approval_card

logger = logging.getLogger(__name__)


class ApprovalBot(ActivityHandler):
    """Bot que envía Adaptive Cards y procesa Aprobar/Rechazar."""

    def __init__(self, approvals: ApprovalService) -> None:
        self.approvals = approvals

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        value = turn_context.activity.value
        if not value or "approval_id" not in value:
            return
        approval_id = value["approval_id"]
        decision = value.get("decision")
        user = turn_context.activity.from_property
        user_id = user.id if user else "unknown"
        try:
            decision_enum = ApprovalDecision(decision)
        except ValueError:
            await turn_context.send_activity("Decisión no válida.")
            return
        try:
            req = self.approvals.decide(approval_id, decision_enum, user_id)
        except KeyError:
            await turn_context.send_activity("Aprobación no encontrada.")
            return
        except TimeoutError:
            await turn_context.send_activity("La aprobación expiró.")
            return
        if req.decided and req.decided_by != user_id:
            # Segundo clic de otro usuario: ignorado.
            await turn_context.send_activity("Esta aprobación ya fue resuelta.")
            return
        label = "aprobada" if req.decision == ApprovalDecision.APPROVED else "rechazada"
        await turn_context.send_activity(f"Aprobación {approval_id} {label}.")

    async def send_approval(self, turn_context: TurnContext, approval_id: str) -> None:
        req = self.approvals.get(approval_id)
        card = build_approval_card(req)
        activity = MessageFactory.attachment(
            CardFactory.adaptive_card(card)
        )
        await turn_context.send_activity(activity)

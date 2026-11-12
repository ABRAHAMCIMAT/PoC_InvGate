"""Bot de Microsoft Teams para aprobaciones."""

from __future__ import annotations

import logging

from botbuilder.core import ActivityHandler, CardFactory, MessageFactory, TurnContext
from botbuilder.core.teams import TeamsInfo

from backend.approvals.service import ApprovalDecision, ApprovalForbiddenError, ApprovalService
from backend.teams.adaptive_card import NOTE_INPUT_ID, build_approval_card, build_result_card
from backend.teams.references import ReferenceStore

logger = logging.getLogger(__name__)

WELCOME = (
    "Hola, soy el bot de aprobaciones de Valkiria. Te enviaré aquí las solicitudes que requieran tu "
    "aprobación, con botones para aprobar o rechazar y un campo de observaciones."
)


class ApprovalBot(ActivityHandler):
    """Bot que guarda la conversación del manager, envía Adaptive Cards y procesa la decisión."""

    def __init__(self, approvals: ApprovalService, references: ReferenceStore | None = None) -> None:
        self.approvals = approvals
        self.references = references or ReferenceStore()

    async def on_turn(self, turn_context: TurnContext) -> None:
        await self._remember(turn_context)
        await super().on_turn(turn_context)

    async def _remember(self, turn_context: TurnContext) -> None:
        user = turn_context.activity.from_property
        if user is None or turn_context.activity.recipient is None:
            return
        reference = TurnContext.get_conversation_reference(turn_context.activity)
        email = await self._email(turn_context)
        self.references.save(reference, user.id, getattr(user, "aad_object_id", None), email)

    @staticmethod
    async def _email(turn_context: TurnContext) -> str | None:
        user = turn_context.activity.from_property
        if user is None or turn_context.activity.channel_id != "msteams":
            return None
        try:
            member = await TeamsInfo.get_member(turn_context, user.id)
        except Exception as exc:  # sin permisos o fuera de Teams
            logger.info("No se pudo leer el correo del usuario de Teams: %s", exc)
            return None
        return getattr(member, "email", None) or getattr(member, "user_principal_name", None)

    async def on_members_added_activity(self, members_added, turn_context: TurnContext) -> None:
        recipient = turn_context.activity.recipient
        for member in members_added:
            if recipient is None or member.id != recipient.id:
                await turn_context.send_activity(WELCOME)

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        value = turn_context.activity.value
        if not isinstance(value, dict) or "approval_id" not in value:
            await turn_context.send_activity(WELCOME)
            return
        approval_id = str(value["approval_id"])
        user = turn_context.activity.from_property
        user_id = user.id if user else "unknown"
        try:
            decision = ApprovalDecision(value.get("decision"))
        except ValueError:
            await turn_context.send_activity("Decisión no válida.")
            return
        try:
            before = self.approvals.get(approval_id).decided
        except KeyError:
            await turn_context.send_activity("Aprobación no encontrada.")
            return
        try:
            req = self.approvals.decide(
                approval_id,
                decision,
                user_id,
                note=value.get(NOTE_INPUT_ID),
                user_email=await self._email(turn_context),
            )
        except TimeoutError:
            await turn_context.send_activity("La aprobación expiró.")
            return
        except ApprovalForbiddenError:
            await turn_context.send_activity("Solo el manager asignado puede decidir esta aprobación.")
            return
        except Exception:
            logger.exception("No se pudo registrar la decisión de %s", approval_id)
            await turn_context.send_activity(
                "No se pudo registrar la decisión en el ticket. Inténtalo de nuevo."
            )
            return
        if before:
            # Segundo clic: la decisión original se mantiene.
            await turn_context.send_activity(f"Esta aprobación ya fue resuelta ({req.status}).")
            return
        await self._replace_card(turn_context, req)
        label = "aprobada" if req.decision == ApprovalDecision.APPROVED else "rechazada"
        await turn_context.send_activity(f"Aprobación {approval_id} {label}.")

    @staticmethod
    async def _replace_card(turn_context: TurnContext, req) -> None:
        reply_to = turn_context.activity.reply_to_id
        if not reply_to:
            return
        update = MessageFactory.attachment(CardFactory.adaptive_card(build_result_card(req)))
        update.id = reply_to
        try:
            await turn_context.update_activity(update)
        except Exception as exc:
            logger.info("No se pudo actualizar la tarjeta original: %s", exc)

    async def send_approval(self, turn_context: TurnContext, approval_id: str) -> None:
        req = self.approvals.get(approval_id)
        card = build_approval_card(req)
        await turn_context.send_activity(MessageFactory.attachment(CardFactory.adaptive_card(card)))

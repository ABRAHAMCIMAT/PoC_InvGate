"""Integración con Microsoft Teams."""

from backend.teams.adaptive_card import build_approval_card, build_result_card
from backend.teams.bot import ApprovalBot
from backend.teams.notifier import NullNotifier, TeamsBotNotifier, WebhookNotifier
from backend.teams.references import ReferenceStore

__all__ = [
    "ApprovalBot",
    "NullNotifier",
    "ReferenceStore",
    "TeamsBotNotifier",
    "WebhookNotifier",
    "build_approval_card",
    "build_result_card",
]

"""Integración con Microsoft Teams."""

from backend.teams.adaptive_card import build_approval_card
from backend.teams.bot import ApprovalBot

__all__ = ["ApprovalBot", "build_approval_card"]

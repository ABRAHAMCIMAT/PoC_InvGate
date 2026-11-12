"""Rutas de la API."""

from backend.routes.admin import router as admin_router
from backend.routes.approvals import router as approvals_router
from backend.routes.chat import router as chat_router
from backend.routes.teams import router as teams_router

__all__ = ["admin_router", "approvals_router", "chat_router", "teams_router"]

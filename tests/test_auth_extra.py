"""Pruebas adicionales de RBAC."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.security.auth import require_role


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/agent")
    def agent(_: str = Depends(require_role("agent"))) -> dict:
        return {"ok": True}

    return app


def test_agent_role_allowed() -> None:
    settings = Settings(api_keys="agent-key:agent,admin-key:admin")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/agent", headers={"Authorization": "Bearer agent-key"})
    assert resp.status_code == 200


def test_admin_role_allowed_agent_route() -> None:
    settings = Settings(api_keys="admin-key:admin")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/agent", headers={"Authorization": "Bearer admin-key"})
    assert resp.status_code == 200


def test_user_role_denied_agent_route() -> None:
    settings = Settings(api_keys="user-key:user")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/agent", headers={"Authorization": "Bearer user-key"})
    assert resp.status_code == 403

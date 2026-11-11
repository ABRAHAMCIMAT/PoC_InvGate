"""Pruebas de autenticación y RBAC."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.security.auth import require_role


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/admin")
    def admin(_: str = Depends(require_role("admin"))) -> dict:
        return {"ok": True}

    @app.get("/agent")
    def agent(_: str = Depends(require_role("agent"))) -> dict:
        return {"ok": True}

    return app


def test_open_when_no_keys() -> None:
    client = TestClient(_app())
    resp = client.get("/admin")
    assert resp.status_code == 200


def test_valid_admin_key() -> None:
    from backend.config import Settings, get_settings

    settings = Settings(api_keys="admin-key:admin,user-key:user")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": "Bearer admin-key"})
    assert resp.status_code == 200


def test_user_key_denied_admin() -> None:
    from backend.config import Settings, get_settings

    settings = Settings(api_keys="admin-key:admin,user-key:user")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": "Bearer user-key"})
    assert resp.status_code == 403


def test_invalid_key() -> None:
    from backend.config import Settings, get_settings

    settings = Settings(api_keys="admin-key:admin")
    app = _app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401

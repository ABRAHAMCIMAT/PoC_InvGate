"""Autenticación y RBAC por API key."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)

ROLES = {"user", "agent", "admin"}


def _parse_keys(raw: str) -> dict[str, str]:
    """Parsea `API_KEYS=clave:rol,clave:rol`."""
    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            key, role = entry.split(":", 1)
            result[key.strip()] = role.strip()
    return result


def _safe_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def require_role(role: str):
    """Dependencia FastAPI que exige un rol mínimo."""

    def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        settings: Settings = Depends(get_settings),
    ) -> str:
        if not settings.api_keys:
            # Sin API_KEYS configuradas, el acceso es abierto (modo demo).
            return "admin"
        if credentials is None:
            raise HTTPException(status_code=401, detail="API key requerida")
        keys = _parse_keys(settings.api_keys)
        provided = credentials.credentials
        for key, key_role in keys.items():
            if _safe_equal(key, provided):
                if role == "admin" and key_role != "admin":
                    raise HTTPException(status_code=403, detail="Se requiere rol admin")
                if role == "agent" and key_role not in {"agent", "admin"}:
                    raise HTTPException(status_code=403, detail="Se requiere rol agent")
                return key_role
        raise HTTPException(status_code=401, detail="API key no válida")

    return dependency

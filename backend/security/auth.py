"""Autenticación y RBAC por API key."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)

# Cada rol incluye los permisos de los anteriores.
ROLE_RANK = {"user": 1, "agent": 2, "admin": 3}
ROLES = set(ROLE_RANK)

# Respuestas que añade cualquier endpoint protegido, para la documentación OpenAPI.
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta la API key o no es válida"},
    403: {"description": "La API key no tiene el rol necesario"},
    503: {"description": "API_KEYS sin configurar en producción"},
}


def _parse_keys(raw: str) -> dict[str, str]:
    """Parsea `API_KEYS=clave:rol,clave:rol`."""
    result: dict[str, str] = {}
    for entry in (e.strip() for e in raw.split(",")):
        if ":" in entry:
            key, role = entry.split(":", 1)
            result[key.strip()] = role.strip()
    return result


def _safe_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _role_for(api_keys: str, provided: str) -> str | None:
    """Rol de la clave recibida, comparando en tiempo constante; None si no existe."""
    for key, key_role in _parse_keys(api_keys).items():
        if _safe_equal(key, provided):
            return key_role
    return None


def require_role(role: str) -> Callable[..., str]:
    """Dependencia FastAPI que exige un rol mínimo y devuelve el rol de quien llama."""
    needed = ROLE_RANK[role]

    def dependency(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> str:
        if not settings.api_keys:
            if settings.is_production:
                # En producción nunca se abre la API por olvido de configuración.
                raise HTTPException(status_code=503, detail="API_KEYS no configuradas en producción")
            return "admin"  # modo demo: acceso abierto
        if credentials is None:
            raise HTTPException(status_code=401, detail="API key requerida")
        key_role = _role_for(settings.api_keys, credentials.credentials)
        if key_role is None:
            raise HTTPException(status_code=401, detail="API key no válida")
        if ROLE_RANK.get(key_role, 0) < needed:
            raise HTTPException(status_code=403, detail=f"Se requiere rol {role}")
        return key_role

    return dependency


UserRole = Annotated[str, Depends(require_role("user"))]
AgentRole = Annotated[str, Depends(require_role("agent"))]
AdminRole = Annotated[str, Depends(require_role("admin"))]

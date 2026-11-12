"""Cliente HTTP de la API de InvGate Service Management.

Sigue las convenciones de la API v1 documentada en
https://releases.invgate.com/service-desk/api/ : los recursos se nombran con
puntos (``/incident.comment``, ``/incident.approval.accept``) y el
identificador viaja como parámetro (``id``, ``request_id``, ``approval_id``),
no como segmento de la ruta.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Generator
from typing import Any

import httpx

from backend.invgate.mapping import FieldMapper, ValueMapper
from backend.invgate.models import CatalogItem, Comment, Incident, IncidentStatus, IncidentType

logger = logging.getLogger(__name__)

RETRY_STATUS = (429, 500, 502, 503, 504)

# Campos del dominio que en InvGate se llaman distinto. INVGATE_FIELD_MAP los sobreescribe.
DEFAULT_FIELD_MAP = {
    "category": "category_id",
    "priority": "priority_id",
    "type": "type_id",
    "status": "status_id",
    "requester": "customer_id",
    "assignee": "assigned_id",
    "helpdesk": "assigned_group_id",
}

# Valores del dominio -> ids de InvGate (enums documentados de PUT/POST /incident).
# INVGATE_VALUE_MAP los sobreescribe o amplía (p. ej. categorías y estados de la instancia).
DEFAULT_VALUE_MAP: dict[str, dict[str, str]] = {
    "priority": {"baja": "1", "media": "2", "alta": "3", "urgente": "4", "critica": "5"},
    "type": {"incident": "1", "request": "2", "problem": "4", "change": "5"},
}


class InvGateError(Exception):
    """Error base del cliente InvGate."""


class InvGateAuthError(InvGateError):
    """Error de autenticación contra InvGate."""


class InvGateNotFoundError(InvGateError):
    """Recurso no encontrado en InvGate."""


class OAuth2ClientCredentials(httpx.Auth):
    """Auth OAuth 2.0 *client credentials* con caché del token y renovación ante 401."""

    requires_response_body = True

    def __init__(self, token_url: str, client_id: str, client_secret: str, timeout: float = 15.0) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _fetch_token(self) -> str:
        resp = httpx.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise InvGateAuthError(f"No se pudo obtener token OAuth2 (HTTP {resp.status_code})")
        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise InvGateAuthError("La respuesta OAuth2 no trae access_token")
        # Renovar un poco antes de que expire.
        self._expires_at = time.time() + max(int(body.get("expires_in", 3600)) - 30, 30)
        self._token = str(token)
        return self._token

    def token(self, force: bool = False) -> str:
        with self._lock:
            if force or not self._token or time.time() >= self._expires_at:
                return self._fetch_token()
            return self._token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        response = yield request
        if response.status_code == 401:
            request.headers["Authorization"] = f"Bearer {self.token(force=True)}"
            yield request


class InvGateClient:
    """Cliente HTTP con auth por token u OAuth2, reintentos y mapeo de campos."""

    # El token vacío significa "sin configurar" (se usa OAuth2), no es una credencial.
    def __init__(  # nosec B107
        self,
        base_url: str,
        api_token: str = "",
        username: str = "api",
        timeout: float = 15.0,
        max_retries: int = 3,
        *,
        api_prefix: str = "/api/v1",
        field_map: str = "",
        value_map: str = "",
        defaults: dict[str, Any] | None = None,
        oauth: OAuth2ClientCredentials | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/" + api_prefix.strip("/") if api_prefix.strip("/") else ""
        self.username = username
        self.api_token = api_token
        self.max_retries = max_retries
        self.fields = FieldMapper(field_map, defaults=DEFAULT_FIELD_MAP)
        self.values = ValueMapper(value_map, defaults=DEFAULT_VALUE_MAP)
        self.defaults = defaults or {}
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        self._client.auth = oauth if oauth is not None else httpx.BasicAuth(username, api_token)

    # ------------------------------------------------------------------ HTTP
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.api_prefix}{path}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("InvGate %s %s falló (intento %d): %s", method, url, attempt + 1, exc)
                self._backoff(attempt)
                continue
            if resp.status_code in RETRY_STATUS:
                last_error = InvGateError(f"HTTP {resp.status_code} en {url}")
                logger.warning("InvGate %s %s -> %s (intento %d)", method, url, resp.status_code, attempt + 1)
                self._backoff(attempt)
                continue
            if resp.status_code in (401, 403):
                raise InvGateAuthError(f"Autenticación fallida (HTTP {resp.status_code})")
            if resp.status_code == 404:
                raise InvGateNotFoundError(f"Recurso no encontrado: {url}")
            if resp.status_code >= 400:
                raise InvGateError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise InvGateError(f"InvGate no respondió tras {self.max_retries} intentos: {last_error}")

    # ------------------------------------------------------------- Incidentes
    def create_incident(self, incident: Incident) -> Incident:
        payload = {**self.defaults, **self._to_invgate(incident)}
        data = self._request("POST", "/incident", json=payload)
        request_id = self._extract_id(data)
        if request_id is None:
            raise InvGateError(f"POST /incident no devolvió request_id: {data}")
        return incident.model_copy(update={"id": request_id, "number": request_id})

    def get_incident(self, incident_id: str) -> Incident:
        data = self._request("GET", "/incident", params={"id": incident_id, "date_format": "iso8601"})
        if isinstance(data, list):
            if not data:
                raise InvGateNotFoundError(f"Incidente no encontrado: {incident_id}")
            data = data[0]
        return self._parse_incident(data)

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        payload = {"id": incident_id, **self._to_invgate(incident)}
        self._request("PUT", "/incident", json=payload)
        return incident.model_copy(update={"id": incident_id})

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        data = self._request("GET", "/incidents.last.hour", params={"limit": limit})
        items = self._items(data)
        return [self._parse_incident(item) for item in items[:limit]]

    # ------------------------------------------------------------ Comentarios
    def add_comment(
        self,
        incident_id: str,
        body: str,
        author: str | None = None,
        customer_visible: bool = True,
    ) -> Comment:
        author_id = author or self.defaults.get("creator_id")
        payload: dict[str, Any] = {
            "request_id": incident_id,
            "comment": body,
            "customer_visible": 1 if customer_visible else 0,
        }
        if author_id is not None:
            payload["author_id"] = author_id
        data = self._request("POST", "/incident.comment", json=payload)
        comment_id = self._extract_id(data, keys=("id", "comment_id"))
        return Comment(id=comment_id, incident_id=incident_id, body=body, author=str(author_id or "") or None)

    def list_comments(self, incident_id: str) -> list[Comment]:
        data = self._request(
            "GET", "/incident.comment", params={"request_id": incident_id, "date_format": "iso8601"}
        )
        comments: list[Comment] = []
        for item in self._items(data):
            text = item.get("message") or item.get("comment") or item.get("body") or ""
            if not text:
                continue
            comments.append(
                Comment(
                    id=_str(item.get("id")),
                    incident_id=incident_id,
                    body=str(text),
                    author=_str(item.get("author_id")),
                    created_at=_str(item.get("created_at")),
                )
            )
        return comments

    # ----------------------------------------------------------- Aprobaciones
    def request_approval(self, incident_id: str, approver_id: str, description: str, author_id: str) -> None:
        """Crea una aprobación espontánea (POST /incident.spontaneous_approval)."""
        self._request(
            "POST",
            "/incident.spontaneous_approval",
            json={
                "request_id": incident_id,
                "approval_user_id": approver_id,
                "author_id": author_id,
                "description": description,
            },
        )

    def list_approvals(self, incident_id: str, only_pending: bool = False) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"request_id": incident_id, "date_format": "iso8601"}
        if only_pending:
            params["only_pending"] = True
        return self._items(self._request("GET", "/incident.approval", params=params))

    def accept_approval(self, approval_id: str, user_id: str, note: str | None = None) -> None:
        self._vote("/incident.approval.accept", approval_id, user_id, note)

    def reject_approval(self, approval_id: str, user_id: str, note: str | None = None) -> None:
        self._vote("/incident.approval.reject", approval_id, user_id, note)

    def _vote(self, path: str, approval_id: str, user_id: str, note: str | None) -> None:
        payload: dict[str, Any] = {"approval_id": approval_id, "user_id": user_id}
        if note:
            payload["note"] = note
        self._request("PUT", path, json=payload)

    # -------------------------------------------------------------- Catálogos
    def list_catalog(self, catalog: str) -> list[CatalogItem]:
        """Catálogos: incident.attributes.priority|status|type|source, categories, helpdesks, users."""
        data = self._request("GET", f"/{catalog.lstrip('/')}")
        result: list[CatalogItem] = []
        if isinstance(data, dict) and "data" not in data and all(isinstance(v, str) for v in data.values()):
            # Algunos catálogos devuelven un mapa {id: nombre}.
            return [CatalogItem(id=str(k), name=v, value=str(k)) for k, v in data.items()]
        for item in self._items(data):
            name = item.get("name") or item.get("description") or item.get("value")
            if name is None:
                continue
            result.append(
                CatalogItem(
                    id=_str(item.get("id")),
                    name=str(name),
                    value=_str(item.get("value") or item.get("id")),
                    extra={k: v for k, v in item.items() if k not in {"id", "name", "value"}},
                )
            )
        return result

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------- Utilidades
    def _to_invgate(self, incident: Incident) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        data = incident.model_dump(mode="json", exclude_none=True)
        for domain, value in data.items():
            if domain in {"id", "number", "created_at", "updated_at", "extra"}:
                continue
            if domain == "status" and value == IncidentStatus.NEW.value:
                # InvGate asigna el estado inicial; no se envía en altas ni ediciones.
                continue
            if domain == "description" and not value:
                continue
            payload[self.fields.to_invgate(domain)] = self.values.to_invgate(domain, value)
        payload.update(incident.extra)
        return payload

    def _parse_incident(self, data: dict[str, Any]) -> Incident:
        domain: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        known = set(Incident.model_fields)
        for key, value in data.items():
            name = self.fields.from_invgate(key)
            if name in known and name != "extra":
                domain[name] = self.values.from_invgate(name, value)
            else:
                extra[key] = value
        if "updated_at" not in domain and "last_update" in data:
            domain["updated_at"] = data["last_update"]
        status = domain.get("status")
        try:
            domain["status"] = IncidentStatus(str(status)) if status is not None else IncidentStatus.NEW
        except ValueError:
            extra["status_id"] = status
            domain["status"] = IncidentStatus.OPEN
        for key in ("id", "number", "category", "priority", "requester", "assignee", "helpdesk"):
            if key in domain and domain[key] is not None:
                domain[key] = str(domain[key])
        if "type" in domain:
            try:
                domain["type"] = IncidentType(str(domain["type"]))
            except ValueError:
                extra["type_id"] = domain.pop("type")
        domain.setdefault("number", _str(data.get("pretty_id")) or domain.get("id"))
        domain["title"] = domain.get("title") or f"Incidente {domain.get('id', '')}".strip()
        domain["description"] = domain.get("description") or ""
        return Incident(**domain, extra=extra)

    @staticmethod
    def _items(data: Any) -> list[dict[str, Any]]:
        if data is None:
            return []
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        if isinstance(data, dict):
            for key in ("data", "requests", "incidents", "results"):
                if isinstance(data.get(key), list):
                    return [d for d in data[key] if isinstance(d, dict)]
            if all(isinstance(v, dict) for v in data.values()) and data:
                return list(data.values())
        return []

    @staticmethod
    def _extract_id(data: Any, keys: tuple[str, ...] = ("request_id", "id")) -> str | None:
        if isinstance(data, dict):
            for key in keys:
                if data.get(key) is not None:
                    return str(data[key])
        if isinstance(data, (int, str)) and str(data):
            return str(data)
        return None

    @staticmethod
    def _backoff(attempt: int) -> None:
        """Espera exponencial con jitter antes de reintentar."""
        delay = min(0.5 * (2**attempt), 8.0) + secrets.randbelow(250) / 1000.0
        time.sleep(delay)


def _str(value: Any) -> str | None:
    return None if value is None else str(value)

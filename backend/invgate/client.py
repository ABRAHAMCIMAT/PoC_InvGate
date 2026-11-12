"""Cliente HTTP de la API de InvGate Service Management."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

import httpx

from backend.invgate.models import CatalogItem, Comment, Incident

logger = logging.getLogger(__name__)


class InvGateError(Exception):
    """Error base del cliente InvGate."""


class InvGateAuthError(InvGateError):
    """Error de autenticación contra InvGate."""


class InvGateNotFoundError(InvGateError):
    """Recurso no encontrado en InvGate."""


class InvGateClient:
    """Cliente HTTP con auth por token, reintentos y degradación elegante."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        username: str = "api",
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self._client.auth = httpx.BasicAuth(username, api_token)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"/api/v1{path}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("InvGate %s %s falló (intento %d): %s", method, url, attempt + 1, exc)
                self._backoff(attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = InvGateError(f"HTTP {resp.status_code} en {url}")
                logger.warning("InvGate %s %s -> %s (intento %d)", method, url, resp.status_code, attempt + 1)
                self._backoff(attempt)
                continue
            if resp.status_code == 401 or resp.status_code == 403:
                raise InvGateAuthError(f"Autenticación fallida (HTTP {resp.status_code})")
            if resp.status_code == 404:
                raise InvGateNotFoundError(f"Recurso no encontrado: {url}")
            if resp.status_code >= 400:
                raise InvGateError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
            if resp.status_code == 204:
                return None
            return resp.json()
        raise InvGateError(f"InvGate no respondió tras {self.max_retries} intentos: {last_error}")

    def create_incident(self, incident: Incident) -> Incident:
        data = self._request("POST", "/incident", json=incident.model_dump(exclude_none=True))
        return self._parse_incident(data)

    def get_incident(self, incident_id: str) -> Incident:
        data = self._request("GET", f"/incident/{incident_id}")
        return self._parse_incident(data)

    def update_incident(self, incident_id: str, incident: Incident) -> Incident:
        data = self._request(
            "PUT",
            f"/incident/{incident_id}",
            json=incident.model_dump(exclude_none=True, exclude={"id", "number"}),
        )
        return self._parse_incident(data)

    def list_incidents(self, limit: int = 50) -> list[Incident]:
        data = self._request("GET", "/incident", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("data", [])
        return [self._parse_incident(item) for item in items]

    def add_comment(self, incident_id: str, body: str, author: str | None = None) -> Comment:
        payload: dict[str, Any] = {"body": body}
        if author:
            payload["author"] = author
        data = self._request("POST", f"/incident/{incident_id}/comment", json=payload)
        return Comment(incident_id=incident_id, **data)

    def list_comments(self, incident_id: str) -> list[Comment]:
        data = self._request("GET", f"/incident/{incident_id}/comment")
        items = data if isinstance(data, list) else data.get("data", [])
        return [Comment(incident_id=incident_id, **item) for item in items]

    def list_catalog(self, catalog: str) -> list[CatalogItem]:
        data = self._request("GET", f"/{catalog}")
        items = data if isinstance(data, list) else data.get("data", [])
        return [CatalogItem(**item) for item in items]

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _backoff(attempt: int) -> None:
        """Espera exponencial con jitter antes de reintentar."""
        delay = min(0.5 * (2**attempt), 8.0) + secrets.randbelow(250) / 1000.0
        time.sleep(delay)

    @staticmethod
    def _parse_incident(data: dict[str, Any]) -> Incident:
        return Incident(**data)

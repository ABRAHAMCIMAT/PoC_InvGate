"""Límite de peticiones por cliente con ventana deslizante en memoria."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

# Rutas que no cuentan: el healthcheck y el canal del Bot Framework (lo llama Microsoft).
EXEMPT_PATHS = {"/api/health", "/api/messages"}


class SlidingWindowLimiter:
    """Permite `max_requests` por `window` segundos para cada clave."""

    def __init__(self, max_requests: int, window: float) -> None:
        self.max_requests = max_requests
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> tuple[bool, int, float]:
        """Registra un intento. Devuelve (permitido, restantes, segundos hasta liberar un hueco)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False, 0, max(hits[0] + self.window - now, 0.0)
            hits.append(now)
            if len(self._hits) > 10_000:  # evita crecer sin límite con muchas IPs
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True, self.max_requests - len(hits), 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    """La API key si viene (hasheada), si no la IP del cliente."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 7:
        return "key:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:16]
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def rate_limit_middleware(
    limiter_factory: Callable[[], SlidingWindowLimiter | None],
    on_limited: Callable[[str], None] | None = None,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        limiter = limiter_factory()
        if limiter is None or not path.startswith("/api/") or path in EXEMPT_PATHS:
            return await call_next(request)
        allowed, remaining, retry_after = limiter.hit(client_key(request))
        if not allowed:
            if on_limited:
                on_limited(path)
            retry = max(1, math.ceil(retry_after))
            return JSONResponse(
                {"detail": f"Demasiadas peticiones. Intenta de nuevo en {retry} s."},
                status_code=429,
                headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(limiter.max_requests)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    return middleware

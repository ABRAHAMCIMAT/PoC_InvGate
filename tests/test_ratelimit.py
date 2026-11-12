"""Pruebas del límite de peticiones."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.runtime import get_runtime, reset_runtime
from backend.security.ratelimit import SlidingWindowLimiter


def test_sliding_window() -> None:
    limiter = SlidingWindowLimiter(2, 10)
    assert limiter.hit("a", now=0)[0]
    assert limiter.hit("a", now=1) == (True, 0, 0.0)
    allowed, remaining, retry = limiter.hit("a", now=2)
    assert not allowed and remaining == 0 and retry == 8
    assert limiter.hit("b", now=2)[0]  # otra clave, otro cupo
    assert limiter.hit("a", now=10.5)[0]  # la primera salió de la ventana
    limiter.reset()
    assert limiter.hit("a", now=11)[1] == 1


def _client(monkeypatch, **env) -> TestClient:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    reset_runtime()
    from backend.server import app

    return TestClient(app)


def test_middleware_returns_429(monkeypatch) -> None:
    client = _client(monkeypatch, RATE_LIMIT_MAX="2", RATE_LIMIT_WINDOW="60")
    assert client.get("/api/conversations").headers["X-RateLimit-Remaining"] == "1"
    assert client.get("/api/conversations").status_code == 200
    blocked = client.get("/api/conversations")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # el healthcheck y los estáticos no cuentan
    assert client.get("/api/health").status_code == 200
    # cada API key tiene su propio cupo
    assert client.get("/api/conversations", headers={"Authorization": "Bearer otra"}).status_code == 200
    events = [e["event"] for e in get_runtime().telemetry.read()]
    assert "rate_limited" in events


def test_middleware_disabled(monkeypatch) -> None:
    client = _client(monkeypatch, RATE_LIMIT_MAX="1", RATE_LIMIT_ENABLED="false")
    for _ in range(3):
        assert client.get("/api/conversations").status_code == 200

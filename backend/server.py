"""API REST del PoC Valkiria InvGate."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.routes import admin_router, approvals_router, chat_router, teams_router
from backend.runtime import get_runtime
from backend.security.ratelimit import rate_limit_middleware

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

settings = get_settings()

app = FastAPI(title="Valkiria InvGate PoC", version="0.2.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def _limiter():
    return get_runtime().limiter


def _on_limited(path: str) -> None:
    get_runtime().telemetry.emit("rate_limited", path=path)


app.middleware("http")(rate_limit_middleware(_limiter, _on_limited))

app.include_router(chat_router)
app.include_router(approvals_router)
app.include_router(admin_router)
app.include_router(teams_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "valkiria-invgate", "version": "0.2.0"}


# El chat web y el dashboard se sirven desde el mismo origen que la API.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

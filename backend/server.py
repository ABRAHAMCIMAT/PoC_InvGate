"""API REST del PoC Valkiria InvGate."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes.chat import router as chat_router

settings = get_settings()

app = FastAPI(title="Valkiria InvGate PoC", version="0.1.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "valkiria-invgate", "version": "0.1.0"}

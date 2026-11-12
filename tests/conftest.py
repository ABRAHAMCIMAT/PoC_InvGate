"""Fixtures comunes: cada prueba usa su propio DATA_DIR y un runtime nuevo."""

from __future__ import annotations

import pytest

from backend.config import get_settings
from backend.runtime import reset_runtime


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    for var in ("API_KEYS", "TICKETING_PROVIDER", "LLM_PROVIDER", "NOTIFY_CHANNEL", "POC_MANAGER_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    reset_runtime()
    yield
    from backend.server import app

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    reset_runtime()

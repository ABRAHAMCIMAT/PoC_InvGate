"""Pruebas de la configuración centralizada."""

from __future__ import annotations

from backend.config import Settings, get_settings


def test_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    s = Settings()
    assert s.app_env == "development"
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.log_level == "INFO"
    assert s.log_user_content is False
    assert s.data_dir == "backend/data"
    assert s.api_keys == ""
    assert s.cors_origins == "http://localhost:8000"
    assert s.rate_limit_max == 60
    assert s.rate_limit_window == 60
    assert s.llm_provider == "mock"
    assert s.llm_base_url == ""
    assert s.llm_model == ""
    assert s.llm_api_key == ""
    assert s.ticketing_provider == "demo"
    assert s.storage_backend == "file"
    assert s.approval_ttl_hours == 72
    assert s.invgate_base_url == ""
    assert s.invgate_api_token == ""
    assert s.invgate_username == "api"
    assert s.invgate_field_map == ""
    assert s.invgate_value_map == ""
    assert s.invgate_action_type == ""
    assert s.poc_manager_name == ""
    assert s.poc_manager_email == ""
    assert s.notify_channel == "teams"
    assert s.teams_bot_app_id == ""
    assert s.teams_bot_app_password == ""
    assert s.teams_tenant_id == ""
    assert s.teams_service_url == "https://smba.trafficmanager.net/teams/"
    assert s.teams_workflow_url == ""
    assert s.public_base_url == ""
    assert s.langfuse_public_key == ""
    assert s.langfuse_secret_key == ""
    assert s.langfuse_host == "https://cloud.langfuse.com"
    assert s.is_production is False
    assert s.cors_origin_list == ["http://localhost:8000"]
    assert s.rate_limit_enabled is True
    assert s.invgate_api_prefix == "/api/v1"
    assert s.invgate_client_id == ""
    assert s.llm_cost_per_1k_tokens == 0


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_USER_CONTENT", "true")
    monkeypatch.setenv("CORS_ORIGINS", "a.com,b.com")
    monkeypatch.setenv("TICKETING_PROVIDER", "invgate")
    monkeypatch.setenv("INVGATE_USERNAME", "api")
    monkeypatch.setenv("APPROVAL_TTL_HOURS", "48")
    s = Settings()
    assert s.app_env == "production"
    assert s.port == 9000
    assert s.log_user_content is True
    assert s.cors_origin_list == ["a.com", "b.com"]
    assert s.ticketing_provider == "invgate"
    assert s.approval_ttl_hours == 48
    assert s.is_production is True


def test_get_settings_cached() -> None:
    assert get_settings() is get_settings()

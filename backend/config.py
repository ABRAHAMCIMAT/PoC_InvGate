"""Configuración centralizada por entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))  # nosec B104
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_user_content: bool = field(
        default_factory=lambda: os.getenv("LOG_USER_CONTENT", "false").lower() == "true"
    )
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "backend/data"))

    # Seguridad (Fase 5)
    api_keys: str = field(default_factory=lambda: os.getenv("API_KEYS", ""))
    cors_origins: str = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:8000"))
    rate_limit_max: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_MAX", "60")))
    rate_limit_window: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW", "60")))
    rate_limit_enabled: bool = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    )

    # LLM
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    # Vacío: se usa la URL por defecto del proveedor (Ollama :11434, Jan :1337)
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT", "30")))
    # Costo estimado por 1K tokens (USD) para el dashboard; 0 para modelos locales
    llm_cost_per_1k_tokens: float = field(
        default_factory=lambda: float(os.getenv("LLM_COST_PER_1K_TOKENS", "0"))
    )

    # Ticketing
    ticketing_provider: str = field(default_factory=lambda: os.getenv("TICKETING_PROVIDER", "demo"))
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "file"))
    approval_ttl_hours: int = field(default_factory=lambda: int(os.getenv("APPROVAL_TTL_HOURS", "72")))

    # InvGate
    invgate_base_url: str = field(default_factory=lambda: os.getenv("INVGATE_BASE_URL", ""))
    invgate_api_token: str = field(default_factory=lambda: os.getenv("INVGATE_API_TOKEN", ""))
    invgate_username: str = field(default_factory=lambda: os.getenv("INVGATE_USERNAME", "api"))
    invgate_field_map: str = field(default_factory=lambda: os.getenv("INVGATE_FIELD_MAP", ""))
    invgate_value_map: str = field(default_factory=lambda: os.getenv("INVGATE_VALUE_MAP", ""))
    invgate_action_type: str = field(default_factory=lambda: os.getenv("INVGATE_ACTION_TYPE", ""))
    invgate_api_prefix: str = field(default_factory=lambda: os.getenv("INVGATE_API_PREFIX", "/api/v1"))
    # OAuth 2.0 client credentials (alternativa al API token)
    invgate_client_id: str = field(default_factory=lambda: os.getenv("INVGATE_CLIENT_ID", ""))
    invgate_client_secret: str = field(default_factory=lambda: os.getenv("INVGATE_CLIENT_SECRET", ""))
    invgate_oauth_token_url: str = field(default_factory=lambda: os.getenv("INVGATE_OAUTH_TOKEN_URL", ""))
    # Valores por defecto para crear incidentes (JSON), p. ej. {"creator_id": 1, "customer_id": 1}
    invgate_defaults: str = field(default_factory=lambda: os.getenv("INVGATE_DEFAULTS", ""))
    # Usuario InvGate que firma comentarios y aprobaciones del PoC
    invgate_author_id: str = field(default_factory=lambda: os.getenv("INVGATE_AUTHOR_ID", ""))

    # Aprobaciones
    poc_manager_name: str = field(default_factory=lambda: os.getenv("POC_MANAGER_NAME", ""))
    poc_manager_email: str = field(default_factory=lambda: os.getenv("POC_MANAGER_EMAIL", ""))
    poc_manager_invgate_id: str = field(default_factory=lambda: os.getenv("POC_MANAGER_INVGATE_ID", ""))
    # teams (bot proactivo) | webhook (TEAMS_WORKFLOW_URL) | none
    notify_channel: str = field(default_factory=lambda: os.getenv("NOTIFY_CHANNEL", "teams"))

    # Teams
    teams_bot_app_id: str = field(default_factory=lambda: os.getenv("TEAMS_BOT_APP_ID", ""))
    teams_bot_app_password: str = field(default_factory=lambda: os.getenv("TEAMS_BOT_APP_PASSWORD", ""))
    teams_tenant_id: str = field(default_factory=lambda: os.getenv("TEAMS_TENANT_ID", ""))
    teams_service_url: str = field(
        default_factory=lambda: os.getenv("TEAMS_SERVICE_URL", "https://smba.trafficmanager.net/teams/")
    )
    teams_workflow_url: str = field(default_factory=lambda: os.getenv("TEAMS_WORKFLOW_URL", ""))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", ""))

    # Observabilidad
    langfuse_public_key: str = field(default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", ""))
    langfuse_secret_key: str = field(default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", ""))
    langfuse_host: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

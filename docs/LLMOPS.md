# LLMOps

## Modelo

- **Por defecto:** LLM mock determinista (clasificación por palabras clave), sin credenciales.
- **Opcional:** Llama 3.1 8B vía Ollama/Jan (`LLM_BASE_URL`, `LLM_MODEL`).

## Orquestación

- El **Coordinador** orquesta 8 agentes: clasificador, diagnóstico, políticas, ejecución, conocimiento, seguimiento y escalación.
- Cada agente devuelve un resultado con rol, salida y estado (`ok`/`warning`/`error`) para el semáforo.

## Observabilidad

- Telemetría JSONL modelo-agnóstica (`backend/observability/telemetry.py`).
- Redacción de PII (emails y teléfonos) antes de registrar.
- Langfuse opcional (`LANGFUSE_*`).

## Seguridad

- RBAC por API key (roles `user`/`agent`/`admin`).
- Rate limit configurable (`RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`).
- Audit trail append-only con redacción de PII.

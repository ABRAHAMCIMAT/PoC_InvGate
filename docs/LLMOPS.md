# LLMOps

## Modelo

- **Por defecto:** LLM mock determinista (clasificación por palabras clave), sin credenciales.
- **Local:** Llama 3.1 8B vía Ollama (`LLM_PROVIDER=ollama`) o Jan (`LLM_PROVIDER=jan`), con la API `/v1/chat/completions` compatible con OpenAI. `LLM_BASE_URL` y `LLM_MODEL` son opcionales.
- **Degradación elegante:** si el modelo no responde o devuelve algo inválido, el clasificador usa el mock y su agente pasa a amarillo («LLM no disponible»). El evento cuenta en `degradaciones_llm` del dashboard.

## Orquestación

El **Coordinador** ejecuta 7 agentes en orden, y cada uno devuelve rol, salida, estado y latencia:

| Agente | Qué hace | Amarillo / rojo cuando |
|---|---|---|
| Clasificador | Categoría, prioridad y si requiere aprobación (LLM) | Respuesta no reconocida o LLM degradado |
| Diagnóstico | Causa raíz probable (reglas, o LLM si hay uno real) | No se pudo determinar la causa |
| Políticas | Aplica la política de aprobación (el software siempre se aprueba) | — |
| Ejecución | Crea el ticket y, si aplica, abre la aprobación y avisa al manager | Espera aprobación / falla la creación o la aprobación (rojo) |
| Conocimiento | Busca un artículo en `backend/agents/kb_articles.json` y lo comenta en el ticket | No hay artículo aplicable |
| Seguimiento | Programa el seguimiento | Espera aprobación / no hay ticket (rojo) |
| Escalación | Nivel 2 (prioridad alta o fallo) o Nivel 3 (crítica) | Hubo escalación |

`POST /api/chat/stream` emite un evento SSE en cuanto termina cada agente.

## Observabilidad

- **Telemetría JSONL** (`DATA_DIR/telemetry.jsonl`): eventos `agent_step`, `chat_completed`, `approval_requested`, `approval_decided`, `rate_limited` y `manual_escalation`.
- **Dashboard** (`/dashboard.html`, datos en `GET /api/metrics?hours=N`):
  - **Negocio/ITSM:** conversaciones, tickets, categorías, prioridades, escalaciones por nivel y aprobaciones.
  - **Rendimiento:** latencia p50/p95/máx del chat y por agente, y peticiones limitadas.
  - **Costos:** llamadas al LLM, tokens y costo estimado (`LLM_COST_PER_1K_TOKENS`) por modelo.
  - **Orquestación:** estados ok/warning/error por agente y degradaciones del LLM.
- **Langfuse (opcional):** con `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY`, cada conversación se envía como una traza, con un *span* por agente y una *generation* por llamada al LLM. El texto del usuario solo se envía (con PII redactada) si `LOG_USER_CONTENT=true`.

## Seguridad

- RBAC por API key (roles `user`/`agent`/`admin`). Sin `API_KEYS`, la API queda abierta solo fuera de producción.
- Rate limit con ventana deslizante por API key o IP (`RATE_LIMIT_MAX` por `RATE_LIMIT_WINDOW` segundos). Responde 429 con `Retry-After`.
- Audit trail append-only y encadenado por hash. `GET /api/audit/verify` detecta ediciones o borrados.
- Redacción de emails y teléfonos en telemetría, auditoría y Langfuse.

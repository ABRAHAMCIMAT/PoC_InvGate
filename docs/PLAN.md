# Plan incremental — PoC Valkiria InvGate

## Objetivo

Replicar el PoC multiagente de `valkiria_servitonic` sustituyendo ServiceTonic por **InvGate Service Management**, manteniendo la arquitectura multiagente, las aprobaciones en Microsoft Teams, la calidad (cobertura >90 %, Ruff/Mypy/Bandit/SonarCloud) y la observabilidad. Todo se desarrolla en `ABRAHAMCIMAT/PoC_InvGate`.

## Diferencias clave ServiceTonic → InvGate

- **Auth:** InvGate usa API token (usuario `api` + token) u OAuth 2.0 client credentials, no usuario/contraseña + project ID.
- **Endpoints:** `/incident` (GET/PUT/POST), `/incident.comment`, `/incident.approval` + `accept/reject/cancel/add_voter`, `/incident.custom_approval`, `/incident.reassign`, `/incident.cancel`, `/incident.reopen`, catálogos `/incident.attributes.*`, `/categories`, `/users`, `/helpdesks`.
- **Aprobaciones:** InvGate tiene aprobaciones nativas (predefinidas y espontáneas) con votos y notas; el PoC las aprovechará en lugar de un mecanismo propio.

---

## Fase 0 — Fundaciones y esqueleto ✅

**Objetivo:** Repositorio funcional con CI y estructura base.

- Estructura: `backend/`, `frontend/`, `scripts/`, `tests/`, `bruno/`, `docs/`, `infra/`.
- `README.md`, `.gitignore`, `.env.example`, `pyproject.toml` (Ruff, Mypy, pytest, cobertura >90 %), `Dockerfile`, `docker-compose.yml`.
- `backend/config.py` centralizado con variables InvGate (`INVGATE_BASE_URL`, `INVGATE_API_TOKEN`, `INVGATE_USERNAME`, `INVGATE_FIELD_MAP`, `INVGATE_VALUE_MAP`).
- `GET /api/health` público.
- CI (`.github/workflows/ci.yml`): lint, tipos, tests, Bandit, pip-audit, build Docker.
- **Criterio de aceptación:** `make local-up` levanta el API y pasa healthcheck; CI verde.

## Fase 1 — Adaptador InvGate (núcleo) ✅

**Objetivo:** Cliente de API InvGate con CRUD de tickets y catálogos.

- Cliente HTTP con auth por token (y soporte OAuth2 opcional), reintentos con backoff, degradación elegante.
- Crear, consultar y actualizar incidentes (`POST/PUT/GET /incident`).
- Comentarios (`GET/POST /incident.comment`).
- Catálogos: prioridades, estados, tipos, fuentes, categorías, helpdesks, usuarios (`/incident.attributes.*`, `/categories`, `/helpdesks`, `/users`).
- Mapeo de campos y valores (`INVGATE_FIELD_MAP`, `INVGATE_VALUE_MAP`), con `TICKETING_PROVIDER=demo|simulated|invgate`.
- Tests unitarios con mock del cliente.
- **Criterio de aceptación:** crear/consultar/actualizar/comentar un ticket real en InvGate por API; 100 % de los tests del adaptador en verde.

## Fase 2 — Agentes multiagente ✅

**Objetivo:** Flujo conversacional completo con los 8 agentes.

- Coordinador (orquestador), Clasificador (triaje, categoría, prioridad SLA), Diagnóstico (causa raíz), Políticas (¿requiere aprobación?), Ejecución (autoservicio), Conocimiento, Seguimiento (método del Coordinador), Escalación (automática a Nivel 2/3).
- Integración de los agentes con el adaptador InvGate.
- LLM mock determinista por defecto; Llama 3.1 8B vía Ollama/Jan opcional.
- Endpoints `/api/chat`, `/api/chat/stream` (SSE por agente), `/api/conversations`, `/api/escalate`.
- **Criterio de aceptación:** un caso de extremo a extremo (solicitud → clasificación → creación de ticket en InvGate → seguimiento) con mock; semáforo de agentes funcionando.

## Fase 3 — Aprobaciones InvGate + Microsoft Teams ✅ (código)

**Objetivo:** Aprobaciones interactivas usando las nativas de InvGate.

- Disparar aprobación (`/incident.custom_approval` o predefinida) cuando el Agente de Políticas lo decide.
- Adaptive Card en Teams al manager: Aprobar/Rechazar con observaciones; solo el manager decide; segundo clic ignorado.
- Sincronizar la decisión con InvGate (`/incident.approval.accept` / `.reject` con `user_id` y `note`).
- Bot de Teams (Bot Framework), túnel HTTPS temporal, `NOTIFY_CHANNEL=teams`.
- **Criterio de aceptación:** el manager aprueba/rechaza desde Teams y el ticket en InvGate refleja la decisión; segundo clic sin efecto.

## Fase 4 — Frontend y chat web ✅

**Objetivo:** Interfaz de chat web (estilo Jan).

- `frontend/index.html`: chat, tarjeta de estado del ticket con observaciones del manager, semáforo de agentes (🟢/🟡/🔴).
- **Criterio de aceptación:** el solicitante conversa, ve el estado del ticket y las observaciones.

## Fase 5 — Seguridad y observabilidad ✅

**Objetivo:** Control total y capa de seguridad.

- RBAC por API key (roles `user`/`agent`/`admin`), rate limit, redacción de PII, audit trail append-only.
- Telemetría JSONL modelo-agnóstica, dashboard de 4 dimensiones (negocio/ITSM, rendimiento, costos, orquestación), Langfuse opcional.
- **Criterio de aceptación:** dashboard poblado con telemetría de demo; endpoints protegidos por rol.

## Fase 6 — Calidad, pruebas y cierre 🔄

**Objetivo:** Cerrar el PoC con 10/10 criterios.

- pytest unit/integration/e2e con cobertura >90 %; Ruff, Mypy, Bandit, pip-audit, SonarCloud.
- Colección de Bruno para pruebas de API (incluida la de InvGate, solo lectura para no consumir cuota).
- Documentación C4 y LLMOps en español; `docs/POC_LOCAL.md`, `docs/ESTADO_DESARROLLO.md`, `docs/POC_EVIDENCIAS.md`.
- **Criterio de aceptación:** 10/10 criterios cumplidos en real (tickets reales en InvGate, bot de Teams en tenant, calidad en verde).

---

## Nota de acceso

El adaptador de InvGate se construye contra la API pública documentada. La validación "en real" de las Fases 1 y 3 requiere la URL de instancia y el token de una instancia InvGate real (configurables en `.env`). El resto del PoC corre con `TICKETING_PROVIDER=demo|simulated` y LLM mock sin credenciales.

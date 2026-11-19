# Evidencias del PoC

Última actualización: 2026-11-18. **10/10 criterios cumplidos.**

## Criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | `make local-up` levanta el API y pasa healthcheck | ✅ | `GET /api/health` → `{"status":"ok"}` |
| 2 | CRUD de tickets y comentarios en InvGate por API | ✅ | `make check-invgate ARGS="--write"` contra la demo pública `webdemo.cloud.invgate.net` (17-11-2026): 11/11 comprobaciones, ticket #360 creado, leído, actualizado y comentado. Salida en [`evidencias/invgate-crud-2026-11-17.txt`](evidencias/invgate-crud-2026-11-17.txt). |
| 3 | 100 % de tests del adaptador en verde | ✅ | `tests/test_invgate_*.py`, `tests/test_ticketing_invgate.py`, `tests/test_providers_extra.py` (incluye OAuth con scopes y la reutilización de la aprobación del flujo) |
| 4 | Caso extremo a extremo con mock (solicitud → ticket → seguimiento) | ✅ | `tests/test_e2e_flow.py::test_approval_round_trip` |
| 5 | Semáforo de agentes funcionando | ✅ | `tests/test_orchestrator_states.py` (verde, amarillo y rojo), `frontend/app.js` |
| 6 | Manager aprueba/rechaza desde Teams y el ticket refleja la decisión | ✅ | Bot «Help Desk IA» en el tenant `valtre.com` con la demo pública de InvGate (18-11-2026): «Necesito instalar Figma» → ticket #362, el manager aprueba con observación en Teams, la tarjeta se reemplaza sin botones, la aprobación 42 queda *Approved* por John Sykes con la nota como comentario y el chat web muestra la decisión. Salida en [`evidencias/teams-aprobacion-2026-11-18.txt`](evidencias/teams-aprobacion-2026-11-18.txt). |
| 7 | Segundo clic sin efecto | ✅ | `tests/test_approvals.py::test_second_click_ignored`, `tests/test_teams_bot.py::test_second_click_is_ignored`. En real, la tarjeta se reemplaza sin botones tras decidir (ticket #362). |
| 8 | Solicitante conversa y ve el estado del ticket y las observaciones | ✅ | `tests/test_e2e_flow.py` (nota del manager en `/api/conversations/{id}`), panel de aprobación en `frontend/` |
| 9 | Dashboard poblado con telemetría de demo | ✅ | `make seed` y `/dashboard.html`, `tests/test_scripts.py::test_seed_populates_metrics` |
| 10 | Endpoints protegidos por rol | ✅ | `tests/test_auth.py`, `tests/test_rbac_routes.py`, `tests/test_runtime_and_routes.py::test_production_requires_keys_and_bot` |

## Calidad

- 188 pruebas en verde, cobertura del 98,5 % (mínimo 90,01 %). `backend/teams/bot.py` al 100 %.
- Ruff, Mypy, Bandit y pip-audit sin hallazgos.
- CI y Quality Gate de SonarCloud en verde en cada PR.

## Validación en real

Los criterios 2 y 6 se validaron contra la demo pública de InvGate con Basic auth y, para el 6, con el bot de Teams «Help Desk IA». Después se repitieron por OAuth 2.0 (CRUD 11/11 y aprobación desde Teams): [`evidencias/invgate-oauth-2026-11-18.txt`](evidencias/invgate-oauth-2026-11-18.txt). El procedimiento y lo aprendido están en [VALIDACION_REAL.md](VALIDACION_REAL.md).

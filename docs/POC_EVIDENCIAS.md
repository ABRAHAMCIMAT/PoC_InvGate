# Evidencias del PoC

## Criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | `make local-up` levanta el API y pasa healthcheck | ✅ | `GET /api/health` → `{"status":"ok"}` |
| 2 | CRUD de tickets y comentarios en InvGate por API | ⏳ Código listo | `tests/test_invgate_client.py`, `tests/test_client_extra.py`. Falta ejecutar `make check-invgate ARGS="--write"` en una instancia real. |
| 3 | 100 % de tests del adaptador en verde | ✅ | `tests/test_invgate_*.py`, `tests/test_providers_extra.py` |
| 4 | Caso extremo a extremo con mock (solicitud → ticket → seguimiento) | ✅ | `tests/test_e2e_flow.py::test_approval_round_trip` |
| 5 | Semáforo de agentes funcionando | ✅ | `tests/test_orchestrator_states.py` (verde, amarillo y rojo), `frontend/app.js` |
| 6 | Manager aprueba/rechaza desde Teams y el ticket refleja la decisión | ⏳ Código listo | `tests/test_teams_bot.py` (bot, tarjeta y notificación proactiva con el adaptador de pruebas). Falta el tenant real. |
| 7 | Segundo clic sin efecto | ✅ | `tests/test_approvals.py::test_second_click_ignored`, `tests/test_teams_bot.py::test_second_click_is_ignored` |
| 8 | Solicitante conversa y ve el estado del ticket y las observaciones | ✅ | `tests/test_e2e_flow.py` (nota del manager en `/api/conversations/{id}`), panel de aprobación en `frontend/` |
| 9 | Dashboard poblado con telemetría de demo | ✅ | `make seed` y `/dashboard.html`, `tests/test_scripts.py::test_seed_populates_metrics` |
| 10 | Endpoints protegidos por rol | ✅ | `tests/test_auth.py`, `tests/test_rbac_routes.py`, `tests/test_runtime_and_routes.py::test_production_requires_keys_and_bot` |

## Calidad (local, Python 3.12)

- 170 pruebas en verde, cobertura de 98.16 % (mínimo 90.01 %).
- Ruff, Mypy y Bandit sin hallazgos.

## Nota

Los criterios 2 y 6 necesitan credenciales reales de InvGate y de un tenant de Microsoft Teams. El procedimiento está en [VALIDACION_REAL.md](VALIDACION_REAL.md).

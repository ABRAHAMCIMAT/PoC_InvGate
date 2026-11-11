# Evidencias del PoC

## Criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | `make local-up` levanta el API y pasa healthcheck | ✅ | `GET /api/health` → `{"status":"ok"}` |
| 2 | CRUD de tickets y comentarios en InvGate por API | ⏳ | Requiere instancia InvGate real |
| 3 | 100 % de tests del adaptador en verde | ✅ | `tests/test_invgate_*.py` |
| 4 | Caso extremo a extremo con mock (solicitud → ticket → seguimiento) | ✅ | `tests/test_agents.py`, `tests/test_chat_routes.py` |
| 5 | Semáforo de agentes funcionando | ✅ | `frontend/app.js` |
| 6 | Manager aprueba/rechaza desde Teams y el ticket refleja la decisión | ⏳ | Requiere tenant de Teams real |
| 7 | Segundo clic sin efecto | ✅ | `tests/test_approvals.py::test_second_click_ignored` |
| 8 | Solicitante conversa y ve estado del ticket | ✅ | `frontend/` |
| 9 | Dashboard poblado con telemetría de demo | ✅ | `backend/observability/telemetry.py` |
| 10 | Endpoints protegidos por rol | ✅ | `tests/test_auth.py` |

## Nota

Los criterios 2 y 6 requieren credenciales reales de InvGate y de un tenant de Microsoft Teams; el resto del PoC corre en modo demo/simulado sin credenciales.

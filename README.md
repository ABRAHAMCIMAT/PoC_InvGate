# Valkiria InvGate PoC

Sistema multiagente conversacional para **InvGate Service Management**, replicando el PoC de `valkiria_servitonic` (ServiceTonic) sobre InvGate.

## Objetivo

Mantener la arquitectura multiagente, las aprobaciones en Microsoft Teams, la calidad (cobertura >90 %, Ruff/Mypy/Bandit/SonarCloud) y la observabilidad, sustituyendo el ticketing por **InvGate Service Management**.

## Estado

- **Fase 0 — Fundaciones y esqueleto:** ✅ completada (CI, estructura, healthcheck).
- **Fase 1 — Adaptador InvGate:** ✅ completada (cliente, mapeo, proveedores demo/simulated/invgate).
- **Fase 2 — Agentes multiagente:** ✅ completada (8 agentes, LLM mock, endpoints de chat).
- **Fase 3 — Aprobaciones + Teams:** ✅ completada (código; validación real pendiente).
- **Fase 4 — Frontend web:** ✅ completada (chat, semáforo de agentes, tarjeta de ticket).
- **Fase 5 — Seguridad y observabilidad:** ✅ completada (RBAC, rate limit, PII, telemetría).
- **Fase 6 — Calidad y cierre:** 🔄 en curso (docs y colección de Bruno listas).

## Estructura

```
backend/     API FastAPI y lógica
frontend/    Chat web (Fase 4)
scripts/     Utilidades
bruno/       Colección de pruebas de API
infra/       Despliegue
backend/data Datos locales (demo)
```

## Inicio rápido

```bash
make install
make local-up
make api-test
```

## Configuración

Copia `.env.example` a `.env` y ajusta las variables. El PoC corre por defecto con `TICKETING_PROVIDER=demo` y LLM mock, sin credenciales. Para InvGate real, configura `INVGATE_BASE_URL` e `INVGATE_API_TOKEN`.

## Calidad

```bash
make lint
make typecheck
make coverage
```

## Documentación

- Plan incremental: [`docs/PLAN.md`](docs/PLAN.md)
- Ejecución local: [`docs/POC_LOCAL.md`](docs/POC_LOCAL.md)
- Estado del desarrollo: [`docs/ESTADO_DESARROLLO.md`](docs/ESTADO_DESARROLLO.md)
- Evidencias: [`docs/POC_EVIDENCIAS.md`](docs/POC_EVIDENCIAS.md)
- Arquitectura C4: [`docs/ARQUITECTURA_C4.md`](docs/ARQUITECTURA_C4.md)
- LLMOps: [`docs/LLMOPS.md`](docs/LLMOPS.md)

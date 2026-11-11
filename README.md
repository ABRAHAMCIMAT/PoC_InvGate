# Valkiria InvGate PoC

Sistema multiagente conversacional para **InvGate Service Management**, replicando el PoC de `valkiria_servitonic` (ServiceTonic) sobre InvGate.

## Objetivo

Mantener la arquitectura multiagente, las aprobaciones en Microsoft Teams, la calidad (cobertura >90 %, Ruff/Mypy/Bandit/SonarCloud) y la observabilidad, sustituyendo el ticketing por **InvGate Service Management**.

## Estado

- **Fase 0 — Fundaciones y esqueleto:** ✅ completada (CI, estructura, healthcheck).
- **Fase 1 — Adaptador InvGate:** en desarrollo.
- Fases 2–6: pendientes (ver `docs/PLAN.md`).

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

Plan detallado: [`docs/PLAN.md`](docs/PLAN.md).

# Valkiria InvGate PoC

Sistema multiagente conversacional para **InvGate Service Management**, replicando el PoC de `valkiria_servitonic` (ServiceTonic) sobre InvGate.

## Objetivo

Mantener la arquitectura multiagente, las aprobaciones en Microsoft Teams, la calidad (cobertura >90 %, Ruff/Mypy/Bandit/SonarCloud) y la observabilidad, sustituyendo el ticketing por **InvGate Service Management**.

## Estado

- **Fases 0, 2, 4 y 5:** ✅ completadas.
- **Fase 1 — Adaptador InvGate:** ✅ código completo (API v1, token u OAuth2, aprobaciones nativas). ⏳ Falta validar en una instancia real.
- **Fase 3 — Aprobaciones + Teams:** ✅ código completo (bot proactivo, observaciones, solo vota el manager). ⏳ Falta validar en un tenant real.
- **Fase 6 — Calidad:** ✅ 170 pruebas, 98 % de cobertura, Ruff, Mypy y Bandit en verde. ⏳ SonarCloud necesita el secreto `SONAR_TOKEN`.

Lo pendiente necesita credenciales; los pasos están en [`docs/VALIDACION_REAL.md`](docs/VALIDACION_REAL.md).

## Estructura

```
backend/     API FastAPI, agentes, adaptador InvGate, aprobaciones, Teams y observabilidad
frontend/    Chat web y dashboard (servidos por la API)
scripts/     seed_demo_telemetry (demo del dashboard) y check_invgate (prueba real)
bruno/       Colección de pruebas de API (incluye InvGate en solo lectura)
infra/       Manifiesto de la app de Teams
backend/data Datos locales: telemetría, auditoría, tickets simulados (se crea al arrancar)
```

## Inicio rápido

```bash
make install
make local-up      # chat en http://127.0.0.1:8000/ y dashboard en /dashboard.html
make seed          # poblar el dashboard con conversaciones de demo
```

## Configuración

Copia `.env.example` a `.env` y ajusta las variables. El PoC corre por defecto con `TICKETING_PROVIDER=demo` y LLM mock, sin credenciales. Para InvGate real, configura `INVGATE_BASE_URL` y `INVGATE_API_TOKEN` (o `INVGATE_CLIENT_ID`/`INVGATE_CLIENT_SECRET`) y sigue [`docs/VALIDACION_REAL.md`](docs/VALIDACION_REAL.md).

## Calidad

```bash
make lint
make typecheck
make security
make coverage
```

### Dependencias

Las versiones se fijan en `requirements*.txt`, y la instalación usa los locks con hash (`requirements.lock` para la imagen, `requirements-dev.lock` para CI y desarrollo, `requirements-security.lock` para Bandit). En CI y en Docker solo se instalan wheels (`--only-binary :all: --require-hashes`), así que no se ejecuta código de instalación de terceros. Tras cambiar una versión, regenera los locks con `make lock` (requiere [uv](https://docs.astral.sh/uv/)).

## Documentación

- Plan incremental: [`docs/PLAN.md`](docs/PLAN.md)
- Ejecución local: [`docs/POC_LOCAL.md`](docs/POC_LOCAL.md)
- Estado del desarrollo: [`docs/ESTADO_DESARROLLO.md`](docs/ESTADO_DESARROLLO.md)
- Evidencias: [`docs/POC_EVIDENCIAS.md`](docs/POC_EVIDENCIAS.md)
- Arquitectura C4: [`docs/ARQUITECTURA_C4.md`](docs/ARQUITECTURA_C4.md)
- LLMOps: [`docs/LLMOPS.md`](docs/LLMOPS.md)
- Validación en real (InvGate, Teams, SonarCloud): [`docs/VALIDACION_REAL.md`](docs/VALIDACION_REAL.md)

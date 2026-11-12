# Estado del desarrollo

Última actualización: 2026-11-12

## Fases

| Fase | Descripción | Estado |
|------|-------------|--------|
| 0 | Fundaciones y esqueleto (CI, estructura, healthcheck) | ✅ Completada |
| 1 | Adaptador InvGate (API v1, token y OAuth2, mapeo, aprobaciones nativas) | ✅ Código completo · ⏳ validación en instancia real |
| 2 | Agentes multiagente, LLM mock y Ollama/Jan, streaming SSE | ✅ Completada |
| 3 | Aprobaciones InvGate y bot de Teams (proactivo, con observaciones) | ✅ Código completo · ⏳ validación en tenant real |
| 4 | Frontend web (chat, semáforo, decisión y observaciones del manager) | ✅ Completada |
| 5 | Seguridad (RBAC, rate limit, PII, auditoría) y observabilidad (dashboard, Langfuse) | ✅ Completada |
| 6 | Calidad, pruebas y cierre | ✅ Calidad en verde · ⏳ SonarCloud necesita `SONAR_TOKEN` |

## Cierre de las observaciones de la revisión del 12 de noviembre

| Observación | Resolución |
|---|---|
| El workflow de SonarCloud fallaba en `main` | Era YAML inválido (`--only-binary :all:` sin comillas). Se corrigió. Sin `SONAR_TOKEN`, el paso se omite con un aviso en lugar de fallar. |
| Las aprobaciones no estaban conectadas | Ejecución abre la aprobación al crear el ticket. El servicio notifica al manager por bot de Teams o webhook. `/api/messages` recibe a Teams. InvGate usa `/incident.spontaneous_approval` y `/incident.approval.accept\|reject`. |
| No había límite de peticiones | Middleware con ventana deslizante por API key o IP, 429 con `Retry-After`. |
| Las rutas de InvGate no coincidían con la API | El cliente usa las rutas con punto y `id`/`request_id` como parámetros, según la documentación pública. |
| Telemetría, auditoría y mapeo sin usar | Los tres están conectados. La auditoría ahora se encadena por hash. Se añadieron `GET /api/metrics` y `/dashboard.html` con las 4 dimensiones. |
| Faltaban Ollama, OAuth2 y Langfuse | Cliente OpenAI-compatible con respaldo al mock, OAuth2 client credentials con caché del token, y exportador a Langfuse. |
| Diagnóstico y Conocimiento devolvían texto fijo | Diagnóstico usa reglas o el LLM, y Conocimiento busca en una base de 7 artículos. Los agentes reportan amarillo y rojo reales. |
| `make lint` fallaba y el bot tenía 22.7 % de cobertura | Se añadieron `scripts/` e `infra/`. El bot tiene ahora 89 % de cobertura, y el total es 98 %. |

## Pendiente (requiere credenciales; ver [VALIDACION_REAL.md](VALIDACION_REAL.md))

- **InvGate:** ejecutar `make check-invgate ARGS="--write"` en una instancia y ajustar `INVGATE_DEFAULTS` e `INVGATE_VALUE_MAP` a sus ids.
- **Teams:** registrar el Azure Bot, publicar el túnel HTTPS y subir la app.
- **SonarCloud:** crear el secreto `SONAR_TOKEN` en GitHub.

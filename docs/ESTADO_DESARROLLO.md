# Estado del desarrollo

Última actualización: 2026-11-18

**Resumen:** PoC completo. Los 10 criterios de aceptación se cumplen y los 56 elementos del plan están hechos. InvGate y Teams se validaron con credenciales reales.

## Fases

| Fase | Descripción | Estado |
|------|-------------|--------|
| 0 | Fundaciones y esqueleto (CI, estructura, healthcheck) | ✅ Completada |
| 1 | Adaptador InvGate (API v1, Basic auth y OAuth 2.0, mapeo, aprobaciones nativas) | ✅ Completada · validada en la demo pública |
| 2 | Agentes multiagente, LLM mock y Ollama/Jan, streaming SSE | ✅ Completada |
| 3 | Aprobaciones InvGate y bot de Teams (proactivo, con observaciones) | ✅ Completada · validada con «Help Desk IA» |
| 4 | Frontend web (chat, semáforo, decisión y observaciones del manager) | ✅ Completada |
| 5 | Seguridad (RBAC, rate limit, PII, auditoría) y observabilidad (dashboard, Langfuse) | ✅ Completada |
| 6 | Calidad, pruebas, documentación y cierre | ✅ Completada · CI y SonarCloud en verde |

## Calidad

| Control | Resultado |
|---|---|
| Pruebas | 188 en verde |
| Cobertura | 98,5 % (mínimo 90,01 %). `teams/bot.py` y `teams/adaptive_card.py` al 100 % |
| Ruff, Mypy, Bandit, pip-audit | Sin hallazgos |
| SonarCloud | Quality Gate aprobado, escaneo desde CI con `SONAR_TOKEN` |
| Dependencias | Locks con hash, solo wheels |

## Validación en real (17 y 18 de noviembre de 2026)

| Qué | Resultado | Evidencia |
|---|---|---|
| CRUD de InvGate con Basic auth | 11/11 contra `webdemo.cloud.invgate.net` | [`evidencias/invgate-crud-2026-11-17.txt`](evidencias/invgate-crud-2026-11-17.txt) |
| Aprobación desde Teams | Bot «Help Desk IA» en el tenant `valtre.com`: aprobación con observación registrada en InvGate | [`evidencias/teams-aprobacion-2026-11-18.txt`](evidencias/teams-aprobacion-2026-11-18.txt) |
| InvGate con OAuth 2.0 | CRUD 11/11 y aprobación desde Teams | [`evidencias/invgate-oauth-2026-11-18.txt`](evidencias/invgate-oauth-2026-11-18.txt) |

## Cambios surgidos de la validación en real

| Hallazgo | Cambio |
|---|---|
| En la demo, la categoría *New Software* crea una aprobación por flujo, e InvGate rechaza otra espontánea con 409 | El proveedor reutiliza la aprobación pendiente y solo crea una espontánea si no hay ninguna |
| El token OAuth salía sin permisos (`scopes: []`) y la API daba 403 | El cliente pide los permisos en el parámetro `scope` (`DEFAULT_OAUTH_SCOPES`, configurable con `INVGATE_OAUTH_SCOPES`) |
| Los botones de tarjetas de versiones anteriores del bot daban error 501 en Teams | El bot las sustituye por «Tarjeta no vigente», sin botones |
| `PUT /incident` no cambia el estado del ticket | Documentado: el estado lo gestiona el flujo de InvGate |
| Los túneles rápidos de Cloudflare cambian de URL y caducan | Documentado en el [Manual técnico](MANUAL_TECNICO.md#52-túnel-https-y-messaging-endpoint) |

## Cierre de las observaciones de la revisión del 12 de noviembre

| Observación | Resolución |
|---|---|
| El workflow de SonarCloud fallaba en `main` | Se corrigió el YAML y se migró a `sonarqube-scan-action` (Java 21). `SONAR_TOKEN` está configurado y el escaneo importa la cobertura. |
| Las aprobaciones no estaban conectadas | Ejecución abre la aprobación al crear el ticket. El servicio avisa al manager por el bot de Teams o por webhook. `/api/messages` recibe a Teams. InvGate usa `/incident.spontaneous_approval` y `/incident.approval.accept\|reject`. |
| No había límite de peticiones | Middleware con ventana deslizante por API key o IP, que responde 429 con `Retry-After`. |
| Las rutas de InvGate no coincidían con la API | El cliente usa las rutas con punto y `id`/`request_id` como parámetros. Se confirmó en la demo pública. |
| Telemetría, auditoría y mapeo sin usar | Los tres están conectados. La auditoría se encadena por hash. Se añadieron `GET /api/metrics` y `/dashboard.html`. |
| Faltaban Ollama, OAuth2 y Langfuse | Cliente compatible con OpenAI con respaldo al mock, OAuth2 client credentials con caché del token y scopes, y exportador a Langfuse. |
| Diagnóstico y Conocimiento devolvían texto fijo | Diagnóstico usa reglas o el LLM, y Conocimiento busca en una base de 7 artículos. Los agentes reportan amarillo y rojo reales. |
| SonarCloud: puerta de calidad en rojo en el PR #3 | Se corrigieron los 34 issues del PR y los 18 de `main`. |
| `make lint` fallaba y el bot tenía 22,7 % de cobertura | Se añadieron `scripts/` e `infra/` al lint. El bot tiene ahora el 100 % de cobertura. |

## Mejoras opcionales (fuera del alcance del PoC)

- Túnel con dominio fijo (túnel con nombre de Cloudflare o ngrok) para no actualizar el *messaging endpoint* en cada arranque.
- Que `make local-up` cargue `.env` automáticamente.
- Una instancia propia de InvGate en lugar de la demo pública, que se reinicia y borra credenciales y tickets.

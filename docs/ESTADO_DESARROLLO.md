# Estado del desarrollo

Última actualización: 2026-11-11

## Fases

| Fase | Descripción | Estado |
|------|-------------|--------|
| 0 | Fundaciones y esqueleto (CI, estructura, healthcheck) | ✅ Completada |
| 1 | Adaptador InvGate (cliente, mapeo, proveedores) | ✅ Completada |
| 2 | Agentes multiagente + LLM mock + endpoints de chat | ✅ Completada |
| 3 | Aprobaciones InvGate + bot de Teams (Adaptive Cards) | ✅ Completada (código) |
| 4 | Frontend web de chat | ✅ Completada |
| 5 | Seguridad (RBAC, rate limit, PII) y observabilidad | ✅ Completada |
| 6 | Calidad, pruebas y cierre | 🔄 En curso |

## Pendiente para validación "en real"

- **Fase 1:** crear/consultar/actualizar/comentar un ticket real en una instancia InvGate (requiere `INVGATE_BASE_URL` e `INVGATE_API_TOKEN`).
- **Fase 3:** bot de Teams en un tenant real (requiere credenciales del bot y túnel HTTPS).
- **Fase 6:** CI verde con cobertura >90 % y SonarCloud.

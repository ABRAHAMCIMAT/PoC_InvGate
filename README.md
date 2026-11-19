# Valkiria InvGate PoC

Asistente de mesa de ayuda **multiagente** para **InvGate Service Management**: el empleado describe su problema en un chat, el PoC crea y sigue el ticket en InvGate y, si hace falta, pide la aprobación del manager en **Microsoft Teams**. Replica el PoC de `valkiria_servitonic` (ServiceTonic) sobre InvGate.

## Qué hace el PoC

**Para el solicitante (chat web)**
- Conversa en lenguaje natural («Necesito instalar Figma», «Olvidé mi contraseña»).
- Clasifica la solicitud por **categoría** (acceso, software, hardware, infraestructura o general) y **prioridad** (baja a crítica).
- **Crea el ticket en InvGate** y le añade un comentario con el artículo de la base de conocimiento que aplique.
- Muestra un **semáforo en vivo** con los 8 agentes (🟢 🟡 🔴) mientras trabajan.
- Si hace falta aprobación, muestra la **decisión y las observaciones del manager** en cuanto las da.

**Para el manager (Microsoft Teams)**
- Recibe una **tarjeta interactiva** del bot con **Aprobar** y **Rechazar** y un campo de observaciones.
- Su decisión se registra en la **aprobación nativa de InvGate**, y la observación como comentario del ticket.
- Solo el manager asignado puede decidir. El **segundo clic no tiene efecto** y la tarjeta se queda sin botones.
- Las aprobaciones **vencen** a las 72 horas, un plazo configurable.

**Para operación (agentes y administradores)**
- **Dashboard** de 4 dimensiones: negocio/ITSM, rendimiento, costos del LLM y orquestación.
- **Escalado** automático a Nivel 2 o 3 según la prioridad o los fallos, y escalado manual por API.
- **Seguridad:** roles por API key (`user`, `agent`, `admin`), límite de peticiones, ocultación de correos y teléfonos, y auditoría encadenada por hash.
- **Observabilidad:** telemetría propia y trazas opcionales en Langfuse.

**Agentes:** Coordinador, Clasificador, Diagnóstico, Políticas, Ejecución, Conocimiento, Seguimiento y Escalación.
**LLM:** mock determinista por defecto, sin credenciales. Opcional: Llama 3.1 8B con Ollama o Jan, con respaldo automático al mock si el modelo no responde.
**InvGate:** API v1 con Basic auth u OAuth 2.0 (con scopes), mapeo configurable de campos e ids, y reutilización de las aprobaciones que crea el flujo de InvGate.

## Estado

**PoC completo: 10/10 criterios de aceptación y 56/56 elementos del plan.**

- InvGate se validó contra la demo pública con **Basic auth y OAuth 2.0**: CRUD de tickets y comentarios, 11/11.
- Teams se validó con el bot **«Help Desk IA»**: aprobación con observación, de punta a punta.
- **188 pruebas**, **98,5 %** de cobertura, y Ruff, Mypy, Bandit, pip-audit y el Quality Gate de SonarCloud en verde.

El detalle está en [`docs/ESTADO_DESARROLLO.md`](docs/ESTADO_DESARROLLO.md) y las pruebas en [`docs/POC_EVIDENCIAS.md`](docs/POC_EVIDENCIAS.md).

## Inicio rápido

```bash
make install
make local-up      # chat en http://127.0.0.1:8000/ y dashboard en /dashboard.html
make seed          # poblar el dashboard con conversaciones de demo
```

Sin configuración, el PoC funciona con tickets en memoria y el LLM mock. Para InvGate y Teams, copia `.env.example` a `.env` y sigue el [Manual técnico](docs/MANUAL_TECNICO.md). Con un `.env`, arranca con `uvicorn backend.server:app --port 8000 --env-file .env`, porque `make local-up` no lo lee.

## Estructura

```
backend/     API FastAPI, agentes, adaptador InvGate, aprobaciones, Teams, seguridad y observabilidad
frontend/    Chat web y dashboard (servidos por la API)
scripts/     seed_demo_telemetry (demo del dashboard) y check_invgate (prueba contra InvGate)
tests/       Pruebas unitarias, de integración y extremo a extremo
bruno/       Colección de pruebas de API (incluye InvGate en solo lectura)
infra/       Manifiesto de la app de Teams
docs/        Plan, manuales, arquitectura, evidencias y validación en real
```

## Calidad

```bash
make lint          # ruff
make typecheck     # mypy
make security      # bandit
make coverage      # pytest, mínimo 90.01 %
```

Las dependencias se instalan desde locks con hash y solo wheels (`requirements*.lock`). Tras cambiar una versión, regenera los locks con `make lock`, que requiere [uv](https://docs.astral.sh/uv/).

## Documentación

| Documento | Para qué |
|---|---|
| [Manual de usuario](docs/MANUAL_USUARIO.md) | Uso del chat, de la aprobación en Teams y del dashboard |
| [Manual técnico](docs/MANUAL_TECNICO.md) | Instalación, configuración, mantenimiento y soporte |
| [Plan incremental](docs/PLAN.md) | Fases y criterios del PoC |
| [Ejecución local](docs/POC_LOCAL.md) | Arranque rápido y pruebas por API |
| [Estado del desarrollo](docs/ESTADO_DESARROLLO.md) | Avance por fase y decisiones |
| [Evidencias](docs/POC_EVIDENCIAS.md) | Criterios de aceptación y su prueba |
| [Arquitectura C4](docs/ARQUITECTURA_C4.md) | Contexto, contenedores, componentes y flujo |
| [LLMOps](docs/LLMOPS.md) | Modelo, agentes, observabilidad y seguridad |
| [Validación en real](docs/VALIDACION_REAL.md) | InvGate, Teams y SonarCloud con credenciales reales |

# Arquitectura C4

## Nivel 1 — Contexto

El **solicitante** conversa con el **sistema Valkiria InvGate PoC**, que gestiona tickets en **InvGate Service Management** y notifica aprobaciones al **manager** vía **Microsoft Teams**.

## Nivel 2 — Contenedores

- **API (FastAPI):** expone `/api/chat`, `/api/chat/stream`, `/api/conversations`, `/api/escalate`, `/api/health`.
- **Orquestador multiagente:** coordina los 8 agentes (clasificador, diagnóstico, políticas, ejecución, conocimiento, seguimiento, escalación).
- **Adaptador InvGate:** cliente HTTP con auth por token, reintentos y mapeo de campos/valores.
- **Proveedores de ticketing:** `demo` (memoria), `simulated` (para Teams), `invgate` (real).
- **Bot de Teams:** envía Adaptive Cards y procesa Aprobar/Rechazar.
- **Frontend web:** chat con semáforo de agentes y tarjeta de estado del ticket.
- **Observabilidad:** telemetría JSONL modelo-agnóstica.

## Nivel 3 — Componentes (API)

```
backend/
  agents/          Orquestador y modelos de agentes
  approvals/       Servicio de aprobaciones con TTL y decisión única
  invgate/         Cliente HTTP, modelos y mapeo de InvGate
  llmops/          LLM mock y contrato de LLM
  observability/   Telemetría JSONL
  routes/          Endpoints de chat y conversaciones
  security/        RBAC por API key, redacción de PII, audit trail
  teams/           Bot de Teams y Adaptive Cards
  ticketing/       Proveedores demo/simulated/invgate y fábrica
```

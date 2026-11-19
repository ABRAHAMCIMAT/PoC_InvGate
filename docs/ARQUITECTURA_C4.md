# Arquitectura C4

Última actualización: 2026-11-18. Los detalles de instalación y operación están en el [Manual técnico](MANUAL_TECNICO.md).

## Nivel 1 — Contexto

El **solicitante** conversa con el **sistema Valkiria InvGate PoC**. El sistema gestiona tickets en **InvGate Service Management** y pide las aprobaciones al **manager** por **Microsoft Teams**. Las trazas se envían opcionalmente a **Langfuse**, y el LLM puede ser local (**Ollama/Jan**).

## Nivel 2 — Contenedores

- **API (FastAPI):** expone `/api/chat`, `/api/chat/stream` (SSE por agente), `/api/conversations`, `/api/escalate`, `/api/approvals`, `/api/metrics`, `/api/audit/verify`, `/api/messages` (Bot Framework) y `/api/health`. También sirve el frontend.
- **Orquestador multiagente:** el Coordinador ejecuta en orden a Clasificador, Diagnóstico, Políticas, Ejecución, Conocimiento, Seguimiento y Escalación. Cada uno reporta `ok`, `warning` o `error`.
- **Adaptador InvGate:** cliente de la API v1 (`/incident`, `/incident.comment`, `/incident.approval`, `/incident.spontaneous_approval`, `/incident.approval.accept|reject`, catálogos), con Basic auth u OAuth 2.0 (scopes `api.v1.<recurso>:<método>` pedidos en el token), reintentos con backoff y mapeo de campos y valores.
- **Proveedores de ticketing:** `demo` (memoria), `simulated` (archivo JSON) e `invgate` (real, con aprobaciones nativas: reutiliza la que crea el flujo de InvGate o abre una espontánea).
- **Servicio de aprobaciones:** TTL, una sola decisión, solo el manager vota, y sincroniza con el proveedor antes de dar la decisión por buena.
- **Bot de Teams:** guarda la conversación del manager (con su correo), envía la Adaptive Card de forma proactiva, procesa Aprobar/Rechazar con observaciones, reemplaza la tarjeta por el resultado y retira las tarjetas de versiones anteriores.
- **Frontend web:** chat con semáforo en vivo, tarjeta del ticket, decisión y observaciones del manager, y dashboard de 4 dimensiones.
- **Observabilidad:** telemetría JSONL, métricas agregadas, audit trail encadenado por hash y Langfuse opcional.

## Nivel 3 — Componentes (API)

```
backend/
  agents/          Orquestador, diagnóstico, base de conocimiento y modelos
  approvals/       Servicio de aprobaciones con TTL, decisión única y persistencia
  invgate/         Cliente HTTP (token/OAuth2), modelos y mapeo de InvGate
  llmops/          LLM mock, cliente OpenAI-compatible (Ollama/Jan) y respaldo
  observability/   Telemetría JSONL, métricas del dashboard y exportador a Langfuse
  routes/          chat, approvals, admin (métricas y auditoría) y teams
  security/        RBAC por API key, rate limit, redacción de PII y audit trail
  teams/           Bot, Adaptive Cards, notificadores y referencias de conversación
  ticketing/       Proveedores demo/simulated/invgate y fábrica
  runtime.py       Dependencias compartidas por proceso
scripts/           seed_demo_telemetry (demo del dashboard) y check_invgate (prueba real)
infra/             Manifiesto de la app de Teams
```

## Flujo de una solicitud con aprobación

```mermaid
sequenceDiagram
    participant S as Solicitante (web)
    participant A as API / Orquestador
    participant I as InvGate
    participant T as Teams (manager)
    S->>A: POST /api/chat/stream "Necesito instalar Figma"
    A->>I: POST /incident
    A->>I: GET /incident.approval (¿ya la creó el flujo?)
    opt No hay aprobación pendiente
        A->>I: POST /incident.spontaneous_approval
    end
    A-->>T: Adaptive Card (mensaje proactivo)
    A-->>S: eventos SSE por agente + "esperando aprobación"
    T->>A: POST /api/messages (Aprobar + observaciones)
    A->>I: PUT /incident.approval.accept (user_id, note)
    Note over I: InvGate guarda la nota como comentario del ticket
    A-->>T: tarjeta actualizada "Solicitud aprobada"
    S->>A: GET /api/conversations/{id} (sondeo)
    A-->>S: decisión y observaciones del manager
```

## Despliegue del PoC

```mermaid
flowchart LR
    U[Solicitante<br/>navegador] -->|HTTP| API[API FastAPI<br/>localhost:8000]
    M[Manager<br/>Teams] --> BF[Bot Framework<br/>Azure Bot]
    BF -->|HTTPS /api/messages| T[Túnel cloudflared]
    T --> API
    API -->|REST + Basic u OAuth| IG[InvGate<br/>instancia cloud]
    API -->|mensaje proactivo| BF
    API -.->|opcional| L[Ollama / Jan]
    API -.->|opcional| LF[Langfuse]
    API --- D[(DATA_DIR<br/>telemetría, auditoría,<br/>aprobaciones, referencias)]
```

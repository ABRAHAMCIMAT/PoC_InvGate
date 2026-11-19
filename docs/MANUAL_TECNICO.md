# Manual técnico: instalación, mantenimiento y soporte

Para el equipo que instala, opera y da soporte al PoC Valkiria InvGate. El uso funcional está en el [Manual de usuario](MANUAL_USUARIO.md) y la arquitectura en [ARQUITECTURA_C4.md](ARQUITECTURA_C4.md).

## Índice

1. [Componentes](#1-componentes)
2. [Instalación](#2-instalación)
3. [Configuración](#3-configuración)
4. [Conexión con InvGate](#4-conexión-con-invgate)
5. [Conexión con Microsoft Teams](#5-conexión-con-microsoft-teams)
6. [Operación](#6-operación)
7. [Mantenimiento](#7-mantenimiento)
8. [Soporte y resolución de problemas](#8-soporte-y-resolución-de-problemas)

---

## 1. Componentes

| Componente | Qué es | Dónde |
|---|---|---|
| API | FastAPI con el orquestador de 8 agentes. Sirve también el frontend | `backend/server.py` |
| Chat web y dashboard | HTML y JavaScript estáticos | `frontend/` |
| Adaptador InvGate | Cliente de la API v1 con Basic auth u OAuth 2.0 | `backend/invgate/`, `backend/ticketing/` |
| Bot de Teams | Bot Framework: recibe en `/api/messages` y avisa al manager | `backend/teams/` |
| Datos locales | Telemetría, auditoría, aprobaciones y conversaciones de Teams | `DATA_DIR`, por defecto `backend/data/` |
| LLM | Mock por defecto. Opcional: Llama 3.1 8B con Ollama o Jan | `backend/llmops/` |

**Dependencias externas, todas opcionales:**
- Una instancia de InvGate Service Management.
- Un tenant de Microsoft 365 con un Azure Bot.
- Un túnel HTTPS (cloudflared o ngrok).
- Langfuse.
- Ollama o Jan.

Sin ninguna de ellas, el PoC funciona con tickets en memoria y el LLM mock.

---

## 2. Instalación

### 2.1 Requisitos

- Python **3.15**, que es la versión de CI y de la imagen Docker. En desarrollo también funciona con 3.12.
- `git` y `make`.
- Opcional:
  - Docker con Compose.
  - `cloudflared` o `ngrok`, para Teams.
  - [uv](https://docs.astral.sh/uv/), para regenerar los locks.
  - Ollama o Jan.

### 2.2 Instalación local paso a paso

```bash
git clone https://github.com/ABRAHAMCIMAT/PoC_InvGate.git
cd PoC_InvGate
python3 -m venv .venv && source .venv/bin/activate
make install                      # dependencias con hash, solo wheels
cp .env.example .env              # y edita los valores (sección 3)
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --env-file .env
```

- Chat: `http://localhost:8000/`
- Dashboard: `http://localhost:8000/dashboard.html`
- Healthcheck: `make api-test`, que debe devolver `{"status":"ok","service":"valkiria-invgate","version":"0.2.0"}`.

> `make local-up` arranca con `--reload` pero **no lee `.env`**: solo usa las variables ya exportadas en la shell. Con un `.env`, usa `--env-file .env` como arriba, o exporta las variables antes. `source .env` falla con valores que tienen caracteres especiales si no van entre comillas simples.

Datos de demo para el dashboard:

```bash
make seed            # 40 conversaciones
make seed N=200
```

### 2.3 Instalación con Docker

```bash
cp .env.example .env              # Compose lo lee para interpolar variables
docker compose up -d --build
docker compose logs -f
```

Los datos persisten en el volumen `valkiria-data`, montado en `/app/data`. Desde el contenedor, un Ollama del anfitrión está en `http://host.docker.internal:11434/v1`.

### 2.4 Comprobación tras la instalación

```bash
make api-test
curl -s -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"message": "Olvidé mi contraseña"}' | python3 -m json.tool | head
```

Si responde con `ticket_id` y la lista de agentes, la instalación es correcta.

---

## 3. Configuración

Todas las variables están comentadas en [`.env.example`](../.env.example). Las principales:

| Grupo | Variable | Valores y notas |
|---|---|---|
| Entorno | `APP_ENV` | `development` o `production`. En producción, `API_KEYS` es obligatorio |
| Entorno | `DATA_DIR` | Carpeta de telemetría, auditoría y aprobaciones |
| Seguridad | `API_KEYS` | `clave:rol,clave:rol`, con roles `user`, `agent` o `admin` |
| Seguridad | `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW` | Peticiones por ventana, en segundos. Por defecto 60 por 60 |
| Seguridad | `CORS_ORIGINS` | Orígenes permitidos para el navegador |
| LLM | `LLM_PROVIDER` | `mock`, `ollama`, `jan` u `openai_compatible` |
| LLM | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | Vacíos: valores por defecto de Ollama o Jan |
| Ticketing | `TICKETING_PROVIDER` | `demo` (memoria), `simulated` (archivo) o `invgate` (real) |
| Aprobaciones | `APPROVAL_TTL_HOURS` | Por defecto 72 |
| Aprobaciones | `POC_MANAGER_NAME`, `POC_MANAGER_EMAIL` | Solo ese correo puede decidir desde Teams |
| Aprobaciones | `POC_MANAGER_INVGATE_ID` | Id del manager en InvGate, que es quien vota |
| Avisos | `NOTIFY_CHANNEL` | `teams` (bot), `webhook` (`TEAMS_WORKFLOW_URL`) o `none` |
| Observabilidad | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LOG_USER_CONTENT` | Langfuse es opcional |

Las variables de InvGate y Teams se explican en las secciones 4 y 5.

**Permisos por rol**

| Endpoint | Rol mínimo |
|---|---|
| `GET /api/health` | Público |
| `POST /api/chat`, `POST /api/chat/stream`, `GET /api/conversations[/{id}]` | `user` |
| `POST /api/escalate`, `GET /api/approvals[/{id}]`, `GET /api/metrics` | `agent` |
| `POST /api/approvals/{id}/decision`, `GET /api/audit/verify` | `admin` |
| `POST /api/messages` | Token de Bot Framework (lo valida el SDK) |

Sin `API_KEYS`, y fuera de producción, la API queda abierta.

---

## 4. Conexión con InvGate

### 4.1 Credencial

En InvGate, ve a **Settings → Integrations → API → API credential**. Hay dos opciones:

- **Basic auth (usuario y token):** rellena `INVGATE_USERNAME` e `INVGATE_API_TOKEN`.
- **OAuth 2.0 (client credentials):** rellena `INVGATE_CLIENT_ID` e `INVGATE_CLIENT_SECRET`. Si ambas opciones están configuradas, OAuth tiene prioridad.

En los dos casos, en **Permissions → API resources** marca los recursos que usa el PoC:

```
api.v1.helpdesks:get          api.v1.categories:get
api.v1.incident:get|post|put  api.v1.incidents:get
api.v1.incident.comment:get|post
api.v1.incident.attributes.{category,type,priority,source,status,statuses}:get
api.v1.incident.approval:get  api.v1.incident.approval.accept:put  api.v1.incident.approval.reject:put
api.v1.incident.approval.possible_voters:get  api.v1.incident.spontaneous_approval:post
```

**OAuth:** InvGate solo incluye en el token los permisos que se piden en el parámetro `scope`. El PoC pide esa lista por defecto (`DEFAULT_OAUTH_SCOPES` en `backend/invgate/client.py`). Si concedes otros, ajústalos en `INVGATE_OAUTH_SCOPES`, separados por espacios. La URL del token es `<base>/oauth/v2.0/access_token`; cámbiala con `INVGATE_OAUTH_TOKEN_URL` si tu instancia usa otra.

### 4.2 Ids de tu instancia

```bash
TICKETING_PROVIDER=invgate
INVGATE_BASE_URL=https://<instancia>.cloud.invgate.net   # URL de la instancia, no la web comercial
make check-invgate                                       # solo lectura: catálogos
make check-invgate ARGS="--incident 1"                   # lee un ticket: creator_id, user_id, assigned_id
```

Con esa salida, completa:

```bash
INVGATE_DEFAULTS='{"creator_id": 8, "customer_id": 8, "category_id": 1, "source_id": 2, "priority_id": 2}'
INVGATE_VALUE_MAP='{"category": {"acceso": "27", "software": "25", "hardware": "26", "general": "1"}, "status": {"open": "2", "waiting": "4", "resolved": "5", "closed": "6"}}'
INVGATE_AUTHOR_ID=8          # usuario que firma los comentarios
POC_MANAGER_INVGATE_ID=4     # usuario que vota las aprobaciones
```

Los valores de ejemplo son los de la demo pública `webdemo.cloud.invgate.net`.

### 4.3 Prueba de escritura

```bash
make check-invgate ARGS="--write"    # crea, lee, actualiza y comenta un ticket de prueba
```

Debe terminar con «Todo correcto». Después cierra el ticket de prueba desde la interfaz de InvGate: el `PUT` de estado no lo cambia, porque el estado lo gestiona el flujo de InvGate.

### 4.4 Aprobaciones en InvGate

- Si el flujo de InvGate ya crea una aprobación al abrir el ticket (en la demo, la categoría *New Software*), el PoC **reutiliza esa aprobación**.
- Si no hay ninguna, el PoC crea una aprobación espontánea con `POC_MANAGER_INVGATE_ID` como aprobador.
- La decisión se registra con `PUT /incident.approval.accept` o `.reject`, con el voto de `POC_MANAGER_INVGATE_ID` y la observación como `note`. InvGate guarda esa nota como comentario del ticket.

---

## 5. Conexión con Microsoft Teams

### 5.1 Azure Bot

1. En Azure Portal, crea un **Azure Bot** de tipo **Single Tenant**.
2. Anota el **Microsoft App ID** (`TEAMS_BOT_APP_ID`) y el **Tenant ID** (`TEAMS_TENANT_ID`).
3. En **Configuration → Manage Password**, crea un *client secret* y copia su **Value**, no el *Secret ID*. Va en `TEAMS_BOT_APP_PASSWORD`.
4. En **Channels**, activa **Microsoft Teams**.

```bash
NOTIFY_CHANNEL=teams
TEAMS_BOT_APP_ID=<app id>
TEAMS_BOT_APP_PASSWORD='<value del secreto>'
TEAMS_TENANT_ID=<tenant id>
POC_MANAGER_EMAIL=manager@empresa.com
```

Para comprobar las credenciales sin Teams, pide un token. Debe devolver HTTP 200:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "https://login.microsoftonline.com/$TEAMS_TENANT_ID/oauth2/v2.0/token" \
  -d grant_type=client_credentials -d client_id="$TEAMS_BOT_APP_ID" \
  --data-urlencode client_secret="$TEAMS_BOT_APP_PASSWORD" \
  -d scope=https://api.botframework.com/.default
```

### 5.2 Túnel HTTPS y messaging endpoint

```bash
cloudflared tunnel --protocol http2 --url http://localhost:8000
```

1. Copia la URL `https://<algo>.trycloudflare.com` y ponla en `PUBLIC_BASE_URL`.
2. En el Azure Bot, ve a **Configuration → Messaging endpoint**, pon `https://<algo>.trycloudflare.com/api/messages` y pulsa **Apply**.
3. Comprueba la conexión con **Test in Web Chat** del Azure Bot: al escribir «hola», el bot debe responder.

**Cuidado con los túneles rápidos:** la URL cambia en cada arranque y Cloudflare la da de baja pasadas unas horas («Tunnel not found»). Cada vez hay que repetir los pasos 1 y 2. Para algo estable, usa un túnel con nombre de Cloudflare o un dominio fijo de ngrok.

### 5.3 App de Teams

Sigue [`infra/README.md`](../infra/README.md): rellena `infra/teams/manifest.json` con el App ID y la URL, añade los iconos, comprímelo y súbelo en **Aplicaciones → Administrar aplicaciones**. Si ya tienes una app publicada, como «Help Desk IA», basta con que use el mismo App ID.

### 5.4 Activación

El manager escribe «hola» al bot una vez. El bot guarda esa conversación en `DATA_DIR/teams_references.json`, junto con su correo, y desde entonces puede enviarle tarjetas.

---

## 6. Operación

### 6.1 Arranque y parada

| Modo | Arrancar | Parar |
|---|---|---|
| Local | `uvicorn backend.server:app --port 8000 --env-file .env` | Ctrl+C |
| Docker | `docker compose up -d` | `docker compose down` |
| Túnel | `cloudflared tunnel --protocol http2 --url http://localhost:8000` | Ctrl+C |

### 6.2 Archivos de datos (`DATA_DIR`)

| Archivo | Contenido | ¿Se puede borrar? |
|---|---|---|
| `telemetry.jsonl` | Eventos del dashboard | Sí, se pierde el histórico del dashboard |
| `audit.jsonl` | Auditoría encadenada por hash | No, rompería la verificación. Archívalo entero |
| `approvals.json` | Aprobaciones y su decisión (no se usa con `TICKETING_PROVIDER=demo`) | Solo si no hay aprobaciones pendientes |
| `teams_references.json` | Conversación del manager en Teams | Sí, pero el manager tendrá que volver a escribir «hola» |
| `simulated_tickets.json` | Tickets del proveedor `simulated` | Sí |

### 6.3 Comprobaciones periódicas

```bash
make api-test                                                   # salud
curl -H "Authorization: Bearer <admin>" localhost:8000/api/audit/verify   # integridad de la auditoría
curl -H "Authorization: Bearer <agent>" "localhost:8000/api/metrics?hours=24"
```

---

## 7. Mantenimiento

### 7.1 Calidad antes de cada cambio

```bash
make lint          # ruff check y ruff format --check
make typecheck     # mypy --explicit-package-bases backend
make security      # bandit
make coverage      # pytest; falla por debajo del 90.01 %
```

En cada PR, GitHub Actions ejecuta **CI** (`quality` y `security`) y **SonarCloud**, que usa el secreto `SONAR_TOKEN`. Las dos tienen que pasar antes de fusionar. Si un PR no lanza los checks, ciérralo y reábrelo.

### 7.2 Dependencias

- Las versiones están en `requirements*.txt`. La instalación usa los locks con hash (`requirements*.lock`) y solo wheels.
- Para actualizar: cambia la versión en el `.txt`, ejecuta `make lock` (requiere uv), luego `make install` y `make coverage`.
- `pip-audit` se ejecuta en CI. Si aparece una vulnerabilidad, sube la versión y regenera los locks.

### 7.3 Rotación de credenciales

| Credencial | Dónde se cambia | Después |
|---|---|---|
| Token o secreto de InvGate | InvGate → API credential → **Generate** | Actualiza `.env` y reinicia. El secreto anterior deja de valer |
| Secreto del Azure Bot | Azure Bot → Configuration → Manage Password | Actualiza `TEAMS_BOT_APP_PASSWORD` y reinicia |
| `API_KEYS` | `.env` | Reinicia y reparte las claves nuevas |
| `SONAR_TOKEN` | sonarcloud.io → My Account → Security | GitHub → Settings → Secrets → Actions |

### 7.4 Ampliar la base de conocimiento

Los artículos están en `backend/agents/kb_articles.json`. Añade uno con `id`, `title`, `category`, `keywords` y `summary`, y ejecuta las pruebas.

### 7.5 Cambiar la política de aprobación

La regla está en el Agente de Políticas y en el clasificador, en `backend/agents/orchestrator.py` y `backend/llmops/llm.py`. Hoy, toda solicitud de software, licencia o permiso elevado requiere aprobación.

---

## 8. Soporte y resolución de problemas

### 8.1 Dónde mirar

- **Logs de la API:** salida de uvicorn, o `docker compose logs -f`. Cada petición aparece con su código HTTP.
- **Semáforo del chat:** el agente en rojo dice qué falló, por ejemplo «no se pudo crear el ticket (InvGateAuthError)».
- **Dashboard → Orquestación:** errores por agente y degradaciones del LLM.

### 8.2 Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| El PoC usa `demo` aunque `.env` dice `invgate` | `make local-up` no lee `.env` | Arranca con `--env-file .env` (sección 2.2) |
| InvGate responde 404 en todo | `INVGATE_BASE_URL` apunta a la web comercial | Usa la URL de la instancia: `https://<instancia>.cloud.invgate.net` |
| InvGate 401 | Token incorrecto o credencial borrada. La demo pública se reinicia y borra credenciales | Vuelve a crear la credencial y actualiza `.env` |
| InvGate 403 con OAuth | El token no trae permisos (`scopes: []`) | Concede los recursos en la credencial. El PoC ya los pide en `scope`; revisa `INVGATE_OAUTH_SCOPES` |
| OAuth devuelve `invalid_scope` | Se pide un permiso que la credencial no tiene | Concédelo en **API resources** o quítalo de `INVGATE_OAUTH_SCOPES` |
| 409 «not allowed to request an approval» | Ya hay una aprobación pendiente, o el autor no es un agente | El PoC reutiliza la pendiente. Si persiste, revisa `INVGATE_AUTHOR_ID` |
| El ticket sigue «esperando aprobación» tras aprobar | El estado lo gestiona el flujo de InvGate | Es esperado. Comprueba el voto en la sección Aprobaciones del ticket |
| `AADSTS700016` al pedir el token del bot | `TEAMS_BOT_APP_ID` no es el App ID (por ejemplo, es el Tenant ID) | Copia el **Microsoft App ID** del Azure Bot |
| `AADSTS7000215` | Se copió el *Secret ID* en lugar del **Value** | Crea un secreto nuevo y copia su Value |
| Teams: «No se puede conectar con la aplicación» | Túnel caducado o messaging endpoint con la URL antigua | Arranca el túnel y actualiza el endpoint (sección 5.2) |
| Cloudflare error 1033 o el túnel no registra | Puerto de salida 7844 bloqueado | Usa `--protocol http2` o abre el puerto 7844 |
| `curl` no resuelve `*.trycloudflare.com` | El DNS local tarda en ver el subdominio nuevo | Espera, o prueba con `--resolve` usando la IP de `dig @1.1.1.1` |
| `POST /api/messages` devuelve 401 | Petición sin token de Bot Framework | Esperado si no viene de Microsoft. Si viene de Teams, revisa el App ID y el Tenant |
| El manager no recibe la tarjeta | No ha escrito «hola» al bot, o su correo no coincide con `POC_MANAGER_EMAIL` | Que escriba «hola». Revisa `teams_references.json` |
| «Solo el manager asignado puede decidir» | Votó otra cuenta | Esperado. Ajusta `POC_MANAGER_EMAIL` si el manager es otro |
| Tarjeta «Tarjeta no vigente» | Botón de una tarjeta de una versión anterior del bot | Esperado. No requiere acción |
| Agente en amarillo con «LLM no disponible» | Ollama o Jan no responde | Revisa `LLM_BASE_URL`, o deja el mock |
| 429 Too Many Requests | Límite de peticiones | Espera lo que indique `Retry-After`, o sube `RATE_LIMIT_MAX` |
| `GET /api/audit/verify` falla | Alguien editó o borró `audit.jsonl` | Restaura la copia archivada e investiga el acceso |

### 8.3 Escalar un incidente del PoC

Antes de abrir una incidencia, reúne:
- La hora del fallo.
- Las líneas del log de esa hora.
- El `conversation_id` o el número de ticket.
- La salida de `make api-test` y, si afecta a InvGate, la de `make check-invgate`.

Nunca incluyas tokens, secretos ni el contenido de `.env`.

# Validación en real: InvGate y Microsoft Teams

Última actualización: 2026-11-18.

Los criterios 2 y 6 del PoC requieren una instancia de InvGate y un tenant de Microsoft 365. Esta guía explica cómo validarlos con credenciales reales. Los resultados contra la demo pública están en los apartados 1.5 y 2.5: **ambos criterios se cumplen**, con Basic auth y con OAuth 2.0. La guía de instalación completa, con la resolución de problemas, está en el [Manual técnico](MANUAL_TECNICO.md).

## 1. InvGate Service Management (criterio 2)

### 1.1 Credenciales

En InvGate, **Settings → Integrations → API**, crea una credencial con una de estas opciones:

- **API token (Basic auth):** usuario `api` (o el que te asignen) y el token. Configura `INVGATE_USERNAME` e `INVGATE_API_TOKEN`.
- **OAuth 2.0 client credentials:** Client ID y Client Secret. Configura `INVGATE_CLIENT_ID` e `INVGATE_CLIENT_SECRET`. Si tu instancia no usa `<base>/oauth/v2.0/access_token`, indica la URL en `INVGATE_OAUTH_TOKEN_URL`. En **API resources** de la credencial concede los endpoints que usa el PoC (lista en `DEFAULT_OAUTH_SCOPES`, `backend/invgate/client.py`).

```bash
TICKETING_PROVIDER=invgate
INVGATE_BASE_URL=https://tu-instancia.cloud.invgate.net
INVGATE_API_TOKEN=...
```

### 1.2 Prueba de solo lectura

No consume cuota de escritura:

```bash
make check-invgate                          # catálogos: prioridades, estados, tipos, fuentes, categorías, helpdesks
make check-invgate ARGS="--incident 1234"   # además consulta un incidente y sus comentarios
```

Con la salida, completa los ids de tu instancia:

```bash
# Obligatorios para POST /incident
INVGATE_DEFAULTS={"creator_id": 5, "customer_id": 5, "category_id": 12, "source_id": 1}
# Categorías y estados del PoC -> ids de tu instancia
INVGATE_VALUE_MAP={"category": {"acceso": "12", "software": "15", "hardware": "18", "general": "20"}, "status": {"open": "2", "waiting": "3", "resolved": "5", "closed": "6"}}
INVGATE_AUTHOR_ID=5
POC_MANAGER_INVGATE_ID=9
```

Las prioridades (`baja`=1 … `critica`=5) y los tipos (`incident`=1, `request`=2…) ya usan los valores documentados por InvGate.

### 1.3 Prueba de escritura

```bash
make check-invgate ARGS="--write"
```

El script crea un incidente de prueba y luego lo consulta, lo actualiza y lo comenta. Guarda la salida como evidencia y cierra el ticket de prueba en InvGate.

### 1.4 Puntos por confirmar en la instancia

La documentación pública de InvGate no precisa estos detalles. Si alguno falla, se ajusta sin tocar el código:

| Qué | Valor actual | Cómo ajustarlo |
|---|---|---|
| Prefijo de la API | `/api/v1` | `INVGATE_API_PREFIX` |
| URL del token OAuth2 | `<base>/oauth/v2.0/access_token` | `INVGATE_OAUTH_TOKEN_URL` |
| Parámetros de POST/PUT | cuerpo JSON | Si la instancia exige *form data*, cambiar `json=` por `data=` en `backend/invgate/client.py` |
| Nombres de campo | `category_id`, `priority_id`, `customer_id`… | `INVGATE_FIELD_MAP` |

### 1.5 Resultado en la demo pública (17-11-2026)

Validado contra `https://webdemo.cloud.invgate.net` con Basic auth (credencial de API con endpoints habilitados). Evidencia: [`evidencias/invgate-crud-2026-11-17.txt`](evidencias/invgate-crud-2026-11-17.txt).

- `INVGATE_BASE_URL` es la URL de la instancia (`https://<instancia>.cloud.invgate.net`), no la página comercial de la demo.
- El prefijo `/api/v1`, el cuerpo JSON y los nombres de campo por defecto funcionan sin cambios.
- Ids usados en la demo: `INVGATE_DEFAULTS={"creator_id": 8, "customer_id": 8, "category_id": 1, "source_id": 2, "priority_id": 2}`, estados `open=2`, `waiting=4`, `resolved=5`, `closed=6`.
- OAuth2: el token se emite en `<base>/oauth/v2.0/access_token`. InvGate solo incluye en el token los permisos que se piden en el parámetro `scope` (formato `api.v1.<recurso>:<método>`) y que estén concedidos en **API resources** de la credencial; sin `scope`, sale con `scopes: []` y la API responde 403. El PoC pide por defecto los 19 permisos que usa (`INVGATE_OAUTH_SCOPES` permite cambiarlos). Validado por OAuth el 18-11-2026: CRUD 11/11 y aprobación desde Teams ([`evidencias/invgate-oauth-2026-11-18.txt`](evidencias/invgate-oauth-2026-11-18.txt)).
- Sin permiso sobre `users`, los ids de usuario se obtienen de un incidente existente (`GET /incident?id=1` → `creator_id`, `user_id`).
- `PUT /incident` acepta `status_id` pero no cambia el estado: InvGate lo gestiona con su flujo de trabajo. Los tickets de prueba se cierran desde la interfaz.
- El `.env` se carga con `python-dotenv` o exportando las variables; con `source .env`, los valores con caracteres especiales van entre comillas simples.

## 2. Microsoft Teams (criterio 6)

### 2.1 Túnel HTTPS

Teams necesita llegar al endpoint `/api/messages`:

```bash
uvicorn backend.server:app --port 8000 --env-file .env
cloudflared tunnel --protocol http2 --url http://localhost:8000   # o: ngrok http 8000
```

Anota la URL pública como `PUBLIC_BASE_URL`.

### 2.2 Azure Bot

1. En Azure Portal, crea un recurso **Azure Bot** de tipo *Single Tenant*.
2. En **Configuration**, pon `https://<PUBLIC_BASE_URL>/api/messages` como *Messaging endpoint*.
3. Copia el *Microsoft App ID* y crea un *client secret*. Usa su **Value**, no el *Secret ID*:

```bash
TEAMS_BOT_APP_ID=...
TEAMS_BOT_APP_PASSWORD=...
TEAMS_TENANT_ID=...
NOTIFY_CHANNEL=teams
POC_MANAGER_EMAIL=manager@empresa.com
```

4. En **Channels**, activa **Microsoft Teams**.

### 2.3 App de Teams

Sigue [`infra/README.md`](../infra/README.md) para empaquetar `infra/teams/manifest.json` y subirlo a Teams.

### 2.4 Prueba

1. El manager abre el chat con el bot y escribe «hola». El bot guarda su conversación para poder escribirle después.
2. En el chat web, el solicitante escribe «Necesito instalar Figma».
3. El manager recibe la tarjeta, escribe una observación y pulsa **Aprobar**.
4. Comprueba lo siguiente:
   - La tarjeta cambia a «Solicitud aprobada» con la observación.
   - En InvGate, el incidente tiene la aprobación aceptada y la nota.
   - En el chat web, el solicitante ve la decisión y la observación.
   - Un segundo clic responde «Esta aprobación ya fue resuelta».
   - Si otro usuario pulsa, recibe «Solo el manager asignado puede decidir».

### 2.5 Resultado con «Help Desk IA» (18-11-2026)

Validado con el bot «Help Desk IA» (tenant `valtre.com`) y la demo pública de InvGate. Evidencia: [`evidencias/teams-aprobacion-2026-11-18.txt`](evidencias/teams-aprobacion-2026-11-18.txt).

- En la demo, la categoría *New Software* crea sola una aprobación (tipo *Defined*) al abrir el ticket. InvGate no admite una aprobación espontánea mientras haya otra pendiente (HTTP 409), así que el PoC reutiliza la pendiente y solo crea una espontánea si no hay ninguna.
- El voto por API (`PUT /incident.approval.accept`) deja la aprobación *Approved*, anula los votos del resto y guarda la observación como comentario visible para el cliente. El estado del ticket lo sigue gestionando el flujo de InvGate.
- Los botones `Action.Execute` de tarjetas de versiones anteriores del bot ya no dan error: el bot las sustituye por «Tarjeta no vigente», sin botones.
- Con un túnel *quick* de Cloudflare la URL cambia en cada arranque: hay que actualizar el *messaging endpoint* del Azure Bot y `PUBLIC_BASE_URL`. **Test in Web Chat** del Azure Bot sirve para comprobarlo sin Teams.
- La demo pública se reinicia: borra credenciales de API y tickets, y reutiliza los números. Si la API pasa a 401, hay que volver a crear la credencial.

Sin bot, `NOTIFY_CHANNEL=webhook` con `TEAMS_WORKFLOW_URL` publica un aviso en un canal. La decisión se toma entonces con `POST /api/approvals/{id}/decision`.

## 3. SonarCloud

1. En sonarcloud.io, importa el repositorio `ABRAHAMCIMAT/PoC_InvGate` en la organización `abrahamcimat`.
2. Genera un token en **My Account → Security**.
3. En GitHub, ve a **Settings → Secrets and variables → Actions** y crea el secreto `SONAR_TOKEN`.
4. Desactiva el *Automatic Analysis* de SonarCloud, porque el análisis lo hace el workflow.

Mientras el secreto no exista, el workflow pasa con un aviso en lugar de fallar.

**Estado:** configurado. El workflow usa `SonarSource/sonarqube-scan-action` (Java 21), importa la cobertura de pytest y el Quality Gate está en verde. También se puede lanzar a mano (`workflow_dispatch`).

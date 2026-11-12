# Validación en real: InvGate y Microsoft Teams

Los criterios 2 y 6 del PoC requieren una instancia de InvGate y un tenant de Microsoft 365. Todo el código está listo y probado contra respuestas simuladas. Esta guía es lo que falta ejecutar con credenciales reales.

## 1. InvGate Service Management (criterio 2)

### 1.1 Credenciales

En InvGate, **Settings → Integrations → API**, crea una credencial con una de estas opciones:

- **API token (Basic auth):** usuario `api` (o el que te asignen) y el token. Configura `INVGATE_USERNAME` e `INVGATE_API_TOKEN`.
- **OAuth 2.0 client credentials:** Client ID y Client Secret. Configura `INVGATE_CLIENT_ID` e `INVGATE_CLIENT_SECRET`. Si tu instancia no usa `<base>/oauth/v2.0/access_token`, indica la URL en `INVGATE_OAUTH_TOKEN_URL`.

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

## 2. Microsoft Teams (criterio 6)

### 2.1 Túnel HTTPS

Teams necesita llegar al endpoint `/api/messages`:

```bash
make local-up
cloudflared tunnel --url http://localhost:8000   # o: ngrok http 8000
```

Anota la URL pública como `PUBLIC_BASE_URL`.

### 2.2 Azure Bot

1. En Azure Portal, crea un recurso **Azure Bot** de tipo *Single Tenant*.
2. En **Configuration**, pon `https://<PUBLIC_BASE_URL>/api/messages` como *Messaging endpoint*.
3. Copia el *Microsoft App ID* y crea un *client secret*:

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

Sin bot, `NOTIFY_CHANNEL=webhook` con `TEAMS_WORKFLOW_URL` publica un aviso en un canal. La decisión se toma entonces con `POST /api/approvals/{id}/decision`.

## 3. SonarCloud

1. En sonarcloud.io, importa el repositorio `ABRAHAMCIMAT/PoC_InvGate` en la organización `abrahamcimat`.
2. Genera un token en **My Account → Security**.
3. En GitHub, ve a **Settings → Secrets and variables → Actions** y crea el secreto `SONAR_TOKEN`.
4. Desactiva el *Automatic Analysis* de SonarCloud, porque el análisis lo hace el workflow.

Mientras el secreto no exista, el workflow pasa con un aviso en lugar de fallar.

# Infraestructura

## `teams/manifest.json`

Plantilla del paquete de la app de Teams para el bot de aprobaciones.

1. Sustituye `{{TEAMS_BOT_APP_ID}}` por el *App ID* del Azure Bot y `{{PUBLIC_BASE_URL}}` por la URL pública del PoC.
2. Añade dos iconos PNG junto al manifiesto: `color.png` (192×192) y `outline.png` (32×32, blanco sobre transparente).
3. Comprime los tres archivos en un `.zip`, sin carpeta intermedia.
4. En Teams, abre **Aplicaciones → Administrar aplicaciones → Cargar una aplicación personalizada** y sube el `.zip`.

El paso a paso completo, con el Azure Bot y el túnel HTTPS, está en [`docs/VALIDACION_REAL.md`](../docs/VALIDACION_REAL.md).

## Docker

El `Dockerfile` y el `docker-compose.yml` viven en la raíz del repositorio. `docker compose up -d` levanta la API con el chat web y el dashboard en `http://localhost:8000`. Los datos (telemetría, auditoría, tickets simulados y referencias de Teams) persisten en el volumen `valkiria-data`.

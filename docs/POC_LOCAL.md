# Ejecución local del PoC

## Requisitos

- Python 3.15+
- Docker (opcional, para `docker compose`)
- Ollama o Jan con Llama 3.1 8B (opcional; sin ellos se usa el LLM mock)

## Sin Docker

```bash
make install
make local-up
```

- Chat web: `http://127.0.0.1:8000/`
- Dashboard: `http://127.0.0.1:8000/dashboard.html`

```bash
make api-test
# -> {"status":"ok","service":"valkiria-invgate","version":"0.2.0"}
```

## Con Docker

```bash
docker compose up --build
```

## Poblar el dashboard

```bash
make seed            # 40 conversaciones de demo, con aprobaciones resueltas y pendientes
make seed N=200
```

## Probar por API

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Necesito instalar Figma"}'

curl http://127.0.0.1:8000/api/approvals
curl -X POST http://127.0.0.1:8000/api/approvals/APR-xxxx/decision \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "note": "Usa la licencia del equipo", "user_email": "manager@empresa.com"}'
```

La colección de Bruno en `bruno/valkiria-invgate/` tiene todas las peticiones, incluidas las de InvGate en solo lectura.

## LLM local (Llama 3.1 8B)

```bash
ollama pull llama3.1:8b
LLM_PROVIDER=ollama make local-up
```

Para Jan: `LLM_PROVIDER=jan`. Si el modelo no responde, el clasificador usa el mock y el semáforo lo marca en amarillo.

## Seguridad

```bash
API_KEYS="u-123:user,a-456:agent,ad-789:admin" make local-up
```

En el chat web, escribe la clave en **API key**. Con `APP_ENV=production`, la API rechaza las peticiones si `API_KEYS` está vacío.

## InvGate real y Teams

Ver [`VALIDACION_REAL.md`](VALIDACION_REAL.md).

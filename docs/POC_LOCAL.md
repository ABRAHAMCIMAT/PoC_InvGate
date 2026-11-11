# Ejecución local del PoC

## Requisitos

- Python 3.11+
- Docker (opcional, para `docker compose`)

## Sin Docker

```bash
make install
make local-up
```

El API queda en `http://127.0.0.1:8000`. Verifica:

```bash
make api-test
# -> {"status":"ok","service":"valkiria-invgate","version":"0.1.0"}
```

## Con Docker

```bash
docker compose up --build
```

## Probar el chat

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "No enciende mi laptop"}'
```

## Frontend

Abre `frontend/index.html` (o sírvelo con cualquier servidor estático apuntando al API).

## InvGate real

Copia `.env.example` a `.env` y configura:

```
TICKETING_PROVIDER=invgate
INVGATE_BASE_URL=https://tu-instancia.invgate.net
INVGATE_API_TOKEN=tu-token
```

El resto del PoC corre con `TICKETING_PROVIDER=demo` y LLM mock sin credenciales.

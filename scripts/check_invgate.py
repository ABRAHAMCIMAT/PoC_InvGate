"""Prueba de humo contra una instancia real de InvGate (criterio 2 del PoC).

Por defecto solo lee (catálogos y, si se da, un incidente) para no consumir cuota:
    python -m scripts.check_invgate
    python -m scripts.check_invgate --incident 1234

Con --write crea un incidente de prueba, lo consulta, lo actualiza y lo comenta:
    python -m scripts.check_invgate --write

Requiere INVGATE_BASE_URL y INVGATE_API_TOKEN (o INVGATE_CLIENT_ID/SECRET). Para --write,
INVGATE_DEFAULTS debe traer al menos creator_id, customer_id y category_id válidos.
"""

from __future__ import annotations

import argparse
import sys

from backend.config import get_settings
from backend.invgate.client import InvGateError
from backend.invgate.models import Incident
from backend.ticketing.factory import build_invgate_client

CATALOGS = [
    "incident.attributes.priority",
    "incident.attributes.status",
    "incident.attributes.type",
    "incident.attributes.source",
    "categories",
    "helpdesks",
]


def run(incident_id: str | None, write: bool) -> int:
    client = build_invgate_client(get_settings())
    failures = 0

    def step(label: str, fn) -> object:
        nonlocal failures
        try:
            result = fn()
        except (InvGateError, ValueError) as exc:
            failures += 1
            print(f"✕ {label}: {exc}")
            return None
        print(f"✓ {label}")
        return result

    for catalog in CATALOGS:
        items = step(f"GET /{catalog}", lambda c=catalog: client.list_catalog(c))
        if items:
            sample = ", ".join(f"{i.id}={i.name}" for i in items[:5])  # type: ignore[attr-defined]
            print(f"    {sample}")

    if incident_id:
        inc = step(f"GET /incident?id={incident_id}", lambda: client.get_incident(incident_id))
        if inc is not None:
            print(f"    {inc.title!r} · estado {inc.status.value} · prioridad {inc.priority}")  # type: ignore[attr-defined]
        step(f"GET /incident.comment?request_id={incident_id}", lambda: client.list_comments(incident_id))

    if write:
        created = step(
            "POST /incident",
            lambda: client.create_incident(
                Incident(
                    title="[Valkiria PoC] prueba de integración",
                    description="Ticket de prueba; puede cerrarse.",
                )
            ),
        )
        if created is not None:
            new_id = created.id  # type: ignore[attr-defined]
            print(f"    request_id={new_id}")
            step(f"GET /incident?id={new_id}", lambda: client.get_incident(new_id))
            step(
                "PUT /incident",
                lambda: client.update_incident(new_id, Incident(title="[Valkiria PoC] prueba actualizada")),
            )
            step("POST /incident.comment", lambda: client.add_comment(new_id, "Comentario de prueba del PoC"))
            step("GET /incident.comment", lambda: client.list_comments(new_id))

    client.close()
    print("Todo correcto." if failures == 0 else f"{failures} comprobación(es) fallaron.")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueba de humo de la API de InvGate")
    parser.add_argument("--incident", help="id de un incidente existente para consultar")
    parser.add_argument(
        "--write", action="store_true", help="crear, actualizar y comentar un incidente de prueba"
    )
    args = parser.parse_args(argv)
    try:
        return run(args.incident, args.write)
    except ValueError as exc:
        print(f"Configuración incompleta: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

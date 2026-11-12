"""Puebla el dashboard con telemetría de demo ejecutando el flujo real de agentes.

Uso:
    python -m scripts.seed_demo_telemetry            # 40 conversaciones en DATA_DIR
    python -m scripts.seed_demo_telemetry -n 100 --seed 7

Usa el proveedor y el LLM configurados (por defecto demo + mock), así que no consume
cuota de InvGate salvo que TICKETING_PROVIDER=invgate.
"""

from __future__ import annotations

import argparse
import random
import time

from backend.approvals.service import ApprovalDecision
from backend.runtime import build_runtime

SAMPLES = [
    "Olvidé mi contraseña y no puedo entrar",
    "Mi cuenta está bloqueada después de varios intentos",
    "No me conecta la VPN desde casa",
    "Necesito instalar Figma para el nuevo proyecto",
    "Solicito licencia de Adobe Acrobat",
    "Quiero instalar una aplicación de diagramas",
    "Mi laptop no enciende aunque está cargada",
    "La impresora del piso 3 no imprime",
    "La pantalla parpadea y se pone negra",
    "Se cayó producción para todos los usuarios",
    "El correo de Outlook no sincroniza",
    "Tengo una duda sobre el procedimiento de vacaciones",
]
NOTES = ["Aprobado para este trimestre", "Usa la licencia del equipo", "No hay presupuesto", None]


def seed(count: int, rng: random.Random) -> dict[str, int]:
    rt = build_runtime()
    stats = {"conversaciones": 0, "aprobadas": 0, "rechazadas": 0, "pendientes": 0}
    for _ in range(count):
        started = time.time()
        orch = rt.orchestrator()
        conv = orch.new_conversation(rng.choice(SAMPLES))
        rt.conversations[conv.id] = conv
        results = list(orch.run(conv))
        rt.record_chat(conv, results, orch, started, actor="seed")
        stats["conversaciones"] += 1
        if not conv.approval_id:
            continue
        roll = rng.random()
        if roll < 0.2:
            stats["pendientes"] += 1
            continue
        decision = ApprovalDecision.APPROVED if roll < 0.75 else ApprovalDecision.REJECTED
        req = rt.approvals.get(conv.approval_id)
        req.created_at -= rng.uniform(60, 6 * 3600)  # simula horas de espera del manager
        rt.approvals.decide(
            conv.approval_id,
            decision,
            "seed-manager",
            note=rng.choice(NOTES),
            user_email=req.manager_email or None,
        )
        stats["aprobadas" if decision == ApprovalDecision.APPROVED else "rechazadas"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-n", "--count", type=int, default=40, help="conversaciones a generar")
    parser.add_argument("--seed", type=int, default=None, help="semilla para resultados repetibles")
    args = parser.parse_args(argv)
    # Datos de demo: no se necesita aleatoriedad criptográfica.
    stats = seed(args.count, random.Random(args.seed))  # noqa: S311  # nosec B311
    print(", ".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

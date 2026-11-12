"""Agregados de telemetría para el dashboard de 4 dimensiones."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

STATUSES = ("ok", "warning", "error")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 1)


def _latency(values: list[float]) -> dict[str, float]:
    return {
        "p50": _percentile(values, 0.5),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 1) if values else 0.0,
    }


def summarize(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Resume eventos de telemetría en negocio/ITSM, rendimiento, costos y orquestación."""
    chats: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    requested: set[str] = set()
    decided: dict[str, str] = {}
    waits: list[float] = []
    rate_limited = 0
    first_ts: float | None = None
    last_ts: float | None = None

    for e in events:
        ts = e.get("ts")
        if isinstance(ts, (int, float)):
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        kind = e.get("event")
        if kind == "chat_completed":
            chats.append(e)
        elif kind == "agent_step":
            steps.append(e)
        elif kind == "approval_requested" and e.get("approval_id"):
            requested.add(str(e["approval_id"]))
        elif kind == "approval_decided" and e.get("approval_id"):
            decided[str(e["approval_id"])] = str(e.get("decision"))
            if isinstance(e.get("wait_seconds"), (int, float)):
                waits.append(float(e["wait_seconds"]))
        elif kind == "rate_limited":
            rate_limited += 1

    n = len(chats)
    tickets = sum(1 for c in chats if c.get("ticket_id"))
    escalated = [c for c in chats if c.get("escalated")]
    decisions = Counter(decided.values())

    by_agent_latency: dict[str, list[float]] = defaultdict(list)
    by_agent_status: dict[str, Counter[str]] = defaultdict(Counter)
    for s in steps:
        agent = str(s.get("agent"))
        if isinstance(s.get("latency_ms"), (int, float)):
            by_agent_latency[agent].append(float(s["latency_ms"]))
        by_agent_status[agent][str(s.get("status", "ok"))] += 1
    status_total = Counter[str]()
    for counter in by_agent_status.values():
        status_total.update(counter)

    tokens_in = sum(int(c.get("prompt_tokens") or 0) for c in chats)
    tokens_out = sum(int(c.get("completion_tokens") or 0) for c in chats)
    cost = round(sum(float(c.get("cost_usd") or 0) for c in chats), 6)
    by_model: dict[str, dict[str, float]] = defaultdict(
        lambda: {"llamadas": 0, "tokens": 0, "costo_usd": 0.0}
    )
    for c in chats:
        m = by_model[str(c.get("llm_model") or "desconocido")]
        m["llamadas"] += int(c.get("llm_calls") or 1)
        m["tokens"] += int(c.get("prompt_tokens") or 0) + int(c.get("completion_tokens") or 0)
        m["costo_usd"] = round(m["costo_usd"] + float(c.get("cost_usd") or 0), 6)

    return {
        "periodo": {"desde": first_ts, "hasta": last_ts, "eventos_chat": n},
        "negocio": {
            "conversaciones": n,
            "tickets_creados": tickets,
            "por_categoria": dict(Counter(str(c.get("category")) for c in chats)),
            "por_prioridad": dict(Counter(str(c.get("priority")) for c in chats)),
            "escaladas": len(escalated),
            "tasa_escalacion": round(len(escalated) / n, 3) if n else 0.0,
            "por_nivel": dict(Counter(str(c.get("escalation_level")) for c in escalated)),
            "aprobaciones": {
                "solicitadas": len(requested),
                "aprobadas": decisions.get("approved", 0),
                "rechazadas": decisions.get("rejected", 0),
                "pendientes": len(requested - set(decided)),
                "espera_media_s": round(sum(waits) / len(waits), 1) if waits else 0.0,
            },
        },
        "rendimiento": {
            "chat_ms": _latency([float(c["latency_ms"]) for c in chats if "latency_ms" in c]),
            "por_agente_ms": {a: _latency(v) for a, v in sorted(by_agent_latency.items())},
            "peticiones_limitadas": rate_limited,
        },
        "costos": {
            "llamadas_llm": sum(int(c.get("llm_calls") or 1) for c in chats),
            "tokens_entrada": tokens_in,
            "tokens_salida": tokens_out,
            "costo_usd": cost,
            "costo_por_conversacion_usd": round(cost / n, 6) if n else 0.0,
            "por_modelo": dict(by_model),
        },
        "orquestacion": {
            "estados": {s: status_total.get(s, 0) for s in STATUSES},
            "por_agente": {a: {s: c.get(s, 0) for s in STATUSES} for a, c in sorted(by_agent_status.items())},
            "degradaciones_llm": sum(1 for c in chats if c.get("llm_degraded")),
        },
    }

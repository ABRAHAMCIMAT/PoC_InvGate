"""Agregados de telemetría para el dashboard de 4 dimensiones."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
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


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


@dataclass
class _Collector:
    """Agrupa los eventos por tipo en una sola pasada."""

    chats: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    requested: set[str] = field(default_factory=set)
    decided: dict[str, str] = field(default_factory=dict)
    waits: list[float] = field(default_factory=list)
    rate_limited: int = 0
    first_ts: float | None = None
    last_ts: float | None = None

    def add(self, e: dict[str, Any]) -> None:
        self._track_time(e.get("ts"))
        handler = {
            "chat_completed": self.chats.append,
            "agent_step": self.steps.append,
            "approval_requested": self._requested,
            "approval_decided": self._decided,
            "rate_limited": self._limited,
        }.get(str(e.get("event")))
        if handler is not None:
            handler(e)

    def _track_time(self, ts: Any) -> None:
        if not isinstance(ts, (int, float)):
            return
        self.first_ts = ts if self.first_ts is None else min(self.first_ts, ts)
        self.last_ts = ts if self.last_ts is None else max(self.last_ts, ts)

    def _requested(self, e: dict[str, Any]) -> None:
        if e.get("approval_id"):
            self.requested.add(str(e["approval_id"]))

    def _decided(self, e: dict[str, Any]) -> None:
        if not e.get("approval_id"):
            return
        self.decided[str(e["approval_id"])] = str(e.get("decision"))
        if isinstance(e.get("wait_seconds"), (int, float)):
            self.waits.append(float(e["wait_seconds"]))

    def _limited(self, _: dict[str, Any]) -> None:
        self.rate_limited += 1


def _business(c: _Collector) -> dict[str, Any]:
    n = len(c.chats)
    escalated = [chat for chat in c.chats if chat.get("escalated")]
    decisions = Counter(c.decided.values())
    return {
        "conversaciones": n,
        "tickets_creados": sum(1 for chat in c.chats if chat.get("ticket_id")),
        "por_categoria": dict(Counter(str(chat.get("category")) for chat in c.chats)),
        "por_prioridad": dict(Counter(str(chat.get("priority")) for chat in c.chats)),
        "escaladas": len(escalated),
        "tasa_escalacion": round(len(escalated) / n, 3) if n else 0.0,
        "por_nivel": dict(Counter(str(chat.get("escalation_level")) for chat in escalated)),
        "aprobaciones": {
            "solicitadas": len(c.requested),
            "aprobadas": decisions.get("approved", 0),
            "rechazadas": decisions.get("rejected", 0),
            "pendientes": len(c.requested - set(c.decided)),
            "espera_media_s": round(sum(c.waits) / len(c.waits), 1) if c.waits else 0.0,
        },
    }


def _performance(c: _Collector) -> dict[str, Any]:
    by_agent: dict[str, list[float]] = defaultdict(list)
    for step in c.steps:
        if isinstance(step.get("latency_ms"), (int, float)):
            by_agent[str(step.get("agent"))].append(float(step["latency_ms"]))
    return {
        "chat_ms": _latency([float(chat["latency_ms"]) for chat in c.chats if "latency_ms" in chat]),
        "por_agente_ms": {agent: _latency(values) for agent, values in sorted(by_agent.items())},
        "peticiones_limitadas": c.rate_limited,
    }


def _costs(c: _Collector) -> dict[str, Any]:
    n = len(c.chats)
    cost = round(sum(_num(chat.get("cost_usd")) for chat in c.chats), 6)
    by_model: dict[str, dict[str, float]] = defaultdict(
        lambda: {"llamadas": 0, "tokens": 0, "costo_usd": 0.0}
    )
    for chat in c.chats:
        model = by_model[str(chat.get("llm_model") or "desconocido")]
        model["llamadas"] += int(chat.get("llm_calls") or 1)
        model["tokens"] += int(chat.get("prompt_tokens") or 0) + int(chat.get("completion_tokens") or 0)
        model["costo_usd"] = round(model["costo_usd"] + _num(chat.get("cost_usd")), 6)
    return {
        "llamadas_llm": sum(int(chat.get("llm_calls") or 1) for chat in c.chats),
        "tokens_entrada": sum(int(chat.get("prompt_tokens") or 0) for chat in c.chats),
        "tokens_salida": sum(int(chat.get("completion_tokens") or 0) for chat in c.chats),
        "costo_usd": cost,
        "costo_por_conversacion_usd": round(cost / n, 6) if n else 0.0,
        "por_modelo": dict(by_model),
    }


def _orchestration(c: _Collector) -> dict[str, Any]:
    by_agent: dict[str, Counter[str]] = defaultdict(Counter)
    for step in c.steps:
        by_agent[str(step.get("agent"))][str(step.get("status", "ok"))] += 1
    total = Counter[str]()
    for counter in by_agent.values():
        total.update(counter)
    return {
        "estados": {s: total.get(s, 0) for s in STATUSES},
        "por_agente": {a: {s: cnt.get(s, 0) for s in STATUSES} for a, cnt in sorted(by_agent.items())},
        "degradaciones_llm": sum(1 for chat in c.chats if chat.get("llm_degraded")),
    }


def summarize(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Resume eventos de telemetría en negocio/ITSM, rendimiento, costos y orquestación."""
    collector = _Collector()
    for event in events:
        collector.add(event)
    return {
        "periodo": {
            "desde": collector.first_ts,
            "hasta": collector.last_ts,
            "eventos_chat": len(collector.chats),
        },
        "negocio": _business(collector),
        "rendimiento": _performance(collector),
        "costos": _costs(collector),
        "orquestacion": _orchestration(collector),
    }

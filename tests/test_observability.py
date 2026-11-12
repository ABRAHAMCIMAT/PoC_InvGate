"""Pruebas de métricas del dashboard, Langfuse, telemetría y audit trail encadenado."""

from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from backend.observability.langfuse import LangfuseExporter
from backend.observability.metrics import _percentile, summarize
from backend.observability.telemetry import Telemetry
from backend.security.audit import AuditLog


def test_summarize_four_dimensions() -> None:
    events = [
        {
            "ts": 1,
            "event": "chat_completed",
            "ticket_id": "T1",
            "category": "acceso",
            "priority": "alta",
            "escalated": True,
            "escalation_level": 2,
            "latency_ms": 100,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost_usd": 0.01,
            "llm_model": "m",
            "llm_calls": 1,
        },
        {
            "ts": 5,
            "event": "chat_completed",
            "ticket_id": None,
            "category": "software",
            "priority": "media",
            "escalated": False,
            "latency_ms": 300,
            "llm_degraded": True,
        },
        {"ts": 2, "event": "agent_step", "agent": "clasificador", "status": "ok", "latency_ms": 4},
        {"ts": 2, "event": "agent_step", "agent": "clasificador", "status": "warning", "latency_ms": 8},
        {"ts": 2, "event": "agent_step", "agent": "ejecucion", "status": "error"},
        {"ts": 3, "event": "approval_requested", "approval_id": "A1"},
        {"ts": 3, "event": "approval_requested", "approval_id": "A2"},
        {
            "ts": 4,
            "event": "approval_decided",
            "approval_id": "A1",
            "decision": "approved",
            "wait_seconds": 60,
        },
        {"ts": 4, "event": "rate_limited"},
        {"event": "otro"},
    ]
    m = summarize(events)
    assert m["periodo"] == {"desde": 1, "hasta": 5, "eventos_chat": 2}
    assert m["negocio"]["tickets_creados"] == 1
    assert m["negocio"]["tasa_escalacion"] == 0.5
    assert m["negocio"]["por_nivel"] == {"2": 1}
    assert m["negocio"]["aprobaciones"] == {
        "solicitadas": 2,
        "aprobadas": 1,
        "rechazadas": 0,
        "pendientes": 1,
        "espera_media_s": 60.0,
    }
    assert m["rendimiento"]["chat_ms"]["p50"] == 200.0
    assert m["rendimiento"]["por_agente_ms"]["clasificador"]["max"] == 8.0
    assert m["rendimiento"]["peticiones_limitadas"] == 1
    assert m["costos"]["tokens_entrada"] == 10
    assert m["costos"]["costo_por_conversacion_usd"] == 0.005
    assert m["costos"]["por_modelo"]["m"]["tokens"] == 15
    assert m["orquestacion"]["estados"] == {"ok": 1, "warning": 1, "error": 1}
    assert m["orquestacion"]["degradaciones_llm"] == 1


def test_summarize_empty() -> None:
    m = summarize([])
    assert m["negocio"]["conversaciones"] == 0
    assert m["costos"]["costo_por_conversacion_usd"] == 0.0
    assert _percentile([], 0.5) == 0.0


def test_metrics_endpoint_after_chats() -> None:
    from backend.server import app

    client = TestClient(app)
    client.post("/api/chat", json={"message": "Olvidé mi contraseña"})
    client.post("/api/chat", json={"message": "Instalar software"})
    m = client.get("/api/metrics").json()
    assert m["negocio"]["conversaciones"] == 2
    assert m["negocio"]["aprobaciones"]["solicitadas"] == 1
    assert sum(m["orquestacion"]["estados"].values()) == 16
    assert m["costos"]["tokens_entrada"] > 0
    assert client.get("/api/metrics?hours=1").json()["negocio"]["conversaciones"] == 2


def test_telemetry_read_skips_corrupt(tmp_path) -> None:
    path = tmp_path / "t.jsonl"
    tel = Telemetry(str(path))
    assert list(tel.read()) == []
    tel.emit("a")
    with open(path, "a") as fh:
        fh.write("{roto\n")
    tel.emit("b")
    assert [e["event"] for e in tel.read()] == ["a", "b"]
    assert list(tel.read(since=10**12)) == []


def test_audit_chain_detects_tampering(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    log.record("a", "x", {"n": 1})
    log.record("b", "x")
    assert log.verify()
    # reabrir continúa la cadena
    log2 = AuditLog(str(path))
    log2.record("c", "y")
    assert log2.verify()
    lines = path.read_text().splitlines()
    tampered = json.loads(lines[1])
    tampered["actor"] = "otro"
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n")
    assert not log2.verify()
    path.write_text(path.read_text() + "no json\n")
    assert not log2.verify()


def test_langfuse_batch_and_send() -> None:
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.url.path, request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(207)

    exp = LangfuseExporter(
        "https://lf.example/", "pk", "sk", transport=httpx.MockTransport(handler), background=False
    )
    trace = {"id": "c1", "start": 1_700_000_000, "input": "hola juan@x.com", "output": "ok"}
    steps = [
        {
            "agent": "clasificador",
            "status": "ok",
            "start": 1_700_000_000,
            "end": 1_700_000_001,
            "model": "llama",
            "prompt_tokens": 3,
            "completion_tokens": 1,
        },
        {"agent": "ejecucion", "status": "error", "start": 1_700_000_001, "end": 1_700_000_002},
    ]
    exp.export(trace, steps)
    path, auth, body = sent[0]
    assert path == "/api/public/ingestion"
    assert auth.startswith("Basic ")
    types = [e["type"] for e in body["batch"]]
    assert types == ["trace-create", "generation-create", "span-create"]
    assert body["batch"][0]["body"]["input"] == "[15 caracteres omitidos]"
    assert body["batch"][1]["body"]["usage"] == {"input": 3, "output": 1, "unit": "TOKENS"}
    assert body["batch"][2]["body"]["level"] == "ERROR"

    with_content = LangfuseExporter("https://lf", "pk", "sk", include_content=True, background=False)
    assert with_content.build_batch(trace, [])[0]["body"]["input"] == "hola [EMAIL]"


def test_langfuse_errors_are_swallowed() -> None:
    def fail(request):
        raise httpx.ConnectError("x")

    LangfuseExporter("https://lf", "pk", "sk", transport=httpx.MockTransport(fail), background=False).export(
        {"id": "c", "start": 0}, []
    )
    LangfuseExporter(
        "https://lf",
        "pk",
        "sk",
        transport=httpx.MockTransport(lambda r: httpx.Response(401)),
        background=False,
    ).export({"id": "c", "start": 0}, [])


def test_langfuse_wired_in_runtime(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    from backend.config import get_settings
    from backend.runtime import get_runtime, reset_runtime

    get_settings.cache_clear()
    reset_runtime()
    rt = get_runtime()
    assert rt.langfuse is not None
    exported = []
    monkeypatch.setattr(rt.langfuse, "export", lambda trace, steps: exported.append((trace, steps)))
    from backend.server import app

    TestClient(app).post("/api/chat", json={"message": "vpn"})
    trace, steps = exported[0]
    assert trace["name"] == "chat"
    assert len(steps) == 8

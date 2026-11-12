"""Estados del semáforo: cada agente reporta ok, warning o error según lo que pasó."""

from __future__ import annotations

from backend.agents.models import AgentRole
from backend.agents.orchestrator import MultiAgentOrchestrator
from backend.approvals.service import ApprovalService
from backend.llmops.llm import LLM, MockLLM
from backend.ticketing.demo import DemoProvider


def _status(results) -> dict[str, str]:
    return {r.role.value: r.status for r in results}


class FixedLLM(LLM):
    name = "fake"
    model = "fake-1"

    def __init__(self, answer: str, degraded: bool = False) -> None:
        super().__init__()
        self.answer = answer
        self._degraded = degraded

    def complete(self, system: str, user: str) -> str:
        self.degraded = self._degraded
        return self.answer


class BrokenProvider(DemoProvider):
    def create_incident(self, incident):
        raise ConnectionError("InvGate no responde")


def test_simple_request_all_green_except_none() -> None:
    orch = MultiAgentOrchestrator(MockLLM(), DemoProvider())
    conv, results = orch.handle("Olvidé mi contraseña")
    statuses = _status(results)
    assert len(results) == 8
    assert results[0].role == AgentRole.COORDINATOR
    assert statuses["clasificador"] == "ok"
    assert statuses["conocimiento"] == "ok"
    assert conv.article_id == "KB-001"
    assert statuses["escalacion"] == "warning"  # prioridad alta -> Nivel 2
    assert conv.escalation_level == 2
    assert all(r.latency_ms >= 0 for r in results)


def test_general_request_is_green() -> None:
    orch = MultiAgentOrchestrator(MockLLM(), DemoProvider())
    conv, results = orch.handle("El correo de outlook no sincroniza")
    assert set(_status(results).values()) == {"ok"}
    assert "Le daremos seguimiento" in conv.messages[-1]["content"]


def test_ticket_failure_is_red_and_escalates() -> None:
    orch = MultiAgentOrchestrator(MockLLM(), BrokenProvider())
    conv, results = orch.handle("Tengo una duda")
    statuses = _status(results)
    assert statuses["ejecucion"] == "error"
    assert statuses["seguimiento"] == "error"
    assert conv.escalation_level == 2
    assert conv.ticket_id is None
    assert "No pude registrar" in conv.messages[-1]["content"]


def test_critical_goes_to_level_3() -> None:
    orch = MultiAgentOrchestrator(MockLLM(), DemoProvider())
    conv, _ = orch.handle("Se cayó producción para todos los usuarios")
    assert conv.priority == "critica"
    assert conv.escalation_level == 3


def test_approval_is_requested_through_service() -> None:
    provider = DemoProvider()
    approvals = ApprovalService(provider, manager_name="Laura")
    orch = MultiAgentOrchestrator(MockLLM(), provider, approvals)
    conv, results = orch.handle("Necesito instalar Photoshop")
    assert conv.approval_id is not None
    assert approvals.get(conv.approval_id).status == "pending"
    assert _status(results)["ejecucion"] == "warning"
    assert "Laura" in results[4].output
    assert provider.get_incident(conv.ticket_id).status.value == "waiting"
    assert "aprobación de tu manager" in conv.messages[-1]["content"]


def test_policy_forces_approval_for_software() -> None:
    orch = MultiAgentOrchestrator(
        FixedLLM("categoria=software;prioridad=baja;requiere_aprobacion=no"), DemoProvider()
    )
    conv, results = orch.handle("Quiero un programa nuevo")
    assert conv.requires_approval is True
    assert "política" in results[3].output
    assert _status(results)["ejecucion"] == "warning"  # sin servicio de aprobaciones


def test_approval_request_failure_is_red() -> None:
    class FailingApprovals(ApprovalService):
        def request_approval(self, *a, **k):
            raise RuntimeError("InvGate rechazó la aprobación")

    provider = DemoProvider()
    orch = MultiAgentOrchestrator(MockLLM(), provider, FailingApprovals(provider))
    _, results = orch.handle("instalar software")
    assert _status(results)["ejecucion"] == "error"


def test_unparseable_classification_is_yellow() -> None:
    orch = MultiAgentOrchestrator(FixedLLM("no sé"), DemoProvider())
    conv, results = orch.handle("mensaje extraño")
    statuses = _status(results)
    assert statuses["clasificador"] == "warning"
    assert conv.category == "general"
    assert conv.priority == "media"
    assert statuses["diagnostico"] == "ok"  # con LLM real, el diagnóstico es su respuesta
    assert statuses["conocimiento"] == "warning"


def test_degraded_llm_is_yellow() -> None:
    orch = MultiAgentOrchestrator(
        FixedLLM("categoria=acceso;prioridad=media;requiere_aprobacion=no", degraded=True), DemoProvider()
    )
    _, results = orch.handle("vpn")
    assert results[1].status == "warning"
    assert "respaldo" in results[1].output


def test_agent_exception_does_not_break_flow(monkeypatch) -> None:
    orch = MultiAgentOrchestrator(MockLLM(), DemoProvider())

    def boom(*a, **k):
        raise ValueError("kb rota")

    monkeypatch.setattr(orch.kb, "search", boom)
    conv, results = orch.handle("olvidé mi contraseña")
    assert _status(results)["conocimiento"] == "error"
    assert conv.ticket_id is not None


def test_comment_failures_are_tolerated(monkeypatch) -> None:
    provider = DemoProvider()

    def no_comments(*a, **k):
        raise ConnectionError("x")

    monkeypatch.setattr(provider, "add_comment", no_comments)
    orch = MultiAgentOrchestrator(MockLLM(), provider)
    _, results = orch.handle("Mi laptop no enciende")
    assert _status(results)["conocimiento"] == "ok"
    assert _status(results)["escalacion"] == "warning"


def test_run_streams_incrementally() -> None:
    orch = MultiAgentOrchestrator(MockLLM(), DemoProvider())
    conv = orch.new_conversation("Olvidé mi contraseña")
    gen = orch.run(conv)
    first = next(gen)
    assert first.role == AgentRole.COORDINATOR
    assert conv.ticket_id is None  # aún no ha corrido Ejecución
    rest = list(gen)
    assert len(rest) == 7
    assert conv.ticket_id is not None

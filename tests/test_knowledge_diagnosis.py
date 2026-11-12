"""Pruebas de la base de conocimiento y del agente de diagnóstico."""

from __future__ import annotations

from backend.agents.diagnosis import diagnose
from backend.agents.knowledge import KnowledgeBase
from backend.llmops.llm import LLM, LLMError, MockLLM


def test_kb_finds_best_article() -> None:
    kb = KnowledgeBase.load()
    assert kb.search("Olvidé mi contraseña de red").id == "KB-001"
    assert kb.search("La impresora no imprime", "hardware").id == "KB-005"
    assert kb.search("xyz") is None
    assert kb.search("vpn", min_score=5) is None


def test_diagnosis_rules() -> None:
    assert diagnose("Mi cuenta está bloqueada", "acceso").confident
    assert "alimentación" in diagnose("La laptop no enciende", "hardware").cause
    # palabra clave de otra categoría
    assert "Impresora" in diagnose("la impresora falla", "general").cause
    unknown = diagnose("algo pasa", "general")
    assert unknown.confident is False


class Answer(LLM):
    name = "ollama"

    def __init__(self, text: str = "", fail: bool = False, degraded: bool = False) -> None:
        super().__init__()
        self.text, self.fail, self._deg = text, fail, degraded

    def complete(self, system: str, user: str) -> str:
        if self.fail:
            raise LLMError("x")
        self.degraded = self._deg
        return self.text


def test_diagnosis_with_llm() -> None:
    assert diagnose("algo", None, Answer("Disco lleno.\nOtra línea")).cause == "Disco lleno."
    # si el LLM falla o está degradado, se usan las reglas
    assert diagnose("no enciende", "hardware", Answer(fail=True)).confident
    assert not diagnose("algo", None, Answer("x", degraded=True)).confident
    assert diagnose("no enciende", "hardware", MockLLM()).confident

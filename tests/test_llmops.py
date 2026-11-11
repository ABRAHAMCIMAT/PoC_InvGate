"""Pruebas del LLM mock."""

from __future__ import annotations

from backend.llmops.llm import MockLLM, get_llm


def test_mock_classifies_access() -> None:
    llm = MockLLM()
    out = llm.complete("", "Se me olvidó mi contraseña")
    assert "categoria=acceso" in out


def test_mock_classifies_software() -> None:
    llm = MockLLM()
    out = llm.complete("", "Instalar software de diseño")
    assert "requiere_aprobacion=si" in out


def test_get_llm_mock() -> None:
    assert isinstance(get_llm("mock"), MockLLM)

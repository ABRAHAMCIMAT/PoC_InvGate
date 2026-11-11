"""Pruebas adicionales del LLM mock."""

from __future__ import annotations

import pytest

from backend.llmops.llm import MockLLM, get_llm


def test_mock_classifies_hardware() -> None:
    llm = MockLLM()
    out = llm.complete("", "Mi laptop no enciende")
    assert "categoria=hardware" in out
    assert "prioridad=alta" in out


def test_mock_classifies_general() -> None:
    llm = MockLLM()
    out = llm.complete("", "Tengo una duda")
    assert "categoria=general" in out


def test_get_llm_unsupported() -> None:
    with pytest.raises(ValueError):
        get_llm("openai")

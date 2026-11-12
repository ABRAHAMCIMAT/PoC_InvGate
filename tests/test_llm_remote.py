"""Pruebas del LLM compatible con OpenAI (Ollama/Jan) y del respaldo al mock."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.llmops.llm import FallbackLLM, LLMError, MockLLM, OpenAICompatibleLLM, estimate_tokens, get_llm


def _llm(handler) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        "http://ollama:11434/v1",
        "llama3.1:8b",
        api_key="k",
        name="ollama",
        transport=httpx.MockTransport(handler),
    )


def test_completion_and_usage() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": " categoria=acceso;prioridad=alta "}}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 9},
            },
        )

    llm = _llm(handler)
    assert llm.complete("sys", "hola") == "categoria=acceso;prioridad=alta"
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "llama3.1:8b"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert llm.last_usage.total == 49


def test_usage_estimated_when_missing() -> None:
    llm = _llm(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "abcdefgh"}}]}))
    llm.complete("s" * 40, "u" * 40)
    assert llm.last_usage.prompt_tokens == 20
    assert llm.last_usage.completion_tokens == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="fallo"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="x"),
    ],
)
def test_errors_raise_llm_error(response) -> None:
    llm = _llm(lambda r: response)
    with pytest.raises(LLMError):
        llm.complete("s", "u")


def test_connection_error() -> None:
    def handler(request):
        raise httpx.ConnectError("sin servidor")

    llm = _llm(handler)
    with pytest.raises(LLMError):
        llm.complete("s", "u")


def test_requires_model() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleLLM("http://x", "")


def test_fallback_to_mock() -> None:
    def handler(request):
        raise httpx.ConnectError("caído")

    llm = FallbackLLM(_llm(handler))
    out = llm.complete("s", "olvidé mi contraseña")
    assert "categoria=acceso" in out
    assert llm.degraded is True
    assert llm.name == "mock"


def test_fallback_uses_primary_when_ok() -> None:
    primary = _llm(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}))
    llm = FallbackLLM(primary)
    assert llm.complete("s", "u") == "ok"
    assert llm.degraded is False
    assert llm.model == "llama3.1:8b"


def test_get_llm_variants() -> None:
    assert isinstance(get_llm("mock"), MockLLM)
    ollama = get_llm("ollama")
    assert isinstance(ollama, FallbackLLM)
    assert ollama.primary.model == "llama3.1:8b"
    jan = get_llm("jan", model="custom")
    assert jan.primary.model == "custom"
    with pytest.raises(ValueError):
        get_llm("openai_compatible")  # sin modelo


def test_mock_extras() -> None:
    assert "prioridad=critica" in MockLLM().complete("", "Se cayó producción")
    assert estimate_tokens("") == 0

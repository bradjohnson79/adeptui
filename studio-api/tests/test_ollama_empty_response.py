"""Ollama empty-response classification and thinking-content extraction."""

from __future__ import annotations

import asyncio

import pytest

from app.codirector.errors import OLLAMA_EMPTY_RESPONSE, CoDirectorError
from app.codirector.providers.base import ChatRequest, ProviderHealthResult
from app.codirector.providers import ollama as ollama_mod
from app.codirector.providers.ollama import OllamaProvider, _message_text, parse_stream_line


def test_message_text_prefers_content():
    assert _message_text({"content": "Hello", "thinking": "plan"}) == "Hello"


def test_message_text_never_promotes_thinking():
    """Thinking/reasoning must stay server-only — never become creator-facing content."""
    assert _message_text({"content": "", "thinking": "Internal plan only"}) == ""
    assert _message_text({"content": "", "reasoning": "Analyze User Input"}) == ""


def test_message_text_empty():
    assert _message_text({"content": "  ", "thinking": ""}) == ""
    assert _message_text(None) == ""


def test_parse_stream_line_ok():
    assert parse_stream_line('{"message":{"content":"a"},"done":false}')["message"]["content"] == "a"


def test_generate_raises_ollama_empty_response(monkeypatch):
    async def empty_chat(_client, _endpoint, _payload):
        return {"message": {"content": "", "thinking": ""}, "eval_count": 0}

    monkeypatch.setattr(ollama_mod, "_chat_once", empty_chat)

    provider = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3.6:35b-a3b")

    async def fake_health(*, force: bool = False):
        return ProviderHealthResult(
            provider_id="ollama",
            display_name="Ollama",
            status="Ready",
            reachable=True,
            endpoint=provider.endpoint,
            selected_model="qwen3.6:35b-a3b",
            model_available=True,
            models=[],
        )

    monkeypatch.setattr(provider, "health", fake_health)
    monkeypatch.setattr(provider, "_resolve_model", lambda request, health: "qwen3.6:35b-a3b")

    req = ChatRequest(request_id="r1", messages=[{"role": "user", "content": "hi"}], model_id="qwen3.6:35b-a3b")

    async def _run():
        with pytest.raises(CoDirectorError) as exc:
            await provider.generate(req)
        assert exc.value.code == OLLAMA_EMPTY_RESPONSE

    asyncio.run(_run())

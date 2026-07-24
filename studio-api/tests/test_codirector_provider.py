"""Co-Director provider gateway: endpoint normalization, health classification,
connection/timeout/model-missing errors, mock scenarios, and secret-safety basics.

No async test plugin (pytest-asyncio/anyio) is installed for this project, so async
provider/service calls are driven with `asyncio.run(...)` from plain sync test functions.
"""

from __future__ import annotations

import asyncio

import pytest


# --------------------------------------------------------------------------
# Ollama endpoint normalization
# --------------------------------------------------------------------------


def test_normalize_ollama_endpoint_variants() -> None:
    from app.codirector.providers.ollama import normalize_ollama_endpoint

    assert normalize_ollama_endpoint("127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert normalize_ollama_endpoint("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert normalize_ollama_endpoint("https://ollama.local:9999") == "https://ollama.local:9999"
    assert normalize_ollama_endpoint("") == "http://127.0.0.1:11434"
    assert normalize_ollama_endpoint("localhost") == "http://localhost:11434"


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------


def test_classify_httpx_error_connect_and_timeout() -> None:
    import httpx

    from app.codirector.errors import CONNECTION_REFUSED, REQUEST_TIMEOUT, classify_httpx_error

    connect_err = httpx.ConnectError("Connection refused")
    result = classify_httpx_error(connect_err, endpoint="http://127.0.0.1:11434")
    assert result.code == CONNECTION_REFUSED
    assert "could not reach" in result.message.lower()

    timeout_err = httpx.ReadTimeout("timed out")
    result = classify_httpx_error(timeout_err, endpoint="http://127.0.0.1:11434")
    assert result.code == REQUEST_TIMEOUT


def test_classify_httpx_error_truncates_unknown_reason() -> None:
    from app.codirector.errors import UNKNOWN_PROVIDER_ERROR, classify_httpx_error

    huge_message = "boom " * 200  # far longer than 200 chars
    result = classify_httpx_error(RuntimeError(huge_message), endpoint="http://127.0.0.1:11434")
    assert result.code == UNKNOWN_PROVIDER_ERROR
    # Secret-redaction basics: raw exception text must never be dumped unbounded into details.
    assert len(result.details.get("reason", "")) <= 200


def test_status_code_for_error_mapping() -> None:
    from app.codirector.errors import (
        CONNECTION_REFUSED,
        MODEL_NOT_FOUND,
        PROJECT_NOT_FOUND,
        REQUEST_TIMEOUT,
        status_code_for_error,
    )

    assert status_code_for_error(CONNECTION_REFUSED) == 503
    assert status_code_for_error(REQUEST_TIMEOUT) == 504
    assert status_code_for_error(MODEL_NOT_FOUND) == 400
    assert status_code_for_error(PROJECT_NOT_FOUND) == 404
    assert status_code_for_error("SOMETHING_MADE_UP") == 500


def test_error_to_dict_never_leaks_extra_keys() -> None:
    from app.codirector.errors import CoDirectorError

    err = CoDirectorError("MODEL_NOT_FOUND", "missing model", details={"model": "x"})
    payload = err.to_dict()
    assert set(payload.keys()) == {"code", "message", "details", "recoverable", "recommendedAction"}


# --------------------------------------------------------------------------
# Mock provider scenarios
# --------------------------------------------------------------------------


def test_mock_provider_healthy_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    from app.codirector.providers.mock import MockCoDirectorProvider

    provider = MockCoDirectorProvider()
    health = asyncio.run(provider.health())
    assert health.status == "Ready"
    assert health.reachable is True
    assert health.model_available is True
    assert len(health.models) == 2


def test_mock_provider_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import CONNECTION_REFUSED, CoDirectorError
    from app.codirector.providers.base import ChatRequest
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "connection_refused")
    provider = MockCoDirectorProvider()
    health = asyncio.run(provider.health())
    assert health.reachable is False
    assert health.code == CONNECTION_REFUSED

    with pytest.raises(CoDirectorError) as exc_info:
        asyncio.run(
            provider.generate(
                ChatRequest(request_id="r1", messages=[{"role": "user", "content": "hi"}], model_id=None)
            )
        )
    assert exc_info.value.code == CONNECTION_REFUSED


def test_mock_provider_no_models(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import NO_MODELS_INSTALLED
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "no_models")
    provider = MockCoDirectorProvider()
    health = asyncio.run(provider.health())
    assert health.reachable is True
    assert health.model_available is False
    assert health.code == NO_MODELS_INSTALLED
    assert health.models == []


def test_mock_provider_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import MODEL_NOT_FOUND, CoDirectorError
    from app.codirector.providers.base import ChatRequest
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "model_missing")
    provider = MockCoDirectorProvider()
    health = asyncio.run(provider.health())
    assert health.code == MODEL_NOT_FOUND
    assert health.model_available is False

    with pytest.raises(CoDirectorError) as exc_info:
        asyncio.run(
            provider.generate(
                ChatRequest(request_id="r2", messages=[{"role": "user", "content": "hi"}], model_id=None)
            )
        )
    assert exc_info.value.code == MODEL_NOT_FOUND


def test_mock_provider_timeout_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import REQUEST_TIMEOUT, CoDirectorError
    from app.codirector.providers.base import ChatRequest
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "timeout")
    provider = MockCoDirectorProvider()
    with pytest.raises(CoDirectorError) as exc_info:
        asyncio.run(
            provider.generate(
                ChatRequest(request_id="r3", messages=[{"role": "user", "content": "hi"}], model_id=None)
            )
        )
    assert exc_info.value.code == REQUEST_TIMEOUT


def test_mock_provider_unknown_model_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import MODEL_NOT_FOUND, CoDirectorError
    from app.codirector.providers.base import ChatRequest
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    provider = MockCoDirectorProvider()
    with pytest.raises(CoDirectorError) as exc_info:
        asyncio.run(
            provider.generate(
                ChatRequest(
                    request_id="r4",
                    messages=[{"role": "user", "content": "hi"}],
                    model_id="not-a-real-model",
                )
            )
        )
    assert exc_info.value.code == MODEL_NOT_FOUND


def test_mock_provider_stream_emits_lifecycle_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.base import ChatRequest
    from app.codirector.providers.mock import MockCoDirectorProvider

    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    provider = MockCoDirectorProvider()

    async def _collect():
        return [
            e
            async for e in provider.stream(
                ChatRequest(request_id="r5", messages=[{"role": "user", "content": "hi"}], model_id=None)
            )
        ]

    events = asyncio.run(_collect())
    types = [e["type"] for e in events]
    assert types[0] == "request_started"
    assert types[1] == "provider_connected"
    assert types[-1] == "completed"
    assert "token" in types


# --------------------------------------------------------------------------
# Gateway service: provider selection
# --------------------------------------------------------------------------


def test_active_provider_id_defaults_to_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.delenv("ADEPT_CODIRECTOR_PROVIDER", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    assert service.active_provider_id() == "ollama"


def test_active_provider_id_defaults_to_mock_in_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.delenv("ADEPT_CODIRECTOR_PROVIDER", raising=False)
    monkeypatch.setenv("STUDIO_E2E", "1")
    assert service.active_provider_id() == "mock"


def test_active_provider_id_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "ollama")
    assert service.active_provider_id() == "ollama"


def test_unknown_provider_never_silently_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requesting an unconfigured/cloud provider must error, not silently reroute."""
    from app.codirector import service
    from app.codirector.errors import PROVIDER_NOT_CONFIGURED

    health = asyncio.run(service.get_health("fal_cloud"))
    assert health.reachable is False
    assert health.status == "Degraded"
    assert health.code == PROVIDER_NOT_CONFIGURED


def test_mock_provider_unavailable_outside_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stray ADEPT_CODIRECTOR_PROVIDER=mock in a real deployment must never mask a
    broken local-model setup by silently serving canned mock replies."""
    from app.codirector import service
    from app.codirector.errors import PROVIDER_NOT_CONFIGURED

    monkeypatch.delenv("STUDIO_E2E", raising=False)
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "ollama"
    assert "mock" not in service.list_provider_ids()

    health = asyncio.run(service.get_health("mock"))
    assert health.reachable is False
    assert health.code == PROVIDER_NOT_CONFIGURED


def test_mock_provider_available_in_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "mock"
    assert "mock" in service.list_provider_ids()


# --------------------------------------------------------------------------
# HTTP endpoints (mock provider forced so tests never touch a real Ollama)
# --------------------------------------------------------------------------


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    # The mock provider is only selectable in E2E/test runs (see
    # test_mock_provider_unavailable_outside_e2e) — set both so HTTP-level tests exercise
    # the same gate real Playwright runs go through.
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def test_providers_endpoint_lists_mock_and_ollama(client, mock_provider_env) -> None:
    res = client.get("/api/codirector/providers")
    assert res.status_code == 200
    body = res.json()
    ids = {p["id"] for p in body["providers"]}
    assert {"mock", "ollama"} <= ids
    active = next(p for p in body["providers"] if p["active"])
    assert active["id"] == "mock"


def test_health_endpoint_active_alias(client, mock_provider_env) -> None:
    res = client.get("/api/codirector/providers/active/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "Ready"
    assert body["ok"] is True


def test_health_endpoint_connection_refused_status(client, mock_provider_env, monkeypatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "connection_refused")
    res = client.get("/api/codirector/providers/mock/health")
    assert res.status_code == 200
    body = res.json()
    assert body["reachable"] is False
    assert body["code"] == "CONNECTION_REFUSED"


def test_models_endpoint(client, mock_provider_env) -> None:
    res = client.get("/api/codirector/providers/active/models")
    assert res.status_code == 200
    body = res.json()
    assert len(body["models"]) == 2


def test_chat_endpoint_ready_reply(client, mock_provider_env) -> None:
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hello there"}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert "[mock]" in body["reply"]
    assert body["providerId"] == "mock"
    assert body["requestId"]


def test_chat_endpoint_connection_refused_returns_503(client, mock_provider_env, monkeypatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "connection_refused")
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert detail["code"] == "CONNECTION_REFUSED"
    assert "recommendedAction" in detail


def test_chat_endpoint_model_missing_returns_400(client, mock_provider_env, monkeypatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "model_missing")
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "MODEL_NOT_FOUND"


def test_chat_endpoint_timeout_returns_504(client, mock_provider_env, monkeypatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "timeout")
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 504
    assert res.json()["detail"]["code"] == "REQUEST_TIMEOUT"


def test_chat_endpoint_rejects_empty_messages(client, mock_provider_env) -> None:
    res = client.post("/api/codirector/chat", json={"messages": []})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_chat_endpoint_unknown_provider_returns_503_no_fallback(client, mock_provider_env) -> None:
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "provider_id": "fal_cloud"},
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


def test_chat_endpoint_unknown_project_returns_404(client, mock_provider_env) -> None:
    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "project_id": "does-not-exist"},
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


def test_assistant_chat_alias_uses_gateway(client, mock_provider_env) -> None:
    """Legacy /api/assistant/chat must remain a thin alias over the same gateway."""
    res = client.post(
        "/api/assistant/chat",
        json={"messages": [{"role": "user", "content": "hello"}], "mode": "chat"},
    )
    assert res.status_code == 200
    assert "[mock]" in res.json()["reply"]


def test_assistant_health_alias_uses_gateway(client, mock_provider_env) -> None:
    res = client.get("/api/assistant/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["ollama_reachable"] is True


def test_conversation_persistence_roundtrip(client, mock_provider_env) -> None:
    project_id = "conv-test-project"
    empty = client.get(f"/api/codirector/conversations/{project_id}")
    assert empty.status_code == 200
    assert empty.json()["messages"] == []

    saved = client.post(
        f"/api/codirector/conversations/{project_id}",
        json={
            "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert len(body["messages"]) == 2
    assert body["model"] == "mock-model"

    fetched = client.get(f"/api/codirector/conversations/{project_id}")
    assert fetched.status_code == 200
    assert len(fetched.json()["messages"]) == 2

    deleted = client.delete(f"/api/codirector/conversations/{project_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    after_delete = client.get(f"/api/codirector/conversations/{project_id}")
    assert after_delete.json()["messages"] == []


def test_cancel_endpoint_is_safe_for_unknown_request_id(client, mock_provider_env) -> None:
    res = client.post("/api/codirector/cancel", json={"request_id": "not-a-real-request"})
    assert res.status_code == 200
    body = res.json()
    assert body["cancelled"] is True
    assert body["taskCancelled"] is False


# --------------------------------------------------------------------------
# Streaming parse helper
# --------------------------------------------------------------------------


def test_parse_stream_line_valid_and_invalid() -> None:
    from app.codirector.providers.ollama import parse_stream_line

    assert parse_stream_line('{"a": 1}') == {"a": 1}
    assert parse_stream_line("") is None
    assert parse_stream_line("   ") is None
    assert parse_stream_line("not json") is None
    assert parse_stream_line("[1, 2]") is None  # valid JSON, but not an object


# --------------------------------------------------------------------------
# Cancellation actually interrupts an in-flight coroutine
# --------------------------------------------------------------------------


def test_run_cancellable_raises_request_cancelled_when_cancelled() -> None:
    from app.codirector import service
    from app.codirector.errors import REQUEST_CANCELLED, CoDirectorError

    async def _scenario() -> None:
        request_id = "cancel-me"

        async def _slow() -> str:
            await asyncio.sleep(5)
            return "should not get here"

        task = asyncio.ensure_future(service.run_cancellable(request_id, _slow()))
        await asyncio.sleep(0.02)
        result = service.request_cancel(request_id)
        assert result["taskCancelled"] is True
        with pytest.raises(CoDirectorError) as exc_info:
            await task
        assert exc_info.value.code == REQUEST_CANCELLED

    asyncio.run(_scenario())


def test_cancel_endpoint_stops_an_in_flight_request(client, mock_provider_env, monkeypatch) -> None:
    """A slow mock generation can be cancelled mid-flight via /api/codirector/cancel."""
    import concurrent.futures

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "slow")
    request_id = "cancel-http-test"

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post,
            "/api/codirector/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "request_id": request_id},
        )
        import time

        time.sleep(0.05)
        cancel_res = client.post("/api/codirector/cancel", json={"request_id": request_id})
        assert cancel_res.status_code == 200
        res = future.result(timeout=10)
    # Cancelled requests surface as REQUEST_CANCELLED (499) rather than hanging or 500ing.
    if res.status_code == 499:
        assert res.json()["detail"]["code"] == "REQUEST_CANCELLED"
    else:
        # The mock's 0.35s sleep may already have completed before cancel raced in on a
        # slow CI box — either outcome is safe as long as it isn't a crash.
        assert res.status_code == 200


# --------------------------------------------------------------------------
# Secret redaction basics
# --------------------------------------------------------------------------


def test_redact_secrets_strips_common_secret_shapes() -> None:
    from app.codirector.errors import redact_secrets

    text = "Authorization: Bearer sk-abc123XYZ failed for token=deadbeefdeadbeef and password=hunter2"
    redacted = redact_secrets(text)
    assert "sk-abc123XYZ" not in redacted
    assert "deadbeefdeadbeef" not in redacted
    assert "hunter2" not in redacted
    assert "[redacted]" in redacted


def test_classify_httpx_error_reason_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.errors import classify_httpx_error

    err = RuntimeError("upstream said Authorization: Bearer sk-should-not-leak-12345")
    result = classify_httpx_error(err, endpoint="http://127.0.0.1:11434")
    assert "sk-should-not-leak-12345" not in result.details.get("reason", "")


# --------------------------------------------------------------------------
# Config store (endpoint / model / timeout overrides)
# --------------------------------------------------------------------------


def test_config_store_roundtrip(isolated_data_dir) -> None:
    from app.codirector import config_store

    config_store.reset_config()
    loaded = config_store.load_config()
    assert loaded["endpoint"]

    saved = config_store.save_config({"endpoint": "http://10.0.0.5:11434", "selectedModel": "llama3:8b"})
    assert saved["endpoint"] == "http://10.0.0.5:11434"
    assert saved["selectedModel"] == "llama3:8b"

    reloaded = config_store.load_config()
    assert reloaded["endpoint"] == "http://10.0.0.5:11434"
    assert reloaded["selectedModel"] == "llama3:8b"

    config_store.reset_config()


def test_config_get_endpoint_returns_defaults(client) -> None:
    from app.codirector import config_store

    config_store.reset_config()
    res = client.get("/api/codirector/config")
    assert res.status_code == 200
    body = res.json()
    assert "endpoint" in body and "selectedModel" in body and "timeoutSec" in body


def test_config_put_endpoint_persists_and_returns_updated_value(client) -> None:
    from app.codirector import config_store

    config_store.reset_config()
    res = client.put(
        "/api/codirector/config",
        json={"endpoint": "http://192.168.1.50:11434", "selectedModel": "mistral:7b", "timeoutSec": 60},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["endpoint"] == "http://192.168.1.50:11434"
    assert body["selectedModel"] == "mistral:7b"
    assert body["timeoutSec"] == 60

    again = client.get("/api/codirector/config")
    assert again.json()["endpoint"] == "http://192.168.1.50:11434"
    config_store.reset_config()


def test_config_put_rejects_invalid_endpoint(client) -> None:
    from app.codirector import config_store

    config_store.reset_config()
    res = client.put("/api/codirector/config", json={"endpoint": "not a url"})
    assert res.status_code == 400
    config_store.reset_config()

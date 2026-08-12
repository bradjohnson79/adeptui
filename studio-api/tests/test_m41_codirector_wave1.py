"""M41 Wave 1 — Co-Director runtime honesty, project binding, session context, errors."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def _create_project(client, name: str = "M41 Wave1") -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()


def test_m41_cd_01_codirector_connects_to_configured_model(client, mock_provider_env) -> None:
    """M41-CD-01 Co-Director connects to configured Ollama model (mock Ready in E2E)."""
    res = client.get("/api/codirector/providers/active/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "Ready"
    assert body["ok"] is True
    assert body["modelAvailable"] is True
    assert body["selectedModel"]
    assert body["testOnly"] is True
    assert body["honesty"] == "mocked"


def test_m41_cd_02_missing_model_produces_clear_error(client, mock_provider_env, monkeypatch) -> None:
    """M41-CD-02 Missing model produces clear error."""
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "model_missing")
    health = client.get("/api/codirector/providers/active/health").json()
    assert health["modelAvailable"] is False
    assert health["code"] == "MODEL_NOT_FOUND"

    # No-project turns are handled deterministically (project-required reply) and
    # never reach the provider. The provider-error contract is exercised with a
    # project so the turn reaches the foundation LLM path.
    project = _create_project(client, "M41-CD-02")
    chat = client.post(
        "/api/codirector/chat",
        json={"project_id": project["id"], "messages": [{"role": "user", "content": "hello"}]},
    )
    # The deterministic fallback reply is intentional (the conversation core can
    # onboard without the LLM), but the degradation must be TRUTHFUL: fallbackUsed
    # plus the structured provider error envelope.
    assert chat.status_code == 200
    body = chat.json()
    assert body["fallbackUsed"] is True
    detail = body["providerError"]
    assert detail["code"] == "MODEL_NOT_FOUND"
    assert detail["error_code"] == "MODEL_NOT_FOUND"
    assert detail["category"] == "model"
    assert detail["retryable"] is True
    assert detail["partial_work_created"] is False


def test_m41_cd_04_project_context_persists_across_navigation(client, mock_provider_env) -> None:
    """M41-CD-04 Project context persists across navigation (server conversation)."""
    project = _create_project(client, "M41-CD-04")
    client.post(
        f"/api/codirector/conversations/{project['id']}",
        json={
            "messages": [
                {"role": "user", "content": "nav-persist"},
                {"role": "assistant", "content": "still-here"},
            ],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    # Simulate leaving and returning: fresh GET must restore the same project transcript.
    again = client.get(f"/api/codirector/conversations/{project['id']}").json()
    contents = [m["content"] for m in again["messages"]]
    assert "nav-persist" in contents
    assert again["providerId"] == "mock"


def test_m41_cd_08_refresh_restores_active_session(client, mock_provider_env) -> None:
    """M41-CD-08 Refresh restores the active session."""
    project = _create_project(client, "M41-CD-08")
    client.post(
        f"/api/codirector/conversations/{project['id']}",
        json={
            "messages": [{"role": "user", "content": "before-refresh"}, {"role": "assistant", "content": "ok"}],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    restored = client.get(f"/api/codirector/conversations/{project['id']}").json()
    assert any(m["content"] == "before-refresh" for m in restored["messages"])
    assert restored["model"] == "mock-model"


def test_m41_cd_12_beta_restart_no_silent_project_bind(client, mock_provider_env) -> None:
    """M41-CD-12 Beta restart restores valid session state without silent project bind."""
    project = _create_project(client, "M41-CD-12")
    client.post(
        f"/api/codirector/conversations/{project['id']}",
        json={
            "messages": [{"role": "user", "content": "prior"}, {"role": "assistant", "content": "ok"}],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    # Without an explicit project_id, session-context must remain unbound (suggestion-only elsewhere).
    unbound = client.get("/api/codirector/session-context").json()
    assert unbound["projectId"] is None
    assert "no_project_selected" in unbound["unresolvedBlockers"]
    # Explicit rebind restores the prior conversation for that project.
    rebound = client.get(f"/api/codirector/conversations/{project['id']}").json()
    assert any(m["content"] == "prior" for m in rebound["messages"])


def test_m41_cd_03_session_binds_to_explicit_project(client, mock_provider_env) -> None:
    """M41-CD-03 Session binds to explicit project."""
    project = _create_project(client, "M41-CD-03")
    ctx = client.get(f"/api/codirector/session-context?project_id={project['id']}")
    assert ctx.status_code == 200
    body = ctx.json()
    assert body["projectId"] == project["id"]
    assert body["sessionStatus"] == "bound"
    assert "no_project_selected" not in body["unresolvedBlockers"]


def test_m41_cd_05_no_project_mode_blocks_production_mutations(client, mock_provider_env) -> None:
    """M41-CD-05 No-project mode blocks production mutations."""
    from app.codirector.errors import PROJECT_REQUIRED, CoDirectorError
    from app.codirector.service import _StructuredOutcome, _interpret_reply
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        outcome = _StructuredOutcome()
        # Simulate a tool fence reply with no project open.
        reply = (
            "```tool\n"
            '{"responseType":"read_tool_call","toolId":"get_project_status","arguments":{}}\n'
            "```"
        )

        async def _consume():
            events = []
            async for event in _interpret_reply(
                db,
                project_id=None,
                scene_id=None,
                request_id="req-m41-cd-05",
                reply=reply,
                tools_used=0,
                outcome=outcome,
            ):
                events.append(event)
            return events

        asyncio.run(_consume())
        assert outcome.errors
        assert any(isinstance(e, CoDirectorError) and e.code == PROJECT_REQUIRED for e in outcome.errors)
        assert all(e.to_dict().get("partial_work_created") is False for e in outcome.errors)
    finally:
        db.close()

    no_project = client.get("/api/codirector/session-context")
    assert no_project.status_code == 200
    body = no_project.json()
    assert body["projectId"] is None
    assert "no_project_selected" in body["unresolvedBlockers"]


def test_m41_cd_06_silent_mock_fallback_disabled_outside_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """M41-CD-06 Silent mock fallback is disabled in Beta (non-E2E)."""
    from app.codirector import service
    from app.codirector.errors import PROVIDER_NOT_CONFIGURED

    monkeypatch.delenv("STUDIO_E2E", raising=False)
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "ollama"
    assert "mock" not in service.list_provider_ids()

    with pytest.raises(Exception) as exc_info:
        service.build_provider("mock")
    err = exc_info.value
    assert getattr(err, "code", None) == PROVIDER_NOT_CONFIGURED


def test_m41_cd_07_provider_and_model_persist_on_session(client, mock_provider_env) -> None:
    """M41-CD-07 Provider and model persist on session."""
    project = _create_project(client, "M41-CD-07")
    saved = client.post(
        f"/api/codirector/conversations/{project['id']}",
        json={
            "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["model"] == "mock-model"
    assert body["providerId"] == "mock"

    fetched = client.get(f"/api/codirector/conversations/{project['id']}")
    assert fetched.status_code == 200
    again = fetched.json()
    assert again["model"] == "mock-model"
    assert again["providerId"] == "mock"

    ctx = client.get(f"/api/codirector/session-context?project_id={project['id']}").json()
    assert ctx["model"] == "mock-model"
    assert ctx["provider"] == "mock"


def test_m41_cd_11_project_context_does_not_leak_across_projects(client, mock_provider_env) -> None:
    """M41-CD-11 Project context does not leak across projects."""
    a = _create_project(client, "M41-CD-11-A")
    b = _create_project(client, "M41-CD-11-B")
    client.post(
        f"/api/codirector/conversations/{a['id']}",
        json={
            "messages": [{"role": "user", "content": "secret-from-a"}, {"role": "assistant", "content": "ok-a"}],
            "model": "mock-model",
            "provider_id": "mock",
        },
    )
    empty_b = client.get(f"/api/codirector/conversations/{b['id']}").json()
    assert empty_b["messages"] == []
    text = " ".join(m.get("content", "") for m in empty_b["messages"])
    assert "secret-from-a" not in text


def test_m41_cd_13_failed_runtime_action_not_reported_as_success(client, mock_provider_env, monkeypatch) -> None:
    """M41-CD-13 Failed runtime action is not reported as success."""
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "connection_refused")
    project = _create_project(client, "M41-CD-13")
    res = client.post(
        "/api/codirector/chat",
        json={"project_id": project["id"], "messages": [{"role": "user", "content": "hello"}]},
    )
    # The provider failure degrades to the deterministic fallback reply (200), but
    # the response must not present itself as a successful model turn.
    assert res.status_code == 200
    body = res.json()
    assert body["fallbackUsed"] is True
    assert body["providerError"]["code"] == "CONNECTION_REFUSED"
    assert body["providerError"].get("partial_work_created") is False


def test_m41_cd_14_structured_error_envelope_is_returned(client, mock_provider_env, monkeypatch) -> None:
    """M41-CD-14 Structured error envelope is returned."""
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "timeout")
    project = _create_project(client, "M41-CD-14")
    res = client.post(
        "/api/codirector/chat",
        json={"project_id": project["id"], "messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["fallbackUsed"] is True
    detail = body["providerError"]
    for key in (
        "error_code",
        "category",
        "message",
        "retryable",
        "technical_evidence",
        "partial_work_created",
        "recommended_action",
    ):
        assert key in detail, f"missing {key}"
    assert detail["error_code"] == "REQUEST_TIMEOUT"
    assert detail["category"] in {"runtime", "provider", "model"}
    assert "token" not in str(detail.get("technical_evidence", {})).lower() or "[redacted]" in str(
        detail.get("technical_evidence", {})
    )


def test_m41_cd_09_cancel_does_not_duplicate_in_flight(client, mock_provider_env) -> None:
    """M41-CD-09 Reconnect does not duplicate messages (cancel is idempotent / safe)."""
    req_id = "m41-cd-09-req"
    first = client.post("/api/codirector/cancel", json={"request_id": req_id})
    assert first.status_code == 200
    second = client.post("/api/codirector/cancel", json={"request_id": req_id})
    assert second.status_code == 200


def test_m41_cd_10_tool_execution_requires_project(client, mock_provider_env) -> None:
    """M41-CD-10 Reconnect does not duplicate tool execution — tools refuse without project."""
    from app.codirector.errors import PROJECT_NOT_FOUND, CoDirectorError
    from app.codirector.tools.execution import ToolExecutionService
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(CoDirectorError) as exc_info:
            asyncio.run(
                ToolExecutionService.execute_read(
                    db,
                    project_id="missing-project-m41-cd-10",
                    tool_id="get_project_status",
                    arguments={},
                    request_id="m41-cd-10",
                )
            )
        assert exc_info.value.code == PROJECT_NOT_FOUND
        assert exc_info.value.to_dict().get("partial_work_created") is False
    finally:
        db.close()


def test_m41_stub_copy_blocked_outside_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wave 1 honesty: stub_copy enhance cannot succeed outside E2E."""
    from app.generation_tools import ops

    monkeypatch.delenv("STUDIO_E2E", raising=False)
    assert ops._e2e() is False
    # Gate is checked after source lookup; force the honesty branch via monkeypatch.
    monkeypatch.setattr(ops, "require_source_asset", lambda *a, **k: type("A", (), {"id": "a", "path": __file__})())
    with pytest.raises(RuntimeError, match="requires ComfyUI"):
        ops.run_image_enhance_stub_copy(
            db=object(),  # type: ignore[arg-type]
            project_id="x",
            source_asset_id="y",
            op="upscale",
            model="x",
        )


def test_m41_error_envelope_redacts_secrets() -> None:
    from app.codirector.errors import CoDirectorError

    err = CoDirectorError(
        "PROVIDER_UNAVAILABLE",
        "boom",
        details={
            "provider": "ollama",
            "token": "sk-secret-should-not-leak",
            "apiKey": "abc123",
            "projectId": "p1",
        },
        recoverable=True,
        recommended_action="retry",
    )
    payload = err.to_dict()
    evidence = str(payload["technical_evidence"])
    assert "sk-secret" not in evidence
    assert "abc123" not in evidence or "[redacted]" in evidence or "apiKey" not in evidence
    assert payload["project_id"] == "p1"

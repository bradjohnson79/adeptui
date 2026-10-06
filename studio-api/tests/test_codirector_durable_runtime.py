"""Authority invariants for the durable Co-Director runtime."""

from __future__ import annotations

import os

import pytest

from app.codirector.durable.admission import classify_turn_mode
from app.codirector.durable.authority import authorize_tool
from app.codirector.durable.barrier import apply_with_barrier
from app.codirector.durable.legacy import LegacyRuntimeRetired, refuse_legacy_chat
from app.codirector.durable.models import AuthorityEnvelope, FailureState, ToolReceipt, ToolRequest
from app.codirector.durable.prompt import PROMPT_VERSION, prompt_hash
from app.codirector.durable.wording import scrub_unverified_success
from app.codirector.tools.exposure import is_shelved_tool


def _envelope(**overrides) -> AuthorityEnvelope:
    payload = dict(
        workflow_id="wf-1",
        project_id="project-1",
        scene_id="scene-1",
        turn_mode="MUTATE",
        system_prompt_version=PROMPT_VERSION,
        system_prompt_hash=prompt_hash(),
        provider_id="ollama",
        model_id="test-model",
        exposed_tool_ids=["get_project_profile", "timeline.propose_add_prompt_segment"],
        feature_flags={"promptVersion": PROMPT_VERSION},
        master_hash_before="before",
        context_snapshot_id="conversation:1",
        user_text="place the prompt",
    )
    payload.update(overrides)
    return AuthorityEnvelope.model_validate(payload)


def _request() -> ToolRequest:
    return ToolRequest(
        workflow_id="wf-1",
        tool_call_id="call-1",
        mutation_id="mutation-1",
        project_id="project-1",
        scene_id="scene-1",
        tool_id="timeline.propose_add_prompt_segment",
        arguments={"text": "hello"},
        action="mutating:timeline.propose_add_prompt_segment",
    )


def test_unapproved_mutation_stays_a_proposal(monkeypatch):
    from app.codirector.durable.execute import _mutate
    from app.codirector.tools.execution import ToolExecutionService

    async def fake_propose(session, **kwargs):
        return {"id": "proposal-1", "summary": "Set the scene prompt."}

    monkeypatch.setattr(ToolExecutionService, "propose", staticmethod(fake_propose))
    monkeypatch.setattr(
        "app.codirector.execution_authority.should_auto_approve",
        lambda *args, **kwargs: False,
    )
    receipt = _mutate(
        None,
        ToolRequest(
            workflow_id="wf-propose",
            tool_call_id="call-propose",
            mutation_id="mutation-propose",
            project_id="project-1",
            scene_id="scene-1",
            tool_id="set_scene_prompt",
            arguments={"sceneId": "scene-1", "prompt": "hello"},
            action="mutating:set_scene_prompt",
        ),
    )
    assert receipt.mutation_status == "proposed"
    assert receipt.verification_status == "not_applicable"
    assert receipt.evidence["proposed"]["id"] == "proposal-1"


def test_read_receipt_includes_the_tool_payload(monkeypatch):
    from app.codirector.durable.execute import _run_read
    from app.codirector.tools.execution import ToolExecutionService

    async def fake_read(session, **kwargs):
        return {"name": "CD Durable Cert A", "api_key": "secret-value"}

    monkeypatch.setattr(ToolExecutionService, "execute_read", staticmethod(fake_read))
    receipt = _run_read(
        ToolRequest(
            workflow_id="wf-read",
            tool_call_id="call-read",
            mutation_id="mutation-read",
            project_id="project-1",
            scene_id=None,
            tool_id="get_project_profile",
            arguments={},
            action="read:get_project_profile",
        )
    )
    assert receipt.evidence["read"]["name"] == "CD Durable Cert A"
    assert receipt.evidence["read"]["api_key"] == "[redacted]"


def test_decision_parser_uses_the_first_json_object():
    from app.codirector.durable.agent import _parse_decision

    raw = """```json
{"reply": "Reading the project.", "tool_id": "get_project_profile", "arguments": {}}
```
```json
{"reply": "Reading the project.", "tool_id": "get_project_profile", "arguments": {}}
```"""
    parsed = _parse_decision(raw)
    assert parsed is not None
    assert parsed["tool_id"] == "get_project_profile"


def test_master_readback_finds_nested_prompt_text():
    from app.codirector.durable.approval import master_has_text

    wrapped = {
        "ok": True,
        "master": {
            "batchBlocks": [
                {"promptSegments": [{"text": "[0s-4s] hello from the durable closure."}]}
            ]
        },
    }
    assert master_has_text(wrapped, "[0s-4s] hello from the durable closure.")
    assert not master_has_text(wrapped, "some other prompt")


def test_timed_instruction_admits_the_timeline_tool_only():
    from app.codirector.durable.admission import exposed_tool_ids

    ids = exposed_tool_ids(
        surface=None,
        user_text="Place this timed prompt on the timeline: [0s-4s] hello from the durable closure.",
    )
    assert "timeline.propose_add_prompt_segment" in ids
    assert "set_scene_prompt" not in ids


def test_named_surface_keeps_candidates_and_drops_conflicts():
    from app.codirector.durable.admission import exposed_tool_ids

    timeline = exposed_tool_ids(
        surface=None,
        user_text=(
            "Use Timeline. Create a 10-second 21:9 scene. Prepare the timed prompt "
            "and show me what you are preparing before anything is placed."
        ),
    )
    assert "timeline.propose_add_prompt_segment" in timeline
    assert "create_scene" in timeline
    assert "set_scene_prompt" not in timeline
    assert "propose_image_generate" not in timeline

    image = exposed_tool_ids(
        surface=None,
        user_text="Use Image Generator to create a cinematic 16:9 image. Do not create a video.",
    )
    assert "propose_image_generate" in image
    assert "propose_video_generate" not in image
    assert "timeline.propose_add_prompt_segment" not in image

    character = exposed_tool_ids(
        surface=None,
        user_text=(
            "Use Character Creator to create a new character named Mira Vale. "
            "She is calm and analytical. Create her as a new character; do not modify any existing character."
        ),
    )
    assert "character_creator.create_from_brief" in character
    assert "propose_character_update" not in character
    assert "create_draft_character_profile" not in character
    assert len(character) > 1


def test_crash_hook_is_one_shot(monkeypatch, tmp_path):
    import app.codirector.durable.crash as crash
    from app.codirector.durable.journal import crash_consumed

    monkeypatch.setenv("ADEPT_CD_JOURNAL_PATH", str(tmp_path / "journal.sqlite"))
    monkeypatch.setenv("ADEPT_CD_CRASH_AT", "before_execute")
    monkeypatch.setenv("ADEPT_CD_CRASH_SCOPE", "approve:wf:p1")
    calls = []
    monkeypatch.setattr(crash.os, "_exit", lambda code: calls.append(code))
    crash.maybe_crash("before_execute", "approve:other:p1")
    assert calls == []
    crash.maybe_crash("before_execute", "approve:wf:p1")
    crash.maybe_crash("before_execute", "approve:wf:p1")
    assert calls == [86]
    assert crash_consumed("approve:wf:p1", "before_execute")


def test_turn_modes_are_deterministic():
    assert classify_turn_mode("Hello there") == "CONVERSATION"
    assert classify_turn_mode("Hello. Do not change the project. Just say hello back.") == "CONVERSATION"
    assert classify_turn_mode("What is in this scene?") == "READ"
    assert (
        classify_turn_mode(
            "I'm working on a space-drama scene. How would you approach that character beat?"
        )
        == "CONVERSATION"
    )
    assert classify_turn_mode("Place this timed prompt on the timeline") == "MUTATE"
    assert classify_turn_mode("Just draft a change, do not apply it") == "PROPOSE"
    assert classify_turn_mode("Take me to the timeline") == "NAVIGATE"
    assert (
        classify_turn_mode(
            "Actually, change one thing: I don't want the audience to be certain he cares yet either."
        )
        == "CONVERSATION"
    )
    assert (
        classify_turn_mode(
            "Prepare the timed prompt for Timeline and show me what you are preparing before anything is placed."
        )
        == "PROPOSE"
    )


def test_shelved_tools_stay_out_of_exposure():
    assert is_shelved_tool("spatial.create_map")
    assert is_shelved_tool("avatar.inspect")
    assert not is_shelved_tool("get_project_profile")


def test_conversation_mode_cannot_authorize_a_mutation():
    decision = authorize_tool(
        _envelope(turn_mode="CONVERSATION"),
        tool_id="timeline.propose_add_prompt_segment",
        arguments={},
        tool_call_id="call-1",
        kind="mutating",
        shelved=False,
    )
    assert isinstance(decision, FailureState)
    assert decision.code == "MUTATION_NOT_AUTHORIZED"


def test_shelved_or_unadmitted_tool_fails_closed():
    denied = authorize_tool(
        _envelope(),
        tool_id="spatial.create_map",
        arguments={},
        tool_call_id="call-1",
        kind="mutating",
        shelved=True,
    )
    assert isinstance(denied, FailureState)
    assert denied.code == "TOOL_NOT_ADMITTED"


def test_assistant_text_cannot_claim_success_without_a_receipt():
    reply = scrub_unverified_success("I've placed it on the timeline.", [])
    assert "can't confirm" in reply
    proposed = scrub_unverified_success(
        'I\'ve set the timed prompt for "Durable cert scene" to "hello from the durable runtime".',
        [],
    )
    assert "can't confirm" in proposed
    kept = scrub_unverified_success(
        "Placed on the timeline.",
        [
            ToolReceipt(
                requested_action="place",
                target="scene-1",
                tool_id="timeline.propose_add_prompt_segment",
                execution_status="succeeded",
                mutation_status="written",
                verification_status="verified",
            )
        ],
    )
    assert kept.startswith("Placed")


def test_replay_after_save_does_not_execute_again(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_CD_JOURNAL_PATH", str(tmp_path / "journal.sqlite"))
    calls = {"n": 0}
    state = {"hash": "before"}

    def executor():
        calls["n"] += 1
        state["hash"] = "after"
        if calls["n"] == 1:
            raise RuntimeError("crash after save, before step completion")
        return {"ok": True, "verified": True}

    first = apply_with_barrier(
        _request(),
        before_hash="before",
        read_hash=lambda: state["hash"],
        executor=executor,
        verify=lambda raw, after: raw.get("verified") is True and after == "after",
    )
    assert isinstance(first, FailureState)
    second = apply_with_barrier(
        _request(),
        before_hash="before",
        read_hash=lambda: state["hash"],
        executor=executor,
        verify=lambda raw, after: False,
    )
    assert isinstance(second, FailureState)
    assert second.code == "AMBIGUOUS_REPLAY"
    assert calls["n"] == 1


def test_verified_replay_returns_the_prior_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_CD_JOURNAL_PATH", str(tmp_path / "journal.sqlite"))
    calls = {"n": 0}
    state = {"hash": "before"}

    def executor():
        calls["n"] += 1
        state["hash"] = "after"
        return {"ok": True, "verified": True}

    first = apply_with_barrier(
        _request(),
        before_hash="before",
        read_hash=lambda: state["hash"],
        executor=executor,
        verify=lambda raw, after: after == "after",
    )
    assert isinstance(first, ToolReceipt)
    assert first.verification_status == "verified"
    second = apply_with_barrier(
        _request(),
        before_hash="before",
        read_hash=lambda: state["hash"],
        executor=executor,
        verify=lambda raw, after: False,
    )
    assert isinstance(second, ToolReceipt)
    assert second.verification_status == "verified"
    assert calls["n"] == 1


def test_legacy_chat_entry_is_not_executable():
    with pytest.raises(LegacyRuntimeRetired):
        refuse_legacy_chat("chat_for_project")


def test_legacy_service_entries_are_deleted():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("app", "codirector", "service.py").read_text(encoding="utf-8")
    router = Path(__file__).resolve().parents[1].joinpath("app", "routers", "codirector.py").read_text(encoding="utf-8")
    for name in (
        "async def chat_for_project",
        "async def stream_for_project",
        "async def _stream_for_project_inner",
        "async def _foundation_llm_turn",
        "async def _generate_foundation_reply",
        "async def _stream_foundation_tokens",
        "def _estimate_tokens",
    ):
        assert name not in src
    approve = router[router.find("async def approve_proposal(") : router.find("async def reject_proposal(")]
    assert "begin_approval(" in approve
    assert "ProposalService.approve" not in approve
    assert "execute_approved_proposal" not in approve
    assert "from ..codirector.execution.dispatcher import" not in router


def test_one_prompt_version_is_stable():
    assert PROMPT_VERSION == "codirector-durable-v1"
    assert len(prompt_hash()) == 64


def test_dbos_database_is_not_the_studio_database(monkeypatch, tmp_path):
    monkeypatch.setenv("ADEPT_DBOS_SYSTEM_DATABASE_URL", "sqlite:///" + str(tmp_path / "dbos.sqlite"))
    from app.codirector.durable.runtime import system_database_url

    url = system_database_url()
    assert "studio.db" not in url
    assert url.endswith("dbos.sqlite")


def test_conversational_workflow_uses_the_durable_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_DBOS_SYSTEM_DATABASE_URL", "sqlite:///" + (tmp_path / "dbos.sqlite").as_posix())
    monkeypatch.setenv("ADEPT_CD_JOURNAL_PATH", str(tmp_path / "journal.sqlite"))
    from pydantic_ai.messages import ModelResponse, TextPart

    from app.codirector.durable.agent import set_model_override
    from app.codirector.durable.journal import legacy_names
    from app.codirector.durable.runtime import ensure_started

    def fake(messages, info):
        return ModelResponse(parts=[TextPart(content="Just talking. Nothing was changed.")])

    set_model_override(fake)
    ensure_started()
    from dbos import SetWorkflowID

    from app.codirector.durable.workflow import codirector_turn

    payload = {
        "envelope": {
            "workflow_id": "wf-conversation",
            "project_id": "missing-project",
            "scene_id": None,
            "turn_mode": "CONVERSATION",
            "system_prompt_version": "codirector-durable-v1",
            "system_prompt_hash": "abc",
            "provider_id": "ollama",
            "model_id": "fake",
            "exposed_tool_ids": ["get_project_profile"],
            "feature_flags": {},
            "master_hash_before": None,
            "context_snapshot_id": "conversation:none",
            "user_text": "Hello",
            "surface": None,
        }
    }

    async def _run():
        with SetWorkflowID("wf-conversation"):
            return await codirector_turn(payload)

    import asyncio

    result = asyncio.run(_run())
    assert "Nothing was changed" in result["reply"]
    assert "chat_for_project" not in legacy_names()
    assert "stream_for_project" not in legacy_names()
    set_model_override(None)


def test_prop_creator_request_binds_the_generate_button_plan():
    from app.codirector.durable.bind import (
        QWEN_EXPRESS_SOURCES,
        bind_request_arguments,
        is_prop_generation_request,
    )

    text = "I'd like you to create a silver metal mug filled with coffee as a prop in prop creator."
    assert is_prop_generation_request(text)
    args, refusal = bind_request_arguments(
        None,  # type: ignore[arg-type]
        tool_id="prop_creator.generate_view",
        arguments={},
        user_text=text,
        project_id="project-1",
    )
    assert refusal is None
    assert args["name"] == "silver metal mug filled with coffee"
    assert "silver metal mug filled with coffee" in args["description"]
    assert args["generatorSources"] == QWEN_EXPRESS_SOURCES
    assert args["local_enabled"] is True
    assert args["api_enabled"] is False
    assert args["local_family"] == "qwen2512"
    assert args["candidate_count"] == 1
    assert args["view"] == "primary"


def test_queued_prop_job_is_not_a_failed_verification(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_CD_JOURNAL_PATH", str(tmp_path / "journal.sqlite"))
    from app.codirector.durable.approval import _prop_image_ready, _prop_job_submitted

    calls = {"n": 0}
    queued = {
        "ok": True,
        "toolId": "prop_creator.generate_view",
        "toolResult": {
            "ok": True,
            "jobId": "job-prop-1",
            "propId": "prop-1",
            "assetId": "",
            "status": "queued",
            "provider": "local",
            "model": "qwen-image-2512",
            "workflowKey": "qwen2512.txt2img",
            "message": "The prop image is generating. It is not in the Library yet.",
        },
    }

    def executor():
        calls["n"] += 1
        return queued

    request = _request()
    request.mutation_id = "mutation-prop-1"
    request.tool_id = "prop_creator.generate_view"
    first = apply_with_barrier(
        request,
        before_hash="before",
        read_hash=lambda: "before",
        executor=executor,
        verify=lambda raw, after: _prop_job_submitted(raw),
    )
    assert isinstance(first, ToolReceipt)
    assert first.evidence["handler"]["jobId"] == "job-prop-1"
    assert first.evidence["handler"]["workflowKey"] == "qwen2512.txt2img"
    assert _prop_image_ready(first.evidence["handler"]) is False
    second = apply_with_barrier(
        request,
        before_hash="before",
        read_hash=lambda: "before",
        executor=executor,
        verify=lambda raw, after: False,
    )
    assert isinstance(second, ToolReceipt)
    assert calls["n"] == 1
    assert _prop_image_ready({"assetId": "asset-1", "status": "done", "message": "The prop image is in the Library."}) is True


def test_langfuse_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:9")
    from app.codirector.durable.tracing import emit_trace

    trace_id = emit_trace(
        workflow_id="wf",
        project_id="p",
        scene_id=None,
        model="m",
        prompt_version=PROMPT_VERSION,
        user_text="hello",
        tool_ids=[],
        receipts=[],
        reply="hi",
        failure=None,
    )
    assert trace_id

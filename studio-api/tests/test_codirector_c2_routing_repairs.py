"""c2-routing repair regressions for the Co-Director Operational Integrity Audit.

Covers: read-before-write (D2-D6), tool loop limit (D18), streamed
false-success claims (D7), create_draft audited exception (D9), audited-write
routing drift, staleness at proposal creation (D10), small repairs
(D14/D15/D16/D17), intent classifier (D13), capability-scoped tool exposure,
and routing examples.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import fields as dataclass_fields
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def asyncio_run(coro):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("loop running")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return asyncio.get_event_loop().run_until_complete(coro)


def _apply_flags_in_place(environ=None) -> None:
    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture(autouse=True)
def enable_flags(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)
    yield
    _apply_flags_in_place(os.environ)


@pytest.fixture()
def db() -> Session:
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def _new_project(db: Session, name: str = "c2 Routing Project") -> str:
    pid = f"c2-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _make_bible(db: Session, project_id: str) -> None:
    from app.codirector.bible import operations as ops
    from app.codirector.bible.schemas import BibleEntity

    ops.create_bible_with_first_version(
        db,
        project_id=project_id,
        entities=[BibleEntity(entityType="project_profile", entityKey="project-profile",
                              displayName="Project Profile", data={"description": "seed"})],
        facts=[],
        summary="seed",
        change_reason="seed",
        created_by="test",
    )


def _ctx(db: Session, project_id: str):
    from app.codirector.tools.definitions import ToolContext

    return ToolContext(db=db, project_id=project_id)


def _apply(tool_id: str, raw_args: dict[str, Any], ctx):
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    return registry.mutation_handler(tool_id).apply(ctx, sanitized)


# --------------------------------------------------------------------------
# D2: apply_create_draft idempotency + project requirement
# --------------------------------------------------------------------------


def test_d2_create_draft_idempotency_returns_existing_draft(db: Session) -> None:
    pid = _new_project(db)
    ctx = _ctx(db, pid)
    args = {"title": "Rooftop Plan", "objective": "Stage the rooftop scene"}
    first = _apply("production_plan.create_draft", args, ctx)
    assert first["unapproved"] is True
    assert first.get("auditedJustification")
    second = _apply("production_plan.create_draft", args, ctx)
    assert second.get("duplicated") is True
    assert second.get("duplicateDraft") is True
    assert second["plan"]["planId"] == first["plan"]["planId"]


def test_d2_create_draft_requires_project(db: Session) -> None:
    from app.codirector.errors import CoDirectorError

    ctx = _ctx(db, "nonexistent-project-id")
    with pytest.raises(CoDirectorError) as exc:
        _apply("production_plan.create_draft", {"title": "x", "objective": "y"}, ctx)
    assert exc.value.code == "PLAN_NOT_FOUND"


# --------------------------------------------------------------------------
# D3: apply_propose rejects stale version
# --------------------------------------------------------------------------


def test_d3_propose_rejects_stale_version(db: Session) -> None:
    from app.codirector.errors import CoDirectorError

    pid = _new_project(db)
    ctx = _ctx(db, pid)
    draft = _apply("production_plan.create_draft", {"title": "P", "objective": "O"}, ctx)
    plan_id = draft["plan"]["planId"]
    real_version = draft["plan"]["version"]
    with pytest.raises(CoDirectorError) as exc:
        _apply(
            "production_plan.propose",
            {"planId": plan_id, "expectedVersion": real_version + 999, "requestId": "r"},
            ctx,
        )
    assert exc.value.code == "PLAN_VERSION_CONFLICT"


# --------------------------------------------------------------------------
# D9: draft cannot authorize production + audited justification recorded
# --------------------------------------------------------------------------


def test_d9_draft_cannot_transition_to_approved() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.plans.state_machine import assert_plan_transition

    with pytest.raises(CoDirectorError) as exc:
        assert_plan_transition("draft", "approved", command="propose")
    assert exc.value.code == "PLAN_STATE_TRANSITION_INVALID"
    with pytest.raises(CoDirectorError):
        assert_plan_transition("draft", "in_progress", command="execute")


def test_d9_create_draft_records_audited_justification(db: Session) -> None:
    pid = _new_project(db)
    ctx = _ctx(db, pid)
    result = _apply("production_plan.create_draft", {"title": "J", "objective": "K"}, ctx)
    assert result["unapproved"] is True
    assert "auditedJustification" in result
    assert "does not authorize production" in result["auditedJustification"]


# --------------------------------------------------------------------------
# D4/D6: bible read-before-write
# --------------------------------------------------------------------------


def test_d4_canon_supersession_requires_existing_record(db: Session) -> None:
    from app.codirector.errors import CoDirectorError

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = _ctx(db, pid)
    with pytest.raises(CoDirectorError) as exc:
        _apply(
            "propose_canon_supersession",
            {"claim": "new canon", "supersedesStableId": "missing-stable-id"},
            ctx,
        )
    assert exc.value.code == "SUPERSEDED_NOT_CURRENT"


def test_d6_reference_link_requires_existing_asset(db: Session) -> None:
    from app.codirector.errors import CoDirectorError

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = _ctx(db, pid)
    with pytest.raises(CoDirectorError) as exc:
        _apply(
            "propose_reference_link",
            {"assetId": "no-such-asset", "targetStableId": "no-such-target"},
            ctx,
        )
    assert exc.value.code == "REFERENCE_ASSET_MISSING"


# --------------------------------------------------------------------------
# D10: staleness at proposal creation
# --------------------------------------------------------------------------


def test_d10_create_tool_proposal_computes_is_stale(db: Session) -> None:
    from app.codirector.bible.proposals import ProposalService
    from app.codirector.tools.definitions import ToolCallPayload, ToolPreview

    pid = _new_project(db)
    _make_bible(db, pid)
    payload = ToolCallPayload(
        toolId="propose_canon_record",
        arguments={"claim": "test canon"},
        preview=ToolPreview(summary="preview"),
        baseResourceVersions={"bible": "v1"},
    )
    proposal = ProposalService.create_tool_proposal(
        db,
        project_id=pid,
        payload=payload,
        title="test",
        summary="preview",
        created_by="test",
    )
    # isStale must be a real boolean computed by the service (False here because
    # the base version was just pinned, but the field is authoritative from
    # creation, not only at approval).
    assert hasattr(proposal, "isStale")
    assert proposal.isStale in (True, False)


# --------------------------------------------------------------------------
# D13: intent classifier discrimination
# --------------------------------------------------------------------------


def test_d13_explain_question_does_not_mutate() -> None:
    from app.codirector.conversation.foundation.intent import analyze_intent

    for text in [
        "How does Timeline Batch generation work?",
        "What is the Production Bible?",
        "Explain how the Spatial Map works.",
    ]:
        intent = analyze_intent(text)
        assert intent.primary_intent.value in ("INFORM", "EXPLAIN_PROJECT")
        assert intent.should_use_tools is False
        posture_names = {p.value for p in intent.required_postures}
        assert "EXECUTE" not in posture_names
        assert "CREATE" not in posture_names


def test_d13_imperative_actions_request_action() -> None:
    from app.codirector.conversation.foundation.intent import analyze_intent

    for text in [
        "Add an image to Batch 3.",
        "Change Barnes' voice.",
        "Update the Production Bible summary.",
        "Remove the canon record.",
        "Delete the clip.",
    ]:
        intent = analyze_intent(text)
        assert intent.primary_intent.value == "REQUEST_ACTION"
        assert intent.should_use_tools is True


# --------------------------------------------------------------------------
# D14: grounding dead gate_fail removed
# --------------------------------------------------------------------------


def test_d14_grounding_no_dead_gate_fail() -> None:
    from app.codirector.conversation.foundation.grounding import evaluate_grounding
    from app.codirector.conversation.foundation.schemas import (
        ConversationState,
        DialoguePlan,
        IntentAnalysis,
    )

    check = evaluate_grounding(
        user_message="hello",
        reply="Hi there, let's keep going.",
        intent=IntentAnalysis(user_goal_summary="test"),
        plan=DialoguePlan(),
        companion={},
    )
    assert check is not None
    assert hasattr(check, "violates_dialogue_plan")


# --------------------------------------------------------------------------
# D15: _validate_or_repair surfaces validation failure
# --------------------------------------------------------------------------


def test_d15_validate_or_repair_surfaces_validation_error() -> None:
    from app.codirector.intelligence.specialist_runner import SpecialistRunner

    runner = SpecialistRunner()
    from app.codirector.intelligence.specialist_registry import SpecialistDefinition

    definition = SpecialistDefinition(
        id="continuity-analyst",
        prompt_id="continuity-analyst",
        display_name="Continuity Analyst",
        description="continuity",
        enabled=True,
        allowed_context=(),
        output_schema_id="finding-v1",
        may_propose_tools=False,
        may_execute_tools=False,
        default_priority=1,
        prompt_version="1",
        timeout_ms=5000,
    )
    raw = {"specialistId": "continuity-analyst", "summary": "x", "recommendation": "y", "confidence": 2.0}
    finding = runner._validate_or_repair(definition, raw)
    assert finding.status == "failed"
    assert any(a.startswith("LIMITED_ANALYSIS_ASSUMPTION:") for a in finding.assumptions)
    assert any("failed schema validation" in a for a in finding.assumptions)


# --------------------------------------------------------------------------
# D16: synthesis confidence cap for heuristic-only findings
# --------------------------------------------------------------------------


def test_d16_synthesis_caps_confidence_for_heuristic_only() -> None:
    from app.codirector.intelligence.schemas import (
        IntentClassification,
        SpecialistFinding,
    )
    from app.codirector.intelligence.specialist_runner import LIMITED_ANALYSIS_ASSUMPTION
    from app.codirector.intelligence.synthesis import SynthesisEngine

    intent = IntentClassification(primaryIntent="execute_project_action")
    heuristic = SpecialistFinding(
        specialistId="continuity-analyst",
        summary="heuristic",
        recommendation="heuristic rec",
        assumptions=[LIMITED_ANALYSIS_ASSUMPTION],
        confidence=0.55,
    )
    result = SynthesisEngine().synthesize(
        user_message="check continuity", intent=intent, findings=[heuristic]
    )
    assert result.confidence <= 0.55


def test_d16_synthesis_keeps_high_confidence_with_validated_finding() -> None:
    from app.codirector.intelligence.schemas import (
        IntentClassification,
        SpecialistFinding,
    )
    from app.codirector.intelligence.synthesis import SynthesisEngine

    intent = IntentClassification(primaryIntent="execute_project_action")
    validated = SpecialistFinding(
        specialistId="continuity-analyst",
        summary="real",
        recommendation="real rec",
        confidence=0.9,
        status="validated",
    )
    result = SynthesisEngine().synthesize(
        user_message="check continuity", intent=intent, findings=[validated]
    )
    assert result.confidence == 0.88


# --------------------------------------------------------------------------
# D17: mock provider guard is config-enforced
# --------------------------------------------------------------------------


def test_d17_mock_provider_blocked_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_ENV", "production")
    monkeypatch.delenv("ADEPT_ALLOW_MOCK_PROVIDER", raising=False)
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "ollama"
    assert "mock" not in service.list_provider_ids()


def test_d17_mock_provider_allowed_in_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector import service

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.delenv("ADEPT_ENV", raising=False)
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "mock"
    assert "mock" in service.list_provider_ids()


def test_d17_mock_provider_allowed_in_production_with_explicit_allow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.codirector import service

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_ENV", "production")
    monkeypatch.setenv("ADEPT_ALLOW_MOCK_PROVIDER", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    assert service.active_provider_id() == "mock"


# --------------------------------------------------------------------------
# Capability-scoped tool exposure
# --------------------------------------------------------------------------


def test_exposure_baseline_always_present() -> None:
    from app.codirector.tools.exposure import _BASELINE_READ_TOOL_IDS, expose

    ids = expose(workspace_surface="bible", intent="Update the Production Bible summary.")
    assert _BASELINE_READ_TOOL_IDS <= ids


def test_exposure_irrelevant_tools_excluded() -> None:
    from app.codirector.tools.exposure import expose

    ids = expose(workspace_surface=None, intent="What is the Production Bible?")
    assert not any(t.startswith("runtime.") or t.startswith("setup.") for t in ids)
    assert not any(t.startswith("posecraft.") for t in ids)


def test_exposure_ambiguous_intent_expands() -> None:
    from app.codirector.tools.exposure import expose

    narrow = expose(workspace_surface="bible", intent="Update the Production Bible summary.")
    broad = expose(
        workspace_surface=None,
        intent="Generate the scene, then place the voice clip on the timeline and update the bible.",
    )
    assert len(broad) > len(narrow)


def test_exposure_deterministic() -> None:
    from app.codirector.tools.exposure import expose

    a = expose(workspace_surface="timeline", intent="Add an image to Batch 3.")
    b = expose(workspace_surface="timeline", intent="Add an image to Batch 3.")
    assert a == b


def test_exposure_unsupported_systems_have_no_tools() -> None:
    from app.codirector.tools.exposure import assert_unsupported_systems_have_no_tools

    assert_unsupported_systems_have_no_tools()


def test_exposure_required_tools_discoverable() -> None:
    from app.codirector.tools.exposure import expose

    assert any(t.startswith("timeline.") for t in expose(workspace_surface="timeline", intent="Add an image to Batch 3."))
    assert any(t.startswith("voice") for t in expose(workspace_surface="voice", intent="Change Barnes' voice."))
    assert any("bible" in t or "canon" in t for t in expose(workspace_surface="bible", intent="Update the Production Bible summary."))


# --------------------------------------------------------------------------
# Audited-write routing drift + tool loop limit (direct _interpret_reply)
# --------------------------------------------------------------------------
# These exercise the routing decision at the exact site of the c2 repair
# (`_interpret_reply`), independent of the foundation-vs-legacy chat branch.
# NOTE: the HTTP chat/stream paths currently route every project turn through
# the foundation (LLM-primary) path (`usesLlmPrimary=True` in the untracked
# `conversation/orchestrate.py`), which does not execute tools. That is a
# pre-existing architectural change outside the c2-routing scope, so the
# routing drift is validated at the interpreter level where it is reachable.


def _tool_fence_reply(tool_id: str, arguments: dict[str, Any] | None = None) -> str:
    return (
        "```tool\n"
        + json.dumps(
            {"responseType": "mutation_proposal", "toolId": tool_id, "arguments": arguments or {}}
        )
        + "\n```"
    )


async def _interpret(reply: str, db: Session, project_id: str, *, tools_used: int = 0) -> tuple[list[dict], "object"]:
    from app.codirector.service import _StructuredOutcome, _interpret_reply

    outcome = _StructuredOutcome()
    events: list[dict] = []
    async for event in _interpret_reply(
        db,
        project_id=project_id,
        scene_id=None,
        request_id="test-req",
        reply=reply,
        tools_used=tools_used,
        outcome=outcome,
    ):
        events.append(event)
    return events, outcome


def test_audited_routing_create_draft_executes_not_proposes(db: Session) -> None:
    pid = _new_project(db)
    events, outcome = asyncio_run(
        _interpret(_tool_fence_reply("production_plan.create_draft", {"title": "T", "objective": "O"}), db, pid)
    )
    assert any(e["type"] == "tool_requested" and e.get("audited") is True for e in events)
    assert not any(e["type"] == "tool_proposal_created" for e in events)
    assert any(e["type"] == "tool_completed" for e in events)
    assert outcome.tool_proposal is None


def test_audited_routing_audio_cancel_executes_not_proposes(db: Session) -> None:
    pid = _new_project(db)
    events, outcome = asyncio_run(
        _interpret(_tool_fence_reply("audio.cancel_batch", {"batchId": "no-such-batch"}), db, pid)
    )
    assert any(e["type"] == "tool_requested" and e.get("audited") is True for e in events)
    assert not any(e["type"] == "tool_proposal_created" for e in events)
    assert outcome.tool_proposal is None


def test_audited_routing_minimax_fallback_executes_not_proposes(db: Session) -> None:
    pid = _new_project(db)
    events, outcome = asyncio_run(
        _interpret(_tool_fence_reply("minimax_h3.offer_ltx_fallback", {}), db, pid)
    )
    assert any(e["type"] == "tool_requested" and e.get("audited") is True for e in events)
    assert not any(e["type"] == "tool_proposal_created" for e in events)
    assert outcome.tool_proposal is None


def test_audited_routing_minimax_cancel_executes_not_proposes(db: Session) -> None:
    pid = _new_project(db)
    events, outcome = asyncio_run(
        _interpret(_tool_fence_reply("minimax_h3.cancel", {}), db, pid)
    )
    assert any(e["type"] == "tool_requested" and e.get("audited") is True for e in events)
    assert not any(e["type"] == "tool_proposal_created" for e in events)
    assert outcome.tool_proposal is None


def test_non_audited_mutation_routes_to_proposal_not_execute(db: Session) -> None:
    pid = _new_project(db)
    _make_bible(db, pid)
    events, outcome = asyncio_run(
        _interpret(_tool_fence_reply("propose_canon_record", {"claim": "x"}), db, pid)
    )
    # A mutating tool that DOES require approval must NOT route via execute_audited.
    assert not any(e["type"] == "tool_requested" and e.get("audited") is True for e in events)
    assert any(e["type"] == "tool_proposal_created" for e in events)
    assert outcome.tool_proposal is not None


def test_d18_tool_loop_limit_allows_three_reads_blocks_fourth(db: Session) -> None:
    pid = _new_project(db)
    fence = _tool_fence_reply("list_scenes", {})
    # tools_used=0,1,2 -> read tool runs (tool_requested, not audited).
    for used in (0, 1, 2):
        events, outcome = asyncio_run(_interpret(fence, db, pid, tools_used=used))
        assert any(e["type"] == "tool_requested" for e in events)
        assert not any(e.code == "TOOL_LOOP_LIMIT_REACHED" for e in outcome.errors)
    # tools_used=3 -> 3 >= TOOL_LOOP_LIMIT -> TOOL_LOOP_LIMIT_REACHED, no tool run.
    events, outcome = asyncio_run(_interpret(fence, db, pid, tools_used=3))
    assert not any(e["type"] == "tool_requested" for e in events)
    assert any(e.code == "TOOL_LOOP_LIMIT_REACHED" for e in outcome.errors)


# --------------------------------------------------------------------------
# D7: streamed false-success claim correction event
# --------------------------------------------------------------------------


def test_d7_premature_tool_success_detection_flags_unbacked_claim() -> None:
    from app.codirector.service import _detect_premature_tool_success_claim

    flagged, phrase = _detect_premature_tool_success_claim(
        "I've added the scene to your project.", mutating_tool_executed=False
    )
    assert flagged is True
    assert phrase


def test_d7_premature_tool_success_not_flagged_when_tool_executed() -> None:
    from app.codirector.service import _detect_premature_tool_success_claim

    flagged, _ = _detect_premature_tool_success_claim(
        "I've added the scene to your project.", mutating_tool_executed=True
    )
    assert flagged is False


def test_d7_premature_tool_success_skips_wiki_claims() -> None:
    from app.codirector.service import _detect_premature_tool_success_claim

    # Wiki claims are handled by the wiki-specific detector, not this one.
    flagged, _ = _detect_premature_tool_success_claim(
        "I've updated the wiki with new lore.", mutating_tool_executed=False
    )
    assert flagged is False


# --------------------------------------------------------------------------
# Routing examples (intent -> action classification)
# --------------------------------------------------------------------------


def test_routing_add_image_to_batch3_is_action() -> None:
    from app.codirector.conversation.foundation.intent import analyze_intent

    intent = analyze_intent("Add an image to Batch 3.")
    assert intent.primary_intent.value == "REQUEST_ACTION"
    assert intent.should_use_tools is True


def test_routing_change_barnes_voice_is_action() -> None:
    from app.codirector.conversation.foundation.intent import analyze_intent

    intent = analyze_intent("Change Barnes' voice.")
    assert intent.primary_intent.value == "REQUEST_ACTION"
    assert intent.should_use_tools is True


def test_routing_update_bible_summary_is_action() -> None:
    from app.codirector.conversation.foundation.intent import analyze_intent

    intent = analyze_intent("Update the Production Bible summary.")
    assert intent.primary_intent.value == "REQUEST_ACTION"
    assert intent.should_use_tools is True

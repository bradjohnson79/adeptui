"""Unit tests — Co-Director Production Planner core (Ch 2–12 foundation)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.codirector.deliberation import TalkAskAct, build_decision, reason_codes as RC
from app.codirector.execution.contracts import (
    ExecutionPlan,
    ExecutionStep,
    PlanStepLifecycle,
)
from app.codirector.production_planner import (
    FailureReasonCode,
    IntentEvidence,
    PLANNER_SCHEMA_VERSION,
    PlanStep,
    ProductionPlan,
    bind_pending_brief,
    build_intent_evidence,
    compile_execution_steps,
    compile_multistep_request,
    is_pending_fresh,
)
from app.codirector.production_planner.compile import apply_dependency_block, is_planning_speech
from app.codirector.production_planner.failure_codes import stamp_failure
from app.codirector.production_planner.plan_contracts import PlanStepStatus
from app.codirector.routing.unified_intent import (
    DispatchStrategy,
    UnifiedIntent,
    UnifiedIntentKind,
)


def test_intent_evidence_schema_bus() -> None:
    ev = build_intent_evidence(
        semantic_intent="PLANNING",
        commitment="NONE",
        artifact_type="image",
        planning_speech=True,
        multi_step=True,
        requested_modalities=["image", "video"],
        classifier_sources=["speech_act"],
    )
    assert isinstance(ev, IntentEvidence)
    assert ev.schemaVersion == "cd-intent-evidence-v1"
    assert ev.planningSpeech is True
    assert ev.multiStep is True
    assert "image" in ev.requestedModalities


def test_production_plan_schema_versioned() -> None:
    plan = ProductionPlan(goal="Test", steps=[
        PlanStep(title="Image", capabilityId="image.generate", status=PlanStepStatus.READY),
    ])
    assert plan.schemaVersion == PLANNER_SCHEMA_VERSION == "cd-production-planner-v1"
    assert plan.version == 1
    assert plan.steps[0].capabilityId == "image.generate"


def test_multistep_compile_image_video_audio_asset_slots() -> None:
    plan = compile_multistep_request(
        user_message="Generate an image of the corridor, then make a video, then add audio footsteps.",
        project_id="proj-1",
    )
    assert plan is not None
    assert len(plan.steps) == 3
    assert [s.capabilityId for s in plan.steps] == [
        "image.generate",
        "video.generate",
        "timeline.add_audio",
    ]
    # First READY, dependents BLOCKED with dependsOn stepIds (not free text)
    assert plan.steps[0].status == PlanStepStatus.READY
    assert plan.steps[1].status == PlanStepStatus.BLOCKED
    assert plan.steps[1].dependsOn == [plan.steps[0].stepId]
    assert plan.steps[2].dependsOn == [plan.steps[1].stepId]
    assert plan.steps[1].params.get("input_asset_slot") == plan.steps[0].producesAssetSlot
    # Timeline=R2V when video follows image
    assert plan.steps[1].params.get("timelineMode") == "R2V"

    exec_steps = compile_execution_steps(plan)
    assert len(exec_steps) == 3
    assert exec_steps[1]["metadata"]["dependsOn"] == [plan.steps[0].stepId]


def test_dependency_block_and_ready_promotion() -> None:
    plan = compile_multistep_request(
        user_message="Create an image then a video",
        project_id="p",
    )
    assert plan is not None
    plan.steps[0].status = PlanStepStatus.COMPLETED
    plan.steps[0].resultAssetIds = ["asset-img-1"]
    apply_dependency_block(plan)
    assert plan.steps[1].status == PlanStepStatus.READY
    assert "DEPENDENCY_BLOCKED" not in plan.steps[1].reasonCodes


def test_dependency_blocked_on_upstream_failure() -> None:
    plan = compile_multistep_request(
        user_message="Create an image then a video",
        project_id="p",
    )
    assert plan is not None
    plan.steps[0].status = PlanStepStatus.FAILED
    plan.steps[0].failureReasonCodes = [FailureReasonCode.PROVIDER_ERROR.value]
    apply_dependency_block(plan)
    assert plan.steps[1].status == PlanStepStatus.BLOCKED
    assert "DEPENDENCY_BLOCKED" in plan.steps[1].failureReasonCodes


def test_pending_bind_only_fresh() -> None:
    fresh = SimpleNamespace(
        state="AWAITING_CONFIRMATION",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    )
    bound, codes = bind_pending_brief(
        user_message="Do it",
        pending=fresh,
        commitment_explicit=True,
    )
    assert bound is True
    assert "PENDING_BRIEF_BOUND" in codes

    expired = SimpleNamespace(
        state="AWAITING_CONFIRMATION",
        expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    )
    bound2, codes2 = bind_pending_brief(
        user_message="Go ahead",
        pending=expired,
        commitment_explicit=True,
    )
    assert bound2 is False
    assert "PENDING_BRIEF_EXPIRED" in codes2
    assert is_pending_fresh(expired) is False


def test_pending_do_it_without_pending_not_bound() -> None:
    bound, codes = bind_pending_brief(
        user_message="Do it",
        pending=None,
        commitment_explicit=True,
    )
    assert bound is False
    assert "PENDING_BRIEF_MISSING" in codes


def test_execution_plan_lineage_fields() -> None:
    step = ExecutionStep(
        step_index=0,
        label="image",
        capability="image.generate",
        step_id="step-a",
        depends_on=[],
        lifecycle_status=PlanStepLifecycle.READY,
        parent_execution_id="exec-parent",
        parent_step_id=None,
        plan_id="plan-1",
    )
    plan = ExecutionPlan(
        execution_id="exec-child",
        capability="image.generate",
        project_id="proj-1",
        planned_steps=[step],
        parent_execution_id="exec-parent",
        parent_step_id="step-root",
        plan_id="plan-1",
    )
    assert plan.parent_execution_id == "exec-parent"
    assert plan.planned_steps[0].lifecycle_status == PlanStepLifecycle.READY


def test_strict_retry_no_silent_swap() -> None:
    reason, codes = stamp_failure(
        reason="model unavailable",
        codes=[FailureReasonCode.STRICT_MODEL_UNAVAILABLE.value],
        strict=True,
    )
    assert FailureReasonCode.STRICT_NO_SILENT_SWAP.value in codes
    assert reason


def test_build_decision_attaches_intent_evidence_and_plan() -> None:
    decision = build_decision(
        user_message="Let's plan: generate an image, then a video, then add audio.",
        project_id="proj-1",
        speech_act="DISCUSSION",
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.TALK
    assert decision.responsePlan.purpose == "plan"
    assert decision.intentEvidence.get("schemaVersion") == "cd-intent-evidence-v1"
    assert decision.productionPlan.get("schemaVersion") == PLANNER_SCHEMA_VERSION
    assert len(decision.productionPlan.get("steps") or []) == 3
    assert RC.INTENT_EVIDENCE_BUILT in decision.reasonCodes
    assert RC.PRODUCTION_PLAN_ATTACHED in decision.reasonCodes
    assert RC.PLANNING_SPEECH in decision.reasonCodes
    assert decision.pendingBrief.get("planId")
    assert RC.PENDING_BRIEF_READY in decision.reasonCodes
    # No fourth act boss
    assert decision.act.value != "PLAN"
    assert not decision.should_dispatch()


def test_build_decision_multistep_without_lets_plan_still_plans() -> None:
    decision = build_decision(
        user_message="Generate an image of Korri then make a video then add audio.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    # Prefer TALK + purpose=plan for multi-step (no silent ACT storm)
    assert decision.act == TalkAskAct.TALK
    assert decision.responsePlan.purpose == "plan"
    assert len(decision.productionPlan.get("steps") or []) == 3
    assert RC.MULTI_STEP_COMPILED in decision.reasonCodes


def test_selective_preflight_on_multistep() -> None:
    decision = build_decision(
        user_message="Let's plan an image then video.",
        project_id="proj-1",
        runtime_precheck=False,
        route_lock={"level": "STRICT", "provider": "flux"},
    )
    assert decision.selectivePreflight.get("required") is True
    assert decision.selectivePreflight.get("strict") is True
    assert decision.selectivePreflight.get("multiStep") is True
    assert RC.SELECTIVE_PREFLIGHT in decision.reasonCodes


def test_failure_informed_strict_stamp_on_decision() -> None:
    decision = build_decision(
        user_message="Retry that image.",
        project_id="proj-1",
        runtime_precheck=False,
        failed_execution_history=[
            {
                "capability": "image.generate",
                "error": "model unavailable",
                "lockLevel": "STRICT",
                "failureReasonCodes": [FailureReasonCode.STRICT_MODEL_UNAVAILABLE.value],
            }
        ],
    )
    assert RC.FAILURE_INFORMED_RETRY in decision.reasonCodes
    assert FailureReasonCode.STRICT_NO_SILENT_SWAP.value in decision.reasonCodes
    assert "strict_no_silent_swap" in decision.evidence


def test_is_planning_speech() -> None:
    assert is_planning_speech("Let's plan the sequence") is True
    assert is_planning_speech("Generate an image now") is False


def test_talk_ask_act_unchanged_single_image() -> None:
    """Single-step still uses existing ACT path — planner must not steal it."""
    decision = build_decision(
        user_message="Create a cinematic image of the Venture corridor.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.95,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert decision.responsePlan.purpose != "plan"
    assert not decision.productionPlan.get("steps")


# ---------------------------------------------------------------------------
# Phase GO: pack bridge, stale pending, dependency BLOCKED, retry, pending UI contract
# ---------------------------------------------------------------------------


def test_pack_bridge_compile_to_execution_steps_depends_on_and_lineage():
    from app.codirector.production_planner.compile import compile_multistep_request
    from app.codirector.production_planner.pack_bridge import (
        bridge_compile_to_execution_steps,
        dependency_blocked_steps,
        apply_production_plan_to_pack,
    )
    from app.codirector.execution.contracts import ExecutionPlan, ExecutionStatus

    plan = compile_multistep_request(
        user_message="Let's plan: corridor still then video then footsteps audio",
        project_id="proj-bridge",
        parent_execution_id="parent-exec-1",
    )
    assert plan is not None
    assert len(plan.steps) >= 3
    steps = bridge_compile_to_execution_steps(plan, parent_execution_id="parent-exec-1")
    assert steps[0]["depends_on"] == []
    assert steps[1]["depends_on"] == [steps[0]["step_id"]]
    assert steps[2]["depends_on"] == [steps[1]["step_id"]]
    assert steps[1]["parent_execution_id"] == "parent-exec-1"
    assert steps[1]["plan_id"] == plan.planId
    assert "producesAssetSlot" in (steps[0]["metadata"] or {})
    blocked = dependency_blocked_steps(steps)
    assert steps[1]["step_id"] in blocked  # not yet completed upstream

    pack = ExecutionPlan(
        execution_id="exec-new",
        capability="image.generate",
        project_id="proj-bridge",
        status=ExecutionStatus.PREPARING,
    )
    apply_production_plan_to_pack(pack, production_plan=plan, parent_execution_id="parent-exec-1")
    assert len(pack.planned_steps) >= 3
    assert pack.plan_id == plan.planId
    assert pack.parent_execution_id == "parent-exec-1"
    assert pack.planned_steps[1].depends_on == [pack.planned_steps[0].step_id]


def test_pending_ui_contract_fields_on_decision():
    """DeliberationDecision carries pendingBrief + purpose=plan for UI consumer."""
    from app.codirector.deliberation.service import build_decision
    from app.codirector.deliberation.contracts import TalkAskAct

    d = build_decision(
        user_message="Let's plan a corridor still then video then footsteps",
        project_id="proj-ui",
    )
    assert d.act == TalkAskAct.TALK
    assert d.responsePlan.purpose == "plan"
    assert d.productionPlan.get("planId")
    assert d.pendingBrief.get("planId") or d.pendingBrief.get("summary")
    assert d.pendingBrief.get("state") == "AWAITING_CONFIRMATION"
    assert d.pendingBrief.get("expiresAt")
    # Selective preflight for multi-step
    assert d.selectivePreflight.get("multiStep") or d.selectivePreflight.get("required")


def test_stale_pending_must_not_bind_go():
    from datetime import datetime, timedelta, timezone
    from app.codirector.production_planner.pending_brief import (
        bind_pending_brief,
        is_pending_fresh,
        PendingBrief,
    )

    expired = PendingBrief(
        planId="p1",
        summary="old",
        state="AWAITING_CONFIRMATION",
        expiresAt=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    assert is_pending_fresh(expired) is False
    bound, codes = bind_pending_brief(
        user_message="Go ahead",
        pending=expired,
        commitment_explicit=True,
    )
    assert bound is False
    assert "PENDING_BRIEF_EXPIRED" in codes


def test_failure_informed_retry_reads_pack_strict_no_silent_swap():
    from app.codirector.execution.contracts import (
        ExecutionPlan,
        ExecutionStatus,
        ExecutionStep,
        PlanStepLifecycle,
        ChildJobStatus,
    )
    from app.codirector.production_planner.retry import build_retry_brief
    from app.codirector.production_planner.failure_codes import FailureReasonCode

    pack = ExecutionPlan(
        execution_id="exec-fail-1",
        capability="video.generate",
        project_id="proj-r",
        status=ExecutionStatus.FAILED,
        plan_id="plan-r",
        parent_execution_id="exec-parent",
        failure_reason_codes=[FailureReasonCode.PROVIDER_ERROR.value],
        error="provider blew up",
        planned_steps=[
            ExecutionStep(
                step_index=1,
                label="Generate video",
                capability="video.generate",
                status=ChildJobStatus.FAILED,
                step_id="step-video-1",
                lifecycle_status=PlanStepLifecycle.FAILED,
                failure_reason="provider blew up",
                failure_reason_codes=[FailureReasonCode.PROVIDER_ERROR.value],
                parent_execution_id="exec-fail-1",
                plan_id="plan-r",
                metadata={
                    "routeLock": {"provider": "local", "modelId": "locked-model", "level": "STRICT"},
                    "params": {"provider": "local", "model": "locked-model"},
                },
            )
        ],
        plan_data={"routeLock": {"provider": "local", "modelId": "locked-model", "level": "STRICT"}},
    )
    brief = build_retry_brief(pack, strict=True, allow_provider_swap=False)
    assert brief["ok"] is True
    assert brief["silentSwapForbidden"] is True
    assert FailureReasonCode.STRICT_NO_SILENT_SWAP.value in brief["reasonCodes"]
    assert brief["routeLock"]["modelId"] == "locked-model"
    assert brief["params"]["model"] == "locked-model"
    assert brief["parentExecutionId"] == "exec-fail-1"


def test_wave4_reconnect_policy_documents_skip_without_active():
    from app.codirector.production_planner.wave4_reconnect import (
        WAVE4_RECONNECT_POLICY,
        link_active_wave4_plan_id,
    )
    from app.codirector.production_planner.plan_contracts import ProductionPlan

    assert WAVE4_RECONNECT_POLICY["create_draft"] == "SKIPPED"
    plan = ProductionPlan(goal="x", projectId="p")
    out, meta = link_active_wave4_plan_id(None, "p", plan)
    assert meta["linked"] is False
    assert out.wave4PlanId == ""


def test_multistep_corridor_video_footsteps_dependency_fields_dry():
    """Dry multi-step journey: corridor still → video → footsteps compile + deps."""
    from app.codirector.production_planner.compile import (
        compile_multistep_request,
        apply_dependency_block,
    )
    from app.codirector.production_planner.pack_bridge import bridge_compile_to_execution_steps
    from app.codirector.production_planner.plan_contracts import PlanStepStatus

    plan = compile_multistep_request(
        user_message=(
            "Let's plan: generate a corridor still image, then make a video from it, "
            "then add footsteps audio"
        ),
        project_id="proj-journey",
    )
    assert plan is not None
    mods = [s.params.get("modality") for s in plan.steps]
    assert mods == ["image", "video", "audio"]
    assert plan.steps[1].params.get("timelineMode") == "R2V"
    assert plan.steps[0].status == PlanStepStatus.READY
    assert plan.steps[1].status == PlanStepStatus.BLOCKED
    assert "DEPENDENCY_BLOCKED" in plan.steps[1].reasonCodes
    assert plan.steps[1].dependsOn == [plan.steps[0].stepId]
    assert plan.steps[2].dependsOn == [plan.steps[1].stepId]
    # Promote after image completes
    plan.steps[0].status = PlanStepStatus.COMPLETED
    plan.steps[0].resultAssetIds = ["asset-corridor-1"]
    apply_dependency_block(plan)
    assert plan.steps[1].status == PlanStepStatus.READY
    assert plan.steps[2].status == PlanStepStatus.BLOCKED
    bridged = bridge_compile_to_execution_steps(plan)
    assert bridged[1]["depends_on"] == [bridged[0]["step_id"]]
    assert bridged[1]["metadata"]["params"]["timelineMode"] == "R2V"

"""Wave 6P unit/contract tests."""

from __future__ import annotations

from app.codirector.production_intent.approval import evaluate_approval_requirement
from app.codirector.production_intent.bridge import to_resolver_request, to_studio_job_params
from app.codirector.production_intent.compiler import compile_intent
from app.codirector.production_intent.handoffs import create_handoff, handoff_to_intent
from app.codirector.production_intent.planner_bridge import step_to_intent
from app.codirector.production_intent.recovery import classify_failure
from app.codirector.plans.readiness import annotate_step_availability
from app.codirector.plans.schemas import ProductionPlan, ProductionPlanStep
from app.codirector.tools.registry import find
from app.video_runtime.workflow_resolver import resolve_from_scene_params, resolve_workflow
from app.video_runtime.wave6p_gate import evaluate_wave6p_gate


def test_required_media_tools_registered():
    for tid in (
        "propose_video_generate",
        "propose_shot_generate",
        "propose_scene_generate",
        "propose_three_frame_generate",
        "propose_lipsync",
        "editor.place_asset",
        "job.cancel",
        "job.retry",
    ):
        assert find(tid) is not None, tid


def test_compile_intent_and_resolve_scene():
    intent = compile_intent(
        project_id="p1",
        operation="video.scene_render",
        prompt="test",
        source_assets=["start"],
        include_creative_context=False,
    )
    req = to_resolver_request(intent)
    assert req["intent"] == "scene_render"
    contract = resolve_from_scene_params(engine="ltx", start_asset_id="start", intent="scene_render")
    params = to_studio_job_params(intent, contract.to_dict())
    assert params["productionIntent"]["intentId"] == intent.intentId
    assert params["videoRuntime"]["workflow_key"]


def test_approval_required_for_video():
    intent = compile_intent(
        project_id="p1",
        operation="video.batch_timeline",
        include_creative_context=False,
    )
    policy = evaluate_approval_requirement(intent, batch_count=3)
    assert policy.required
    assert policy.disclosure["intendedAction"] == "video.batch_timeline"


def test_planner_bridge_marks_available():
    plan = ProductionPlan(planId="pl", projectId="p1", title="t", state="approved")
    step = ProductionPlanStep(
        stepId="s1",
        title="Shot",
        proposedToolId="propose_shot_generate",
        state="ready",
        toolArguments={"sceneId": "sc1", "startAssetId": "a"},
    )
    annotated = annotate_step_availability([step])[0]
    assert annotated.executionAvailability == "available"
    intent = step_to_intent(plan, annotated)
    assert intent is not None
    assert intent.operation == "video.shot_render"


def test_handoff_traceability():
    h = create_handoff(
        project_id="p1",
        specialist_id="director",
        task_type="shot",
        inputs={"prompt": "x", "sourceAssets": ["a"]},
        recommended_operation="video.shot_render",
    )
    intent = handoff_to_intent(h)
    assert intent.handoffId == h.handoffId
    assert intent.sourceSurface == "specialist"


def test_recovery_no_uncertified_fallback():
    action = classify_failure("workflow blocked", context={"code": "workflow_blocked"})
    assert action.policy == "blocked_no_safe_fallback"
    assert action.providerChangeAllowed is False


def test_extend_and_lipsync_resolve_certified():
    ext = resolve_workflow("extend")
    lip = resolve_workflow("lipsync")
    assert str(ext.status).lower() == "certified"
    assert str(lip.status).lower() == "certified"


def test_wave6p_gate_shape():
    gate = evaluate_wave6p_gate()
    assert gate["phase"] == "M41-W6P"
    assert "wave6pGo" in gate
    assert "missingRequirements" in gate

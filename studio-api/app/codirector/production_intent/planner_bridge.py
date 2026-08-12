"""Bridge Wave 4 ProductionPlan steps → ProductionIntent (W6P-5)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..plans.schemas import ProductionPlan, ProductionPlanStep
from .compiler import compile_intent
from .execute import enqueue_intent, preflight_intent
from .schemas import ProductionIntent
from .store import get_intent_store


_TOOL_TO_OPERATION: dict[str, str] = {
    "propose_image_generate": "image.generate",
    "propose_video_generate": "video.generate",
    "propose_shot_generate": "video.shot_render",
    "propose_scene_generate": "video.scene_render",
    "propose_three_frame_generate": "video.three_frame",
    "propose_timeline_render": "video.timeline_render",
    "propose_batch_timeline": "video.batch_timeline",
    "propose_video_extend": "video.extend",
    "propose_lipsync": "video.lipsync",
    "propose_music_generate": "music.generate",
    "propose_sfx_generate": "sfx.generate",
    "audio.generate_music": "music.generate",
    "audio.generate_sfx": "sfx.generate",
    "audio.generate_ambience": "sfx.generate",
    "audio.cancel_batch": "job.cancel",
    "propose_voice_generate": "voice.generate",
    "propose_subtitle_generate": "subtitle.generate",
    "editor.place_asset": "editor.place",
    "job.cancel": "job.cancel",
    "job.retry": "job.retry",
}


def step_to_intent(
    plan: ProductionPlan,
    step: ProductionPlanStep,
    *,
    db: Any = None,
) -> Optional[ProductionIntent]:
    tool = step.proposedToolId or ""
    op = _TOOL_TO_OPERATION.get(tool)
    if not op:
        return None
    args = dict(step.toolArguments or {})
    intent = compile_intent(
        project_id=plan.projectId,
        operation=op,
        source_surface="planner",
        scene_id=str(args.get("sceneId") or step.sceneId or "") or None,
        shot_id=str(args.get("shotId") or step.shotId or "") or None,
        prompt=str(args.get("prompt") or step.title or step.description or ""),
        objective=str(step.description or step.title or op),
        source_assets=[
            str(x)
            for x in (
                args.get("sourceAssets")
                or ([args["sourceAssetId"]] if args.get("sourceAssetId") else [])
            )
            if x
        ],
        engine_preference=args.get("engine"),
        workflow_preference=args.get("workflowKey"),
        duration=float(args["durationSec"]) if args.get("durationSec") is not None else None,
        tool_id=tool,
        plan_id=plan.planId,
        plan_step_id=step.stepId,
        metadata={"planStepState": step.state, "dependencies": list(step.dependsOn or [])},
        db=db,
    )
    get_intent_store().save(intent)
    return intent


def ready_steps(plan: ProductionPlan) -> list[ProductionPlanStep]:
    """Steps that may enqueue: approved plan, step ready/available, deps satisfied."""
    completed = {s.stepId for s in plan.steps if s.state == "completed"}
    cancelled_parents = {s.stepId for s in plan.steps if s.state in {"cancelled", "failed"}}
    out: list[ProductionPlanStep] = []
    if plan.state not in {"approved", "ready", "in_progress"}:
        return out
    for s in plan.steps:
        if s.state in {"completed", "cancelled", "skipped", "superseded"}:
            continue
        if s.executionAvailability not in {None, "available"} and s.executionAvailability != "available":
            # annotated availability may be unset on raw steps
            pass
        deps = list(s.dependsOn or [])
        if any(d in cancelled_parents for d in deps):
            continue
        if any(d not in completed for d in deps):
            continue
        if s.state in {"ready", "pending", "awaiting_approval", "blocked"}:
            # blocked steps do not queue
            if s.state == "blocked":
                continue
            out.append(s)
    return out


def enqueue_ready_steps(db: Session, plan: ProductionPlan) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in ready_steps(plan):
        intent = step_to_intent(plan, step, db=db)
        if intent is None:
            results.append(
                {
                    "stepId": step.stepId,
                    "ok": False,
                    "reason": "No executable operation mapping for tool",
                    "toolId": step.proposedToolId,
                }
            )
            continue
        try:
            preflight_intent(intent)
            result = enqueue_intent(db, intent)
            results.append({"stepId": step.stepId, "ok": True, **result})
        except Exception as exc:
            results.append({"stepId": step.stepId, "ok": False, "error": str(exc), "intentId": intent.intentId})
    return results

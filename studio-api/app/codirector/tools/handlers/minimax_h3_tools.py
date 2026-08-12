"""Co-Director handlers for the MiniMax H3 planning surface."""

from __future__ import annotations

from typing import Any

from ...errors import PROJECT_REQUIRED, TOOL_ARGUMENTS_INVALID, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ....minimax_h3.capability import capability_matrix
from ....minimax_h3.contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment, H3TimelineContext
from ....minimax_h3.planner import build_plan
from ....minimax_h3.preflight import evaluate_plan, evaluate_request
from ....minimax_h3.service import cancel, create_job_or_block, get_plan, prepare_plan, preflight, request_fallback_ltx, retry
from ....minimax_h3.three_frame import build_segmented_plan
from ..definitions import ToolContext, ToolPreview


def _project_id(ctx: ToolContext) -> str:
    project_id = str(ctx.project_id or "").strip()
    if not project_id:
        raise CoDirectorError(
            PROJECT_REQUIRED,
            "Open a project before using MiniMax H3 tools.",
            recoverable=True,
            recommended_action="select_project",
        )
    return project_id


def _argument_error(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_ARGUMENTS_INVALID,
        message,
        details=details,
        recoverable=True,
        recommended_action="revise_arguments",
    )


def _target_not_found(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        message,
        details=details,
        recoverable=False,
        recommended_action="none",
    )


def _require_text(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise _argument_error(f"{key} is required.", parameter=key)
    return value


def _optional_text(args: dict[str, Any], key: str) -> str | None:
    value = str(args.get(key) or "").strip()
    return value or None


def _csv_list(args: dict[str, Any], key: str) -> list[str]:
    raw = str(args.get(key) or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _load_plan(ctx: ToolContext, plan_id: str):
    plan = get_plan(_project_id(ctx), plan_id)
    if plan is None:
        raise _target_not_found("MiniMax H3 plan not found in this project.", planId=plan_id, projectId=ctx.project_id)
    return plan


def _request_from_args(ctx: ToolContext, args: dict[str, Any], *, force_mode: str | None = None) -> AdeptMiniMaxH3Request:
    mode = force_mode or _require_text(args, "mode")
    assignments: list[H3ReferenceAssignment] = []
    if _optional_text(args, "startAssetId"):
        assignments.append(H3ReferenceAssignment(role="start", assetId=_require_text(args, "startAssetId"), displayName="Start"))
    if _optional_text(args, "middleAssetId"):
        assignments.append(
            H3ReferenceAssignment(role="middle", assetId=_require_text(args, "middleAssetId"), displayName="Middle")
        )
    if _optional_text(args, "endAssetId"):
        assignments.append(H3ReferenceAssignment(role="end", assetId=_require_text(args, "endAssetId"), displayName="End"))
    for index, asset_id in enumerate(_csv_list(args, "referenceAssetIdsCsv"), start=1):
        assignments.append(H3ReferenceAssignment(role="reference", assetId=asset_id, displayName=f"Reference {index}"))
    timeline_context = H3TimelineContext(
        sceneId=_optional_text(args, "sceneId") or ctx.scene_id,
        shotId=_optional_text(args, "shotId"),
        assemblyPlan="segmented-a" if mode == "three-frame" else None,
    )
    return AdeptMiniMaxH3Request(
        projectId=_project_id(ctx),
        prompt=_require_text(args, "prompt"),
        territory=_optional_text(args, "territory") or "",
        sourceSurface="codirector",
        mode=mode,  # type: ignore[arg-type]
        deployment=(_optional_text(args, "deployment") or "local_weights"),  # type: ignore[arg-type]
        durationSec=float(args.get("durationSec") or 5),
        referenceAssignments=assignments,
        audioAssetId=_optional_text(args, "audioAssetId"),
        approvalId=_optional_text(args, "approvalId"),
        timelineContext=timeline_context,
        creatorNotes=_optional_text(args, "creatorNotes"),
    )


async def capability(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    territory = _optional_text(args, "territory") or ""
    return {
        "ok": True,
        "capability": capability_matrix(territory),
        "_summary": "MiniMax H3 capability snapshot loaded.",
        "_evidence": {"source": "minimax_h3.capability"},
    }


async def get_plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    return {
        "ok": True,
        "plan": plan.model_dump(mode="json"),
        "_summary": plan.creatorSummary,
        "_evidence": {"source": "minimax_h3.store"},
    }


async def preflight_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    result = evaluate_plan(plan, approval_id=_optional_text(args, "approvalId"))
    return {
        "ok": True,
        "planId": plan.planId,
        "preflight": result.model_dump(mode="json"),
        "_summary": result.blockers[0] if result.blockers else "MiniMax H3 preflight checked.",
        "_evidence": {"source": "minimax_h3.preflight"},
    }


def preview_prepare_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    request = _request_from_args(ctx, args)
    plan = build_plan(request)
    check = evaluate_request(request)
    return ToolPreview(
        summary="Prepare a MiniMax H3 plan for this project.",
        lines=[
            plan.creatorSummary,
            f"Mode: {plan.mode}",
            f"Deployment: {plan.deployment}",
            f"Preflight: {check.status}",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
        warnings=list(check.blockers[:1] or check.warnings[:1]),
    )


def apply_prepare_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = prepare_plan(_request_from_args(ctx, args))
    return {
        "ok": True,
        "planId": plan.planId,
        "plan": plan.model_dump(mode="json"),
        "preflight": plan.preflight.model_dump(mode="json") if plan.preflight else None,
        "_summary": plan.creatorSummary,
        "_evidence": {"source": "minimax_h3.service.prepare_plan"},
    }


def preview_prepare_three_frame(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    request = _request_from_args(ctx, args, force_mode="three-frame")
    warnings: list[str] = []
    try:
        three_frame_plan = build_segmented_plan(request)
        lines = [
            "MiniMax H3 will use a two-part assembly plan.",
            *(interval.label for interval in three_frame_plan.intervals),
        ]
    except ValueError as exc:
        lines = ["MiniMax H3 needs three distinct frames before the plan can be assembled."]
        warnings.append(str(exc))
    return ToolPreview(
        summary="Prepare a three-frame MiniMax H3 assembly plan.",
        lines=lines,
        resourceKind="project",
        resourceId=_project_id(ctx),
        warnings=warnings,
    )


def apply_prepare_three_frame(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = prepare_plan(_request_from_args(ctx, args, force_mode="three-frame"))
    return {
        "ok": True,
        "planId": plan.planId,
        "threeFramePlan": plan.threeFramePlan.model_dump(mode="json") if plan.threeFramePlan else None,
        "plan": plan.model_dump(mode="json"),
        "_summary": "Three-frame MiniMax H3 plan prepared.",
        "_evidence": {"source": "minimax_h3.three_frame + minimax_h3.service.prepare_plan"},
    }


def preview_request_generation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    result = evaluate_plan(plan, approval_id=_optional_text(args, "approvalId"))
    warnings = list(result.blockers[:1] or result.warnings[:1])
    return ToolPreview(
        summary="Request MiniMax H3 generation from the stored plan.",
        lines=[
            plan.creatorSummary,
            f"Deployment: {plan.deployment}",
            f"Preflight: {result.status}",
            "No hidden model switch is allowed. LTX remains an explicit fallback choice only.",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
        warnings=warnings,
    )


def apply_request_generation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return create_job_or_block(_project_id(ctx), _require_text(args, "planId"), approval_id=_optional_text(args, "approvalId"))


def preview_offer_ltx_fallback(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    result = evaluate_plan(plan)
    warning = result.blockers[0] if result.blockers else "LTX fallback is available only as an explicit choice."
    return ToolPreview(
        summary="Prepare an explicit LTX fallback offer.",
        lines=[
            "This keeps the prompt, frames, and references together.",
            "MiniMax H3 will not switch automatically.",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
        warnings=[warning],
    )


def apply_offer_ltx_fallback(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = preflight(_load_plan(ctx, _require_text(args, "planId")))
    return {
        "ok": True,
        "planId": plan.planId,
        "fallbackOffer": plan.fallbackOffer.model_dump(mode="json") if plan.fallbackOffer else None,
        "_summary": "Explicit LTX fallback offer prepared.",
        "_evidence": {"source": "minimax_h3.preflight"},
    }


def preview_accept_ltx_fallback(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    return ToolPreview(
        summary="Accept the explicit LTX fallback for this plan.",
        lines=[
            "The prompt, frames, and references stay attached.",
            "This is recorded as a deliberate fallback choice.",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
    )


def apply_accept_ltx_fallback(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = request_fallback_ltx(_project_id(ctx), _require_text(args, "planId"), accepted_by=_optional_text(args, "acceptedBy") or "creator")
    return {
        "ok": True,
        "planId": plan.planId,
        "fallback": plan.fallbackOffer.model_dump(mode="json") if plan.fallbackOffer else None,
        "preserved": {
            "prompt": plan.request.prompt,
            "frames": [item.model_dump(mode="json") for item in plan.referenceAssignments],
            "audioAssetId": plan.request.audioAssetId,
        },
        "_summary": "LTX fallback accepted explicitly.",
        "_evidence": {"source": "minimax_h3.service.request_fallback_ltx"},
    }


def preview_cancel(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Cancel this MiniMax H3 plan request.",
        lines=["The plan remains stored, but its active request state will be marked cancelled."],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_cancel(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = cancel(_project_id(ctx), _require_text(args, "planId"), reason=_optional_text(args, "reason"))
    return {
        "ok": True,
        "plan": plan.model_dump(mode="json"),
        "_summary": "MiniMax H3 plan cancelled.",
        "_evidence": {"source": "minimax_h3.service.cancel"},
    }


def preview_retry(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    return ToolPreview(
        summary="Retry this MiniMax H3 plan honestly.",
        lines=[
            "Retry reruns the same plan checks.",
            "No alternate runtime is selected unless the creator chooses it explicitly.",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
    )


def apply_retry(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = retry(_project_id(ctx), _require_text(args, "planId"), approval_id=_optional_text(args, "approvalId"))
    return {
        "ok": True,
        "plan": plan.model_dump(mode="json"),
        "preflight": plan.preflight.model_dump(mode="json") if plan.preflight else None,
        "_summary": "MiniMax H3 plan retried honestly.",
        "_evidence": {"source": "minimax_h3.service.retry"},
    }

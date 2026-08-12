"""Canonical plan validation service."""

from __future__ import annotations

from .dependencies import validate_dependencies
from .schemas import (
    PlanValidationIssue,
    PlanValidationResult,
    ProductionPlan,
)


# Still non-executable / not Production Ready (enhance + cloud stubs)
_DEFERRED_TOOL_PREFIXES = (
    "propose_image_upscale",
    "propose_video_upscale",
    "propose_background",
    "propose_portrait",
    "propose_brand",
)

_W6P_EXECUTABLE_PREFIXES = (
    "propose_image_generate",
    "propose_video_generate",
    "propose_video_extend",
    "propose_shot_generate",
    "propose_scene_generate",
    "propose_three_frame",
    "propose_timeline_render",
    "propose_batch_timeline",
    "propose_lipsync",
    "propose_music_generate",
    "propose_sfx_generate",
    "audio.generate_",
    "audio.select_",
    "audio.approve_",
    "audio.place",
    "audio.replace_",
    "propose_voice_generate",
    "propose_subtitle_generate",
    "editor.place_asset",
    "job.cancel",
    "job.retry",
)


def validate_plan(plan: ProductionPlan) -> PlanValidationResult:
    errors: list[PlanValidationIssue] = []
    warnings: list[PlanValidationIssue] = []

    if not plan.planId:
        errors.append(PlanValidationIssue(code="PLAN_ID_REQUIRED", message="planId is required."))
    if not plan.projectId:
        errors.append(PlanValidationIssue(code="PROJECT_REQUIRED", message="projectId is required."))
    if not (plan.title or "").strip():
        errors.append(PlanValidationIssue(code="TITLE_REQUIRED", message="title is required."))

    step_ids = [s.stepId for s in plan.steps]
    if len(step_ids) != len(set(step_ids)):
        errors.append(PlanValidationIssue(code="DUPLICATE_STEP_ID", message="Duplicate step IDs are not allowed."))

    orders = [s.order for s in plan.steps]
    if len(orders) != len(set(orders)) and plan.steps:
        warnings.append(PlanValidationIssue(code="DUPLICATE_ORDER", message="Duplicate step order values detected."))

    dep = validate_dependencies(plan.steps)
    if dep.selfDependencies:
        errors.append(
            PlanValidationIssue(
                code="PLAN_DEPENDENCY_SELF",
                message=f"Self-dependencies: {', '.join(dep.selfDependencies)}",
            )
        )
    if dep.missingDependencies:
        errors.append(
            PlanValidationIssue(
                code="PLAN_DEPENDENCY_MISSING",
                message=f"Missing dependencies: {', '.join(dep.missingDependencies)}",
            )
        )
    if dep.cycles:
        errors.append(
            PlanValidationIssue(
                code="PLAN_DEPENDENCY_CYCLE",
                message=f"Dependency cycles: {dep.cycles}",
            )
        )
    for w in dep.warnings:
        warnings.append(PlanValidationIssue(code="DEPENDENCY_WARNING", message=w))

    if plan.activeStepId and plan.activeStepId not in set(step_ids):
        errors.append(
            PlanValidationIssue(
                code="ACTIVE_STEP_INVALID",
                message=f"activeStepId '{plan.activeStepId}' is not a plan step.",
            )
        )

    if plan.state in {"approved", "ready"} and plan.unapproved:
        errors.append(
            PlanValidationIssue(
                code="UNAPPROVED_AUTHORITATIVE",
                message="Authoritative plan state cannot remain labeled unapproved.",
            )
        )

    for s in plan.steps:
        tool = s.proposedToolId or ""
        is_w6p = any(tool.startswith(p) for p in _W6P_EXECUTABLE_PREFIXES)
        is_deferred = (not is_w6p) and any(tool.startswith(p) for p in _DEFERRED_TOOL_PREFIXES)
        if is_deferred and s.executionAvailability == "available":
            errors.append(
                PlanValidationIssue(
                    code="FALSE_AVAILABLE",
                    message=f"Step '{s.stepId}' claims available for deferred tool '{tool}'.",
                    stepId=s.stepId,
                )
            )
        if s.state == "completed" and s.executionAvailability == "deferred" and not is_w6p:
            errors.append(
                PlanValidationIssue(
                    code="FALSE_COMPLETED",
                    message=f"Deferred step '{s.stepId}' cannot be marked completed.",
                    stepId=s.stepId,
                )
            )

    open_blocking = [b for b in plan.blockers if b.state == "open" and b.severity == "blocking"]
    readiness = plan.capabilitySnapshot.readiness if plan.capabilitySnapshot else "deferred"
    if open_blocking and readiness == "ready":
        warnings.append(
            PlanValidationIssue(
                code="BLOCKERS_OPEN",
                message="Open blocking blockers prevent ready readiness.",
            )
        )
        readiness = "blocked"

    if errors:
        status = "invalid"
        valid = False
    elif warnings:
        status = "valid_with_warnings"
        valid = True
    else:
        status = "valid"
        valid = True

    return PlanValidationResult(
        valid=valid,
        status=status,  # type: ignore[arg-type]
        errors=errors,
        warnings=warnings,
        readiness=readiness,  # type: ignore[arg-type]
    )

"""Co-Director handlers for the Adept Image Pipeline foundation."""

from __future__ import annotations

import json
from typing import Any

from ...errors import PROJECT_REQUIRED, TOOL_ARGUMENTS_INVALID, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ....image_pipeline import candidates as candidate_ops
from ....image_pipeline import mastering, orchestrator, posecraft_package, profiles, references, repair, router
from ....image_pipeline import shot_intelligence, spatial_package, store, validation
from ....image_pipeline.contracts import (
    ImageApprovalRequirement,
    ImageCandidate,
    ImageContinuityPackage,
    ImageRepairInstruction,
    ImageMasteringRequest,
    ImageReferenceAssignment,
    ProductionImageRequest,
    StageReceipt,
    utc_now,
)
from ....image_pipeline.creative_direction import build_creative_direction, creator_summary
from ....image_pipeline.staging_risk import recommend_staging
from ..definitions import ToolContext, ToolPreview


def _live_posecraft_payload(ctx: ToolContext, project_id: str) -> dict[str, Any] | None:
    """Hydrate the PoseCraft control payload from the project's live scene.

    Phase 5: the live PoseCraft scene is the canonical creator-driven blocking
    source. Returns None when the project has no scene yet (the orchestrator
    will then fall back to its own staging recommendation path). Never silently
    substitutes a fixture for a creator-edited scene.
    """
    try:
        package = posecraft_package.load_posecraft_control_package_for_project(project_id, ctx.db)
    except Exception:  # noqa: BLE001
        return None
    if package is None or package.source == "fixture":
        return None
    return package.model_dump(mode="json")


def _project_id(ctx: ToolContext) -> str:
    project_id = str(ctx.project_id or "").strip()
    if not project_id:
        raise CoDirectorError(
            PROJECT_REQUIRED,
            "Open a project before using Image Pipeline tools.",
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


def _bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _csv_list(args: dict[str, Any], key: str) -> list[str]:
    raw = str(args.get(key) or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _json_object_arg(args: dict[str, Any], key: str) -> dict[str, Any] | None:
    raw = args.get(key)
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _argument_error(f"{key} must be valid JSON.", parameter=key) from exc
        if not isinstance(parsed, dict):
            raise _argument_error(f"{key} must decode to an object.", parameter=key)
        return parsed
    raise _argument_error(f"{key} must be a JSON object or JSON string.", parameter=key)


def _json_string_list_arg(args: dict[str, Any], key: str) -> list[str]:
    raw = args.get(key)
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        return values
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _argument_error(f"{key} must be valid JSON.", parameter=key) from exc
        if not isinstance(parsed, list):
            raise _argument_error(f"{key} must decode to a list.", parameter=key)
        return [str(item).strip() for item in parsed if str(item).strip()]
    raise _argument_error(f"{key} must be a JSON list or JSON string.", parameter=key)


def _load_plan(ctx: ToolContext, plan_id: str):
    plan = store.load_plan(_project_id(ctx), plan_id)
    if plan is None:
        raise _target_not_found("Image pipeline plan not found in this project.", planId=plan_id, projectId=ctx.project_id)
    return plan


def _load_group(ctx: ToolContext, group_id: str):
    group = store.load_candidate_group(_project_id(ctx), group_id)
    if group is None:
        raise _target_not_found(
            "Image pipeline candidate group not found in this project.",
            groupId=group_id,
            projectId=ctx.project_id,
        )
    return group


def _refresh_plan_readiness(plan, *, touch_timestamp: bool) -> None:
    unresolved = [req for req in plan.approvalRequirements if req.status == "required"]
    if plan.modelRoute.readiness == "blocked" and plan.modelRoute.requiresApproval and not plan.modelRoute.approvedForUse:
        plan.readiness = "blocked"
    elif unresolved:
        plan.readiness = "warning"
    else:
        plan.readiness = "ready"
    if touch_timestamp:
        plan.updatedAt = utc_now()


def _mark_stage(plan, stage_key: str, status: str, summary: str) -> None:
    for stage in plan.stages:
        if stage.stageKey == stage_key:
            stage.status = status
            stage.summary = summary
            break


def _append_plan_receipt(plan, stage_key: str, note: str) -> None:
    plan.stageReceipts.append(StageReceipt(planId=plan.planId, stageKey=stage_key, note=note))


def _append_group_receipt(group, plan_id: str, stage_key: str, note: str) -> None:
    group.stageReceipts.append(StageReceipt(planId=plan_id, stageKey=stage_key, note=note))


def _sync_route_approval(plan) -> None:
    route_requirement = next((item for item in plan.approvalRequirements if item.kind == "deployment-route"), None)
    if plan.modelRoute.requiresApproval:
        if route_requirement is None:
            plan.approvalRequirements.append(
                ImageApprovalRequirement(
                    kind="deployment-route",
                    status="required",
                    reason=plan.modelRoute.approvalReason,
                    creatorTip="Approve the paid route explicitly, or switch back to a local route.",
                )
            )
        elif route_requirement.status == "not-required":
            route_requirement.status = "required"
            route_requirement.reason = plan.modelRoute.approvalReason
    elif route_requirement is not None and route_requirement.status == "required":
        route_requirement.status = "approved"
        route_requirement.approvedBy = "system"
        route_requirement.approvedAt = utc_now()


def _save_plan(plan) -> None:
    plan.updatedAt = utc_now()
    store.save_plan(plan)


def _save_group(group) -> None:
    group.updatedAt = utc_now()
    store.save_candidate_group(group)


def _creator_lines_for_plan(plan) -> list[str]:
    route_target = "API" if plan.modelRoute.deploymentTarget == "api" else "Local"
    lines = [
        plan.previewSummary,
        f"Quality: {plan.request.qualityProfile}",
        f"Staging: {plan.controlPackage.stagingRecommendation}",
        f"Route: {plan.modelRoute.modelFamily} via {route_target}",
        f"Readiness: {plan.readiness}",
    ]
    if plan.readinessReasons:
        lines.append(plan.readinessReasons[0])
    return lines


def _group_summary(group) -> dict[str, Any]:
    counts: dict[str, int] = {}
    selected_candidate_id = None
    for candidate in group.candidates:
        status = str(candidate.status or "draft")
        counts[status] = counts.get(status, 0) + 1
        if candidate.creatorSelected:
            selected_candidate_id = candidate.candidateId
    return {
        "groupId": group.groupId,
        "planId": group.planId,
        "status": group.status,
        "requestedCount": group.requestedCount,
        "candidateCount": len(group.candidates),
        "statusCounts": counts,
        "recommendedCandidateId": group.recommendedCandidateId,
        "selectedCandidateId": selected_candidate_id,
        "explanation": group.explanation,
        "candidates": [candidate.model_dump(mode="json") for candidate in group.candidates],
    }


def _readiness_payload(plan) -> dict[str, Any]:
    warnings = list(plan.readinessReasons)
    for requirement in plan.approvalRequirements:
        if requirement.status == "required" and requirement.reason:
            warnings.append(requirement.reason)
    if plan.modelRoute.honestyNote:
        warnings.append(plan.modelRoute.honestyNote)
    return {
        "projectId": plan.projectId,
        "planId": plan.planId,
        "readiness": plan.readiness,
        "reasons": list(plan.readinessReasons),
        "warnings": warnings,
        "route": plan.modelRoute.model_dump(mode="json"),
        "approvalRequirements": [item.model_dump(mode="json") for item in plan.approvalRequirements],
    }


def _request_from_args(ctx: ToolContext, args: dict[str, Any], *, existing_plan=None) -> ProductionImageRequest:
    project_id = _project_id(ctx)
    base_request = existing_plan.request if existing_plan is not None else None
    prompt = _optional_text(args, "prompt") or (base_request.prompt if base_request is not None else "")
    if not prompt:
        raise _argument_error("prompt is required.", parameter="prompt")
    purpose = _optional_text(args, "purpose") or (base_request.purpose if base_request is not None else "storyboard")
    quality_profile = str(args.get("qualityProfile") or (base_request.qualityProfile if base_request is not None else "enhanced"))
    deployment_preference = str(
        args.get("deploymentPreference") or (base_request.deploymentPreference if base_request is not None else "best-match")
    )
    candidate_count = int(args.get("candidateCount") or (base_request.candidateCount if base_request is not None else 3))
    request = ProductionImageRequest(
        projectId=project_id,
        prompt=prompt,
        purpose=purpose,
        qualityProfile=quality_profile,  # type: ignore[arg-type]
        deploymentPreference=deployment_preference,  # type: ignore[arg-type]
        styleProfileId=_optional_text(args, "styleProfileId") or (base_request.styleProfileId if base_request is not None else None),
        allowApiDeployment=_bool(
            args,
            "allowApiDeployment",
            base_request.allowApiDeployment if base_request is not None else deployment_preference == "api",
        ),
        candidateCount=candidate_count,
        projectContext=_json_object_arg(args, "projectContextJson")
        or (dict(base_request.projectContext) if base_request is not None else {}),
        characterIds=_json_string_list_arg(args, "characterIdsJson")
        or _csv_list(args, "characterIdsCsv")
        or (list(base_request.characterIds) if base_request is not None else []),
        referenceAssetIds=_json_string_list_arg(args, "referenceAssetIdsJson")
        or _csv_list(args, "referenceAssetIdsCsv")
        or (list(base_request.referenceAssetIds) if base_request is not None else []),
        spatialMapPayload=_json_object_arg(args, "spatialMapJson")
        or (dict(base_request.spatialMapPayload) if base_request is not None and base_request.spatialMapPayload else None),
        poseControlPayload=_json_object_arg(args, "poseControlJson")
        or (dict(base_request.poseControlPayload) if base_request is not None and base_request.poseControlPayload else None)
        or _live_posecraft_payload(ctx, project_id),
        continuityNotes=_json_string_list_arg(args, "continuityNotesJson")
        or _csv_list(args, "continuityNotesCsv")
        or (list(base_request.continuityNotes) if base_request is not None else []),
        creatorNotes=_optional_text(args, "creatorNotes") or (base_request.creatorNotes if base_request is not None else None),
    )
    return request


def _candidate_from_args(group, args: dict[str, Any]):
    candidate_id = _optional_text(args, "candidateId")
    if candidate_id:
        candidate = next((item for item in group.candidates if item.candidateId == candidate_id), None)
        if candidate is None:
            raise _target_not_found("Image pipeline candidate not found in this group.", candidateId=candidate_id)
        return candidate
    selected = next((item for item in group.candidates if item.creatorSelected), None)
    if selected is not None:
        return selected
    if group.candidates:
        return group.candidates[0]
    raise _target_not_found("This candidate group does not have any candidates yet.", groupId=group.groupId)


def _instruction_from_args(candidate, args: dict[str, Any]):
    instruction_payload = _json_object_arg(args, "instructionJson")
    if instruction_payload:
        return ImageRepairInstruction.model_validate(instruction_payload)
    if candidate.evaluation is None:
        raise _argument_error("Candidate must be evaluated before a repair can be prepared.", candidateId=candidate.candidateId)
    instructions = repair.least_destructive_repair_ladder(candidate.evaluation)
    if not instructions:
        raise _target_not_found("No repair instruction is available for this candidate.", candidateId=candidate.candidateId)
    index = int(args.get("instructionIndex") or 0)
    if index < 0 or index >= len(instructions):
        raise _argument_error("instructionIndex is out of range.", instructionIndex=index)
    return instructions[index]


async def analyze_request(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prompt = _require_text(args, "prompt")
    project_context = _json_object_arg(args, "projectContextJson") or {}
    style_profile_id = _optional_text(args, "styleProfileId")
    project_policy = _optional_text(args, "projectPolicy") or "Ask"
    shot = shot_intelligence.interpret_shot(prompt, project_context)
    creative = build_creative_direction(prompt, shot, style_profile_id)
    staging = recommend_staging(shot, creative, project_policy=project_policy)
    return {
        "ok": True,
        "prompt": prompt,
        "shotIntent": shot.model_dump(mode="json"),
        "creativeDirection": creative.model_dump(mode="json"),
        "creatorSummary": creator_summary(creative),
        "stagingRecommendation": staging.get("recommendation"),
        "stagingReasons": list(staging.get("reasons") or []),
        "clarificationQuestion": shot.clarificationQuestion,
        "_summary": creator_summary(creative),
        "_evidence": {"source": "image_pipeline.shot_intelligence + creative_direction"},
    }


async def get_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    _refresh_plan_readiness(plan, touch_timestamp=False)
    return _readiness_payload(plan)


async def get_job(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    if group.planId != plan.planId:
        raise _argument_error("groupId does not belong to the requested plan.", planId=plan.planId, groupId=group.groupId)
    return {
        "ok": True,
        "plan": plan.model_dump(mode="json"),
        "readiness": _readiness_payload(plan),
        "group": group.model_dump(mode="json"),
        "summary": _group_summary(group),
        "_summary": f"{len(group.candidates)} candidate(s) in group {group.groupId}.",
        "_evidence": {"source": "image_pipeline.store"},
    }


async def preview_posecraft(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    existing = plan.controlPackage.poseCraft
    force = _bool(args, "force", False)
    payload = _json_object_arg(args, "poseControlJson")
    if existing is not None and existing.creatorModified and not force:
        return {
            "ok": True,
            "planId": plan.planId,
            "status": "preserve_existing",
            "creatorModified": True,
            "message": "Existing creator-edited PoseCraft controls will be preserved unless force=true.",
            "poseCraft": existing.model_dump(mode="json"),
        }
    preview_package = posecraft_package.load_posecraft_control_package(
        payload or (existing.model_dump(mode="json") if existing is not None else None),
        creator_modified=bool(existing.creatorModified) if existing is not None else False,
    )
    return {
        "ok": True,
        "planId": plan.planId,
        "status": "preview_ready",
        "creatorModified": bool(existing.creatorModified) if existing is not None else False,
        "message": "Preview only. This does not overwrite the plan until the approval-gated tool is applied.",
        "poseCraft": preview_package.model_dump(mode="json"),
    }


def preview_prepare_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = orchestrator.prepare_plan(_request_from_args(ctx, args), project_policy=_optional_text(args, "projectPolicy") or "Ask")
    return ToolPreview(
        summary="Prepare an Image Pipeline plan for this prompt.",
        lines=_creator_lines_for_plan(plan),
        resourceKind="project",
        resourceId=_project_id(ctx),
        warnings=["No generation runs here. This stores a plan only."],
    )


def apply_prepare_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = orchestrator.prepare_plan(_request_from_args(ctx, args), project_policy=_optional_text(args, "projectPolicy") or "Ask")
    _mark_stage(plan, "prepare", "complete", "Plan prepared and stored for creator review.")
    _append_plan_receipt(plan, "prepare", "Plan prepared via Co-Director Image Pipeline tools.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "creatorPreview": plan.previewSummary,
        "plan": plan.model_dump(mode="json"),
        "readiness": _readiness_payload(plan),
        "_summary": plan.previewSummary,
        "_evidence": {"source": "image_pipeline.orchestrator.prepare_plan + store.save_plan"},
    }


def preview_prepare_creative_direction(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    prompt = _optional_text(args, "prompt") or plan.request.prompt
    shot = shot_intelligence.interpret_shot(prompt, plan.request.projectContext)
    creative = build_creative_direction(prompt, shot, _optional_text(args, "styleProfileId") or plan.request.styleProfileId)
    return ToolPreview(
        summary="Refresh the creative direction for this image plan.",
        lines=[
            f"Plan: {plan.planId}",
            f"Purpose: {creative.scenePurpose}",
            f"Mood: {creative.mood}",
            f"Audience focus: {', '.join(creative.audienceFocus[:2]) or 'story clarity'}",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
    )


def apply_prepare_creative_direction(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    prompt = _optional_text(args, "prompt") or plan.request.prompt
    plan.request.prompt = prompt
    plan.request.styleProfileId = _optional_text(args, "styleProfileId") or plan.request.styleProfileId
    plan.shotIntent = shot_intelligence.interpret_shot(prompt, plan.request.projectContext)
    plan.creativeDirection = build_creative_direction(prompt, plan.shotIntent, plan.request.styleProfileId)
    plan.previewSummary = orchestrator.creator_plan_preview(plan)
    _mark_stage(plan, "prepare", "complete", "Creative direction refreshed.")
    _append_plan_receipt(plan, "prepare", "Creative direction refreshed for the current prompt.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "creativeDirection": plan.creativeDirection.model_dump(mode="json"),
        "creatorPreview": plan.previewSummary,
        "plan": plan.model_dump(mode="json"),
        "_summary": plan.creativeDirection.creatorSummary or creator_summary(plan.creativeDirection),
        "_evidence": {"source": "image_pipeline.creative_direction + store.save_plan"},
    }


def preview_select_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    next_profile = _require_text(args, "qualityProfile")
    preview_route = router.choose_model_route(
        quality_profile=next_profile,  # type: ignore[arg-type]
        deployment_preference=plan.request.deploymentPreference,
        allow_api_deployment=plan.request.allowApiDeployment,
    )
    preview_stages = profiles.build_profile_stages(
        next_profile,  # type: ignore[arg-type]
        plan.controlPackage.stagingRecommendation,
        preview_route.requiresApproval,
    )
    return ToolPreview(
        summary="Change the quality profile for this image plan.",
        lines=[
            f"Plan: {plan.planId}",
            f"Profile: {plan.request.qualityProfile} -> {next_profile}",
            f"Route: {preview_route.modelFamily} via {preview_route.deploymentTarget}",
            f"Stages: {len(preview_stages)}",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
    )


def apply_select_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    plan.request.qualityProfile = _require_text(args, "qualityProfile")  # type: ignore[assignment]
    plan.modelRoute = router.choose_model_route(
        quality_profile=plan.request.qualityProfile,
        deployment_preference=plan.request.deploymentPreference,
        allow_api_deployment=plan.request.allowApiDeployment,
    )
    _sync_route_approval(plan)
    plan.stages = profiles.build_profile_stages(
        plan.request.qualityProfile,
        plan.controlPackage.stagingRecommendation,
        plan.modelRoute.requiresApproval,
    )
    _refresh_plan_readiness(plan, touch_timestamp=False)
    plan.previewSummary = orchestrator.creator_plan_preview(plan)
    _append_plan_receipt(plan, "prepare", f"Quality profile updated to {plan.request.qualityProfile}.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "qualityProfile": plan.request.qualityProfile,
        "plan": plan.model_dump(mode="json"),
        "readiness": _readiness_payload(plan),
        "_summary": f"Profile set to {plan.request.qualityProfile}.",
        "_evidence": {"source": "image_pipeline.profiles.build_profile_stages + store.save_plan"},
    }


def preview_assign_reference(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Attach one reference to this image plan.",
        lines=[
            f"Plan: {_require_text(args, 'planId')}",
            f"Reference: {_optional_text(args, 'displayName') or _optional_text(args, 'assetId') or 'New reference'}",
            f"Role: {_optional_text(args, 'semanticRole') or 'visual_reference'}",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_assign_reference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    assignment = ImageReferenceAssignment(
        assetId=_optional_text(args, "assetId"),
        referenceId=_optional_text(args, "referenceId"),
        displayName=_optional_text(args, "displayName") or f"Reference {len(plan.references) + 1}",
        semanticRole=_optional_text(args, "semanticRole") or "visual_reference",
        semanticRoles=_json_string_list_arg(args, "semanticRolesJson")
        or _csv_list(args, "semanticRolesCsv")
        or [(_optional_text(args, "semanticRole") or "visual_reference")],
        sourceType=_optional_text(args, "sourceType") or "asset",
        characterId=_optional_text(args, "characterId"),
        lockLevel=(
            _optional_text(args, "lockLevel")
            or references.lock_level_for_reference(_optional_text(args, "semanticRole") or "visual_reference")
        ),  # type: ignore[arg-type]
        dominantColorHex=_optional_text(args, "dominantColorHex"),
        notes=_optional_text(args, "notes"),
    )
    plan.references.append(assignment)
    if assignment.assetId and assignment.assetId not in plan.request.referenceAssetIds:
        plan.request.referenceAssetIds.append(assignment.assetId)
    if assignment.characterId and assignment.characterId not in plan.request.characterIds:
        plan.request.characterIds.append(assignment.characterId)
    if plan.continuity is None:
        plan.continuity = ImageContinuityPackage()
        plan.controlPackage.continuity = plan.continuity
    if assignment.assetId and assignment.assetId not in plan.continuity.lockedReferenceIds:
        plan.continuity.lockedReferenceIds.append(assignment.assetId)
    _append_plan_receipt(plan, "prepare", f"Reference '{assignment.displayName}' attached to the plan.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "reference": assignment.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "_summary": f"Attached {assignment.displayName}.",
        "_evidence": {"source": "image_pipeline.contracts.ImageReferenceAssignment + store.save_plan"},
    }


def preview_load_spatial_map(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Attach spatial layout guidance to this image plan.",
        lines=[
            f"Plan: {_require_text(args, 'planId')}",
            "Loads a spatial package from payload when available, or an honest stub when it is not.",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_load_spatial_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    payload = _json_object_arg(args, "spatialMapJson")
    plan.request.spatialMapPayload = payload
    plan.controlPackage.spatialEnvironment = spatial_package.build_spatial_environment_package(
        plan.creativeDirection.scenePurpose,
        payload,
    )
    plan.controlPackage.stagingRecommendation = "spatialMap"
    _mark_stage(plan, "spatial", "complete", "Spatial map package attached.")
    _append_plan_receipt(plan, "spatial", "Spatial environment package attached to the plan.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "spatialEnvironment": plan.controlPackage.spatialEnvironment.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "_summary": plan.controlPackage.spatialEnvironment.environmentSummary,
        "_evidence": {"source": "image_pipeline.spatial_package.build_spatial_environment_package + store.save_plan"},
    }


def preview_prepare_posecraft(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    existing = plan.controlPackage.poseCraft
    lines = [
        f"Plan: {plan.planId}",
        "Loads the PoseCraft control fixture or supplied control payload.",
    ]
    warnings: list[str] = []
    if existing is not None and existing.creatorModified and not _bool(args, "force", False):
        warnings.append("Existing creator-edited PoseCraft controls will be preserved unless force=true.")
    return ToolPreview(
        summary="Prepare PoseCraft controls for this image plan.",
        lines=lines,
        resourceKind="plan",
        resourceId=plan.planId,
        warnings=warnings,
    )


def apply_prepare_posecraft(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    existing = plan.controlPackage.poseCraft
    force = _bool(args, "force", False)
    if existing is not None and existing.creatorModified and not force:
        _append_plan_receipt(plan, "posecraft", "Creator-edited PoseCraft controls were preserved.")
        _save_plan(plan)
        return {
            "ok": True,
            "planId": plan.planId,
            "preservedExisting": True,
            "poseCraft": existing.model_dump(mode="json"),
            "message": "Existing creator-edited PoseCraft controls were preserved. Use force=true to overwrite them.",
            "_summary": "Creator-edited PoseCraft controls preserved.",
            "_evidence": {"source": "image_pipeline.posecraft_package.preserve_existing"},
        }
    payload = _json_object_arg(args, "poseControlJson")
    creator_modified = _bool(args, "creatorModified", bool(existing.creatorModified) if existing is not None else False)
    plan.request.poseControlPayload = payload
    plan.controlPackage.poseCraft = posecraft_package.load_posecraft_control_package(payload, creator_modified=creator_modified)
    plan.controlPackage.stagingRecommendation = "poseCraft"
    _mark_stage(plan, "posecraft", "complete", "PoseCraft controls attached.")
    _append_plan_receipt(plan, "posecraft", "PoseCraft controls attached to the plan.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "poseCraft": plan.controlPackage.poseCraft.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "_summary": "PoseCraft controls attached.",
        "_evidence": {"source": "image_pipeline.posecraft_package.load_posecraft_control_package + store.save_plan"},
    }


def preview_generate_candidates(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    requested_count = int(args.get("candidateCount") or plan.request.candidateCount)
    return ToolPreview(
        summary="Generate image candidates from the prepared plan.",
        lines=[
            f"Plan: {plan.planId}",
            f"Candidates: {requested_count}",
            f"Route: {plan.modelRoute.modelFamily} via {plan.modelRoute.deploymentTarget}",
            "This starts only after approval and never claims finished assets unless the runtime actually queued jobs.",
        ],
        resourceKind="plan",
        resourceId=plan.planId,
        warnings=["If the runtime cannot queue jobs, the result stays an honest draft instead of a fake success."],
    )


def apply_generate_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    requested_count = int(args.get("candidateCount") or plan.request.candidateCount)
    group = orchestrator.generate_candidates_for_plan(plan, requested_count=requested_count, db=ctx.db)
    _append_group_receipt(group, plan.planId, "generate", f"Generation request recorded with status '{group.status}'.")
    _save_group(group)
    summary = "Real jobs were queued only when the downstream runtime accepted them."
    if group.status != "queued":
        summary = "Candidate slots were created honestly without pretending finished assets exist."
    _mark_stage(plan, "generate", "complete", summary)
    _append_plan_receipt(plan, "generate", summary)
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "group": group.model_dump(mode="json"),
        "summary": _group_summary(group),
        "message": summary,
        "_summary": summary,
        "_evidence": {"source": "image_pipeline.orchestrator.generate_candidates_for_plan + store.save_candidate_group"},
    }


def preview_evaluate_candidates(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate = _candidate_from_args(group, args)
    return ToolPreview(
        summary="Evaluate one image candidate against the prepared plan.",
        lines=[
            f"Group: {group.groupId}",
            f"Candidate: {candidate.label}",
            "Evaluation records honest pass/warning/fail/not-evaluated results. It does not create a new image.",
        ],
        resourceKind="plan",
        resourceId=group.planId,
    )


def apply_evaluate_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    if group.planId != plan.planId:
        raise _argument_error("groupId does not belong to the requested plan.", planId=plan.planId, groupId=group.groupId)
    candidate = _candidate_from_args(group, args)
    evaluation = validation.evaluate_candidate(plan, candidate)
    candidate_ops.attach_evaluation(group, candidate.candidateId, evaluation)
    _append_group_receipt(group, plan.planId, "evaluate", f"Candidate {candidate.label} evaluated as {evaluation.overallStatus}.")
    _save_group(group)
    _mark_stage(plan, "evaluate", "complete", f"{candidate.label} evaluated as {evaluation.overallStatus}.")
    _append_plan_receipt(plan, "evaluate", f"Candidate {candidate.label} evaluated as {evaluation.overallStatus}.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "candidateId": candidate.candidateId,
        "evaluation": evaluation.model_dump(mode="json"),
        "group": group.model_dump(mode="json"),
        "_summary": evaluation.summary,
        "_evidence": {"source": "image_pipeline.validation.evaluate_candidate + store.save_candidate_group"},
    }


def preview_recommend_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    group = _load_group(ctx, _require_text(args, "groupId"))
    return ToolPreview(
        summary="Recommend the best next image candidate for creator review.",
        lines=[
            f"Group: {group.groupId}",
            f"Candidates available: {len(group.candidates)}",
            "Recommendation prefers the most production-ready option with the strongest review status.",
        ],
        resourceKind="plan",
        resourceId=group.planId,
    )


def apply_recommend_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate, explanation = candidate_ops.recommend_candidate(group)
    _append_group_receipt(group, group.planId, "approve", "A recommended candidate was recorded for creator review.")
    _save_group(group)
    return {
        "ok": True,
        "groupId": group.groupId,
        "recommendedCandidateId": candidate.candidateId if candidate else None,
        "explanation": explanation,
        "group": group.model_dump(mode="json"),
        "_summary": explanation,
        "_evidence": {"source": "image_pipeline.candidates.recommend_candidate + store.save_candidate_group"},
    }


def preview_select_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Select one image candidate as the creator's current choice.",
        lines=[
            f"Group: {_require_text(args, 'groupId')}",
            f"Candidate: {_require_text(args, 'candidateId')}",
            "Selection does not fake mastering or timeline placement.",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_select_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate_id = _require_text(args, "candidateId")
    candidate_ops.select_candidate(group, candidate_id)
    candidate = next((item for item in group.candidates if item.candidateId == candidate_id), None)
    _append_group_receipt(group, plan.planId, "approve", f"Candidate {candidate_id} selected.")
    _save_group(group)
    _mark_stage(plan, "approve", "complete", f"Selected {candidate.label if candidate else candidate_id}.")
    _append_plan_receipt(plan, "approve", f"Selected {candidate.label if candidate else candidate_id}.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "candidateId": candidate_id,
        "group": group.model_dump(mode="json"),
        "_summary": f"Selected {candidate.label if candidate else candidate_id}.",
        "_evidence": {"source": "image_pipeline.candidates.select_candidate + store.save_candidate_group"},
    }


def preview_prepare_repair(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Prepare the least-destructive repair ladder for a candidate.",
        lines=[
            f"Group: {_require_text(args, 'groupId')}",
            f"Candidate: {_optional_text(args, 'candidateId') or 'selected/first candidate'}",
            "This builds repair instructions only. It does not create a new asset.",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_prepare_repair(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate = _candidate_from_args(group, args)
    if candidate.evaluation is None:
        raise _argument_error("Candidate must be evaluated before repair instructions can be built.", candidateId=candidate.candidateId)
    regression = None
    parent_candidate_id = _optional_text(args, "parentCandidateId")
    if parent_candidate_id:
        parent = next((item for item in group.candidates if item.candidateId == parent_candidate_id), None)
        if parent is None or parent.evaluation is None:
            raise _argument_error("Parent candidate evaluation not found.", parentCandidateId=parent_candidate_id)
        regression = repair.reject_regression(parent.evaluation, candidate.evaluation)
    instructions = repair.least_destructive_repair_ladder(candidate.evaluation)
    _mark_stage(plan, "repair", "complete", f"Repair ladder prepared for {candidate.label}.")
    _append_plan_receipt(plan, "repair", f"Repair ladder prepared for {candidate.label}.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "candidateId": candidate.candidateId,
        "instructions": [item.model_dump(mode="json") for item in instructions],
        "regression": regression,
        "_summary": f"{len(instructions)} repair step(s) prepared for {candidate.label}.",
        "_evidence": {"source": "image_pipeline.repair.least_destructive_repair_ladder"},
    }


def preview_apply_repair(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Record an approved repair attempt without faking a new image asset.",
        lines=[
            f"Group: {_require_text(args, 'groupId')}",
            f"Candidate: {_optional_text(args, 'candidateId') or 'selected/first candidate'}",
            "This records the repair plan as a draft follow-up candidate. It does not claim a rendered result.",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
        warnings=["A follow-up draft candidate will be recorded, not a finished repaired image."],
    )


def apply_apply_repair(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate = _candidate_from_args(group, args)
    instruction = _instruction_from_args(candidate, args)
    draft = ImageCandidate(
        groupId=group.groupId,
        projectId=group.projectId,
        planId=group.planId,
        label=f"{candidate.label} Repair Draft",
        status="draft",
        previewText=f"{candidate.previewText}\nRepair action: {instruction.action}".strip(),
        explanation=(
            f"Repair instruction recorded honestly: {instruction.action}. "
            "No new asset has been generated yet."
        ),
        parentCandidateId=candidate.candidateId,
        provenance=candidate.provenance.model_copy(
            update={
                "note": "Repair draft recorded from an approved Co-Director repair instruction.",
                "details": {
                    **candidate.provenance.details,
                    "repairInstructionId": instruction.instructionId,
                    "repairAction": instruction.action,
                },
            }
        ),
    )
    candidate_ops.add_candidate(group, draft)
    group.status = "draft"
    _append_group_receipt(group, plan.planId, "repair", f"Repair draft recorded from {candidate.label}.")
    _save_group(group)
    _mark_stage(plan, "repair", "complete", f"Repair draft recorded from {candidate.label}.")
    _append_plan_receipt(plan, "repair", f"Repair draft recorded from {candidate.label}.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "parentCandidateId": candidate.candidateId,
        "repairCandidateId": draft.candidateId,
        "instruction": instruction.model_dump(mode="json"),
        "group": group.model_dump(mode="json"),
        "_summary": f"Recorded a repair draft for {candidate.label} without claiming a new asset.",
        "_evidence": {"source": "image_pipeline.repair.record_only + store.save_candidate_group"},
    }


def preview_master(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Record an approved mastering result for an image candidate.",
        lines=[
            f"Plan: {_require_text(args, 'planId')}",
            f"Group: {_require_text(args, 'groupId')}",
            f"Candidate: {_require_text(args, 'candidateId')}",
            f"Action: {_optional_text(args, 'requestedAction') or 'resize'}",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
        warnings=["Foundation mastering records the request honestly; it does not invent an upscale artifact."],
    )


def apply_master(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    group = _load_group(ctx, _require_text(args, "groupId"))
    candidate = next((item for item in group.candidates if item.candidateId == _require_text(args, "candidateId")), None)
    if candidate is None:
        raise _target_not_found("Image pipeline candidate not found in this group.", candidateId=args.get("candidateId"))
    request = ImageMasteringRequest(
        candidateId=candidate.candidateId,
        requestedAction=(_optional_text(args, "requestedAction") or "resize"),  # type: ignore[arg-type]
        targetLongEdgePx=int(args.get("targetLongEdgePx")) if args.get("targetLongEdgePx") not in (None, "") else None,
        approved=True,
        notes=_optional_text(args, "notes"),
    )
    result = mastering.build_mastering_result(request, candidate, plan=plan)
    if result.status == "completed":
        candidate.status = "mastered"
        candidate.updatedAt = utc_now()
        _save_group(group)
    _mark_stage(plan, "master", "complete" if result.status == "completed" else "blocked", result.disclosure)
    _append_plan_receipt(plan, "master", result.disclosure)
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "groupId": group.groupId,
        "mastering": result.model_dump(mode="json"),
        "group": group.model_dump(mode="json"),
        "_summary": result.disclosure,
        "_evidence": {"source": "image_pipeline.mastering.build_mastering_result"},
    }


def preview_approve(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Approve one pending image pipeline requirement.",
        lines=[
            f"Plan: {_require_text(args, 'planId')}",
            f"Requirement: {_optional_text(args, 'kind') or 'all pending requirements'}",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_approve(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    approved_by = _optional_text(args, "approvedBy") or "creator"
    kind = _optional_text(args, "kind")
    kinds = {kind} if kind else {item.kind for item in plan.approvalRequirements}
    for requirement in plan.approvalRequirements:
        if requirement.kind in kinds and requirement.status == "required":
            requirement.status = "approved"
            requirement.approvedBy = approved_by
            requirement.approvedAt = utc_now()
    if plan.modelRoute.requiresApproval and kind in {None, "deployment-route"}:
        plan.modelRoute.requiresApproval = False
        plan.modelRoute.approvedForUse = True
        plan.modelRoute.readiness = "ready"
    _refresh_plan_readiness(plan, touch_timestamp=False)
    _mark_stage(plan, "approval", "complete", "Required approval recorded.")
    _append_plan_receipt(plan, "approval", "Required image pipeline approval recorded.")
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "plan": plan.model_dump(mode="json"),
        "readiness": _readiness_payload(plan),
        "_summary": f"Approval recorded by {approved_by}.",
        "_evidence": {"source": "image_pipeline.approval + store.save_plan"},
    }


def preview_cancel(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Cancel further progress on this image plan honestly.",
        lines=[
            f"Plan: {_require_text(args, 'planId')}",
            "Marks the plan as blocked/cancelled without pretending the work completed.",
        ],
        resourceKind="plan",
        resourceId=_require_text(args, "planId"),
    )


def apply_cancel(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _load_plan(ctx, _require_text(args, "planId"))
    reason = _optional_text(args, "reason") or "Cancelled by creator request."
    plan.readiness = "blocked"
    if reason not in plan.readinessReasons:
        plan.readinessReasons.append(reason)
    plan.modelRoute.readiness = "blocked"
    plan.modelRoute.honestyNote = reason
    existing = next((item for item in plan.approvalRequirements if item.kind == "plan-cancelled"), None)
    if existing is None:
        plan.approvalRequirements.append(
            ImageApprovalRequirement(
                kind="plan-cancelled",
                status="blocked",
                reason=reason,
                creatorTip="Create a fresh plan when you want to resume this image request.",
            )
        )
    else:
        existing.status = "blocked"
        existing.reason = reason
    for stage in plan.stages:
        if stage.status == "pending":
            stage.status = "skipped"
            stage.summary = "Skipped because the plan was cancelled."
    _append_plan_receipt(plan, "approve", reason)
    _save_plan(plan)
    return {
        "ok": True,
        "planId": plan.planId,
        "plan": plan.model_dump(mode="json"),
        "readiness": _readiness_payload(plan),
        "_summary": reason,
        "_evidence": {"source": "image_pipeline.cancel + store.save_plan"},
    }


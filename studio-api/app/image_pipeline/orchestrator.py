"""Foundation orchestration layer for image pipeline planning and draft generation."""

from __future__ import annotations

from typing import Any

from .candidates import create_candidate_group
from .contracts import (
    ImageApprovalRequirement,
    ImageCandidateGroup,
    ImageControlPackage,
    ImageGenerationPlan,
    ImagePipelineStage,
    ProductionImageRequest,
    ProvenanceRecord,
    StageReceipt,
    utc_now,
)
from .creative_direction import build_creative_direction, creator_summary
from .posecraft_package import load_posecraft_control_package
from .profiles import build_profile_stages
from .references import build_figure_color_map, build_reference_assignments, choose_lock_level
from .router import choose_model_route
from .shot_intelligence import interpret_shot
from .spatial_package import build_spatial_environment_package
from .staging_risk import recommend_staging


def prepare_plan(
    request: ProductionImageRequest | dict[str, Any],
    *,
    project_policy: str = "Ask",
) -> ImageGenerationPlan:
    req = request if isinstance(request, ProductionImageRequest) else ProductionImageRequest.model_validate(request)
    shot_intent = interpret_shot(req.prompt, req.projectContext)
    creative_direction = build_creative_direction(req.prompt, shot_intent, req.styleProfileId)
    reference_assignments = build_reference_assignments(req.referenceAssetIds, req.characterIds)
    continuity = None
    if req.characterIds or req.continuityNotes or reference_assignments:
        continuity = {
            "characterLockLevel": choose_lock_level(len(req.characterIds), req.qualityProfile == "studio-master"),
            "continuityNotes": list(req.continuityNotes),
            "protectedElements": ["core identity", "wardrobe silhouette"] if req.characterIds else [],
            "lockedReferenceIds": [item.assetId for item in reference_assignments if item.assetId],
            "figureColorMap": build_figure_color_map(req.characterIds),
        }
    staging = recommend_staging(shot_intent, creative_direction, project_policy=project_policy)  # type: ignore[arg-type]
    route = choose_model_route(
        quality_profile=req.qualityProfile,
        deployment_preference=req.deploymentPreference,
        allow_api_deployment=req.allowApiDeployment,
    )
    control_package = ImageControlPackage(
        stagingRecommendation=staging["recommendation"],  # type: ignore[arg-type]
        projectPolicy=staging["projectPolicy"],  # type: ignore[arg-type]
        continuity=continuity,
        honestyNotes=list(staging["reasons"]),  # type: ignore[arg-type]
    )
    if control_package.stagingRecommendation == "poseCraft":
        control_package.poseCraft = load_posecraft_control_package(req.poseControlPayload, creator_modified=False)
    if control_package.stagingRecommendation == "spatialMap":
        control_package.spatialEnvironment = build_spatial_environment_package(
            creative_direction.scenePurpose,
            req.spatialMapPayload,
        )

    approval_requirements: list[ImageApprovalRequirement] = []
    staging_approval = staging["approvalRequirement"]
    if isinstance(staging_approval, ImageApprovalRequirement) and staging_approval.status != "not-required":
        approval_requirements.append(staging_approval)
    if route.requiresApproval:
        approval_requirements.append(
            ImageApprovalRequirement(
                kind="deployment-route",
                status="required",
                reason=route.approvalReason,
                creatorTip="Approve the paid route explicitly, or switch back to a local route.",
            )
        )

    stages = build_profile_stages(req.qualityProfile, control_package.stagingRecommendation, route.requiresApproval)
    readiness = "ready"
    readiness_reasons: list[str] = []
    if route.readiness == "blocked":
        readiness = "blocked"
        readiness_reasons.append(route.honestyNote or "Route approval is still required.")
    elif approval_requirements:
        readiness = "warning"
        readiness_reasons.append("Creator review is recommended before running extra controls or paid routes.")
    if shot_intent.clarificationQuestion:
        readiness = "warning" if readiness == "ready" else readiness
        readiness_reasons.append(shot_intent.clarificationQuestion)

    plan = ImageGenerationPlan(
        projectId=req.projectId,
        request=req,
        shotIntent=shot_intent,
        creativeDirection=creative_direction,
        references=reference_assignments,
        continuity=control_package.continuity,
        controlPackage=control_package,
        modelRoute=route,
        stages=stages,
        approvalRequirements=approval_requirements,
        readiness=readiness,  # type: ignore[arg-type]
        readinessReasons=readiness_reasons,
        previewSummary="",
        provenance=ProvenanceRecord(note="Prepared by the image pipeline foundation orchestrator."),
    )
    plan.previewSummary = creator_plan_preview(plan)
    plan.stageReceipts = [
        StageReceipt(
            planId=plan.planId,
            stageKey="prepare",
            note="Plan prepared from deterministic foundation rules.",
        )
    ]
    return plan


def creator_plan_preview(plan: ImageGenerationPlan) -> str:
    parts = [
        f"Purpose: {plan.request.purpose}.",
        f"Shot: {plan.shotIntent.shotSize.replace('_', ' ')} with {plan.shotIntent.subjectCount} subject"
        f"{'' if plan.shotIntent.subjectCount == 1 else 's'}.",
        f"Direction: {creator_summary(plan.creativeDirection)}",
        f"Route: {plan.modelRoute.modelFamily} via {plan.modelRoute.deploymentTarget}.",
    ]
    if plan.controlPackage.stagingRecommendation != "direct":
        parts.append(f"Staging helper: {plan.controlPackage.stagingRecommendation}.")
    if plan.readiness == "blocked":
        parts.append("Generation is honestly blocked until the approval step is resolved.")
    return " ".join(parts)


def _apply_group_status(group: ImageCandidateGroup, status: str) -> ImageCandidateGroup:
    group.status = status
    group.updatedAt = utc_now()
    return group


def generate_candidates_for_plan(
    plan: ImageGenerationPlan,
    *,
    requested_count: int | None = None,
    db: Any | None = None,
) -> ImageCandidateGroup:
    count = requested_count or plan.request.candidateCount
    group = create_candidate_group(plan, count)
    if plan.readiness == "blocked":
        for candidate in group.candidates:
            candidate.explanation = "Draft slot created only. Generation is blocked until the plan is ready."
        return _apply_group_status(group, "blocked")

    if db is None:
        for candidate in group.candidates:
            candidate.explanation = "Draft slot created. No runtime enqueue was attempted in this environment."
        return _apply_group_status(group, "draft")

    try:
        from ..image_product.service import generate_images

        body = {
            "projectId": plan.projectId,
            "prompt": plan.request.prompt,
            "purpose": plan.request.purpose,
            "batchCount": count,
            "quality": plan.request.qualityProfile,
            "modelFamilyPreference": plan.modelRoute.modelFamily,
            "referenceAssetIds": plan.request.referenceAssetIds,
            "creativeContext": {
                "imagePipelinePlanId": plan.planId,
                "creatorPreview": plan.previewSummary,
                "creativeDirection": plan.creativeDirection.model_dump(mode="json"),
            },
        }
        if plan.request.allowApiDeployment is False:
            body["providerPreference"] = "local"
        result = generate_images(db, project_id=plan.projectId, body=body)
        jobs = list(result.get("jobs") or [])
        for index, candidate in enumerate(group.candidates):
            if index < len(jobs):
                job = jobs[index]
                candidate.status = "queued"
                candidate.jobId = str(job.get("jobId") or "")
                candidate.explanation = "Queued through image_product with a real runtime job."
        return _apply_group_status(group, "queued")
    except Exception as exc:
        for candidate in group.candidates:
            candidate.explanation = f"Draft slot created honestly because runtime enqueue failed: {exc}"
        return _apply_group_status(group, "draft")


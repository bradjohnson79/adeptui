"""Creator-first ERS orchestration built on Spatial Map + Image Pipeline."""

from __future__ import annotations

from typing import Any

from ..image_pipeline.contracts import ProductionImageRequest
from ..image_pipeline.orchestrator import prepare_plan as prepare_image_plan
from ..spatial_map.reference_bundle import summarize_reference_bundle
from ..spatial_map.schemas import SpatialCapturePlanBody
from ..spatial_map.service import build_reference_bundle, create_capture_plan, get_document
from .continuity import validate_sheet
from .contracts import (
    DirectionalViewRecord,
    ERSApprovalRequirement,
    ERSCreationPlan,
    ERSStage,
    ERSViewDirection,
    EnvironmentProfile,
    EnvironmentReferenceSheet,
    ERSCompositionRecord,
    OptionalThreeDRecord,
    SpatialMapReference,
    utc_now,
)

_ERS_TO_SPATIAL_DIRECTION: dict[ERSViewDirection, str] = {
    "north": "front",
    "east": "right",
    "south": "rear",
    "west": "left",
}


def _split_keywords(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def _profile_from_description(name: str, description: str, creator_notes: str | None = None) -> EnvironmentProfile:
    return EnvironmentProfile(
        environmentName=name,
        description=description,
        storyPurpose="Environment reference sheet",
        visualDNA=_split_keywords(description)[:6],
        atmosphere=_split_keywords(description)[:5],
        materials=[],
        colorPalette=[],
        lightingNotes=[],
        continuityLocks=["architecture", "layout", "time of day", "material palette"],
        creatorNotes=creator_notes,
    )


def _stages() -> list[ERSStage]:
    return [
        ERSStage(stageKey="profile", label="Environment profile", status="complete"),
        ERSStage(stageKey="spatial", label="Spatial Map", status="pending"),
        ERSStage(stageKey="directional_views", label="Directional views", status="pending"),
        ERSStage(stageKey="continuity", label="Continuity review", status="pending"),
        ERSStage(stageKey="composition", label="Sheet composition", status="pending"),
        ERSStage(stageKey="registration", label="Project registration", status="pending"),
        ERSStage(stageKey="export", label="Export package", status="pending"),
    ]


def _preview(name: str, description: str) -> str:
    return (
        f"{name}: build one environment profile, lock north from the Spatial Map, "
        "prepare north/east/south/west views, validate continuity, and package the sheet for project reuse."
    )


def create_sheet(
    *,
    project_id: str,
    name: str,
    description: str,
    scene_id: str | None = None,
    creator_notes: str | None = None,
) -> EnvironmentReferenceSheet:
    summary = _preview(name, description)
    stages = _stages()
    approval_requirements = [
        ERSApprovalRequirement(
            kind="ers-create",
            status="approved",
            reason="Creation already happened through an approved Co-Director tool proposal.",
        )
    ]
    sheet = EnvironmentReferenceSheet(
        projectId=project_id,
        sceneId=scene_id,
        name=name,
        description=description,
        profile=_profile_from_description(name, description, creator_notes),
        creationPlan=ERSCreationPlan(
            summary=summary,
            creatorPreview=summary,
            readiness="warning",
            readinessReasons=["Attach a Spatial Map before directional view planning can proceed."],
            stages=stages,
            approvalRequirements=approval_requirements,
        ),
        composition=ERSCompositionRecord(sheetTitle=name, subtitle="Environment Reference Sheet"),
        optionalThreeD=OptionalThreeDRecord(truthLabel="illustrative", status="not_requested"),
    )
    sheet.continuity = validate_sheet(sheet)
    return sheet


def attach_spatial_map(db: Any, sheet: EnvironmentReferenceSheet, *, spatial_map_id: str) -> EnvironmentReferenceSheet:
    document = get_document(db, sheet.projectId, spatial_map_id)
    bundle = build_reference_bundle(db, sheet.projectId, spatial_map_id, target="image")
    summary = summarize_reference_bundle(bundle)
    capture_plan = create_capture_plan(
        db,
        sheet.projectId,
        spatial_map_id,
        body=SpatialCapturePlanBody(
            includeCharacters=False,
            masterEnvironmentPrompt=document.masterEnvironmentPrompt,
            cameraHeightMeters=1.6,
            lensMm=24.0,
        ),
    )
    directional_prompts = {
        ers_direction: next(
            (
                shot.prompt
                for shot in capture_plan.shots
                if shot.direction == spatial_direction
            ),
            bundle.directionalPrompts.get(spatial_direction, ""),
        )
        for ers_direction, spatial_direction in _ERS_TO_SPATIAL_DIRECTION.items()
    }
    sheet.spatialMap = SpatialMapReference(
        mapId=document.id,
        mapVersion=document.version,
        sceneId=document.sceneId,
        locationId=document.locationId,
        northLockDirection="north",
        referenceBundleSummary=str(summary.get("summary") or ""),
        warnings=list(bundle.warnings),
        directionalPrompts=directional_prompts,
    )
    sheet.directionalViews = [
        DirectionalViewRecord(
            direction=direction,
            title=f"{sheet.name} {direction.title()}",
            prompt=directional_prompts.get(direction, ""),
            sourceDirection=_ERS_TO_SPATIAL_DIRECTION[direction],
            status="planned",
            warnings=list(bundle.warnings),
        )
        for direction in ("north", "east", "south", "west")
    ]
    sheet.status = "views_pending"
    sheet.updatedAt = utc_now()
    sheet.creationPlan.readiness = "warning"
    sheet.creationPlan.readinessReasons = ["Generate and approve the four primary directions."]
    for stage in sheet.creationPlan.stages:
        if stage.stageKey == "spatial":
            stage.status = "complete"
            stage.summary = "Spatial Map attached with north lock."
        if stage.stageKey == "directional_views":
            stage.status = "ready"
            stage.summary = "Directional prompts prepared from the Spatial Map."
    sheet.continuity = validate_sheet(sheet)
    return sheet


def build_directional_view_image_plan(
    sheet: EnvironmentReferenceSheet,
    *,
    direction: ERSViewDirection,
    quality_profile: str = "cinematic",
    deployment_preference: str = "best-match",
) -> Any:
    if sheet.spatialMap is None:
        raise ValueError("SPATIAL_MAP_REQUIRED")
    view = next((item for item in sheet.directionalViews if item.direction == direction), None)
    if view is None:
        raise ValueError("DIRECTION_NOT_FOUND")
    request = ProductionImageRequest(
        projectId=sheet.projectId,
        prompt=view.prompt or sheet.description,
        purpose=f"ers-{direction}-view",
        qualityProfile=quality_profile,  # type: ignore[arg-type]
        deploymentPreference=deployment_preference,  # type: ignore[arg-type]
        allowApiDeployment=deployment_preference == "api",
        candidateCount=2,
        spatialMapPayload={
            "mapId": sheet.spatialMap.mapId,
            "mapVersion": sheet.spatialMap.mapVersion,
            "northLockDirection": sheet.spatialMap.northLockDirection,
            "direction": direction,
        },
        projectContext={
            "environmentReferenceSheetId": sheet.sheetId,
            "environmentName": sheet.name,
            "direction": direction,
        },
        continuityNotes=[
            "Same environment, same materials, same time of day.",
            f"North lock established from Spatial Map {sheet.spatialMap.mapId}.",
        ],
        creatorNotes=sheet.description,
    )
    return prepare_image_plan(request, project_policy="Ask")


def approve_direction(
    sheet: EnvironmentReferenceSheet,
    *,
    direction: ERSViewDirection,
    approved_asset_id: str,
    selected_candidate_id: str | None = None,
) -> EnvironmentReferenceSheet:
    view = next((item for item in sheet.directionalViews if item.direction == direction), None)
    if view is None:
        raise ValueError("DIRECTION_NOT_FOUND")
    view.approvedAssetId = approved_asset_id
    view.selectedCandidateId = selected_candidate_id
    view.status = "approved"
    view.continuityNotes = list(dict.fromkeys(view.continuityNotes + ["Approved for ERS composition."]))
    sheet.updatedAt = utc_now()
    sheet.continuity = validate_sheet(sheet)
    if sheet.continuity.status == "ready":
        sheet.status = "composition_ready"
        for stage in sheet.creationPlan.stages:
            if stage.stageKey == "directional_views":
                stage.status = "complete"
                stage.summary = "All four directions approved."
            if stage.stageKey == "continuity":
                stage.status = "complete"
                stage.summary = "Continuity passed for the approved directions."
    return sheet


def compose_sheet_metadata(sheet: EnvironmentReferenceSheet) -> EnvironmentReferenceSheet:
    highlights = [
        sheet.profile.environmentType,
        *sheet.profile.atmosphere[:2],
        *sheet.profile.colorPalette[:2],
    ]
    approved = [view.direction.title() for view in sheet.directionalViews if view.approvedAssetId]
    sheet.composition.heroSummary = sheet.spatialMap.referenceBundleSummary if sheet.spatialMap else sheet.description
    sheet.composition.profileHighlights = [item for item in highlights if item]
    sheet.composition.continuitySummary = (
        f"Approved directions: {', '.join(approved)}." if approved else sheet.continuity.summary
    )
    sheet.composition.lastRenderedAt = utc_now()
    for stage in sheet.creationPlan.stages:
        if stage.stageKey == "composition":
            stage.status = "ready" if approved else "pending"
            stage.summary = "Sheet metadata prepared for rendering." if approved else "Approve directions before rendering."
    sheet.updatedAt = utc_now()
    return sheet

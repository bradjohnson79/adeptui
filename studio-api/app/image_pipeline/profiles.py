"""Quality profile stage presets for image pipeline planning."""

from __future__ import annotations

from .contracts import ImagePipelineStage, QualityProfile, StagingRecommendation


def build_profile_stages(
    quality_profile: QualityProfile,
    staging_recommendation: StagingRecommendation,
    requires_route_approval: bool,
) -> list[ImagePipelineStage]:
    stage_defs: list[tuple[str, str, str]] = [
        ("prepare", "Plan", "Shape the shot and route before generation."),
    ]
    if staging_recommendation == "poseCraft":
        stage_defs.append(("posecraft", "Pose Guide", "Stage the character blocking before rendering."))
    if staging_recommendation == "spatialMap":
        stage_defs.append(("spatial", "Scene Layout", "Use scene geography to protect spatial clarity."))
    stage_defs.append(("generate", "Generate", "Create draft image candidates."))
    stage_defs.append(("evaluate", "Review", "Check each image against the plan honestly."))
    if quality_profile in {"enhanced", "cinematic", "studio-master"}:
        stage_defs.append(("repair", "Polish", "Repair only what weakens the shot."))
    if quality_profile in {"cinematic", "studio-master"}:
        stage_defs.append(("master", "Master", "Prepare a final polished delivery asset."))
    if requires_route_approval:
        stage_defs.append(("approval", "Approval", "Wait for creator approval before any paid route is used."))
    stage_defs.append(("approve", "Select", "Choose the version that best serves the story beat."))

    stages: list[ImagePipelineStage] = []
    for key, label, desc in stage_defs:
        stages.append(
            ImagePipelineStage(
                stageKey=key,
                label=label,
                description=desc,
                status="ready" if key == "prepare" else "pending",
            )
        )
    return stages


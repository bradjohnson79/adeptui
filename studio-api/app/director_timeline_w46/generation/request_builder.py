"""Build TimelineGenerationRequest from a BatchBlock + execution snapshot."""

from __future__ import annotations

from ..contracts import BatchBlock, ExecutionSnapshot
from .contracts import GenerationMode, TimelineGenerationRequest
from .registry import get_registry


def build_timeline_generation_request(
    *,
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    snapshot: ExecutionSnapshot,
    fallback_allowed: bool = False,
) -> TimelineGenerationRequest:
    registry = get_registry()
    generator_id = batch.generatorId
    if not generator_id:
        raise ValueError("BATCH_GENERATOR_REQUIRED")
    # Resolve aliases to canonical adapter ids for the shared contract.
    canonical = registry.resolve_id(generator_id)
    caps = registry.capabilities(canonical)

    prompt_parts = [p.text.strip() for p in (batch.promptSegments or []) if (p.text or "").strip()]
    prompt = "\n".join(prompt_parts)
    negative = next((p.negativePrompt for p in batch.promptSegments if p.negativePrompt), None)

    start_image = None
    end_image = None
    planning_start = None
    for anchor in batch.sourceAnchors or []:
        if anchor.kind == "image" and anchor.assetId:
            if planning_start is None:
                planning_start = anchor.assetId
            if anchor.kind == "image" and not start_image:
                # Prefer role-like labels
                label = (anchor.label or "").lower()
                if "end" in label:
                    end_image = anchor.assetId
                else:
                    start_image = start_image or anchor.assetId
        if anchor.kind == "end_frame" and anchor.assetId:
            end_image = anchor.assetId

    # Also accept references dict entries
    ref_ids: list[str] = []
    for ref in batch.references or []:
        if isinstance(ref, dict) and ref.get("assetId"):
            ref_ids.append(str(ref["assetId"]))

    mode: GenerationMode = "text_to_video"
    gen_start = None
    gen_end = None
    if caps.supportsImageToVideo and start_image:
        mode = "image_to_video"
        gen_start = start_image
        if caps.supportsEndFrame and end_image:
            mode = "start_end_frame"
            gen_end = end_image
    elif caps.supportsTextToVideo:
        mode = "text_to_video"
        # Do not pass unsupported start frames as generation inputs (no silent drop of claimed I2V).
        gen_start = None
        gen_end = None
    else:
        mode = "text_to_video"

    # Reference assets only when capabilities allow.
    if not caps.supportsMultipleImageReferences and caps.maximumReferenceImages <= 0:
        ref_ids = []

    return TimelineGenerationRequest(
        projectId=project_id,
        sceneId=scene_id,
        batchBlockId=batch.id,
        executionSnapshotId=snapshot.id,
        generatorId=canonical,
        generationMode=mode,
        prompt=prompt,
        negativePrompt=negative if caps.supportsNegativePrompt else None,
        startImageAssetId=gen_start,
        endImageAssetId=gen_end,
        referenceAssetIds=ref_ids,
        duration=float(batch.duration.plannedDuration or 5.0),
        seed=None,
        cameraMotion=None,
        providerOptions={
            "planningStartImageAssetId": planning_start,
            "originalGeneratorId": generator_id,
            "selectedGenerator": snapshot.selectedGenerator,
        },
        fallbackAllowed=fallback_allowed,
    )

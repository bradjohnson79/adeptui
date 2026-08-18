"""Build TimelineGenerationRequest from a BatchBlock + execution snapshot."""

from __future__ import annotations

from typing import Any

from ...aspect_fps import normalize_production_aspect, production_pixels
from ..contracts import BatchBlock, ExecutionSnapshot
from .contracts import GenerationMode, TimelineGenerationRequest, VideoGeneratorCapabilities
from .registry import get_registry


def _video_reference_from_batch(batch: BatchBlock) -> tuple[str | None, dict[str, Any] | None]:
    """Copy the attached video reference onto the request. Never drop it here."""
    asset_id: str | None = None
    trim: dict[str, Any] | None = None
    for anchor in batch.sourceAnchors or []:
        if anchor.kind == "video" and (anchor.assetId or "").strip():
            asset_id = str(anchor.assetId)
            break
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or ref.get("role") or "").lower()
        rid = str(ref.get("assetId") or "").strip()
        if rid and ("video" in kind or kind == "motion"):
            if ref.get("consumed") is False:
                continue
            asset_id = asset_id or rid
            if isinstance(ref.get("trim"), dict):
                trim = ref.get("trim")
    return asset_id, trim


def _resolution_for_request(
    caps: VideoGeneratorCapabilities,
    aspect: str,
    *,
    draft_mode: bool,
) -> str | None:
    # Hosted cheap-preview uses provider-native labels (480p/720p), never forced pixels.
    if caps.draftPathway == "cheap_preview" and (caps.draftResolution or caps.finalResolution):
        chosen = caps.draftResolution if draft_mode else caps.finalResolution
        return chosen or caps.finalResolution
    quality = "draft" if draft_mode and caps.draftPathway != "none" else "final"
    width, height = production_pixels(aspect, quality)
    return f"{width}x{height}"


def build_timeline_generation_request(
    *,
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    snapshot: ExecutionSnapshot,
    fallback_allowed: bool = False,
    incoming_bridge: object | None = None,
    aspect_ratio: str | None = None,
    draft_mode: bool | None = None,
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

    # Also accept references dict entries (image only — video is a dedicated field).
    ref_ids: list[str] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict) or not ref.get("assetId"):
            continue
        if ref.get("consumed") is False:
            continue
        kind = str(ref.get("kind") or "").lower()
        if "video" in kind:
            continue
        ref_ids.append(str(ref["assetId"]))

    video_ref_id, video_trim = _video_reference_from_batch(batch)
    video_ids = []
    for ref in batch.references or []:
        if not isinstance(ref, dict) or not ref.get("assetId"):
            continue
        kind = str(ref.get("kind") or "").lower()
        if "video" in kind:
            vid = str(ref["assetId"]).strip()
            if vid and vid not in video_ids:
                video_ids.append(vid)

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

    last_frame = None
    tail_asset = None
    bridge_id = None
    if incoming_bridge is not None:
        last_frame = getattr(incoming_bridge, "lastFrameAssetId", None)
        tail_asset = getattr(incoming_bridge, "tailAssetId", None)
        bridge_id = getattr(incoming_bridge, "bridgeId", None)

    strategy = "none"
    if last_frame and caps.supportsImageToVideo:
        mode = "image_to_video"
        gen_start = last_frame
        strategy = "last_frame_i2v"
        if caps.supportsEndFrame and end_image:
            mode = "start_end_frame"
            gen_end = end_image
    elif last_frame:
        strategy = "prompt_context"

    # Multi-angle: batch sourceAnchors still win composition when they exist as
    # dedicated start images AND the generator supports I2V — last-frame is then
    # continuity metadata, not a framing override.
    if start_image and caps.supportsImageToVideo and last_frame:
        gen_start = start_image
        strategy = "prompt_context"
        mode = "image_to_video" if mode == "text_to_video" else mode

    # Never silently drop image references. Adapter validation refuses
    # unsupported / over-limit counts. Bindings stay on the Prompt clip.
    aspect = normalize_production_aspect(aspect_ratio)
    use_draft = bool(draft_mode) if draft_mode is not None else caps.draftPathway != "none"
    if caps.draftPathway == "none":
        use_draft = False
    resolution = _resolution_for_request(caps, aspect, draft_mode=use_draft)
    aspect_warning = ""
    listed_aspects = list(caps.supportedAspectRatios or [])
    if listed_aspects and aspect not in listed_aspects and not any(aspect in str(a) for a in listed_aspects):
        aspect_warning = (
            f"{caps.label} may not honor {aspect}. Adept will not crop a different ratio and call it {aspect}."
        )

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
        videoReferenceAssetId=video_ref_id,
        videoReferenceTrim=video_trim,
        duration=float(batch.duration.plannedDuration or 5.0),
        resolution=resolution,
        aspectRatio=aspect,
        seed=None,
        cameraMotion=None,
        providerOptions={
            "lora": batch.lora,
            "planningStartImageAssetId": planning_start,
            "originalGeneratorId": generator_id,
            "selectedGenerator": snapshot.selectedGenerator,
            "continuityLastFrameAssetId": last_frame,
            "continuityEffectiveTail": getattr(incoming_bridge, "effectiveTailDuration", None)
            if incoming_bridge
            else None,
            "draftMode": use_draft,
            "draftPathway": caps.draftPathway,
            "finalRequiresNewGeneration": caps.finalRequiresNewGeneration,
            "fast_generation": bool(use_draft and caps.draftPathway == "local_live"),
            "aspectWarning": aspect_warning,
            "videoReferenceAssetIds": video_ids,
            "motionSubjectIdentityId": next(
                (
                    str(ref.get("identityId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict) and ref.get("role") == "motion_subject" and ref.get("identityId")
                ),
                None,
            ),
            "motionSubjectBindingId": next(
                (
                    str(ref.get("bindingId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict) and ref.get("role") == "motion_subject" and ref.get("bindingId")
                ),
                None,
            ),
            "motionReferenceAssetId": next(
                (
                    str(ref.get("assetId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict)
                    and ref.get("role") == "motion_reference"
                    and ref.get("consumed")
                    and ref.get("assetId")
                ),
                None,
            ),
            "motionReferenceBindingId": next(
                (
                    str(ref.get("bindingId"))
                    for ref in (batch.references or [])
                    if isinstance(ref, dict)
                    and ref.get("role") == "motion_reference"
                    and ref.get("consumed")
                    and ref.get("bindingId")
                ),
                None,
            ),
        },
        fallbackAllowed=fallback_allowed,
        continuityBridgeId=bridge_id,
        lastFrameAssetId=last_frame,
        tailAssetId=tail_asset,
        continuityStrategy=strategy,
    )

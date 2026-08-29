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
    if draft_mode and caps.draftResolution:
        return caps.draftResolution
    if caps.finalResolution:
        return caps.finalResolution
    listed = [str(item) for item in (caps.supportedResolutions or []) if item]
    if listed:
        return listed[0]
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
    temporal_packet: object | None = None,
    director_timeline: object | None = None,
    window_start: float = 0.0,
    scene_prompt: str | None = None,
) -> TimelineGenerationRequest:
    registry = get_registry()
    generator_id = batch.generatorId
    if not generator_id:
        raise ValueError("BATCH_GENERATOR_REQUIRED")
    # Resolve aliases to canonical adapter ids for the shared contract.
    canonical = registry.resolve_id(generator_id)
    caps = registry.capabilities(canonical)

    # PRODUCTION_PROMPT_PREFERENCE (mission Part 6): Co-Director refinement may
    # compile a more detailed production prompt; it is preferred for the
    # request while the authored text stays preserved as userDirection/text.
    # Dialogue is NOT injected here — speech compilation handles it verbatim.
    prompt_parts = [
        (str(p.productionPrompt or "").strip() or (p.text or "").strip())
        for p in (batch.promptSegments or [])
        if (str(p.productionPrompt or "").strip() or (p.text or "").strip())
    ]
    # Scene Prompt (SQL scenes.prompt) is the per-scene global base.
    # Dedupe only when the first timed text equals the scene base (strip).
    scene_base = _resolve_scene_prompt(project_id, scene_id, scene_prompt)
    if scene_base:
        first_timed = prompt_parts[0] if prompt_parts else ""
        if first_timed != scene_base:
            prompt_parts.insert(0, scene_base)
    prompt = "\n".join(prompt_parts)
    negative = next((p.negativePrompt for p in batch.promptSegments if p.negativePrompt), None)
    temporal_compile: dict[str, Any] = {}
    temporal_packet_id = None
    pose_compile: dict[str, Any] = {}
    if temporal_packet is not None:
        from ...codirector.video_intelligence.compile import compile_temporal_continuation

        rejected = bool(getattr(getattr(temporal_packet, "continuation", None), "creatorRejected", False))
        temporal_compile = compile_temporal_continuation(
            temporal_packet,
            supports_prompt_continuation=bool(getattr(caps, "supportsPromptContinuation", True)),
            creator_rejected=rejected,
        )
        temporal_packet_id = getattr(temporal_packet, "packetId", None)
        prefix = str(temporal_compile.get("promptPrefix") or "").strip()
        if temporal_compile.get("applied") and prefix:
            prompt = "\n".join(part for part in (prefix, prompt) if part)
    pose_compile = _compile_pose_conditioning(project_id, batch, caps)
    pose_prefix = str(pose_compile.get("promptPrefix") or "").strip()
    if pose_compile.get("applied") and pose_prefix:
        prompt = "\n".join(part for part in (pose_prefix, prompt) if part)
    movement_layers = _compile_movement_layers(project_id, batch)
    if movement_layers.get("providerText"):
        # Keep structured layers distinct from free-text Timed Prompt.
        prompt = "\n".join(
            part for part in (movement_layers["providerText"], prompt) if part and not _is_alias_only(part)
        )

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
        kind = _reference_media_kind(ref, project_id)
        if "video" in kind:
            continue
        if _is_audio_kind(kind):
            continue
        if "lineage" in kind:
            continue
        role = str(ref.get("role") or "").lower()
        if role in ("start_image", "end_image"):
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

    if (
        not start_image
        and "minimax" in canonical
        and caps.supportsImageToVideo
    ):
        for ref in batch.references or []:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("source") or "") != "pane":
                continue
            kind = _reference_media_kind(ref, project_id)
            if _is_audio_kind(kind) or "video" in kind:
                continue
            aid = str(ref.get("assetId") or "").strip()
            if aid:
                start_image = aid
                break

    # PANE_SCENE_REFERENCE_BINDINGS: project-scoped + scene-scoped pane rows.
    # Clip reference_binding_ids / batch.references stay. library_asset_ids is
    # Timeline Library staging only — never generation input.
    start_image, video_ref_id = _apply_pane_scene_bindings(
        project_id,
        scene_id,
        caps,
        start_image=start_image,
        video_ref_id=video_ref_id,
        ref_ids=ref_ids,
        video_ids=video_ids,
    )

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
        mode = "image_to_video" if caps.supportsImageToVideo else "text_to_video"

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

    from ...cinematography import camera_nl_instruction, compile_canonical_camera

    planned = float(getattr(getattr(batch, "duration", None), "plannedDuration", None) or 5.0)
    camera = compile_canonical_camera(
        batch=batch,
        director_timeline=director_timeline,
        window_start=window_start,
        window_length=planned,
    )
    # NL-only generators (supportsCameraControls=False): compile camera into prompt.
    # Never set a fake cameraMotion MiniMax/LTX would refuse.
    if camera and not caps.supportsCameraControls:
        camera_nl = camera_nl_instruction(camera)
        if camera_nl and camera_nl not in prompt:
            prompt = "\n".join(part for part in (prompt, camera_nl) if part)
    camera_motion = None
    if caps.supportsCameraControls and camera:
        camera_motion = camera.get("motion") or camera.get("motionType") or camera.get("motionId")

    requested_temp = 1.0
    for seg in batch.promptSegments or []:
        requested_temp = float(getattr(seg, "temperature", 1.0) or 1.0)
        break
    request_temperature = requested_temp if caps.supportsTemperature else None

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
        cameraMotion=camera_motion,
        camera=camera,
        temperature=request_temperature,
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
            "movementLayers": movement_layers.get("layers"),
            "temporalContinuation": temporal_compile,
            "temporalContinuityPacketId": temporal_packet_id,
            "poseMotionConditioning": pose_compile,
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
        temporalContinuityPacketId=temporal_packet_id,
    )





def _pane_binding_kind(binding: Any, asset_kind: str) -> str:
    """Prefer Asset.kind, then binding.media_kind / reference_type."""
    kind = (asset_kind or "").strip().lower()
    if kind:
        return kind
    media = str(getattr(binding, "media_kind", None) or "").strip().lower()
    if media:
        return media
    ref_type = str(getattr(binding, "reference_type", None) or "").strip().lower()
    return ref_type


def _load_scene_pane_bindings(project_id: str, scene_id: str) -> list[dict[str, Any]]:
    """Scene-scoped pane bindings only. Chief lock: no project-scope ingest.

    library_asset_ids is staging only and is never read.
    """
    if not (project_id or "").strip():
        return []
    try:
        from ...db import Asset, SessionLocal
        from ...scene_references.repository import list_pane_generation_bindings

        db = SessionLocal()
        try:
            rows = list_pane_generation_bindings(db, project_id, (scene_id or "").strip() or None)
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                    if not getattr(row, "enabled", True):
                        continue
                    token = str(getattr(row, "id", "") or "").strip()
                    if token and token in seen:
                        continue
                    asset_id = str(getattr(row, "asset_id", "") or "").strip()
                    if not asset_id:
                        continue
                    asset = getattr(row, "asset", None)
                    if asset is None:
                        asset = db.get(Asset, asset_id)
                        if (
                            asset is not None
                            and project_id
                            and getattr(asset, "project_id", None)
                            and str(asset.project_id) != str(project_id)
                        ):
                            asset = None
                    asset_kind = str(getattr(asset, "kind", "") or "").lower() if asset is not None else ""
                    kind = _pane_binding_kind(row, asset_kind)
                    if token:
                        seen.add(token)
                    out.append(
                        {
                            "bindingId": token,
                            "assetId": asset_id,
                            "kind": kind,
                            "referenceType": str(getattr(row, "reference_type", "") or ""),
                            "mediaKind": str(getattr(row, "media_kind", "") or ""),
                        }
                    )
            return out
        finally:
            db.close()
    except Exception:
        return []


def _extra_image_ref_slots(caps: Any, *, start_filled: bool, ref_count: int) -> int:
    """Slots left for pane images on referenceAssetIds. MiniMax T2V max=0."""
    max_n = int(getattr(caps, "maximumReferenceImages", 0) or 0)
    if max_n <= 0:
        return 0
    used = int(ref_count or 0)
    if start_filled and not bool(getattr(caps, "supportsMultipleImageReferences", False)):
        used += 1
    return max(0, max_n - used)


def _apply_pane_scene_bindings(
    project_id: str,
    scene_id: str,
    caps: Any,
    *,
    start_image: str | None,
    video_ref_id: str | None,
    ref_ids: list[str],
    video_ids: list[str],
) -> tuple[str | None, str | None]:
    """Fill empty start / video-ref / extra image slots from the Scene pane."""
    seen: set[str] = set(ref_ids)
    if start_image:
        seen.add(str(start_image))
    if video_ref_id:
        seen.add(str(video_ref_id))
    for binding in _load_scene_pane_bindings(project_id, scene_id):
        aid = str(binding.get("assetId") or "").strip()
        if not aid or aid in seen:
            continue
        kind = str(binding.get("kind") or "").lower()
        if _is_audio_kind(kind):
            continue
        if "video" in kind or kind == "motion":
            if bool(getattr(caps, "supportsVideoReferences", False)) and not video_ref_id:
                video_ref_id = aid
                if aid not in video_ids:
                    video_ids.append(aid)
                seen.add(aid)
            continue
        media = str(binding.get("mediaKind") or "").lower()
        ref_type = str(binding.get("referenceType") or "").lower()
        if media == "entity" or ref_type in ("character", "prop"):
            continue
        is_image = kind == "image" or "image" in kind or media == "image"
        if not is_image:
            continue
        gen_id = str(getattr(caps, "id", "") or "").lower()
        is_minimax_i2v = "minimax" in gen_id and bool(getattr(caps, "supportsImageToVideo", False))
        is_minimax_t2v = "minimax" in gen_id and not bool(getattr(caps, "supportsImageToVideo", False))
        if is_minimax_t2v:
            continue
        # Image slots: start (I2V) then extra referenceAssetIds when the adapter has them.
        if bool(getattr(caps, "supportsImageToVideo", False)) and not start_image:
            start_image = aid
            seen.add(aid)
            continue
        if is_minimax_i2v:
            continue
        if _extra_image_ref_slots(caps, start_filled=bool(start_image), ref_count=len(ref_ids)) > 0:
            ref_ids.append(aid)
            seen.add(aid)
    return start_image, video_ref_id


def _resolve_scene_prompt(project_id: str, scene_id: str, explicit: str | None) -> str:
    """Current SQL scenes.prompt. Explicit None reloads so PATCH/Inspector cannot miss."""
    if explicit is not None:
        return str(explicit).strip()
    try:
        from ...db import SessionLocal
        from ..store import get_scene

        db = SessionLocal()
        try:
            scene = get_scene(db, project_id, scene_id)
            return str(getattr(scene, "prompt", "") or "").strip() if scene else ""
        finally:
            db.close()
    except Exception:
        return ""


def _project_asset_kind(project_id: str, asset_id: str) -> str:
    """Resolve project-scoped Asset.kind only. Never copy blobs."""
    token = (asset_id or "").strip()
    if not token:
        return ""
    try:
        from ...db import Asset, SessionLocal

        db = SessionLocal()
        try:
            row = db.get(Asset, token)
            if row is None:
                return ""
            if project_id and getattr(row, "project_id", None) and str(row.project_id) != str(project_id):
                return ""
            return str(getattr(row, "kind", "") or "").lower()
        finally:
            db.close()
    except Exception:
        return ""


def _reference_media_kind(ref: dict[str, Any], project_id: str) -> str:
    kind = str(ref.get("kind") or ref.get("mediaKind") or ref.get("media_kind") or "").lower()
    if kind:
        return kind
    aid = str(ref.get("assetId") or "").strip()
    return _project_asset_kind(project_id, aid) if aid else ""


def _is_audio_kind(kind: str) -> bool:
    token = (kind or "").lower()
    return token == "audio" or "audio" in token


def _is_alias_only(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"\s*~?M\s*[1-5]\s*", text or "", re.I))


def _compile_movement_layers(project_id: str, batch: BatchBlock) -> dict[str, Any]:
    try:
        from ...spatial_map.movement_compile import (
            compile_generation_layers,
            layers_as_provider_text,
            resolve_segment_for_ref,
        )
        from ...spatial_map.service import list_documents
        from ...db import SessionLocal

        db = SessionLocal()
        try:
            docs = list_documents(db, project_id) or []
            if not docs:
                return {}
            document = docs[0]
            first = (batch.promptSegments or [None])[0]
            ref = getattr(first, "movementSegmentRef", None) if first is not None else None
            text = getattr(first, "text", "") if first is not None else ""
            segment = resolve_segment_for_ref(document, ref, text)
            layers = compile_generation_layers(document, segment, timed_prompt=str(text or ""))
            return {"layers": layers, "providerText": layers_as_provider_text(layers)}
        finally:
            db.close()
    except Exception:
        return {}


def _compile_pose_conditioning(project_id: str, batch: BatchBlock, caps: Any) -> dict[str, Any]:
    """Attach persisted PoseCraft intended state. Never overwrites temporal continuation."""
    try:
        from ...codirector.pose_intelligence.compile import compile_pose_motion_conditioning
        from ...codirector.pose_intelligence.persist import load_packet
        from ...db import SessionLocal

        extra = {}
        for ref in batch.references or []:
            if isinstance(ref, dict) and ref.get("poseWorldStatePacketId"):
                extra = ref
                break
        db = SessionLocal()
        try:
            packet = load_packet(db, project_id)
        finally:
            db.close()
        compiled = compile_pose_motion_conditioning(
            packet,
            supports_prompt_continuation=bool(getattr(caps, "supportsPromptContinuation", True)),
        )
        if extra.get("poseWorldStatePacketId"):
            compiled["sourcePosePacketId"] = extra.get("poseWorldStatePacketId")
        return compiled
    except Exception:
        return {"applied": False, "reason": "POSE_INTELLIGENCE_UNAVAILABLE", "promptPrefix": ""}

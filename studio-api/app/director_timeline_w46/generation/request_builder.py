"""Build TimelineGenerationRequest from a BatchBlock + execution snapshot."""

from __future__ import annotations

from typing import Any

from ...aspect_fps import normalize_production_aspect, production_pixels
from ...video_runtime.legal_canvas import (
    is_minimax_h3_generator,
    resolve_h3_timeline_canvas,
    snap_h3_timeline_duration,
)
from ...video_runtime.workflow_resolver import is_ltx_25_generator
from ..contracts import BatchBlock, ExecutionSnapshot
from .contracts import GenerationMode, TimelineGenerationRequest, VideoGeneratorCapabilities
from .registry import get_registry


def _resolve_project_visual_style(project_id: str) -> str:
    """Best-effort read of the project-level visual style (never raises).

    Single project authority: ``settings_json.visualStyle`` (API field
    ``visual_style``). Character ``visual_style`` and storyboard styles are
    not substitutes. Timed Prompt may still lift a ``Visual style:`` line
    when the project field is empty.
    """
    try:
        from ...db import Project, SessionLocal
        from .semantic_contract import resolve_style_key

        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            if not project:
                return ""
            settings_raw = getattr(project, "settings_json", None) or "{}"
            settings: dict = {}
            if isinstance(settings_raw, str):
                import json

                try:
                    parsed = json.loads(settings_raw)
                except Exception:
                    parsed = {}
                if isinstance(parsed, dict):
                    settings = parsed
            for key in ("visualStyle", "visual_style", "style", "globalStyle"):
                value = settings.get(key)
                if value:
                    return resolve_style_key(str(value)) or str(value).strip()
            # Soft compat: free-text defaults_json.prompt_style if it maps to a
            # known STYLE_REGISTRY key — not a second registry.
            defaults_raw = getattr(project, "defaults_json", None) or "{}"
            if isinstance(defaults_raw, str):
                import json

                try:
                    defaults = json.loads(defaults_raw)
                except Exception:
                    defaults = {}
                if isinstance(defaults, dict):
                    for key in ("visual_style", "visualStyle", "prompt_style"):
                        value = defaults.get(key)
                        if value:
                            resolved = resolve_style_key(str(value))
                            if resolved:
                                return resolved
        finally:
            db.close()
    except Exception:
        return ""
    return ""

def _style_prompt_phrase(style_key: str) -> str:
    """Map a visual style key to a rendering phrase. Style is not identity."""
    from .semantic_contract import style_rendering_phrase

    return style_rendering_phrase(style_key)


def _requested_duration(batch: BatchBlock, range_rep: dict[str, Any]) -> float:
    marked = float(range_rep.get("length") or 0.0) if range_rep else 0.0
    if marked > 0:
        return marked
    return float(batch.duration.plannedDuration or 5.0)


def _h3_duration_for_request(generator_id: str, requested: float) -> tuple[float, dict[str, Any]]:
    """Inspector/batch request → legal H3 duration. Disclose snap. Fail if >15s."""
    if not is_minimax_h3_generator(generator_id):
        return requested, {}
    snap = snap_h3_timeline_duration(requested)
    if not snap.get("ok"):
        raise ValueError(str(snap.get("message") or "MiniMax H3 duration is above 15s."))
    extras = {
        "requestedDurationSec": snap.get("requestedDurationSec"),
        "legalDurationSec": snap.get("legalDurationSec"),
        "durationSnapDisclosed": bool(snap.get("snapped")),
        "durationSnapMessage": snap.get("message") or "",
        "legalFrameCount": snap.get("frames"),
    }
    # Job/legal length is frames/fps; creator durationSec stays on request separately.
    legal = snap.get("legalDurationSec")
    if legal is None:
        legal = snap.get("durationSec")
    return float(legal), extras


def _range_replacement(snapshot: ExecutionSnapshot) -> dict[str, Any]:
    raw = (snapshot.continuityState or {}).get("rangeReplacement")
    return raw if isinstance(raw, dict) else {}


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
    batch: BatchBlock,
    *,
    draft_mode: bool,
) -> str | None:
    # MiniMax H3: BatchBlock's h3Resolution is the authority. Manual wins over
    # draft_mode; Auto picks the policy constant by draft_mode. Width/height
    # are derived from the canonical megapixel grid, never stored.
    if is_minimax_h3_generator(batch.generatorId):
        canvas = resolve_h3_timeline_canvas(batch.h3Resolution, draft_mode=draft_mode)
        return f"{canvas['width']}x{canvas['height']}"

    # Hosted cheap-preview uses provider-native labels (480p/720p), never forced pixels.
    if caps.draftPathway == "cheap_preview" and (caps.draftResolution or caps.finalResolution):
        chosen = caps.draftResolution if draft_mode else caps.finalResolution
        return chosen or caps.finalResolution
    # Local video publishes exact pixels. Never fall through to image PRODUCTION_PIXELS
    # (512×288 / 1280×720), which are not this generator’s legal canvas.
    if caps.finalResolution and "x" in str(caps.finalResolution):
        return caps.finalResolution
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
    turbo_lora: bool = False,
    direct_references: object | None = None,
) -> TimelineGenerationRequest:
    registry = get_registry()
    generator_id = batch.generatorId
    if not generator_id:
        raise ValueError("BATCH_GENERATOR_REQUIRED")
    # Resolve aliases to canonical adapter ids for the shared contract.
    canonical = registry.resolve_id(generator_id)
    caps = registry.capabilities(canonical)

    # Creator Spec Fidelity: Timed Prompt segment text is authoritative action
    # language for delivery. productionPrompt is Co-Director enrichment only.
    # MiniMax H3 Direct Line: never let productionPrompt / Scene Prompt become a
    # second silent authority for Comfy Input Text — use Timed Prompt text only.
    from ...video_runtime.legal_canvas import is_minimax_h3_generator as _is_h3_gen
    _h3_delivery = _is_h3_gen(str(batch.generatorId or ""))
    prompt_parts = []
    for p in (batch.promptSegments or []):
        timed = (p.text or "").strip()
        if _h3_delivery:
            if timed:
                prompt_parts.append(timed)
            # else: leave empty — do not fill from productionPrompt on H3
            continue
        part = timed or str(p.productionPrompt or "").strip()
        if part:
            prompt_parts.append(part)
    prompt = "\n".join(prompt_parts)
    negative = next((p.negativePrompt for p in batch.promptSegments if p.negativePrompt), None)
    range_rep = _range_replacement(snapshot)
    range_prompt = str(range_rep.get("prompt") or "").strip()
    # STYLE AUTHORITY is a separate semantic layer. Do not prepend it into the
    # action blob — that mixes WHO with HOW and lets style language recast people.
    project_style = _resolve_project_visual_style(project_id)
    if not project_style:
        from .semantic_contract import lift_style_from_text

        project_style, _ = lift_style_from_text(prompt)
    style_phrase = _style_prompt_phrase(project_style)
    if range_prompt:
        # Range Replacement replaces the scene/timed prompt but NOT the style layer.
        prompt = range_prompt
    # Creator Spec Fidelity: authoredPrompt is the creator Timed Prompt only.
    # Temporal / pose / Spatial Map movement prefixes must not overwrite it —
    # identity bind and R2V body use authoredPrompt as cast/action authority.
    authored_prompt = prompt
    temporal_compile: dict[str, Any] = {}
    temporal_packet_id = None
    pose_compile: dict[str, Any] = {}
    # Wave 2A H3 call-fence: temporal / pose / movement prefixes must never land on
    # H3 Comfy Input Text. Skip the silent prepend writers entirely for H3 (not only
    # rely on delivery_prompt=authored_prompt). Non-H3 keeps existing behavior.
    if temporal_packet is not None and not range_prompt and not _h3_delivery:
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
    elif temporal_packet is not None and _h3_delivery:
        temporal_packet_id = getattr(temporal_packet, "packetId", None)
        temporal_compile = {
            "applied": False,
            "reason": "H3_DIRECT_LINE_FENCE",
            "promptPrefix": "",
        }
    pose_compile = (
        _compile_pose_conditioning(project_id, batch, caps)
        if (not range_prompt and not _h3_delivery)
        else (
            {"applied": False, "reason": "H3_DIRECT_LINE_FENCE", "promptPrefix": ""}
            if _h3_delivery
            else {}
        )
    )
    pose_prefix = str(pose_compile.get("promptPrefix") or "").strip()
    if pose_compile.get("applied") and pose_prefix and not _h3_delivery:
        prompt = "\n".join(part for part in (pose_prefix, prompt) if part)
    movement_layers = (
        _compile_movement_layers(project_id, batch)
        if (not range_prompt and not _h3_delivery)
        else {}
    )
    if movement_layers.get("providerText") and not _h3_delivery:
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
    cut_in = str(range_rep.get("startImageAssetId") or "").strip()
    if cut_in:
        start_image = cut_in

    # Also accept references dict entries (IMAGE only).
    # Voice/audio/sfx never belong in visual referenceAssetIds — those ride
    # characterVoice / audio slots. Video is a dedicated field below.
    _NON_IMAGE_REF_KINDS = {
        "charactervoice",
        "voice",
        "audio",
        "sfx",
        "lipsync_audio",
        "motion",
    }
    ref_ids: list[str] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict) or not ref.get("assetId"):
            continue
        if ref.get("consumed") is False:
            continue
        kind = str(ref.get("kind") or "").lower()
        if "video" in kind or kind in _NON_IMAGE_REF_KINDS:
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
    if range_rep and float(range_rep.get("start") or 0.0) > 0.05:
        last_frame = None

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

    if caps.executionType == "local":
        # Mapped start/end stay for single-cond engines. Product mode is R2V.
        mode = "reference"

    # Never silently drop image references. Adapter validation refuses
    # unsupported / over-limit counts. Bindings stay on the Prompt clip.
    aspect = normalize_production_aspect(aspect_ratio)
    use_draft = bool(draft_mode) if draft_mode is not None else caps.draftPathway != "none"
    if caps.draftPathway == "none":
        use_draft = False
    speed_quality = is_ltx_25_generator(generator_id)
    # Official LTX 2.5 Fast is fewer steps at production size, not a smaller picture.
    resolution = _resolution_for_request(
        caps, aspect, batch, draft_mode=False if speed_quality else use_draft
    )
    # H3 canvas provenance for job history. Non-H3 batches leave this None.
    h3_resolved_canvas = (
        resolve_h3_timeline_canvas(batch.h3Resolution, draft_mode=use_draft)
        if is_minimax_h3_generator(batch.generatorId)
        else None
    )
    aspect_warning = ""
    listed_aspects = list(caps.supportedAspectRatios or [])
    if listed_aspects and aspect not in listed_aspects and not any(aspect in str(a) for a in listed_aspects):
        aspect_warning = (
            f"{caps.label} may not honor {aspect}. Adept will not crop a different ratio and call it {aspect}."
        )

    requested_duration = _requested_duration(batch, range_rep)
    # Keep request.duration as the RAW creator-requested duration (12.0s).
    # The legal MiniMax generation frame count (294) is stored in providerOptions
    # as legalFrameCount. The generation path uses legalFrameCount for MiniMax,
    # then trims the excess back to requested_duration. This preserves duration
    # honesty: the Scene stays 12.0s, the final clip is 12.0s, and MiniMax
    # internally generates 294 legal frames (12.25s) that are trimmed to 12.0s.
    job_duration, duration_extras = _h3_duration_for_request(generator_id, requested_duration)
    # request.duration stays as the creator's requested duration (not snapped).
    # For MiniMax H3, job_duration is the legal duration (12.25s) but we keep
    # request.duration = requested_duration (12.0s) so the Scene is not mutated
    # and the trim target is the creator's request.
    if is_minimax_h3_generator(generator_id):
        request_duration_value = requested_duration
    else:
        request_duration_value = job_duration
    knowledge = _compile_generator_knowledge(
        generator_id=canonical,
        prompt=prompt,
        negative=negative,
        mode=mode,
        start_image=gen_start,
        reference_ids=ref_ids,
        batch=batch,
        duration=job_duration,
    )
    # Phase A Direct Line (H3): knowledge compiledPrompt must not overwrite
    # Timed Prompt. Non-H3 generators keep the existing compile overwrite.
    if (
        knowledge.get("compiledPrompt")
        and not range_prompt
        and not is_minimax_h3_generator(generator_id)
    ):
        prompt = str(knowledge["compiledPrompt"])
    if knowledge.get("compiledNegative") and caps.supportsNegativePrompt:
        negative = str(knowledge["compiledNegative"])

    # H3 Comfy Input Text = creator Timed Prompt (authoredPrompt), not temporal
    # / pose / movement prefixes or knowledge rewrites.
    delivery_prompt = authored_prompt if is_minimax_h3_generator(generator_id) else prompt

    request = TimelineGenerationRequest(
        projectId=project_id,
        sceneId=scene_id,
        batchBlockId=batch.id,
        executionSnapshotId=snapshot.id,
        generatorId=canonical,
        generationMode=mode,
        prompt=delivery_prompt,
        negativePrompt=negative if caps.supportsNegativePrompt else None,
        startImageAssetId=gen_start,
        endImageAssetId=gen_end,
        referenceAssetIds=ref_ids,
        videoReferenceAssetId=video_ref_id,
        videoReferenceTrim=video_trim,
        duration=request_duration_value,
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
            "fast_generation": bool(use_draft and (caps.draftPathway == "local_live" or speed_quality)),
            "h3ResolvedCanvas": h3_resolved_canvas,
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
            "generatorKnowledge": knowledge,
            "authoredPrompt": authored_prompt,
            "visualStyle": project_style,
            "stylePhrase": style_phrase,
            "rangeReplacement": range_rep or None,
            **duration_extras,
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
    from ...production_control.generator_authority import supports_turbo_lora

    if bool(turbo_lora) and supports_turbo_lora(generator_id):
        request.providerOptions["turbo_lora"] = True
    # Audio authority contract: determine who owns the audio for this generation.
    audio_authority = _resolve_audio_authority(project_id, scene_id, batch, caps)
    request.providerOptions["audioAuthority"] = audio_authority
    request.providerOptions["generate_audio"] = audio_authority.get("generateAudio", False)
    from .r2v import attach_canonical_r2v
    from .direct_reference import attach_direct_reference_payload
    from ...db import SessionLocal as _SessionLocal

    if direct_references is not None:
        attach_direct_reference_payload(request, direct_references)
    _db = _SessionLocal()
    try:
        attach_canonical_r2v(request, batch, caps, db=_db)
        # H3 FM3: Front transport packing when Character Creator Front exists
        # (plain Front bytes into ref sockets). Opt-out: h3CreatorCrsAuthority /
        # h3FrontTransport=False. No Timed Prompt rewrite; no place invent.
        from .h3_front_identity import apply_h3_front_identity_to_request
        from .r2v import H3_MECHANISM, mechanism_for_generator

        product = str(request.generatorId or caps.id or "")
        if mechanism_for_generator(product) == H3_MECHANISM or product.startswith("minimax-h3"):
            # Advisory annotations only — never fail Timed Prompt delivery if the
            # local DB schema/session cannot resolve Front/CRS metadata.
            try:
                apply_h3_front_identity_to_request(_db, request)
            except Exception:
                pass
    finally:
        _db.close()
    return request


def _resolve_audio_authority(
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    caps: VideoGeneratorCapabilities,
) -> dict[str, Any]:
    """Determine who owns the audio for this generation.

    Authority precedence:
    1. Lip Sync / Dialogue Authority — if Timeline has active lip sync tracks,
       Timeline owns the dialogue/voice path.
    2. Explicit Timeline Audio / SFX / Music — if creator placed explicit
       audio clips, SFX clips, or music, Timeline uses those tracks.
    3. No Explicit Audio Tracks — USE GENERATOR-NATIVE AUDIO (default).

    An empty audio track lane is NOT an instruction for silence. It means
    "Let the video generator supply its own audio."
    """
    # Check if the generator supports native audio at all.
    supports_native = bool(getattr(caps, "audio_generation", False))

    # Check for explicit Timeline audio (batch-level).
    has_audio_clips = bool(getattr(batch, "audioClips", None))
    has_sfx_clips = bool(getattr(batch, "sfxClips", None))

    # Check for lip sync tracks (scene-level, via DB).
    has_lip_sync = False
    try:
        from ...db import SessionLocal, Scene

        db = SessionLocal()
        try:
            scene = db.get(Scene, scene_id)
            if scene and getattr(scene, "lipsync_audio_asset_id", None):
                has_lip_sync = True
        finally:
            db.close()
    except Exception:
        pass

    if has_lip_sync:
        return {
            "authority": "timeline",
            "dialogue": "lip_sync",
            "nativeAudio": "preserved_if_supported",
            "generateAudio": False,  # Timeline owns dialogue; generator may still produce ambient
        }
    if has_audio_clips or has_sfx_clips:
        return {
            "authority": "timeline",
            "nativeAudio": "mixed",
            "generateAudio": False,  # Timeline owns audio; generator may still produce ambient
        }
    # No explicit audio — use generator-native audio by default.
    return {
        "authority": "generator_native",
        "nativeAudio": "enabled" if supports_native else "unsupported",
        "generateAudio": supports_native,  # Let the generator produce its own audio
    }


def _compile_generator_knowledge(
    *,
    generator_id: str,
    prompt: str,
    negative: str | None,
    mode: str,
    start_image: str | None,
    reference_ids: list[str],
    batch: BatchBlock,
    duration: float,
) -> dict[str, Any]:
    """Apply the generator knowledge compiler on the W46 generate path.

    If the profile is unavailable, keep the authored prompt. Never empty it.
    """
    try:
        from ...codirector.generator_knowledge.compiler import compile_for_generator
        from ...codirector.generator_knowledge.resolver import try_resolve_profile
        from ...codirector.model_intelligence.schemas import NormalizedGenerationIntent

        profile, _err = try_resolve_profile(generator_id)
        image_slots = dict(getattr(getattr(profile, "capability", None), "imageSlots", None) or {})
        subjects = _real_minimax_slots(batch, image_slots)
        intent = NormalizedGenerationIntent(
            userPrompt=prompt,
            negativePromptHint=negative or "",
            mode=mode,
            mediaType="video",
            durationSec=duration,
            hasSourceImage=bool(start_image),
            referenceCount=len(reference_ids),
            subjects=subjects,
        )
        result = compile_for_generator(generator_id, intent)
        compiled = str(result.compiledPrompt or "").strip()
        if result.status != "ok" or not compiled:
            return {
                "status": result.status,
                "dialect": (result.parameters or {}).get("dialect"),
                "profileId": (result.parameters or {}).get("profileId"),
                "subjectTagsEmitted": False,
                "warnings": list(result.warnings or []),
            }
        return {
            "status": result.status,
            "compiledPrompt": compiled,
            "compiledNegative": str(result.negativePrompt or ""),
            "dialect": (result.parameters or {}).get("dialect"),
            "profileId": (result.parameters or {}).get("profileId"),
            "subjectTagsEmitted": bool((result.parameters or {}).get("subjectTagsEmitted")),
            "knowledgeLoaded": bool((result.parameters or {}).get("knowledgeLoaded")),
            "knowledgeSpecPath": (result.parameters or {}).get("knowledgeSpecPath"),
            "knowledgeFile": (result.parameters or {}).get("knowledgeFile"),
            "r2vDialect": (result.parameters or {}).get("r2vDialect"),
            "r2vContract": (result.parameters or {}).get("r2vContract"),
            "warnings": list(result.warnings or []),
        }
    except Exception as exc:
        return {"status": "GENERATOR_KNOWLEDGE_UNAVAILABLE", "reason": repr(exc), "subjectTagsEmitted": False}


def _real_minimax_slots(batch: BatchBlock, image_slots: dict[str, Any]) -> list[dict[str, Any]]:
    """Subject tags require a wired Route A ref_images slot plus entity + asset."""
    if str(image_slots.get("ref_images") or "").upper() != "WIRED":
        return []
    slots: list[dict[str, Any]] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("consumed") is False:
            continue
        asset_id = str(ref.get("assetId") or "").strip()
        entity_id = str(ref.get("identityId") or ref.get("entityId") or "").strip()
        if not asset_id or not entity_id:
            continue
        slots.append(
            {
                "entityId": entity_id,
                "assetId": asset_id,
                "routeASlot": "ref_images",
                "wired": True,
            }
        )
    return slots


def _is_alias_only(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"\s*~?M\s*[1-5]\s*", text or "", re.I))


def _compile_movement_layers(project_id: str, batch: BatchBlock) -> dict[str, Any]:
    """Compile Spatial Map movement layers only when the creator bound them.

    Creator Spec Fidelity: a fresh Timed Prompt with Korri+Addex bindings must
    not inherit the project's active Spatial Map segment cast (e.g. Anadriya)
    just because a document exists. Require an explicit movementSegmentRef or a
    ~M alias in the Timed Prompt text. Never fall back to active_segment.
    """
    try:
        from ...spatial_map.movement_compile import (
            compile_generation_layers,
            layers_as_provider_text,
            parse_movement_alias,
        )
        from ...spatial_map import movement as movement_mod
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
            timed = getattr(first, "text", "") if first is not None else ""
            movement_mod.hydrate_movement_segments(document)

            segment = None
            if isinstance(ref, dict) and str(ref.get("id") or "").strip():
                segment = movement_mod.find_segment(document, str(ref["id"]))
            else:
                number = None
                if isinstance(ref, dict) and ref.get("segmentNumber"):
                    try:
                        number = int(ref["segmentNumber"])
                    except (TypeError, ValueError):
                        number = None
                if number is None:
                    number = parse_movement_alias(str(timed or ""))
                if number is not None:
                    segment = movement_mod.find_segment_by_number(document, number)

            if segment is None:
                # No creator-bound movement segment — do not inject Spatial Map cast.
                return {}

            layers = compile_generation_layers(document, segment, timed_prompt=str(timed or ""))
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

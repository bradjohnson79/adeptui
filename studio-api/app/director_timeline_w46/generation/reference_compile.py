"""Compile Prompt-clip and Camera-clip reference bindings to canonical IDs.

Never put alias text into the generation prompt. Legacy Image/Video Reference
tracks are not compiled after hydration — Prompt clips remain the scene-action
authority; Camera clips add motion-subject / motion-reference context.
Unsupported generators keep the binding but do not consume it. Over-limit
bindings are kept on the clip and refused at generate — never sliced or dropped.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, TimelineClip, _intervals_overlap
from ...director_timeline_bindings import name_binding_index
from ..contracts import BatchBlock, TimelineVisualAnchor, _nid
from .contracts import VideoGeneratorCapabilities
from .registry import get_registry


def resolve_binding_id(
    db: Session | None,
    project_id: str | None,
    binding_id: str | None,
    *,
    fallback_asset_id: str | None = None,
) -> dict[str, Any]:
    """Resolve a scene-reference binding to canonical IDs. Alias text is display-only."""
    token = (binding_id or "").strip() or None
    asset_id = (fallback_asset_id or "").strip() or None
    identity_id = None
    media_kind = None
    alias = None
    reference_type = None
    broken = False
    broken_reason = None
    approval_status = None
    approved_sheet_asset_id = None
    canonical_tag = None
    if db and project_id and token:
        try:
            from app.scene_references import repository as repo
            from app.scene_references.service import _enrich

            row = repo.get_binding(db, project_id, str(token))
            if row is None:
                broken = True
                broken_reason = "missing_binding"
            else:
                data = _enrich(db, repo.binding_to_dict(row))
                asset_id = data.get("asset_id") or asset_id
                identity_id = data.get("identity_id")
                media_kind = data.get("media_kind")
                alias = data.get("alias")
                reference_type = data.get("reference_type")
                approval_status = data.get("approval_status")
                approved_sheet_asset_id = data.get("approved_sheet_asset_id")
                from app.creator_scope.identity_tag import is_sheet_or_generic_label, sanitize_generator_tag

                raw_tag = str(data.get("canonical_tag") or data.get("display_token") or data.get("alias") or "")
                kind = str(data.get("reference_type") or "prop")
                if kind in {"environment", "location", "place", "scene"}:
                    entity = "environment"
                elif kind in {"character", "wardrobe", "creature"}:
                    entity = "character"
                else:
                    entity = "prop"
                display = str(data.get("identity_name") or "").strip()
                if not display or is_sheet_or_generic_label(display):
                    display = ""
                canonical_tag = sanitize_generator_tag(entity, raw_tag, display)
                if data.get("broken"):
                    broken = True
                    broken_reason = data.get("broken_reason") or "broken_reference"
        except Exception:
            broken = True
            broken_reason = "missing_binding"
    elif not asset_id:
        broken = True
        broken_reason = "missing_asset" if not token else "missing_binding"
    return {
        "bindingId": token,
        "assetId": str(asset_id) if asset_id else None,
        "identityId": identity_id,
        "mediaKind": media_kind,
        "referenceType": reference_type,
        "alias": alias,
        "broken": broken,
        "brokenReason": broken_reason,
        "approvalStatus": approval_status,
        "approvedSheetAssetId": approved_sheet_asset_id,
        "canonicalTag": canonical_tag,
        "displayToken": canonical_tag,
    }


def resolve_binding(
    db: Session | None,
    project_id: str | None,
    clip: TimelineClip,
) -> dict[str, Any]:
    """Resolve a legacy clip to canonical IDs. Alias text is display-only."""
    return resolve_binding_id(
        db,
        project_id,
        getattr(clip, "reference_binding_id", None),
        fallback_asset_id=getattr(clip, "asset_id", None),
    )


def _generator_caps(generator_id: str | None) -> VideoGeneratorCapabilities | None:
    if not generator_id:
        return None
    try:
        registry = get_registry()
        canonical = registry.resolve_id(generator_id)
        return registry.capabilities(canonical)
    except Exception:
        return None


def _overlapping_prompts(
    timeline: DirectorTimeline | None,
    window_start: float,
    window_end: float,
    *,
    master: Any = None,
) -> list[Any]:
    """Master-only: prompt segments come from batch.promptSegments.

    Legacy DirectorTimeline.prompt_segments is retired (410 Gone). When master
    is provided, segments are read from batchBlocks[].promptSegments with
    start-containment / overlap against the window. The timeline arg is kept
    for signature compatibility but is not read for prompts.
    """
    length = max(0.0, float(window_end) - float(window_start))
    segs: list[Any] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            if _intervals_overlap(
                float(getattr(seg, "start", 0.0) or 0.0),
                float(getattr(seg, "length", 0.0) or 0.0),
                window_start,
                length,
            ):
                segs.append(seg)
    return segs


def _drop_compiled_refs(batch: BatchBlock) -> None:
    """Clear previously-compiled references so each generation starts fresh.

    Without this, stale ``characterIdentity`` / ``characterVoice`` references from a
    prior run persist into the next batch and can be mis-resolved (e.g., a voice
    .wav left over from a previous clip being treated as a character image).
    """
    batch.references = [
        ref
        for ref in (batch.references or [])
        if not (
            isinstance(ref, dict)
            and ref.get("source")
            in (
                "prompt_clip",
                "camera_clip",
                "project_character",
                "project_character_voice",
            )
        )
    ]
    batch.sourceAnchors = [
        anchor
        for anchor in (batch.sourceAnchors or [])
        if not (
            anchor.kind == "video"
            and (anchor.label or "") in ("Video Reference", "Motion Reference")
        )
    ]


def _overlapping_cameras(
    timeline: DirectorTimeline | None,
    window_start: float,
    window_end: float,
    *,
    batch: Any = None,
) -> list[Any]:
    """Camera clips overlapping the batch window.

    SINGLE-STORE: when the owning batch is supplied, Master
    batch.cameraInstructions is the authority. Those clips are batch-local
    (reconcile_legacy_cameras subtracts the window start), so overlap is
    tested against [0, window_length). The legacy scene-global
    timeline.camera_clips path remains only for pre-Master callers.
    """
    if batch is not None:
        window_len = max(0.0, float(window_end) - float(window_start))
        return [
            clip
            for clip in getattr(batch, "cameraInstructions", None) or []
            if _intervals_overlap(
                float(getattr(clip, "start", 0.0) or 0.0),
                float(getattr(clip, "length", 0.0) or 0.0),
                0.0,
                window_len,
            )
        ]
    if timeline is None:
        return []
    length = max(0.0, float(window_end) - float(window_start))
    return [
        clip
        for clip in timeline.camera_clips or []
        if _intervals_overlap(clip.start, clip.length, window_start, length)
    ]


def _camera_clip_binding_ids(clip: Any) -> list[str]:
    """Reference binding ids on a camera clip — first-class field on Master
    BatchClip / legacy CameraClip, with a metadata pass-through fallback."""
    bids = [str(b) for b in (getattr(clip, "reference_binding_ids", None) or []) if str(b or "").strip()]
    if bids:
        return bids
    meta = getattr(clip, "metadata", None)
    if isinstance(meta, dict):
        raw = meta.get("reference_binding_ids") or meta.get("referenceBindingIds") or []
        if isinstance(raw, list):
            bids = [str(b) for b in raw if str(b or "").strip()]
    return bids


def _prompt_name_fields(binding_id: str, names_by_id: dict[str, dict[str, str]], fallback_label: str = "") -> dict[str, Any]:
    named = names_by_id.get(binding_id) or {}
    prompt_name = str(named.get("prompt_name") or "").strip()
    return {
        "promptName": prompt_name or None,
        "tag": named.get("tag") or None,
        "bindingType": named.get("type") or None,
        "label": prompt_name or fallback_label,
    }


def _already_consumed(batch: BatchBlock, binding_id: str, kind: str) -> bool:
    token = (binding_id or "").strip()
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("bindingId") == token and ref.get("kind") == kind and ref.get("consumed"):
            return True
    return False


def apply_compiled_references(
    batch: BatchBlock,
    director_timeline: DirectorTimeline | None,
    db: Session | None = None,
    project_id: str | None = None,
    *,
    window_start: float = 0.0,
    window_end: float | None = None,
    master: Any = None,
) -> list[dict[str, Any]]:
    """Bind Prompt-clip references onto the batch without consuming aliases.

    Returns honesty warnings (unsupported / broken / over-limit). Does not
    rewrite adapters or delete stored binding IDs. Prompt segments are read
    from Master batch.promptSegments only (single store).
    """
    warnings: list[dict[str, Any]] = []
    _drop_compiled_refs(batch)

    caps = _generator_caps(batch.generatorId)
    supports_video = bool(caps and caps.supportsVideoReferences and caps.maximumReferenceVideos > 0)
    supports_audio = bool(caps and caps.supportsAudioReferences and caps.maximumReferenceAudio > 0)
    supports_image = bool(
        caps and (caps.supportsMultipleImageReferences or (caps.maximumReferenceImages or 0) > 0)
    )
    max_images = int(caps.maximumReferenceImages or 0) if caps else 0
    max_videos = int(caps.maximumReferenceVideos or 0) if caps else 0
    max_audios = int(caps.maximumReferenceAudio or 0) if caps else 0

    end = float(window_end) if window_end is not None else (
        float(window_start) + float(batch.duration.plannedDuration or 5.0)
    )
    prompts = _overlapping_prompts(director_timeline, window_start, end, master=master)
    # Direct Reference Route: do not invent bindings from Timed Prompt prose.
    # Checked References are already persisted on the segment.

    binding_ids: list[str] = []
    names_by_id: dict[str, dict[str, str]] = {}
    for seg in prompts:
        names_by_id.update(
            name_binding_index(
                getattr(seg, "referenceNameBindings", None)
                or getattr(seg, "reference_name_bindings", None)
            )
        )
        for bid in getattr(seg, "referenceBindingIds", None) or getattr(seg, "reference_binding_ids", None) or []:
            token = (bid or "").strip()
            if token and token not in binding_ids:
                binding_ids.append(token)

    image_consumed = 0
    video_consumed = 0
    audio_consumed = 0

    for binding_id in binding_ids:
        resolved = resolve_binding_id(db, project_id, binding_id)
        kind = (resolved.get("mediaKind") or "").lower()
        ref_type = (resolved.get("referenceType") or "").lower()
        if resolved["broken"] and not resolved["assetId"] and kind != "entity":
            warnings.append(
                {
                    "code": "BROKEN_REFERENCE",
                    "message": "Broken Reference",
                    "bindingId": resolved["bindingId"],
                }
            )
            batch.references = list(batch.references or []) + [
                {
                    "kind": kind or "image",
                    "role": "broken_reference",
                    "bindingId": resolved["bindingId"],
                    "consumed": False,
                    "source": "prompt_clip",
                    "broken": True,
                }
            ]
            continue

        is_video = kind == "video" or ref_type == "video"
        is_audio = kind == "audio" or ref_type in ("audio", "voice")
        is_entity = kind == "entity" or ref_type in ("character", "prop")

        if is_audio:
            consumed = bool(supports_audio and resolved["assetId"])
            if not supports_audio:
                warnings.append(
                    {
                        "code": "AUDIO_REFERENCE_UNSUPPORTED",
                        "message": "Selected generator does not support audio references.",
                        "bindingId": resolved["bindingId"],
                        "assetId": resolved["assetId"],
                    }
                )
                consumed = False
            elif audio_consumed >= max_audios:
                consumed = False
                warnings.append(
                    {
                        "code": "AUDIO_REFERENCE_OVER_LIMIT",
                        "message": (
                            f"This generator supports up to {max_audios} audio reference(s) for this clip."
                        ),
                        "bindingId": resolved["bindingId"],
                    }
                )
            if consumed:
                audio_consumed += 1
            named = _prompt_name_fields(binding_id, names_by_id, str(resolved.get("alias") or ""))
            batch.references = list(batch.references or []) + [
                {
                    "kind": "audio",
                    "role": "audio_reference",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "identityId": resolved.get("identityId"),
                    "label": named["label"],
                    "promptName": named["promptName"],
                    "tag": named["tag"] or resolved.get("canonicalTag"),
                    "bindingType": named["bindingType"],
                    "consumed": bool(consumed and resolved["assetId"]),
                    "source": "prompt_clip",
                }
            ]
            continue

        if is_video:
            consumed = supports_video
            if not consumed:
                warnings.append(
                    {
                        "code": "VIDEO_REFERENCE_UNSUPPORTED",
                        "message": "Selected generator does not support Video Reference.",
                        "bindingId": resolved["bindingId"],
                        "assetId": resolved["assetId"],
                    }
                )
            elif video_consumed >= max_videos:
                consumed = False
                warnings.append(
                    {
                        "code": "VIDEO_REFERENCE_OVER_LIMIT",
                        "message": (
                            f"This generator supports up to {max_videos} video reference(s) for this clip."
                        ),
                        "bindingId": resolved["bindingId"],
                    }
                )
            if consumed and resolved["assetId"]:
                video_consumed += 1
                if not any(a.kind == "video" and (a.assetId or "").strip() for a in (batch.sourceAnchors or [])):
                    batch.sourceAnchors.append(
                        TimelineVisualAnchor(
                            id=_nid("anc_"),
                            kind="video",
                            assetId=str(resolved["assetId"]),
                            label="Video Reference",
                            atTime=float(window_start or 0.0),
                            strength=1.0,
                        )
                    )
            batch.references = list(batch.references or []) + [
                {
                    "kind": "video",
                    "role": "video_reference",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "consumed": bool(consumed and resolved["assetId"]),
                    "source": "prompt_clip",
                }
            ]
            continue

        if is_entity:
            # Approval gating: character references must be approved to be
            # authoritative. Warn (don't block) when a character reference
            # is not approved — the character_identity_bind stage will
            # resolve the approved CRS separately, but the warning surfaces
            # the gap so the UI can show it.
            approval = str(resolved.get("approvalStatus") or "").lower()
            ref_type_lower = str(ref_type or "").lower()
            if ref_type_lower in {"character", "wardrobe", "creature"} and approval not in {"approved", ""}:
                warnings.append(
                    {
                        "code": "CHARACTER_REFERENCE_NOT_APPROVED",
                        "message": (
                            f"{resolved.get('alias') or resolved.get('bindingId')} is bound as a character "
                            f"reference but is not approved (status: {approval or 'unknown'}). "
                            "The character may not render with the intended identity."
                        ),
                        "bindingId": resolved["bindingId"],
                        "approvalStatus": approval or None,
                    }
                )
            canonical = str(resolved.get("canonicalTag") or resolved.get("displayToken") or "").strip()
            alias = str(resolved.get("alias") or "").strip()
            if canonical:
                alias = alias or canonical.lstrip("@#%*")
            batch.references = list(batch.references or []) + [
                {
                    "kind": "entity",
                    "role": "entity_reference",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "identityId": resolved.get("identityId"),
                    "alias": alias or None,
                    "label": alias or None,
                    "promptName": alias or None,
                    "tag": canonical or None,
                    "referenceType": resolved.get("referenceType"),
                    "consumed": False,
                    "source": "prompt_clip",
                    "approvalStatus": approval or None,
                }
            ]
            if not resolved["assetId"]:
                warnings.append(
                    {
                        "code": "ENTITY_REFERENCE_NO_ASSET",
                        "message": "Character/prop reference is bound; this generator may not consume it as an image.",
                        "bindingId": resolved["bindingId"],
                    }
                )
                continue
            # Visual asset on an entity counts toward image-reference capacity.

        if resolved["broken"] or not resolved["assetId"]:
            warnings.append(
                {
                    "code": "BROKEN_IMAGE_REFERENCE",
                    "message": "Broken Reference",
                    "bindingId": resolved["bindingId"],
                }
            )
            continue

        consumed = bool(resolved["assetId"])
        if not supports_image:
            warnings.append(
                {
                    "code": "IMAGE_REFERENCE_UNSUPPORTED",
                    "message": "Selected model does not support image reference. The binding is kept and will not be used.",
                    "bindingId": resolved["bindingId"],
                    "assetId": resolved["assetId"],
                }
            )
        elif max_images >= 0 and image_consumed >= max_images:
            warnings.append(
                {
                    "code": "IMAGE_REFERENCE_OVER_LIMIT",
                    "message": (
                        f"This generator supports up to {max_images} image references for this clip."
                    ),
                    "bindingId": resolved["bindingId"],
                }
            )
        if consumed:
            image_consumed += 1
        from ...scene_references.sheet_tags import r2v_role_for_reference

        sheet_role = r2v_role_for_reference(ref_type, role=None, kind=kind)
        named = _prompt_name_fields(binding_id, names_by_id, str(resolved.get("alias") or ""))
        batch.references = list(batch.references or []) + [
            {
                "kind": kind or "image",
                "role": sheet_role,
                "assetId": resolved["assetId"],
                "bindingId": resolved["bindingId"],
                "identityId": resolved.get("identityId"),
                "label": named["label"],
                "promptName": named["promptName"],
                "tag": named["tag"],
                "bindingType": named["bindingType"],
                "consumed": consumed,
                "source": "prompt_clip",
            }
        ]

    camera_binding_ids: list[str] = []
    # SINGLE-STORE: Master batch.cameraInstructions is the camera authority
    # (batch-local). Legacy timeline.camera_clips only when no batch supplied.
    for clip in _overlapping_cameras(director_timeline, window_start, end, batch=batch):
        for bid in _camera_clip_binding_ids(clip):
            token = (bid or "").strip()
            if token and token not in camera_binding_ids:
                camera_binding_ids.append(token)

    for binding_id in camera_binding_ids:
        resolved = resolve_binding_id(db, project_id, binding_id)
        kind = (resolved.get("mediaKind") or "").lower()
        ref_type = (resolved.get("referenceType") or "").lower()
        is_video = kind == "video" or ref_type == "video"
        is_entity = kind == "entity" or ref_type in ("character", "prop")
        is_character = ref_type == "character" or (kind == "entity" and ref_type != "prop")

        if resolved["broken"] and not resolved["assetId"] and not is_entity:
            warnings.append(
                {
                    "code": "BROKEN_REFERENCE",
                    "message": "Broken Reference",
                    "bindingId": resolved["bindingId"],
                    "source": "camera_clip",
                }
            )
            batch.references = list(batch.references or []) + [
                {
                    "kind": kind or "video",
                    "role": "broken_reference",
                    "bindingId": resolved["bindingId"],
                    "consumed": False,
                    "source": "camera_clip",
                    "broken": True,
                    "voiceCoupled": False,
                }
            ]
            continue

        if is_video:
            already = _already_consumed(batch, resolved["bindingId"] or "", "video")
            consumed = bool(already or (supports_video and resolved["assetId"]))
            if not supports_video:
                consumed = False
                warnings.append(
                    {
                        "code": "VIDEO_MOTION_REFERENCE_UNSUPPORTED",
                        "message": "Selected generator does not support video motion references.",
                        "bindingId": resolved["bindingId"],
                        "assetId": resolved["assetId"],
                        "source": "camera_clip",
                    }
                )
            elif not already and video_consumed >= max_videos:
                consumed = False
                warnings.append(
                    {
                        "code": "VIDEO_MOTION_REFERENCE_OVER_LIMIT",
                        "message": (
                            f"This generator supports up to {max_videos} video reference(s) for this clip."
                        ),
                        "bindingId": resolved["bindingId"],
                        "source": "camera_clip",
                    }
                )
            if consumed and resolved["assetId"] and not already:
                video_consumed += 1
                if not any(a.kind == "video" and (a.assetId or "").strip() for a in (batch.sourceAnchors or [])):
                    batch.sourceAnchors.append(
                        TimelineVisualAnchor(
                            id=_nid("anc_"),
                            kind="video",
                            assetId=str(resolved["assetId"]),
                            label="Motion Reference",
                            atTime=float(window_start or 0.0),
                            strength=1.0,
                        )
                    )
            batch.references = list(batch.references or []) + [
                {
                    "kind": "video",
                    "role": "motion_reference",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "consumed": bool(consumed and resolved["assetId"]),
                    "source": "camera_clip",
                    "voiceCoupled": False,
                }
            ]
            continue

        if is_entity:
            batch.references = list(batch.references or []) + [
                {
                    "kind": "entity",
                    "role": "motion_subject" if is_character else "motion_entity",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "identityId": resolved.get("identityId"),
                    "consumed": False,
                    "source": "camera_clip",
                    "voiceCoupled": False,
                }
            ]
            continue

        warnings.append(
            {
                "code": "CAMERA_IMAGE_REFERENCE_UNSUPPORTED",
                "message": "Camera uses @ characters and * video motion references.",
                "bindingId": resolved["bindingId"],
                "source": "camera_clip",
            }
        )
        batch.references = list(batch.references or []) + [
            {
                "kind": kind or "image",
                "role": "camera_unsupported_reference",
                "assetId": resolved["assetId"],
                "bindingId": resolved["bindingId"],
                "consumed": False,
                "source": "camera_clip",
                "voiceCoupled": False,
            }
        ]
    return warnings

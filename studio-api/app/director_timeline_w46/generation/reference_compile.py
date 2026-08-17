"""Compile Prompt-clip reference bindings to canonical Library / entity IDs.

Never put alias text into the generation prompt. Legacy Image/Video Reference
tracks are not compiled after hydration — Prompt clips are authoritative.
Unsupported generators keep the binding but do not consume it. Over-limit
bindings are kept on the clip and refused at generate — never sliced or dropped.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, PromptSegment, TimelineClip, _intervals_overlap
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
    timeline: DirectorTimeline,
    window_start: float,
    window_end: float,
) -> list[PromptSegment]:
    length = max(0.0, float(window_end) - float(window_start))
    return [
        seg
        for seg in timeline.prompt_segments or []
        if _intervals_overlap(seg.start, seg.length, window_start, length)
    ]


def _drop_compiled_refs(batch: BatchBlock) -> None:
    batch.references = [
        ref
        for ref in (batch.references or [])
        if not (
            isinstance(ref, dict)
            and ref.get("source") == "prompt_clip"
        )
    ]
    batch.sourceAnchors = [
        anchor
        for anchor in (batch.sourceAnchors or [])
        if not (anchor.kind == "video" and (anchor.label or "") == "Video Reference")
    ]


def apply_compiled_references(
    batch: BatchBlock,
    director_timeline: DirectorTimeline | None,
    db: Session | None = None,
    project_id: str | None = None,
    *,
    window_start: float = 0.0,
    window_end: float | None = None,
) -> list[dict[str, Any]]:
    """Bind Prompt-clip references onto the batch without consuming aliases.

    Returns honesty warnings (unsupported / broken / over-limit). Does not
    rewrite adapters or delete stored binding IDs.
    """
    warnings: list[dict[str, Any]] = []
    _drop_compiled_refs(batch)
    if director_timeline is None:
        return warnings

    caps = _generator_caps(batch.generatorId)
    supports_video = bool(caps and caps.supportsVideoReferences and caps.maximumReferenceVideos > 0)
    supports_image = bool(
        caps and (caps.supportsMultipleImageReferences or (caps.maximumReferenceImages or 0) > 0)
    )
    max_images = int(caps.maximumReferenceImages or 0) if caps else 0
    max_videos = int(caps.maximumReferenceVideos or 0) if caps else 0

    end = float(window_end) if window_end is not None else (
        float(window_start) + float(batch.duration.plannedDuration or director_timeline.duration_sec or 5.0)
    )
    prompts = _overlapping_prompts(director_timeline, window_start, end)

    binding_ids: list[str] = []
    for seg in prompts:
        for bid in seg.reference_binding_ids or []:
            token = (bid or "").strip()
            if token and token not in binding_ids:
                binding_ids.append(token)

    image_consumed = 0
    video_consumed = 0

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
        is_entity = kind == "entity" or ref_type in ("character", "prop")

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
            batch.references = list(batch.references or []) + [
                {
                    "kind": "entity",
                    "role": "entity_reference",
                    "assetId": resolved["assetId"],
                    "bindingId": resolved["bindingId"],
                    "identityId": resolved.get("identityId"),
                    "consumed": False,
                    "source": "prompt_clip",
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
        batch.references = list(batch.references or []) + [
            {
                "kind": "image",
                "role": "image_reference",
                "assetId": resolved["assetId"],
                "bindingId": resolved["bindingId"],
                "identityId": resolved.get("identityId"),
                "consumed": consumed,
                "source": "prompt_clip",
            }
        ]
    return warnings

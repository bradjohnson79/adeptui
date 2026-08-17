"""Compile Timeline reference clips to canonical Library / entity IDs.

Never put alias text into the generation prompt. Unsupported generators keep
the binding but do not consume it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, TimelineClip
from ..contracts import BatchBlock, TimelineVisualAnchor, _nid
from .contracts import VideoGeneratorCapabilities
from .registry import get_registry


def _clip_list(timeline: DirectorTimeline | None, attr: str) -> list[TimelineClip]:
    if timeline is None:
        return []
    return list(getattr(timeline, attr, None) or [])


def resolve_binding(
    db: Session | None,
    project_id: str | None,
    clip: TimelineClip,
) -> dict[str, Any]:
    """Resolve a clip to canonical IDs. Alias text is display-only."""
    binding_id = getattr(clip, "reference_binding_id", None) or None
    asset_id = getattr(clip, "asset_id", None) or None
    identity_id = None
    media_kind = None
    alias = None
    broken = False
    broken_reason = None
    if db and project_id and binding_id:
        try:
            from app.scene_references import repository as repo
            from app.scene_references.service import _enrich

            row = repo.get_binding(db, project_id, str(binding_id))
            if row is None:
                broken = True
                broken_reason = "missing_binding"
            else:
                data = _enrich(db, repo.binding_to_dict(row))
                asset_id = data.get("asset_id") or asset_id
                identity_id = data.get("identity_id")
                media_kind = data.get("media_kind")
                alias = data.get("alias")
                if data.get("broken"):
                    broken = True
                    broken_reason = data.get("broken_reason") or "broken_reference"
        except Exception:
            broken = True
            broken_reason = "missing_binding"
    elif not asset_id:
        broken = True
        broken_reason = "missing_asset"
    return {
        "bindingId": binding_id,
        "assetId": str(asset_id) if asset_id else None,
        "identityId": identity_id,
        "mediaKind": media_kind,
        "alias": alias,
        "broken": broken,
        "brokenReason": broken_reason,
    }


def _generator_caps(generator_id: str | None) -> VideoGeneratorCapabilities | None:
    if not generator_id:
        return None
    try:
        registry = get_registry()
        canonical = registry.resolve_id(generator_id)
        return registry.capabilities(canonical)
    except Exception:
        return None


def apply_compiled_references(
    batch: BatchBlock,
    director_timeline: DirectorTimeline | None,
    db: Session | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Bind Image / Video Reference clips onto the batch without consuming aliases.

    Returns honesty warnings (unsupported / broken). Does not rewrite adapters.
    """
    warnings: list[dict[str, Any]] = []
    caps = _generator_caps(batch.generatorId)
    supports_video = bool(caps and caps.supportsVideoReferences and caps.maximumReferenceVideos > 0)
    supports_image = bool(
        caps and (caps.supportsMultipleImageReferences or caps.maximumReferenceImages > 0)
    )

    # Video reference — one clip. Resolve by binding id, never by alias string.
    if not any(a.kind == "video" and (a.assetId or "").strip() for a in (batch.sourceAnchors or [])):
        clips = _clip_list(director_timeline, "video_reference_clips")
        chosen = next((c for c in clips if getattr(c, "reference_binding_id", None) or getattr(c, "asset_id", None)), None)
        if chosen is not None:
            resolved = resolve_binding(db, project_id, chosen)
            if resolved["broken"] or not resolved["assetId"]:
                warnings.append(
                    {
                        "code": "BROKEN_VIDEO_REFERENCE",
                        "message": "Broken Reference",
                        "bindingId": resolved["bindingId"],
                    }
                )
            elif not supports_video:
                warnings.append(
                    {
                        "code": "VIDEO_REFERENCE_UNSUPPORTED",
                        "message": "Selected model does not support video reference. The binding is kept and will not be used.",
                        "bindingId": resolved["bindingId"],
                        "assetId": resolved["assetId"],
                    }
                )
                batch.references = list(batch.references or []) + [
                    {
                        "kind": "video",
                        "role": "video_reference",
                        "assetId": resolved["assetId"],
                        "bindingId": resolved["bindingId"],
                        "consumed": False,
                    }
                ]
            else:
                batch.sourceAnchors = [a for a in (batch.sourceAnchors or []) if a.kind != "video"]
                trim_in = float(getattr(chosen, "trim_start", 0.0) or 0.0)
                length = float(getattr(chosen, "length", 0.0) or 0.0)
                batch.sourceAnchors.append(
                    TimelineVisualAnchor(
                        id=_nid("anc_"),
                        kind="video",
                        assetId=str(resolved["assetId"]),
                        label="Video Reference",
                        atTime=float(getattr(chosen, "start", 0.0) or 0.0),
                        strength=1.0,
                    )
                )
                batch.references = list(batch.references or []) + [
                    {
                        "kind": "video",
                        "role": "video_reference",
                        "assetId": resolved["assetId"],
                        "bindingId": resolved["bindingId"],
                        "consumed": True,
                        "trim": {"in": trim_in, "out": trim_in + length} if length else None,
                    }
                ]

    image_clips = _clip_list(director_timeline, "image_reference_clips")
    for clip in image_clips:
        if not (getattr(clip, "reference_binding_id", None) or getattr(clip, "asset_id", None)):
            continue
        resolved = resolve_binding(db, project_id, clip)
        kind = (resolved.get("mediaKind") or "").lower()
        if kind == "video":
            warnings.append(
                {
                    "code": "WRONG_REFERENCE_TYPE",
                    "message": "Image Reference does not accept video tokens.",
                    "bindingId": resolved["bindingId"],
                }
            )
            continue
        if resolved["broken"] or not resolved["assetId"]:
            warnings.append(
                {
                    "code": "BROKEN_IMAGE_REFERENCE",
                    "message": "Broken Reference",
                    "bindingId": resolved["bindingId"],
                }
            )
            continue
        consumed = supports_image
        if not consumed:
            warnings.append(
                {
                    "code": "IMAGE_REFERENCE_UNSUPPORTED",
                    "message": "Selected model does not support image reference. The binding is kept and will not be used.",
                    "bindingId": resolved["bindingId"],
                    "assetId": resolved["assetId"],
                }
            )
        batch.references = list(batch.references or []) + [
            {
                "kind": "image",
                "role": "image_reference",
                "assetId": resolved["assetId"],
                "bindingId": resolved["bindingId"],
                "identityId": resolved.get("identityId"),
                "consumed": consumed,
            }
        ]
    return warnings

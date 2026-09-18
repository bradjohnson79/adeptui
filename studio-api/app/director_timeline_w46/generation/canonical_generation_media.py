"""Wave 3A — CanonicalGenerationMedia (minimal Omni Visual media authority).

Owner law:
  mediaType=image → generation reference (not Visual playback take)
  mediaType=video → playable Visual media

Adapters map sockets natively (H3 → ref_image_N). No Timeline silent image
generation. No CRS/Front reinterpret. Does not touch 1F/T2V/3F graphs.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

MediaType = Literal["image", "video"]
MediaRole = Literal["reference", "visual_take"]


class CanonicalGenerationMedia(BaseModel):
    """Single deposit/placement shape for Omni Visual + References handoffs."""

    assetId: str
    mediaType: MediaType
    role: MediaRole
    bindingId: Optional[str] = None
    clipId: Optional[str] = None
    label: Optional[str] = None
    sourceSurface: Optional[str] = None


def classify_visual_placement(
    *,
    asset_id: str,
    kind: str,
    clip_id: str | None = None,
    label: str | None = None,
    binding_id: str | None = None,
    source_surface: str | None = None,
) -> CanonicalGenerationMedia:
    """Library → Visual placement law: image=reference, video=visual_take."""
    token = str(kind or "").strip().lower()
    aid = str(asset_id or "").strip()
    if not aid:
        raise ValueError("ASSET_ID_REQUIRED")
    if token == "image":
        return CanonicalGenerationMedia(
            assetId=aid,
            mediaType="image",
            role="reference",
            bindingId=binding_id,
            clipId=clip_id,
            label=label,
            sourceSurface=source_surface or "visual",
        )
    if token == "video":
        return CanonicalGenerationMedia(
            assetId=aid,
            mediaType="video",
            role="visual_take",
            bindingId=binding_id,
            clipId=clip_id,
            label=label,
            sourceSurface=source_surface or "visual",
        )
    raise ValueError(f"UNSUPPORTED_KIND:{token}")


def persist_media_type_on_clip(clip: dict[str, Any], media_type: MediaType) -> dict[str, Any]:
    """Stamp explicit mediaType / media_type on a Visual clip dict (idempotent)."""
    out = dict(clip)
    out["mediaType"] = media_type
    out["media_type"] = media_type
    return out


def map_cgm_images_to_h3_ref_sockets(
    items: list[CanonicalGenerationMedia],
    *,
    maximum: int = 9,
) -> list[dict[str, Any]]:
    """H3 adapter socket map: reference images → ref_image_0..ref_image_N.

    Generator adapter still decides sockets; this is the Omni→H3 native map only.
    Does not invent CRS/Front remaps. Over-limit items are dropped (adapter may
    surface blocked reasons separately via Direct Reference).
    """
    refs = [i for i in items if i.mediaType == "image" and i.role == "reference" and i.assetId]
    sockets: list[dict[str, Any]] = []
    for index, item in enumerate(refs[: max(0, int(maximum))]):
        sockets.append(
            {
                "socket": f"ref_image_{index}",
                "assetId": item.assetId,
                "bindingId": item.bindingId,
                "mediaType": "image",
                "kind": "image",
                "clipId": item.clipId,
                "label": item.label,
            }
        )
    return sockets


def visual_image_clips_to_cgm(
    image_clips: list[Any],
    *,
    source_surface: str = "visual_image_clips",
) -> list[CanonicalGenerationMedia]:
    """Convert Visual image_clips into reference-bearing CGM records."""
    out: list[CanonicalGenerationMedia] = []
    for clip in image_clips or []:
        if isinstance(clip, dict):
            aid = clip.get("asset_id") or clip.get("assetId")
            cid = clip.get("id")
            label = clip.get("label")
            binding = clip.get("reference_binding_id") or clip.get("referenceBindingId")
            mt = (clip.get("mediaType") or clip.get("media_type") or "image").lower()
        else:
            aid = getattr(clip, "asset_id", None)
            cid = getattr(clip, "id", None)
            label = getattr(clip, "label", None)
            binding = getattr(clip, "reference_binding_id", None)
            mt = (getattr(clip, "media_type", None) or getattr(clip, "mediaType", None) or "image")
            mt = str(mt).lower()
        if not aid or mt != "image":
            continue
        out.append(
            CanonicalGenerationMedia(
                assetId=str(aid),
                mediaType="image",
                role="reference",
                bindingId=str(binding) if binding else None,
                clipId=str(cid) if cid else None,
                label=str(label) if label else None,
                sourceSurface=source_surface,
            )
        )
    return out

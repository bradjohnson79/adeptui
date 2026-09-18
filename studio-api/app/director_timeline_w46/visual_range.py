"""Canonical Visual-track range replacement (A | Middle | B).

Library MP4 stitch (range_replacement.compose_range_media) is NOT Visual authority.
This module is the sole Visual write path for bounded range retakes and image-frame
placement. Video middle = rtclip_*; image middle = imgclip_*.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from ..db import Asset
from ..director_timeline import TimelineClip, parse_director_timeline
from ..media_clip import probe_video_duration
from . import store
from .contracts import SceneTimelineMaster, _now
from .scene_stitch import resolve_asset_file

DURATION_EPS = 0.05
GEOMETRY_EPS = 0.05
MANAGED_DIRECTOR_CLIP_PREFIX = "bbclip_"
RETAKE_CLIP_PREFIX = "rtclip_"
IMAGE_CLIP_PREFIX = "imgclip_"
MiddleMediaType = Literal["video", "image"]


def _nid(prefix: str = "clip_") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _clip_meta(clip: Any) -> dict[str, Any]:
    raw = getattr(clip, "metadata", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _is_image_frame_clip(clip: Any) -> bool:
    cid = str(getattr(clip, "id", "") or "")
    meta = _clip_meta(clip)
    mt = str(getattr(clip, "media_type", None) or "").lower()
    return (
        cid.startswith(IMAGE_CLIP_PREFIX)
        or meta.get("role") == "image_frame"
        or mt == "image"
    )


def _is_middle_range_clip(clip: Any) -> bool:
    cid = str(getattr(clip, "id", "") or "")
    meta = _clip_meta(clip)
    role = str(meta.get("role") or "")
    return (
        cid.startswith(RETAKE_CLIP_PREFIX)
        or cid.startswith(IMAGE_CLIP_PREFIX)
        or role in {"retake", "image_frame"}
    )


def _probe_asset_duration(db: Session, project_id: str, asset_id: str) -> float | None:
    path = resolve_asset_file(db, project_id, asset_id)
    if path is None:
        return None
    try:
        return probe_video_duration(path)
    except Exception:
        return None


def _require_image_asset(db: Session, project_id: str, asset_id: str) -> dict[str, Any] | None:
    """Fail-closed image existence check. Returns error dict or None when ok."""
    aid = str(asset_id or "").strip()
    if not aid:
        return {
            "ok": False,
            "error": "IMAGE_ASSET_REQUIRED",
            "message": "Image-frame place needs an imageAssetId.",
            "mock": False,
        }
    asset = db.get(Asset, aid)
    if asset is None or str(getattr(asset, "project_id", "") or "") != str(project_id):
        return {
            "ok": False,
            "error": "IMAGE_ASSET_NOT_FOUND",
            "message": "Image asset does not exist on this project.",
            "mock": False,
        }
    kind = str(getattr(asset, "kind", "") or "").strip().lower()
    if kind != "image":
        return {
            "ok": False,
            "error": "IMAGE_ASSET_KIND_REQUIRED",
            "message": f"Asset kind must be image (got {kind or 'unknown'}).",
            "mock": False,
        }
    return None


def range_retake_batch_ids(video_clips: list[Any] | None) -> set[str]:
    """Batch ids that already have a Visual A|Middle|B composition (rtclip_* / imgclip_*)."""
    found: set[str] = set()
    for clip in video_clips or []:
        cid = str(getattr(clip, "id", "") or "")
        meta = _clip_meta(clip)
        batch_id = str(meta.get("sourceBatchId") or "").strip()
        if not batch_id:
            continue
        if cid.startswith(RETAKE_CLIP_PREFIX) or cid.startswith(IMAGE_CLIP_PREFIX):
            found.add(batch_id)
        elif meta.get("role") in {"retake", "image_frame"}:
            found.add(batch_id)
        elif meta.get("replacementAssetId"):
            found.add(batch_id)
    return found


def clip_belongs_to_range_batch(clip: Any, batch_id: str) -> bool:
    cid = str(getattr(clip, "id", "") or "")
    if cid == f"{MANAGED_DIRECTOR_CLIP_PREFIX}{batch_id}":
        return True
    if cid.startswith(RETAKE_CLIP_PREFIX) or cid.startswith(IMAGE_CLIP_PREFIX):
        return str(_clip_meta(clip).get("sourceBatchId") or "") == batch_id
    return str(_clip_meta(clip).get("sourceBatchId") or "") == batch_id


def find_image_frame_asset_in_range(
    video_clips: list[Any] | None,
    *,
    mark_in: float,
    mark_out: float,
    source_batch_id: str | None = None,
) -> str | None:
    """Return referenceImageAssetId / asset_id for an imgclip overlapping the marked window."""
    mark_in = float(mark_in)
    mark_out = float(mark_out)
    for clip in video_clips or []:
        if not _is_image_frame_clip(clip):
            continue
        meta = _clip_meta(clip)
        if source_batch_id:
            clip_batch = str(meta.get("sourceBatchId") or "").strip()
            if clip_batch and clip_batch != source_batch_id:
                continue
        mi = meta.get("markIn")
        mo = meta.get("markOut")
        if mi is not None and mo is not None:
            if float(mi) < mark_out - GEOMETRY_EPS and mark_in < float(mo) - GEOMETRY_EPS:
                return str(meta.get("referenceImageAssetId") or getattr(clip, "asset_id", None) or "").strip() or None
        c0 = float(getattr(clip, "start", 0.0) or 0.0)
        c1 = c0 + float(getattr(clip, "length", 0.0) or 0.0)
        if c0 < mark_out - GEOMETRY_EPS and mark_in < c1 - GEOMETRY_EPS:
            return str(meta.get("referenceImageAssetId") or getattr(clip, "asset_id", None) or "").strip() or None
    return None


def _reconstruct_virtual_take(
    clips: list[TimelineClip],
    *,
    source_batch_id: str | None,
    source_asset_id: str | None,
) -> TimelineClip | None:
    """Rebuild full original take span from A|Middle|B so mark_in/out stay take-relative."""
    if not source_batch_id:
        return None
    pieces = [c for c in clips if clip_belongs_to_range_batch(c, source_batch_id)]
    if len(pieces) < 2:
        return None
    pieces.sort(key=lambda c: (float(c.start or 0.0), str(c.id)))
    a = next((c for c in pieces if _clip_meta(c).get("role") == "original_a"), None)
    b = next((c for c in pieces if _clip_meta(c).get("role") == "original_b"), None)
    middle = next((c for c in pieces if _is_middle_range_clip(c)), None)
    if middle is None and a is None:
        return None
    v_start = float((a or pieces[0]).start or 0.0)
    v_end = max(float(c.start or 0.0) + float(c.length or 0.0) for c in pieces)
    v_len = v_end - v_start
    if v_len <= GEOMETRY_EPS:
        return None
    prior = float(getattr(a, "trim_start", 0.0) or 0.0) if a is not None else 0.0
    if a is None and middle is not None:
        # No A: middle begins at markIn; recover take start and prior from metadata.
        mi = float(_clip_meta(middle).get("markIn") or 0.0)
        v_start = float(middle.start or 0.0) - mi
        prior = max(0.0, float(_clip_meta(middle).get("priorTrimStart") or 0.0))
        v_end = max(v_end, v_start + float(_clip_meta(middle).get("markOut") or 0.0))
        if b is not None:
            v_end = max(v_end, float(b.start or 0.0) + float(b.length or 0.0))
        v_len = v_end - v_start
    orig = str(
        source_asset_id
        or (a.asset_id if a is not None else None)
        or (b.asset_id if b is not None else None)
        or _clip_meta(middle or pieces[0]).get("sourceAssetId")
        or ""
    )
    if not orig:
        return None
    managed_id = f"{MANAGED_DIRECTOR_CLIP_PREFIX}{source_batch_id}"
    return TimelineClip(
        id=managed_id if any(str(c.id) == managed_id for c in pieces) else str((a or pieces[0]).id),
        asset_id=orig,
        start=v_start,
        length=v_len,
        trim_start=prior,
        label=(a or middle or pieces[0]).label or "Take",
        media_type="video",
        metadata={"role": "virtual_original", "sourceBatchId": source_batch_id},
    )


def _resolve_active_visual_clip(
    video_clips: list[TimelineClip],
    *,
    source_batch_id: str | None,
    source_asset_id: str | None,
    mark_in: float,
    mark_out: float,
) -> TimelineClip | None:
    """Prefer the managed/active Visual take for this batch; never stale lipsync/output paths."""
    clips = list(video_clips or [])
    if source_batch_id:
        managed_id = f"{MANAGED_DIRECTOR_CLIP_PREFIX}{source_batch_id}"
        managed = next((c for c in clips if c.id == managed_id), None)
        if managed and (managed.asset_id or source_asset_id):
            # Full take: use managed. Remnant A after prior split: reconstruct.
            if float(managed.length or 0.0) + GEOMETRY_EPS >= mark_out:
                return managed
            reconstructed = _reconstruct_virtual_take(
                clips,
                source_batch_id=source_batch_id,
                source_asset_id=source_asset_id or str(managed.asset_id or ""),
            )
            if reconstructed is not None:
                return reconstructed
            return managed
        same_batch = [c for c in clips if clip_belongs_to_range_batch(c, source_batch_id)]
        if same_batch:
            reconstructed = _reconstruct_virtual_take(
                clips,
                source_batch_id=source_batch_id,
                source_asset_id=source_asset_id,
            )
            if reconstructed is not None:
                return reconstructed
            spanning = [
                c
                for c in same_batch
                if float(c.length or 0.0) + GEOMETRY_EPS >= (mark_out - mark_in)
                and str(c.asset_id or "") == str(source_asset_id or c.asset_id or "")
                and not _is_middle_range_clip(c)
            ]
            if spanning:
                return max(spanning, key=lambda c: float(c.length or 0.0))

    if source_asset_id:
        by_asset = [c for c in clips if str(c.asset_id or "") == str(source_asset_id)]
        able = [c for c in by_asset if float(c.length or 0.0) + GEOMETRY_EPS >= mark_out]
        if able:
            return max(able, key=lambda c: float(c.length or 0.0))
        if by_asset:
            return max(by_asset, key=lambda c: float(c.length or 0.0))

    if len(clips) == 1:
        return clips[0]
    return None


def _split_active_visual_range(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    mark_in: float,
    mark_out: float,
    middle_asset_id: str,
    middle_media_type: MiddleMediaType,
    middle_clip_id: str,
    middle_role: str,
    middle_label: str,
    middle_extra_meta: dict[str, Any] | None = None,
    retake_id: str | None = None,
    source_batch_id: str | None = None,
    source_asset_id: str | None = None,
) -> dict[str, Any]:
    """Shared A | Middle | B geometry writer. Caller validates middle asset rules."""
    mark_in = float(mark_in)
    mark_out = float(mark_out)
    if mark_out <= mark_in + GEOMETRY_EPS:
        return {
            "ok": False,
            "error": "INVALID_RANGE",
            "message": "markOut must be greater than markIn.",
            "mock": False,
        }

    mid_id = str(middle_asset_id or "").strip()
    if not mid_id:
        return {
            "ok": False,
            "error": "MIDDLE_ASSET_REQUIRED",
            "message": "Range place needs a middle asset id.",
            "mock": False,
        }

    bundle = store.load_master(db, project_id, scene_id)
    if not bundle.get("ok"):
        return bundle
    master = SceneTimelineMaster.model_validate(bundle["master"])
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}

    director_tl = parse_director_timeline(
        scene.director_json,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )
    video_clips = list(director_tl.video_clips or [])

    active = _resolve_active_visual_clip(
        video_clips,
        source_batch_id=source_batch_id,
        source_asset_id=source_asset_id,
        mark_in=mark_in,
        mark_out=mark_out,
    )
    if active is None or not (active.asset_id or source_asset_id):
        return {
            "ok": False,
            "error": "ACTIVE_VISUAL_TAKE_NOT_FOUND",
            "message": "No active Visual take spans the marked range.",
            "mock": False,
        }

    orig_asset = str(source_asset_id or active.asset_id or "")
    if not orig_asset:
        return {
            "ok": False,
            "error": "SOURCE_ASSET_MISSING",
            "message": "Active Visual take has no asset.",
            "mock": False,
        }

    clip_start = float(active.start or 0.0)
    clip_len = float(active.length or 0.0)
    prior_trim = float(getattr(active, "trim_start", 0.0) or 0.0)
    if mark_in < -GEOMETRY_EPS or mark_out > clip_len + GEOMETRY_EPS:
        return {
            "ok": False,
            "error": "RANGE_OUTSIDE_TAKE",
            "message": (
                f"Marked range [{mark_in:.3f}, {mark_out:.3f}) is outside "
                f"active take length {clip_len:.3f}s."
            ),
            "mock": False,
        }
    mark_in = max(0.0, mark_in)
    mark_out = min(clip_len, mark_out)
    expected = mark_out - mark_in

    abs_in = clip_start + mark_in
    abs_out = clip_start + mark_out
    abs_end = clip_start + clip_len

    rid = str(retake_id or "").strip() or None
    created = _now()
    base_meta: dict[str, Any] = {
        "sourceBatchId": source_batch_id,
        "sourceAssetId": orig_asset,
        "markIn": mark_in,
        "markOut": mark_out,
        "createdAt": created,
        "priorTrimStart": prior_trim,
    }
    if rid:
        base_meta["retakeId"] = rid
    if middle_extra_meta:
        for key, value in middle_extra_meta.items():
            if value is not None:
                base_meta[key] = value

    new_pieces: list[TimelineClip] = []
    # A: left remnant - keep original clip.id when present
    if mark_in > GEOMETRY_EPS:
        a_meta = dict(base_meta)
        a_meta["role"] = "original_a"
        keep_id = str(active.id)
        # Virtual reconstruct uses managed id; prefer real remnant id if present.
        if _clip_meta(active).get("role") == "virtual_original":
            keep_id = f"{MANAGED_DIRECTOR_CLIP_PREFIX}{source_batch_id}" if source_batch_id else keep_id
        new_pieces.append(
            TimelineClip(
                id=keep_id,
                asset_id=orig_asset,
                start=clip_start,
                length=mark_in,
                trim_start=prior_trim,
                label=active.label or "Original A",
                media_type="video",
                metadata=a_meta,
            )
        )
    # Middle
    m_meta = dict(base_meta)
    m_meta["role"] = middle_role
    new_pieces.append(
        TimelineClip(
            id=middle_clip_id,
            asset_id=mid_id,
            start=abs_in,
            length=expected,
            trim_start=0.0,
            label=middle_label,
            media_type=middle_media_type,
            metadata=m_meta,
        )
    )
    # B: right remnant - SAME original asset; trim_start = prior + markOut (Hop 6 law)
    if (abs_end - abs_out) > GEOMETRY_EPS:
        b_meta = dict(base_meta)
        b_meta["role"] = "original_b"
        new_pieces.append(
            TimelineClip(
                id=_nid("rtb_"),
                asset_id=orig_asset,
                start=abs_out,
                length=abs_end - abs_out,
                trim_start=prior_trim + mark_out,
                label=active.label or "Original B",
                media_type="video",
                metadata=b_meta,
            )
        )

    remove_ids = {str(active.id)}
    if source_batch_id:
        remove_ids.add(f"{MANAGED_DIRECTOR_CLIP_PREFIX}{source_batch_id}")
        for c in video_clips:
            if clip_belongs_to_range_batch(c, source_batch_id):
                remove_ids.add(str(c.id))
    kept: list[TimelineClip] = []
    for c in video_clips:
        cid = str(c.id or "")
        if cid in remove_ids:
            continue
        c0 = float(c.start or 0.0)
        c1 = c0 + float(c.length or 0.0)
        overlaps = c0 < abs_out - GEOMETRY_EPS and abs_in < c1 - GEOMETRY_EPS
        if overlaps and str(c.asset_id or "") == orig_asset:
            continue
        if overlaps and _is_middle_range_clip(c):
            continue
        kept.append(c)

    merged = kept + new_pieces
    merged.sort(key=lambda c: (float(c.start or 0.0), str(c.id)))
    director_tl.video_clips = merged
    director_tl.media_mode = "video"
    if merged:
        end = max(float(c.start or 0.0) + float(c.length or 0.0) for c in merged)
        director_tl.duration_sec = max(float(director_tl.duration_sec or 0.0), end)

    if source_batch_id and rid and middle_media_type == "video":
        batch = next((b for b in master.batchBlocks if b.id == source_batch_id), None)
        if batch:
            for repair in batch.repairRanges or []:
                if repair.id == rid or str((repair.metadata or {}).get("retakeId") or "") == rid:
                    meta = dict(repair.metadata or {})
                    meta.update(
                        {
                            "visualRangeReplacement": base_meta,
                            "retakeClipId": middle_clip_id,
                        }
                    )
                    repair.metadata = meta
                    repair.status = "applied"
                    break

    store.save_master(
        db,
        project_id,
        scene_id,
        master,
        director_tl=director_tl,
        bump_revision=True,
    )
    return {
        "ok": True,
        "clipIds": [c.id for c in new_pieces],
        "clips": [
            {
                "id": c.id,
                "asset_id": c.asset_id,
                "start": c.start,
                "length": c.length,
                "trim_start": c.trim_start,
                "media_type": c.media_type,
                "metadata": _clip_meta(c),
            }
            for c in new_pieces
        ],
        "markIn": mark_in,
        "markOut": mark_out,
        "middleAssetId": mid_id,
        "sourceAssetId": orig_asset,
        "retakeId": rid,
        "mediaType": middle_media_type,
        "mock": False,
    }


def replace_visual_range(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    mark_in: float,
    mark_out: float,
    replacement_asset_id: str,
    retake_id: str | None = None,
    source_batch_id: str | None = None,
    source_asset_id: str | None = None,
    replacement_duration: float | None = None,
    label: str | None = None,
    reference_image_asset_id: str | None = None,
) -> dict[str, Any]:
    """Split ACTIVE Visual take into A | Retake | B with correct trim_start.

    mark_in / mark_out are take-relative seconds on the active original take
    (same coordinate space as repairRanges / rangeReplacement.start+length).
    """
    mark_in = float(mark_in)
    mark_out = float(mark_out)
    if mark_out <= mark_in + GEOMETRY_EPS:
        return {
            "ok": False,
            "error": "INVALID_RANGE",
            "message": "markOut must be greater than markIn.",
            "mock": False,
        }
    expected = mark_out - mark_in
    repl_id = str(replacement_asset_id or "").strip()
    if not repl_id:
        return {
            "ok": False,
            "error": "REPLACEMENT_ASSET_REQUIRED",
            "message": "Range retake needs a replacement asset id.",
            "mock": False,
        }

    measured = (
        float(replacement_duration)
        if replacement_duration is not None
        else _probe_asset_duration(db, project_id, repl_id)
    )
    if measured is None:
        return {
            "ok": False,
            "error": "REPLACEMENT_DURATION_UNKNOWN",
            "message": "Could not read the replacement clip duration.",
            "mock": False,
        }
    if abs(float(measured) - expected) > DURATION_EPS:
        return {
            "ok": False,
            "error": "REPLACEMENT_DURATION_MISMATCH",
            "message": (
                f"Replacement duration {float(measured):.3f}s does not match "
                f"marked range {expected:.3f}s (epsilon {DURATION_EPS}s). "
                "Refusing to stretch."
            ),
            "expected": expected,
            "actual": float(measured),
            "mock": False,
        }

    rid = str(retake_id or "").strip() or _nid("rr_")
    retake_clip_id = f"{RETAKE_CLIP_PREFIX}{rid}"
    extra: dict[str, Any] = {
        "replacementAssetId": repl_id,
    }
    ref_img = str(reference_image_asset_id or "").strip()
    if ref_img:
        extra["referenceImageAssetId"] = ref_img

    out = _split_active_visual_range(
        db,
        project_id,
        scene_id,
        mark_in=mark_in,
        mark_out=mark_out,
        middle_asset_id=repl_id,
        middle_media_type="video",
        middle_clip_id=retake_clip_id,
        middle_role="retake",
        middle_label=label or "Retake",
        middle_extra_meta=extra,
        retake_id=rid,
        source_batch_id=source_batch_id,
        source_asset_id=source_asset_id,
    )
    if out.get("ok"):
        out["replacementAssetId"] = repl_id
        out["retakeId"] = rid
    return out


def place_visual_image_range(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    mark_in: float,
    mark_out: float,
    image_asset_id: str,
    placement_id: str | None = None,
    source_batch_id: str | None = None,
    source_asset_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Split ACTIVE Visual take into A | Image | B (still spans window; no duration fit)."""
    err = _require_image_asset(db, project_id, image_asset_id)
    if err is not None:
        return err

    img_id = str(image_asset_id).strip()
    pid = str(placement_id or "").strip() or _nid("img_")
    if pid.startswith(IMAGE_CLIP_PREFIX):
        middle_clip_id = pid
        bare_placement = pid[len(IMAGE_CLIP_PREFIX) :]
    else:
        bare_placement = pid
        middle_clip_id = f"{IMAGE_CLIP_PREFIX}{bare_placement}"

    # Prefer approved take asset when batch known and caller omitted source.
    if source_batch_id and not source_asset_id:
        bundle = store.load_master(db, project_id, scene_id)
        if bundle.get("ok"):
            master = SceneTimelineMaster.model_validate(bundle["master"])
            batch = next((b for b in master.batchBlocks if b.id == source_batch_id), None)
            if batch and batch.approvedClip and batch.approvedClip.assetId:
                source_asset_id = str(batch.approvedClip.assetId)

    out = _split_active_visual_range(
        db,
        project_id,
        scene_id,
        mark_in=mark_in,
        mark_out=mark_out,
        middle_asset_id=img_id,
        middle_media_type="image",
        middle_clip_id=middle_clip_id,
        middle_role="image_frame",
        middle_label=label or "Image Frame",
        middle_extra_meta={
            "referenceImageAssetId": img_id,
            "placementId": bare_placement,
        },
        retake_id=None,
        source_batch_id=source_batch_id,
        source_asset_id=source_asset_id,
    )
    if out.get("ok"):
        out["imageAssetId"] = img_id
        out["placementId"] = bare_placement
        out["referenceImageAssetId"] = img_id
    return out

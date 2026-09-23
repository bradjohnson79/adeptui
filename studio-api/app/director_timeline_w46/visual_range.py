"""Canonical Visual-track range replacement (A | Middle | B).

Library MP4 stitch (range_replacement.compose_range_media) is NOT Visual authority.
This module is the sole Visual write path for bounded range retakes and image-frame
placement. Video middle = rtclip_*; image middle = imgclip_*.

SINGLE-STORE: SceneTimelineMaster batch.visualClips is the sole Visual SoT.
Clips are batch-owned and batch-local (start is relative to the owning batch
window, matching playableVisualClipsFromMaster cursor math on the FE). The
retired legacy DirectorTimeline.video_clips array is never read or written
here (PUT /director is 410 Gone; save_master persists Master only).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from ..db import Asset
from ..media_clip import probe_video_duration
from . import store
from .contracts import BatchClip, SceneTimelineMaster, _now
from .scene_stitch import resolve_asset_file

DURATION_EPS = 0.05
GEOMETRY_EPS = 0.05
MANAGED_DIRECTOR_CLIP_PREFIX = "bbclip_"
MANAGED_BATCH_VISUAL_PREFIX = "bbvclip_"
RETAKE_CLIP_PREFIX = "rtclip_"
IMAGE_CLIP_PREFIX = "imgclip_"
B_REMNANT_PREFIX = "rtb_"
MiddleMediaType = Literal["video", "image"]


def _nid(prefix: str = "clip_") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _clip_meta(clip: Any) -> dict[str, Any]:
    raw = getattr(clip, "metadata", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _clip_asset_id(clip: Any) -> str:
    return str(getattr(clip, "assetId", None) or getattr(clip, "asset_id", None) or "").strip()


def _clip_trim(clip: Any) -> float:
    raw = getattr(clip, "trimStart", None)
    if raw is None:
        raw = getattr(clip, "trim_start", 0.0)
    return float(raw or 0.0)


def _clip_start(clip: Any) -> float:
    return float(getattr(clip, "start", 0.0) or 0.0)


def _clip_length(clip: Any) -> float:
    return float(getattr(clip, "length", 0.0) or 0.0)


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


def clip_belongs_to_range_batch(clip: Any, batch_id: str) -> bool:
    """True when the clip is part of the batch's Visual take composition
    (managed whole take, A/B remnants, rtclip_/imgclip_ middles)."""
    cid = str(getattr(clip, "id", "") or "")
    if cid in {
        f"{MANAGED_DIRECTOR_CLIP_PREFIX}{batch_id}",
        f"{MANAGED_BATCH_VISUAL_PREFIX}{batch_id}",
    }:
        return True
    meta = _clip_meta(clip)
    if str(meta.get("sourceBatchId") or "") != str(batch_id):
        return False
    if cid.startswith((RETAKE_CLIP_PREFIX, IMAGE_CLIP_PREFIX, B_REMNANT_PREFIX)):
        return True
    return str(meta.get("role") or "") in {
        "original_a",
        "original_b",
        "retake",
        "image_frame",
        "virtual_original",
    }


def range_retake_batch_ids(master: Any) -> set[str]:
    """Batch ids that already have a Visual A|Middle|B composition on Master
    (rtclip_* / imgclip_* / original_* pieces in batch.visualClips)."""
    found: set[str] = set()
    for batch in getattr(master, "batchBlocks", None) or []:
        batch_id = str(getattr(batch, "id", "") or "")
        if not batch_id:
            continue
        for clip in getattr(batch, "visualClips", None) or []:
            cid = str(getattr(clip, "id", "") or "")
            meta = _clip_meta(clip)
            if cid.startswith(RETAKE_CLIP_PREFIX) or cid.startswith(IMAGE_CLIP_PREFIX):
                found.add(batch_id)
            elif str(meta.get("role") or "") in {"retake", "image_frame", "original_a", "original_b"}:
                found.add(batch_id)
            elif meta.get("replacementAssetId"):
                found.add(batch_id)
    return found


def find_image_frame_asset_in_range(
    clips: list[Any] | None,
    *,
    mark_in: float,
    mark_out: float,
    source_batch_id: str | None = None,
) -> str | None:
    """Return referenceImageAssetId / assetId for an imgclip overlapping the marked window.

    Reads a batch-owned Master visualClips list (batch-local == take-relative
    coordinates for the take composition). metadata.markIn/markOut win over
    raw clip geometry when present.
    """
    mark_in = float(mark_in)
    mark_out = float(mark_out)
    for clip in clips or []:
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
                return str(meta.get("referenceImageAssetId") or _clip_asset_id(clip) or "").strip() or None
        c0 = _clip_start(clip)
        c1 = c0 + _clip_length(clip)
        if c0 < mark_out - GEOMETRY_EPS and mark_in < c1 - GEOMETRY_EPS:
            return str(meta.get("referenceImageAssetId") or _clip_asset_id(clip) or "").strip() or None
    return None


def _batch_playable_take(master: Any, batch: Any) -> tuple[str, float] | None:
    """Whole-take playable (assetId, length) for a batch with no managed
    composition. Mirrors completion._playable_take_for_batch precedence:
    current scene-take membership wins, then approvedClip, then latest
    candidate. Fail-closed when a current take exists but has no member asset
    for this batch."""
    current_take = next(
        (
            t
            for t in (getattr(master, "sceneTakes", None) or [])
            if t.id == getattr(master, "currentSceneTakeId", None)
        ),
        None,
    )
    preferred: str | None = None
    if current_take is not None:
        member = next(
            (
                m
                for m in (getattr(current_take, "batches", None) or [])
                if str(getattr(m, "batchId", "") or "") == str(getattr(batch, "id", "") or "")
            ),
            None,
        )
        preferred = str(getattr(member, "assetId", "") or "").strip() if member is not None else ""
        if not preferred:
            return None
    approved = getattr(batch, "approvedClip", None)
    approved_id = str(getattr(approved, "assetId", None) or "").strip() or None
    cands = [c for c in (getattr(batch, "candidateVersions", None) or []) if getattr(c, "assetId", None)]
    latest = (
        max(cands, key=lambda c: (str(getattr(c, "createdAt", None) or ""), str(getattr(c, "id", None) or "")))
        if cands
        else None
    )
    duration_hint = getattr(latest, "generatedDuration", None) if latest else None
    if preferred:
        asset_id = preferred
    elif approved_id:
        asset_id = approved_id
    elif latest is not None:
        asset_id = str(latest.assetId)
    else:
        return None
    dur = getattr(batch, "duration", None)
    length = float(
        getattr(dur, "timelineVisibleDuration", None)
        or getattr(dur, "generatedDuration", None)
        or duration_hint
        or getattr(dur, "plannedDuration", None)
        or 5.0
    )
    return asset_id, max(0.1, length)


def _resolve_master_active_take(
    master: Any,
    batch: Any,
    *,
    source_asset_id: str | None = None,
) -> dict[str, Any] | None:
    """Active Visual take for the batch from Master batch.visualClips.

    Returns {assetId, start, length, priorTrim, composition} with batch-local
    coordinates, or None when no playable take exists. A prior A|Middle|B
    composition is reconstructed into a virtual whole take so mark_in/out stay
    take-relative.
    """
    batch_id = str(getattr(batch, "id", "") or "")
    comp = [c for c in list(getattr(batch, "visualClips", None) or []) if clip_belongs_to_range_batch(c, batch_id)]
    managed_id = f"{MANAGED_BATCH_VISUAL_PREFIX}{batch_id}"
    managed = next((c for c in comp if str(getattr(c, "id", "") or "") == managed_id), None)
    a = next((c for c in comp if str(_clip_meta(c).get("role") or "") == "original_a"), None)
    b_piece = next((c for c in comp if str(_clip_meta(c).get("role") or "") == "original_b"), None)
    middle = next((c for c in comp if _is_middle_range_clip(c)), None)

    if managed is not None and middle is None and b_piece is None:
        asset = _clip_asset_id(managed) or str(source_asset_id or "")
        if not asset:
            return None
        return {
            "assetId": asset,
            "start": _clip_start(managed),
            "length": _clip_length(managed),
            "priorTrim": _clip_trim(managed),
            "composition": comp,
        }

    if comp and (middle is not None or a is not None):
        pieces = sorted(comp, key=lambda c: (_clip_start(c), str(getattr(c, "id", "") or "")))
        v_start = _clip_start(a or pieces[0])
        v_end = max(_clip_start(c) + _clip_length(c) for c in pieces)
        prior = _clip_trim(a) if a is not None else 0.0
        if a is None and middle is not None:
            # No A: middle begins at markIn; recover take start and prior from metadata.
            m_meta = _clip_meta(middle)
            mi = float(m_meta.get("markIn") or 0.0)
            v_start = _clip_start(middle) - mi
            prior = max(0.0, float(m_meta.get("priorTrimStart") or 0.0))
            v_end = max(v_end, v_start + float(m_meta.get("markOut") or 0.0))
            if b_piece is not None:
                v_end = max(v_end, _clip_start(b_piece) + _clip_length(b_piece))
        v_len = v_end - v_start
        if v_len <= GEOMETRY_EPS:
            return None
        orig = (
            str(source_asset_id or "").strip()
            or _clip_asset_id(a)
            or _clip_asset_id(b_piece)
            or str(_clip_meta(middle or pieces[0]).get("sourceAssetId") or "").strip()
        )
        if not orig:
            return None
        return {
            "assetId": orig,
            "start": v_start,
            "length": v_len,
            "priorTrim": prior,
            "composition": comp,
        }

    take = _batch_playable_take(master, batch)
    if take is None:
        return None
    asset, length = take
    if source_asset_id and str(asset) != str(source_asset_id):
        return None
    return {
        "assetId": str(asset),
        "start": 0.0,
        "length": float(length),
        "priorTrim": 0.0,
        "composition": [],
    }


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
    """Shared A | Middle | B geometry writer on Master batch.visualClips.

    mark_in / mark_out are take-relative seconds on the active original take
    (same coordinate space as repairRanges / rangeReplacement.start+length).
    The take spans the owning batch window, so take-relative == batch-local.
    Caller validates middle asset rules.
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

    # Resolve the owning batch (batch-owned clips: the split never touches
    # another batch's visualClips).
    batch = None
    if source_batch_id:
        batch = next((b for b in master.batchBlocks if str(b.id) == str(source_batch_id)), None)
    else:
        matches = []
        for candidate in master.batchBlocks:
            take = _batch_playable_take(master, candidate)
            if take and source_asset_id and str(take[0]) == str(source_asset_id):
                matches.append(candidate)
        if not matches and len(master.batchBlocks) == 1:
            matches = list(master.batchBlocks)
        batch = matches[0] if matches else None
    if batch is None:
        return {
            "ok": False,
            "error": "ACTIVE_VISUAL_TAKE_NOT_FOUND",
            "message": "No active Visual take spans the marked range.",
            "mock": False,
        }

    active = _resolve_master_active_take(master, batch, source_asset_id=source_asset_id)
    if active is None or not active.get("assetId"):
        return {
            "ok": False,
            "error": "ACTIVE_VISUAL_TAKE_NOT_FOUND",
            "message": "No active Visual take spans the marked range.",
            "mock": False,
        }

    orig_asset = str(active["assetId"])
    clip_start = float(active["start"] or 0.0)
    clip_len = float(active["length"] or 0.0)
    prior_trim = float(active["priorTrim"] or 0.0)
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
        "sourceBatchId": str(batch.id),
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

    managed_id = f"{MANAGED_BATCH_VISUAL_PREFIX}{batch.id}"
    take_label = str(getattr(batch, "label", "") or "") or "Take"
    new_pieces: list[BatchClip] = []
    # A: left remnant — keeps the managed whole-take id so the batch's managed
    # identity survives the split (place_approved_batches_on_timeline will not
    # overwrite an active range composition).
    if mark_in > GEOMETRY_EPS:
        a_meta = dict(base_meta)
        a_meta["role"] = "original_a"
        new_pieces.append(
            BatchClip(
                id=managed_id,
                kind="video",
                assetId=orig_asset,
                start=clip_start,
                length=mark_in,
                trimStart=prior_trim,
                label=take_label,
                metadata=a_meta,
            )
        )
    # Middle
    m_meta = dict(base_meta)
    m_meta["role"] = middle_role
    new_pieces.append(
        BatchClip(
            id=middle_clip_id,
            kind="video" if middle_media_type == "video" else "image",
            assetId=mid_id,
            start=abs_in,
            length=expected,
            trimStart=0.0,
            label=middle_label,
            metadata=m_meta,
        )
    )
    # B: right remnant - SAME original asset; trimStart = prior + markOut (Hop 6 law)
    if (abs_end - abs_out) > GEOMETRY_EPS:
        b_meta = dict(base_meta)
        b_meta["role"] = "original_b"
        new_pieces.append(
            BatchClip(
                id=_nid(B_REMNANT_PREFIX),
                kind="video",
                assetId=orig_asset,
                start=abs_out,
                length=abs_end - abs_out,
                trimStart=prior_trim + mark_out,
                label=take_label,
                metadata=b_meta,
            )
        )

    composition = list(active.get("composition") or [])
    kept = [c for c in list(getattr(batch, "visualClips", None) or []) if c not in composition]
    merged = kept + new_pieces
    merged.sort(key=lambda c: (_clip_start(c), str(getattr(c, "id", "") or "")))
    batch.visualClips = merged

    if rid and middle_media_type == "video":
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
        bump_revision=True,
    )
    return {
        "ok": True,
        "batchId": str(batch.id),
        "clipIds": [c.id for c in new_pieces],
        "clips": [
            {
                "id": c.id,
                "asset_id": c.assetId,
                "start": c.start,
                "length": c.length,
                "trim_start": c.trimStart,
                "media_type": middle_media_type if c.id == middle_clip_id else "video",
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
    """Split ACTIVE Visual take into A | Retake | B with correct trimStart.

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

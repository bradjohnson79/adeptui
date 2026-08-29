"""Reconcile the legacy DirectorTimeline NLE view with the Timeline Master.

Single canonical truth (Timeline certification Phase 2):
  scenes.director_json.timelineMaster (BatchBlocks) is the production state.
The legacy director_json tracks (prompt_segments, image_clips, ...) are the
interactive NLE view and the flattened output view (BATCH_OWNED_CLIPS design:
"legacy scene-global tracks remain as a derived/flattened view").

Directions:
  legacy -> master  (put_director / Co-Director store.save_master with director_tl)
      legacy prompt_segments -> batch.promptSegments   (upsert by
          legacyPromptSegmentId, then by window-proximity; deletion propagates)
      legacy image_clips     -> batch.sourceAnchors    (managed anchors labeled
          "legacy:<clipId>"; user anchors labeled Start/End/etc. are never
          touched; stale managed anchors are removed)
  master -> legacy  (orchestrator.touch_batch_config when promptSegments change)
      batch.promptSegments -> flattened legacy prompt_segments projection

Value-stable invariant: reconciling already-consistent state mutates nothing,
so configFingerprint and staged ExecutionSnapshots never churn, and the
reconciliation is idempotent (safe on every save).
"""

from __future__ import annotations

from typing import Any

from .contracts import BatchBlock, BatchClip, SceneTimelineMaster, TimelinePromptSegment, TimelineVisualAnchor

# Labels that identify reconcile-managed anchors. User-configured anchors
# (Batch Inspector "Start"/"End" select) are never deleted by reconciliation.
_MANAGED_ANCHOR_PREFIX = "legacy:"
# Migration-created anchors carry plain role labels; they are adopted as
# managed when they match a legacy image clip exactly (asset + position).
_ADOPTABLE_ANCHOR_LABELS = frozenset({"", "start", "middle", "end", "guide"})


def batch_time_windows(master: SceneTimelineMaster) -> list[tuple[BatchBlock, float, float]]:
    """[(batch, window_start, window_end)] ordered by batch.order.

    Mirrors resolveBatchAtTime (frontend) — cumulative plannedDuration is the
    canonical scene timebase. The same math must never drift between preview
    and generation (TIMELINE_DURATION_DETERMINISM).
    """
    out: list[tuple[BatchBlock, float, float]] = []
    cursor = 0.0
    for batch in sorted(master.batchBlocks, key=lambda b: b.order):
        length = max(0.1, float(batch.duration.plannedDuration or 0.0))
        out.append((batch, cursor, cursor + length))
        cursor += length
    return out


def _midpoint(start: float, length: float) -> float:
    return float(start) + float(length) / 2.0


def _in_window(start: float, length: float, win_start: float, win_end: float) -> bool:
    mid = _midpoint(start, length)
    return win_start - 1e-6 <= mid < win_end + 1e-6


def _find_batch_segment(batch: BatchBlock, legacy_id: str, start: float, length: float):
    """Match a legacy prompt segment to an existing batch segment.

    Priority: explicit legacyPromptSegmentId, then window-proximity
    (start/length within 10ms), then a unique unmanaged batch segment
    (migration leftover without legacyPromptSegmentId). Adopting that
    leftover is the stale-prompt fix: Inspector PUT updates generation input
    instead of appending a second segment beside the migrated stub.
    """
    for seg in batch.promptSegments:
        if seg.legacyPromptSegmentId and seg.legacyPromptSegmentId == legacy_id:
            return seg
    for seg in batch.promptSegments:
        if seg.legacyPromptSegmentId:
            continue
        if abs(float(seg.start) - float(start)) < 0.01 and abs(float(seg.length) - float(length)) < 0.01:
            return seg
    unmanaged = [s for s in batch.promptSegments if not s.legacyPromptSegmentId]
    if len(unmanaged) == 1:
        return unmanaged[0]
    return None


def reconcile_legacy_prompts(master: SceneTimelineMaster, legacy_segments: list[Any]) -> bool:
    """Sync legacy prompt_segments into batch.promptSegments. Returns changed."""
    if not master.batchBlocks:
        return False
    windows = batch_time_windows(master)
    changed = False
    for batch, w_start, w_end in windows:
        window_segs = [s for s in legacy_segments if _in_window(float(s.start), float(s.length), w_start, w_end)]
        window_ids = {str(s.id) for s in window_segs}
        for seg in window_segs:
            start = max(0.0, round(float(seg.start) - w_start, 6))
            length = round(float(seg.length), 6)
            match = _find_batch_segment(batch, str(seg.id), start, length)
            text = seg.text or ""
            if match is None:
                batch.promptSegments.append(
                    TimelinePromptSegment(
                        legacyPromptSegmentId=str(seg.id),
                        start=start,
                        length=length,
                        text=text,
                        role="primary",
                        strength=float(seg.weight or 1.0),
                        temperature=float(getattr(seg, "temperature", 1.0) or 1.0),
                        negativePrompt=seg.negative_prompt,
                        referenceBindingIds=list(seg.reference_binding_ids or []),
                        userDirection=seg.user_direction or (text or None),
                        productionPrompt=seg.production_prompt,
                        dialogue=seg.dialogue,
                        movementSegmentRef=getattr(seg, "movement_segment_ref", None),
                        movementSegmentRevision=getattr(seg, "movement_segment_revision", None),
                    )
                )
                changed = True
                continue
            old_text = match.text
            new_text = text
            if match.legacyPromptSegmentId != str(seg.id):
                match.legacyPromptSegmentId = str(seg.id)
                changed = True
            if match.text != new_text:
                match.text = new_text
                changed = True
            if abs(match.start - start) > 1e-6:
                match.start = start
                changed = True
            if abs(match.length - length) > 1e-6:
                match.length = length
                changed = True
            new_strength = float(getattr(seg, "weight", None) or match.strength or 1.0)
            if abs(float(match.strength or 1.0) - new_strength) > 1e-6:
                match.strength = new_strength
                changed = True
            if seg.negative_prompt is not None and match.negativePrompt != seg.negative_prompt:
                match.negativePrompt = seg.negative_prompt
                changed = True
            # USER DIRECTION is authored intent, stored separately from the
            # refined production prompt. Mirror only while it equals the OLD
            # text (same author editing); never overwrite a refined value.
            if match.userDirection in (None, ""):
                match.userDirection = seg.user_direction or (new_text or None)
                changed = True
            elif match.userDirection == old_text and new_text != old_text:
                match.userDirection = new_text
                changed = True
            if seg.production_prompt is not None and match.productionPrompt != seg.production_prompt:
                match.productionPrompt = seg.production_prompt
                changed = True
            if seg.dialogue is not None and match.dialogue != seg.dialogue:
                match.dialogue = seg.dialogue
                changed = True
            new_temp = float(getattr(seg, "temperature", 1.0) or 1.0)
            if abs(float(getattr(match, "temperature", 1.0) or 1.0) - new_temp) > 1e-6:
                match.temperature = new_temp
                changed = True
            legacy_ref = getattr(seg, "movement_segment_ref", None)
            if match.movementSegmentRef != legacy_ref:
                match.movementSegmentRef = legacy_ref
                changed = True
            legacy_rev = getattr(seg, "movement_segment_revision", None)
            if match.movementSegmentRevision != legacy_rev:
                match.movementSegmentRevision = legacy_rev
                changed = True
        # Deletion propagation: legacy-managed batch segments whose legacy
        # segment is gone from this batch's window are removed. Segments
        # created on the batch side (no legacyPromptSegmentId) are kept.
        keep = [s for s in batch.promptSegments if not (s.legacyPromptSegmentId and s.legacyPromptSegmentId not in window_ids)]
        if len(keep) != len(batch.promptSegments):
            batch.promptSegments = keep
            changed = True
    return changed


def reconcile_legacy_image_anchors(master: SceneTimelineMaster, legacy_image_clips: list[Any]) -> bool:
    """Sync legacy image_clips into batch.sourceAnchors as managed anchors.

    User-configured anchors (Batch Inspector Start/End) are never deleted or
    relabeled. Managed anchors are labeled "legacy:<clipId>" and removed when
    their clip disappears — no stale start image can survive a lane replace
    (SOURCE_IMAGE_BINDING: no implicit fallback to another image).
    """
    if not master.batchBlocks:
        return False
    windows = batch_time_windows(master)
    clip_ids = {str(c.id) for c in legacy_image_clips}
    changed = False
    for batch, w_start, w_end in windows:
        window_clips = [c for c in legacy_image_clips if _in_window(float(c.start), float(c.length), w_start, w_end)]
        window_clip_ids = {str(c.id) for c in window_clips}
        for clip in window_clips:
            asset_id = clip.asset_id
            if not asset_id:
                continue
            at_time = max(0.0, round(float(clip.start) - w_start, 6))
            label = f"{_MANAGED_ANCHOR_PREFIX}{clip.id}"
            existing = next((a for a in batch.sourceAnchors if a.label == label), None)
            if existing is None:
                existing = next(
                    (
                        a
                        for a in batch.sourceAnchors
                        if a.kind == "image"
                        and a.assetId == asset_id
                        and (a.label or "").lower() in _ADOPTABLE_ANCHOR_LABELS
                        and abs(float(a.atTime or 0.0) - at_time) < 0.01
                    ),
                    None,
                )
            if existing is None:
                batch.sourceAnchors.append(
                    TimelineVisualAnchor(
                        kind="image",
                        assetId=asset_id,
                        label=label,
                        atTime=at_time,
                        strength=1.0,
                    )
                )
                changed = True
            else:
                if existing.label != label:
                    existing.label = label
                    changed = True
                if existing.assetId != asset_id:
                    existing.assetId = asset_id
                    changed = True
                if abs(float(existing.atTime or 0.0) - at_time) > 1e-6:
                    existing.atTime = at_time
                    changed = True
        keep = []
        for a in batch.sourceAnchors:
            if a.label and a.label.startswith(_MANAGED_ANCHOR_PREFIX):
                clip_id = a.label[len(_MANAGED_ANCHOR_PREFIX):]
                if clip_id not in clip_ids or clip_id not in window_clip_ids:
                    changed = True
                    continue
            keep.append(a)
        if len(keep) != len(batch.sourceAnchors):
            batch.sourceAnchors = keep
    return changed



def _camera_optics(clip: Any) -> dict[str, Any]:
    return {
        "shot_id": getattr(clip, "shot_id", None),
        "lens_id": getattr(clip, "lens_id", None),
        "focus_id": getattr(clip, "focus_id", None),
        "focus_name": getattr(clip, "focus_name", None),
        "lighting_id": getattr(clip, "lighting_id", None),
        "text": getattr(clip, "text", None) or "",
        "motion_type": getattr(clip, "motion_type", None),
        "motion_id": getattr(clip, "motion_id", None),
        "rig": getattr(clip, "rig", None),
        "speed": getattr(clip, "speed", None),
        "distance": getattr(clip, "distance", None),
        "ease": getattr(clip, "ease", None),
        "shake": getattr(clip, "shake", None),
        "intensity": getattr(clip, "intensity", None),
        "subject_lock": getattr(clip, "subject_lock", None),
    }


def _find_batch_camera(batch: BatchBlock, legacy_id: str, start: float, length: float):
    for clip in batch.cameraInstructions:
        if clip.legacyClipId and clip.legacyClipId == legacy_id:
            return clip
    for clip in batch.cameraInstructions:
        if clip.legacyClipId:
            continue
        if abs(float(clip.start) - float(start)) < 0.01 and abs(float(clip.length) - float(length)) < 0.01:
            return clip
    return None


def reconcile_legacy_cameras(master: SceneTimelineMaster, legacy_camera_clips: list[Any]) -> bool:
    """Sync legacy camera_clips into batch.cameraInstructions. Returns changed."""
    if not master.batchBlocks:
        return False
    windows = batch_time_windows(master)
    changed = False
    for batch, w_start, w_end in windows:
        window_clips = [
            c for c in legacy_camera_clips if _in_window(float(c.start), float(c.length), w_start, w_end)
        ]
        window_ids = {str(c.id) for c in window_clips}
        for clip in window_clips:
            start = max(0.0, round(float(clip.start) - w_start, 6))
            length = round(float(clip.length), 6)
            optics = _camera_optics(clip)
            match = _find_batch_camera(batch, str(clip.id), start, length)
            if match is None:
                batch.cameraInstructions.append(
                    BatchClip(
                        kind="camera",
                        legacyClipId=str(clip.id),
                        start=start,
                        length=length,
                        label=getattr(clip, "label", None) or "",
                        **optics,
                    )
                )
                changed = True
                continue
            if abs(match.start - start) > 1e-6:
                match.start = start
                changed = True
            if abs(match.length - length) > 1e-6:
                match.length = length
                changed = True
            for key, value in optics.items():
                if getattr(match, key, None) != value:
                    setattr(match, key, value)
                    changed = True
        keep = [
            c
            for c in batch.cameraInstructions
            if not (c.legacyClipId and c.legacyClipId not in window_ids)
        ]
        if len(keep) != len(batch.cameraInstructions):
            batch.cameraInstructions = keep
            changed = True
    return changed


def reconcile_legacy_to_master(master: SceneTimelineMaster, director_tl: Any) -> bool:
    """Reconcile the legacy NLE view into the master. Returns changed."""
    if not master.batchBlocks:
        return False
    changed = reconcile_legacy_prompts(master, list(director_tl.prompt_segments or []))
    changed = reconcile_legacy_image_anchors(master, list(director_tl.image_clips or [])) or changed
    changed = reconcile_legacy_cameras(master, list(getattr(director_tl, "camera_clips", None) or [])) or changed
    return changed


def invalidate_stale_compiled_payloads(master: SceneTimelineMaster) -> None:
    """Bust compiled prompt caches when reconciled Inspector fields change.

    Completed snapshots stay immutable provenance. Do not change Queued/Ready
    status or pendingSnapshotId — sequential chain ownership stays intact.
    """
    live_ids: set[str] = set()
    for batch in master.batchBlocks:
        if batch.status not in ("Draft", "Ready", "Queued"):
            continue
        for job in batch.generationJobs or []:
            sid = getattr(job, "executionSnapshotId", None)
            if sid:
                live_ids.add(str(sid))
    for snap_id, snap in master.executionSnapshots.items():
        if snap_id in live_ids:
            snap.compiledPrompts = {}


def project_prompts_to_legacy(master: SceneTimelineMaster) -> list[dict[str, Any]]:
    """Flatten batch.promptSegments into legacy prompt_segments dicts.

    The legacy prompt track is the derived NLE view of the canonical master.
    Called when the master prompt side is edited (Batch Inspector) so the
    visible lane and the generation input never diverge.
    """
    out: list[dict[str, Any]] = []
    for batch, w_start, _w_end in batch_time_windows(master):
        for seg in batch.promptSegments:
            seg_id = seg.legacyPromptSegmentId or (
                str(seg.id) if str(seg.id).startswith("ps_") else f"ps_{seg.id}"
            )
            out.append(
                {
                    "id": seg_id,
                    "start": round(w_start + float(seg.start), 6),
                    "length": round(float(seg.length), 6),
                    "text": seg.text or "",
                    "weight": float(seg.strength or 1.0),
                    "temperature": float(getattr(seg, "temperature", 1.0) or 1.0),
                    "negative_prompt": seg.negativePrompt,
                    "reference_binding_ids": list(seg.referenceBindingIds or []),
                    "user_direction": seg.userDirection,
                    "production_prompt": seg.productionPrompt,
                    "dialogue": seg.dialogue,
                    "movement_segment_ref": seg.movementSegmentRef,
                    "movement_segment_revision": seg.movementSegmentRevision,
                }
            )
    return out

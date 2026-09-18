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
      legacy image_clips     -> batch.sourceAnchors    (Wave 3A bleed-control:
          do NOT silently inject Visual images as managed sourceAnchors;
          only remove stale managed "legacy:<clipId>" anchors; user Start/End
          anchors are never touched — prefer explicit selection / References)
  master -> legacy  (orchestrator.touch_batch_config when promptSegments change)
      batch.promptSegments -> flattened legacy prompt_segments projection

Value-stable invariant: reconciling already-consistent state mutates nothing,
so configFingerprint and staged ExecutionSnapshots never churn, and the
reconciliation is idempotent (safe on every save).
"""

from __future__ import annotations

from typing import Any

from ..director_timeline_bindings import dump_prompt_name_bindings, parse_prompt_name_bindings
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


def _in_window(start: float, length: float, win_start: float, win_end: float) -> bool:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Window ownership =
    # START CONTAINMENT (12B model). Changing to midpoint/overlap matching
    # duplicates the scene-level Timed Prompt into extension batches and
    # re-creates the Take P "15-second scene twice" regression.
    # Fences: tests/test_timeline_architecture_guard.py · Authority: owner only
    # Charter: docs/release-gate/timeline/TIMELINE_BATCH_ARCHITECTURE_PROTECTION_CHARTER.md
    """Window membership for prompt segments (Take P root cause fix).

    Ownership test: a segment belongs to the window that CONTAINS ITS START —
    never its midpoint and never mere span overlap. The scene-level Timed
    Prompt (start 0, length 30) has its midpoint exactly on the B1/B2 boundary
    (15.0); the old inclusive midpoint test matched it into BOTH windows, so
    B2 received its own copy of the full-scene segment, `_is_extension_batch`
    saw non-empty segments and skipped continuation framing, and B2 shipped
    `Seconds: 0-30` verbatim — the "15-second scene twice" regression. Span
    overlap has the same defect (a whole-scene segment overlaps every window).

    Start containment with a half-open window [win_start, win_end): a segment
    starting exactly at a boundary belongs to the later batch. The whole-scene
    segment (start 0) is owned by the root window only; later windows stay
    inherit-render-windows and get continuation framing at runtime (12B model).
    """
    seg_start = float(start)
    return win_start - 1e-6 <= seg_start < win_end - 1e-6


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
                        referenceNameBindings=parse_prompt_name_bindings(
                            getattr(seg, "reference_name_bindings", None)
                        ),
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
                # Creator edited the visible Timed Prompt. A stale Co-Director
                # refinement must not silently win the next generation unless
                # this write also supplies a new production_prompt.
                incoming_prod = getattr(seg, "production_prompt", None)
                if (
                    incoming_prod
                    and incoming_prod != new_text
                    and incoming_prod != match.productionPrompt
                ):
                    match.productionPrompt = incoming_prod
                    changed = True
                elif match.productionPrompt and match.productionPrompt != new_text:
                    # Author Timed Prompt is the creative object. A stale
                    # Co-Director refinement must not silently win generation
                    # when this write does not supply a new production_prompt.
                    match.productionPrompt = incoming_prod
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
            new_ids = list(seg.reference_binding_ids or [])
            if list(match.referenceBindingIds or []) != new_ids:
                match.referenceBindingIds = new_ids
                changed = True
            incoming_names = parse_prompt_name_bindings(
                getattr(seg, "reference_name_bindings", None)
            )
            if dump_prompt_name_bindings(match.referenceNameBindings) != dump_prompt_name_bindings(
                incoming_names
            ):
                match.referenceNameBindings = incoming_names
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
    """Bleed-control for Visual image_clips vs batch.sourceAnchors (Wave 3A).

    Owner law: Visual images are references — do NOT silently inject them as
    generation sourceAnchors. Prefer explicit selection (Batch Inspector
    Start/End, Timed Prompt / Direct Reference, sceneReferences).

    Behavior:
      - Never create new managed "legacy:<clipId>" anchors from image_clips.
      - Still remove stale managed legacy anchors when their clip disappears
        (hygiene; no leftover silent injects).
      - User-configured anchors (Start/End/etc.) are never deleted or relabeled.
    """
    if not master.batchBlocks:
        return False
    windows = batch_time_windows(master)
    clip_ids = {str(c.id) for c in legacy_image_clips}
    changed = False
    for batch, w_start, w_end in windows:
        window_clips = [
            c
            for c in legacy_image_clips
            if _in_window(float(c.start), float(c.length), w_start, w_end)
        ]
        window_clip_ids = {str(c.id) for c in window_clips}
        # Wave 3A: no silent inject / adopt of Visual images into sourceAnchors.
        _ = (w_start, w_end, window_clips)  # windows still define stale scope
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
    """Sync legacy camera_clips into batch.cameraInstructions. Returns changed.

    Phase 0 (Timed Prompt sole camera authority): FROZEN no-op by default so
    dual authority cannot re-seed cameraInstructions mid-flight after the
    creator CAMERA lane is unmounted. Legacy camera_clips remain in schema.
    Set ADEPT_RECONCILE_LEGACY_CAMERAS=1 to re-enable (debug only).
    """
    import os

    if os.environ.get("ADEPT_RECONCILE_LEGACY_CAMERAS", "0") != "1":
        return False
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


def _scene_duration(master: SceneTimelineMaster) -> float:
    return sum(max(0.0, float(getattr(batch.duration, "plannedDuration", 0) or 0.0)) for batch in (master.batchBlocks or []))


def _is_render_window_batch(batch: BatchBlock) -> bool:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Render-window = no
    # own prompt text + CD production batch index > 0. Batch index ALONE must
    # never skip projection (Take N: hid Batch 2's prompt lane, invented
    # dialogue). Fences: tests/test_timeline_architecture_guard.py
    """Batch with no own prompt that inherits the scene-level Timed Prompt.

    12B working-Timeline model: every batch OWNS its window prompt; a batch is
    only a "render window" when it has no own segment text to project. CD
    batch index alone must not skip projection — that hid Batch 2's prompt
    from the visible lane and broke dialogue allocation (Take N regression).
    """
    if any(str(getattr(seg, "text", "") or "").strip() for seg in (batch.promptSegments or [])):
        return False
    meta = getattr(batch, "migrationMetadata", None) or {}
    if not meta.get("codirectorSceneProduction"):
        return False
    try:
        return int(meta.get("sourceProductionBatchIndex") or 0) > 0
    except (TypeError, ValueError):
        return False


def has_scene_level_timed_prompt(master: SceneTimelineMaster) -> bool:
    """True when one Timed Prompt covers the full scene duration."""
    scene_dur = _scene_duration(master)
    if scene_dur <= 0:
        return False
    for batch in master.batchBlocks or []:
        for seg in batch.promptSegments or []:
            if str(getattr(seg, "text", "") or "").strip() and float(getattr(seg, "length", 0) or 0) >= scene_dur - 0.05:
                return True
    return False


def batch_inherits_scene_timed_prompt(master: SceneTimelineMaster, batch: BatchBlock) -> bool:
    """Empty later batches are extensions of the one scene Timed Prompt."""
    if any(str(getattr(seg, "text", "") or "").strip() for seg in (batch.promptSegments or [])):
        return False
    if not has_scene_level_timed_prompt(master):
        return False
    if _is_render_window_batch(batch):
        return True
    try:
        return int(getattr(batch, "order", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def persist_prompt_projection_to_scene(
    db: Any,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
) -> None:
    """Write the scene Timed Prompt projection (including spoken dialogue) to director_json."""
    from ..director_timeline import (
        PromptSegment as LegacyPromptSegment,
        dumps_director_timeline_preserving_embedded,
        parse_director_timeline,
    )
    from .store import get_scene

    scene_row = get_scene(db, project_id, scene_id)
    if scene_row is None:
        return
    tl = parse_director_timeline(
        scene_row.director_json,
        fallback_duration=float(scene_row.duration_sec or 5.0),
        fallback_prompt=scene_row.prompt or "",
    )
    projected = project_prompts_to_legacy(master)
    segment_type = type(tl.prompt_segments[0]) if tl.prompt_segments else LegacyPromptSegment
    tl.prompt_segments = [segment_type(**seg) for seg in projected] if projected else []
    scene_row.director_json = dumps_director_timeline_preserving_embedded(tl, scene_row.director_json)
    db.add(scene_row)



def project_prompts_to_legacy(master: SceneTimelineMaster) -> list[dict[str, Any]]:
    """Flatten batch.promptSegments into legacy prompt_segments dicts.

    The legacy prompt track is the derived NLE view of the canonical master.
    Called when the master prompt side is edited (Batch Inspector) so the
    visible lane and the generation input never diverge.

    12B working-Timeline shape: EVERY batch's own segments project into the
    visible Timed Prompt lane at their batch window (batch-local start +
    window offset) — 12B shows 0-15 and 15-30 entries. Skipping later batches
    here hid Batch 2's prompt and its dialogue cues from the lane, breaking
    dialogue allocation (invented speech before the authorized line).
    Batches with no own segment legitimately inherit the scene-level Timed
    Prompt at runtime; the lane still shows the owning segment only.

    REBUILD LAW (Timeline source rebuild): the former scene-level branch here
    re-anchored a full-scene segment to 0 and re-stretched its length to the
    scene duration — the "one scene / one prompt" projection. Under the 12B
    law every compliant master is windowed, so plain window projection is the
    only projection: no re-anchor, no stretch, no lane dedupe that could drop
    a batch's own entry. A full-scene segment can only exist in pre-12B
    migrated masters; start containment already assigns it to the root
    window, and it projects verbatim instead of being silently rewritten.
    """
    out: list[dict[str, Any]] = []
    for batch, w_start, _w_end in batch_time_windows(master):
        for seg in batch.promptSegments:
            if not str(getattr(seg, "text", "") or "").strip():
                continue
            abs_start = w_start + float(seg.start)
            length = float(seg.length)
            seg_id = seg.legacyPromptSegmentId or (
                str(seg.id) if str(seg.id).startswith("ps_") else f"ps_{seg.id}"
            )
            spoken = str(getattr(seg, "dialogue", None) or "").strip()
            if not spoken:
                try:
                    from .generation.speech_compile import spoken_line_from_segment

                    spoken = spoken_line_from_segment(seg) or ""
                except Exception:
                    spoken = ""
                if spoken:
                    try:
                        seg.dialogue = spoken
                    except Exception:
                        pass
            out.append(
                {
                    "id": seg_id,
                    "start": round(abs_start, 6),
                    "length": round(float(length), 6),
                    "text": seg.text or "",
                    "weight": float(seg.strength or 1.0),
                    "temperature": float(getattr(seg, "temperature", 1.0) or 1.0),
                    "negative_prompt": seg.negativePrompt,
                    "reference_binding_ids": list(seg.referenceBindingIds or []),
                    "reference_name_bindings": dump_prompt_name_bindings(seg.referenceNameBindings),
                    "user_direction": seg.userDirection,
                    "production_prompt": seg.productionPrompt,
                    "dialogue": spoken or seg.dialogue,
                    "movement_segment_ref": seg.movementSegmentRef,
                    "movement_segment_revision": seg.movementSegmentRevision,
                }
            )
    return out


def project_audio_sfx_to_legacy(master: SceneTimelineMaster) -> dict[str, list[dict[str, Any]]]:
    """Flatten batch audioClips/sfxClips into legacy scene-global track dicts.

    Music/SFX tracks are a derived NLE view of BATCH_OWNED_CLIPS. Scene-absolute
    starts are batch_window_start + local start so every batch region where audio
    plays also has a visible clip (WYSIWYG with collectTimelineAudioAtTime).
    """
    audio_out: list[dict[str, Any]] = []
    sfx_out: list[dict[str, Any]] = []
    for batch, w_start, _w_end in batch_time_windows(master):
        for clip in batch.audioClips or []:
            asset_id = str(clip.assetId or "").strip()
            if not asset_id:
                continue
            audio_out.append(
                {
                    "id": str(getattr(clip, "legacyClipId", None) or clip.id),
                    "asset_id": asset_id,
                    "start": round(w_start + float(clip.start or 0.0), 6),
                    "length": round(float(clip.length or 0.0), 6),
                    "label": clip.label or "music",
                    "volume": float(clip.volume if clip.volume is not None else 1.0),
                    "muted": bool(clip.muted) if clip.muted is not None else False,
                    "trim_start": float(clip.trimStart or 0.0),
                    "fade_in": float(clip.fade_in or 0.0),
                    "fade_out": float(clip.fade_out or 0.0),
                }
            )
        for clip in batch.sfxClips or []:
            asset_id = str(clip.assetId or "").strip()
            if not asset_id:
                continue
            sfx_out.append(
                {
                    "id": str(getattr(clip, "legacyClipId", None) or clip.id),
                    "asset_id": asset_id,
                    "start": round(w_start + float(clip.start or 0.0), 6),
                    "length": round(float(clip.length or 0.0), 6),
                    "label": clip.label or "sfx",
                    "volume": float(clip.volume if clip.volume is not None else 0.32),
                    "muted": bool(clip.muted) if clip.muted is not None else False,
                    "trim_start": float(clip.trimStart or 0.0),
                    "fade_in": float(clip.fade_in or 0.0),
                    "fade_out": float(clip.fade_out or 0.0),
                }
            )
    return {"audio_clips": audio_out, "sfx_clips": sfx_out}

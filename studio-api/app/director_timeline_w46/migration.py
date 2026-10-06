"""Idempotent migration: Director 2.0 director_json → Timeline Master BatchBlocks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..director_timeline import DirectorTimeline, parse_director_timeline
from .contracts import (
    BatchBlock,
    BatchClip,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
    TimelineVisualAnchor,
    _now,
)


def _fingerprint(batch: BatchBlock) -> str:
    payload = {
        "generatorId": batch.generatorId,
        "duration": batch.duration.model_dump(),
        "anchors": [a.model_dump() for a in batch.sourceAnchors],
        "prompts": [
            {
                "text": p.text,
                "start": p.start,
                "length": p.length,
                "strength": p.strength,
                # REVISION AUTHORITY: productionPrompt / userDirection /
                # dialogue are generation- and dialogue-authoritative state.
                # A change to any of them is a material revision and must
                # invalidate staged snapshots / approvals / continuity — not
                # silently reuse them.
                "productionPrompt": p.productionPrompt,
                "userDirection": p.userDirection,
                "dialogue": p.dialogue,
            }
            for p in batch.promptSegments
        ],
        "refs": batch.references,
        "repairs": [r.model_dump() for r in batch.repairRanges],
        "lora": batch.lora,
        "h3Resolution": batch.h3Resolution,
        "ltxQuality": batch.ltxQuality,
        "seedanceResolution": batch.seedanceResolution,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_config_fingerprint(batch: BatchBlock) -> str:
    return _fingerprint(batch)


MIGRATION_VERSION = 1
MIGRATION_SOURCE = "director_json"


def _migration_marker() -> dict[str, Any]:
    return {
        "completedAt": _now(),
        "version": MIGRATION_VERSION,
        "source": MIGRATION_SOURCE,
    }


def _has_authored_content(master: SceneTimelineMaster) -> bool:
    for batch in master.batchBlocks or []:
        if any(str(getattr(s, "text", "") or "").strip() for s in (batch.promptSegments or [])):
            return True
        if batch.visualClips or batch.audioClips or batch.sfxClips or batch.cameraInstructions:
            return True
    return False


def migrate_director_to_master(
    director_raw: str | None,
    *,
    scene_id: str,
    fallback_duration: float = 5.0,
    fallback_prompt: str = "",
    existing: SceneTimelineMaster | None = None,
) -> SceneTimelineMaster:
    """COW migration — never wipe working scenes. Idempotent when already migrated.

    NEVER_COLLAPSE_EXISTING_MULTI_BATCH: if an existing master with batchBlocks
    is present, it is always preserved regardless of migratedFromDirectorJson.
    Re-migration must not collapse multi-batch state into a single Batch 1.

    MIGRATION-COMPLETION MARKER LAW: one-shot migrate is idempotent and one-way.
    - Marker present → never re-read legacy, even if legacy keys remain on disk.
    - Marker absent + Master has authored content → never overwrite from legacy.
    - Marker absent + Master empty → migrate once, set marker atomically.
    """
    if existing and existing.migration and existing.migration.get("completedAt"):
        # Marker present: one-way door closed. Never re-import legacy.
        return existing
    if existing and existing.batchBlocks:
        existing.migratedFromDirectorJson = True
        existing.migrationNote = "Preserved existing BatchBlocks; Director 2.0 tracks remain authoritative for legacy fields."
        # Master has content but no marker: set marker now so legacy is never re-read.
        if not existing.migration or not existing.migration.get("completedAt"):
            existing.migration = _migration_marker()
        return existing
    if existing and existing.migratedFromDirectorJson:
        if not existing.migration or not existing.migration.get("completedAt"):
            existing.migration = _migration_marker()
        return existing

    tl = parse_director_timeline(
        director_raw, fallback_duration=fallback_duration, fallback_prompt=fallback_prompt
    )
    mode = "video_finishing" if tl.media_mode == "video" else "image_planning"

    # (Existing batchBlocks already preserved by the top-of-function guard.)

    batches: list[BatchBlock] = []
    if (
        tl.image_clips
        or tl.prompt_segments
        or tl.video_clips
        or tl.audio_clips
        or tl.sfx_clips
        or tl.camera_clips
    ):
        anchors: list[TimelineVisualAnchor] = []
        for clip in tl.image_clips:
            anchors.append(
                TimelineVisualAnchor(
                    id=f"anc_{clip.id}",
                    kind="image",
                    assetId=clip.asset_id,
                    label=clip.label or clip.role,
                    atTime=clip.start,
                    strength=1.0,
                )
            )
        for clip in tl.video_clips:
            anchors.append(
                TimelineVisualAnchor(
                    id=f"anc_{clip.id}",
                    kind="video",
                    assetId=clip.asset_id,
                    label=clip.label or "Video",
                    atTime=clip.start,
                    strength=1.0,
                )
            )
        segments: list[TimelinePromptSegment] = []
        for seg in tl.prompt_segments:
            segments.append(
                TimelinePromptSegment(
                    id=f"ps_{seg.id}",
                    start=seg.start,
                    length=seg.length,
                    text=seg.text,
                    strength=seg.weight,
                    negativePrompt=seg.negative_prompt,
                    executionStrategy="compiled",
                    legacyPromptSegmentId=seg.id,
                    referenceBindingIds=list(seg.reference_binding_ids or []),
                    referenceNameBindings=list(getattr(seg, "reference_name_bindings", None) or []),
                )
            )
        if not segments:
            segments = [
                TimelinePromptSegment(
                    start=0.0,
                    length=tl.duration_sec,
                    text=fallback_prompt,
                    executionStrategy="compiled",
                )
            ]
        planned = float(tl.duration_sec or fallback_duration)
        # Per-batch owned clips (BATCH_OWNED_CLIPS). Migrate legacy scene-global
        # clips deterministically into the single batch, preserving original
        # IDs in legacyClipId for audit/reversibility. No heuristic
        # redistribution — all legacy clips belong to the one migrated batch.
        visual_clips: list[BatchClip] = [
            BatchClip(
                id=f"bc_{clip.id}",
                kind="image",
                assetId=clip.asset_id,
                start=clip.start,
                length=clip.length,
                trimStart=clip.trim_start,
                label=clip.label,
                role=clip.role,
                legacyClipId=clip.id,
            )
            for clip in tl.image_clips
        ]
        for clip in tl.video_clips:
            visual_clips.append(
                BatchClip(
                    id=f"bc_{clip.id}",
                    kind="video",
                    assetId=clip.asset_id,
                    start=clip.start,
                    length=clip.length,
                    trimStart=clip.trim_start,
                    label=clip.label,
                    legacyClipId=clip.id,
                )
            )
        audio_clips: list[BatchClip] = [
            BatchClip(
                id=f"bc_{clip.id}",
                kind="audio",
                assetId=clip.asset_id,
                start=clip.start,
                length=clip.length,
                trimStart=clip.trim_start,
                label=clip.label,
                volume=clip.volume,
                muted=clip.muted,
                fade_in=clip.fade_in,
                fade_out=clip.fade_out,
                legacyClipId=clip.id,
            )
            for clip in tl.audio_clips
        ]
        sfx_clips: list[BatchClip] = [
            BatchClip(
                id=f"bc_{clip.id}",
                kind="sfx",
                assetId=clip.asset_id,
                start=clip.start,
                length=clip.length,
                trimStart=clip.trim_start,
                label=clip.label,
                volume=clip.volume,
                muted=clip.muted,
                legacyClipId=clip.id,
            )
            for clip in tl.sfx_clips
        ]
        camera_clips: list[BatchClip] = [
            BatchClip(
                id=f"bc_{clip.id}",
                kind="camera",
                start=clip.start,
                length=clip.length,
                label=clip.label,
                motion_type=clip.motion_type,
                rig=clip.rig,
                legacyClipId=clip.id,
            )
            for clip in tl.camera_clips
        ]
        migration_meta = {
            "migratedAt": _now(),
            "source": "director_json",
            "rule": "all_legacy_clips_to_single_batch",
            "legacyClipIds": {
                "image": [c.id for c in tl.image_clips],
                "video": [c.id for c in tl.video_clips],
                "audio": [c.id for c in tl.audio_clips],
                "sfx": [c.id for c in tl.sfx_clips],
                "camera": [c.id for c in tl.camera_clips],
            },
        }
        batch = BatchBlock(
            sceneId=scene_id,
            order=0,
            label="Window 1",
            status="Draft",
            duration=DurationState(
                plannedDuration=planned,
                timelineVisibleDuration=planned,
            ),
            sourceAnchors=anchors,
            promptSegments=segments,
            visualClips=visual_clips,
            audioClips=audio_clips,
            sfxClips=sfx_clips,
            cameraInstructions=camera_clips,
            legacyImageClipIds=[c.id for c in tl.image_clips],
            migrationMetadata=migration_meta,
        )
        batch.configFingerprint = compute_config_fingerprint(batch)
        batches.append(batch)
    else:
        # ORDER 8B / Owner law TIMELINE_BATCHES_CREATOR_UI=false:
        # do not mint creator Batch 1 on empty new scenes.
        from .creator_batch_surface import empty_migrate_batch_blocks

        batches = empty_migrate_batch_blocks()

    note = (
        "Empty master: no Batch 1 mint; awaits CD rematerialize / SceneTake "
        "(Owner: TIMELINE_BATCHES_CREATOR_UI=false)."
        if not batches
        else "Migrated from Director 2.0 image_clips/prompt_segments/video_clips without destructive overwrite."
    )
    return SceneTimelineMaster(
        version=1,
        mode=mode,  # type: ignore[arg-type]
        batchBlocks=batches,
        executionSnapshots={},
        migratedFromDirectorJson=True,
        migrationNote=note,
        migration=_migration_marker(),
    )


def extract_master_from_director_dict(data: dict[str, Any] | None) -> SceneTimelineMaster | None:
    if not data or not isinstance(data, dict):
        return None
    raw = data.get("timelineMaster")
    if not isinstance(raw, dict):
        return None
    try:
        return SceneTimelineMaster.model_validate(raw)
    except Exception:
        return None


def embed_master_into_director_dict(data: dict[str, Any], master: SceneTimelineMaster) -> dict[str, Any]:
    out = dict(data)
    out["timelineMaster"] = master.model_dump()
    return out


def load_or_migrate_scene_master(
    director_raw: str | None,
    *,
    scene_id: str,
    fallback_duration: float = 5.0,
    fallback_prompt: str = "",
) -> tuple[SceneTimelineMaster, DirectorTimeline, dict[str, Any]]:
    data: dict[str, Any] = {}
    if director_raw and str(director_raw).strip():
        try:
            parsed = json.loads(director_raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = {}
    existing = extract_master_from_director_dict(data)
    master = migrate_director_to_master(
        director_raw,
        scene_id=scene_id,
        fallback_duration=fallback_duration,
        fallback_prompt=fallback_prompt,
        existing=existing,
    )
    tl = parse_director_timeline(
        director_raw, fallback_duration=fallback_duration, fallback_prompt=fallback_prompt
    )

    # Gen P4: empty-master bootstrap rematerialize from CD plan (duration+generator).
    if master is not None and not master.batchBlocks and float(fallback_duration or 0) > 0:
        try:
            from .execution_window_materialize import bootstrap_empty_master_from_plan

            gid = getattr(master, "sceneGeneratorId", None)
            if gid:
                bootstrap_empty_master_from_plan(
                    master,
                    scene_id=scene_id,
                    duration_seconds=float(fallback_duration),
                    generator_id=gid,
                )
        except Exception:
            pass

    return master, tl, data

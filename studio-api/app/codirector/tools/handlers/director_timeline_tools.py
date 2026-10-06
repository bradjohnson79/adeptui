"""Co-Director tools for M42 W46 Director Timeline — inspect → propose → preview → approve → execute."""

from __future__ import annotations

import json
from typing import Any

from ....director_timeline import CameraClip
from ....director_references.tags import format_display_tag, parse_tag_number
from ....director_timeline_w46.camera_catalog import describe_camera_clip, get_motion_entry, get_rig_entry
from ....director_timeline_w46.capabilities import disclose_inpaint_strategy
from ....director_timeline_w46 import orchestrator, service, store
from ....director_timeline_w46.contracts import CancelRequest, SceneTimelineMaster, _now
from ....lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks, dumps_lipsync_tracks, parse_lipsync_tracks
from ....director_timeline_w46.master_lookup import (
    find_master_visual_by_tag,
    find_master_visual_clip,
    iter_master_visual_clips,
    visual_clip_public,
)
from ...errors import (
    CONCURRENT_MODIFICATION,
    TOOL_ARGUMENTS_INVALID,
    TOOL_TARGET_NOT_FOUND,
    CoDirectorError,
)
from ...active_timeline_scene_snapshot import build_timeline_v2_read_block
from ..definitions import ToolContext, ToolPreview


def _argument_error(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_ARGUMENTS_INVALID,
        message,
        details=details,
        recoverable=True,
        recommended_action="retry",
    )


def _target_not_found(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        message,
        details=details,
        recoverable=False,
        recommended_action="none",
    )


def _scene_id(ctx: ToolContext, args: dict[str, Any]) -> str:
    sid = str(args.get("sceneId") or ctx.scene_id or "").strip()
    if not sid:
        raise _argument_error("sceneId is required.", parameter="sceneId")
    return sid


def _require_bundle(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = service.load_timeline_bundle(ctx.db, ctx.project_id, _scene_id(ctx, args))
    if not bundle.get("ok"):
        raise _target_not_found("Scene timeline not found.", sceneId=args.get("sceneId"))
    return bundle


def _master_scene_duration(master: Any, fallback: float = 5.0) -> float:
    total = 0.0
    for batch in getattr(master, "batchBlocks", None) or []:
        dur = getattr(batch, "duration", None)
        total += float(
            getattr(dur, "plannedDuration", None) or getattr(dur, "timelineVisibleDuration", None) or 0.0
        )
    return total if total > 0 else max(0.1, float(fallback or 5.0))


def _start_containing_batch(master: Any, start: float):
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    if not blocks:
        raise _argument_error(
            "Timeline Master has no execution windows yet. Rematerialize windows before editing clips.",
            toolId="timeline.master_clip",
        )
    cursor = 0.0
    target = blocks[0]
    for batch in blocks:
        dur = getattr(batch, "duration", None)
        planned = float(
            getattr(dur, "plannedDuration", None) or getattr(dur, "timelineVisibleDuration", None) or 0.0
        )
        planned = max(0.1, planned)
        end = cursor + planned
        if start + 1e-6 >= cursor and start < end - 1e-9:
            return batch
        cursor = end
        target = batch
    return target


def _clip_attr_for_kind(kind: str) -> str:
    if kind in {"imageClip", "videoClip"}:
        return "visualClips"
    if kind == "audioClip":
        return "audioClips"
    if kind == "sfxClip":
        return "sfxClips"
    if kind == "cameraClip":
        return "cameraInstructions"
    raise _argument_error("Unsupported clip kind.", kind=kind)


def _find_master_clip(master: Any, item_id: str, kind: str | None = None):
    attrs = (
        [_clip_attr_for_kind(kind)]
        if kind and kind != "promptSegment"
        else ["visualClips", "audioClips", "sfxClips", "cameraInstructions"]
    )
    for batch in getattr(master, "batchBlocks", None) or []:
        for attr in attrs:
            for clip in list(getattr(batch, attr, None) or []):
                if str(getattr(clip, "id", "") or "") == str(item_id) or str(
                    getattr(clip, "legacyClipId", "") or ""
                ) == str(item_id):
                    return batch, attr, clip
    return None, None, None


def _payload_to_batch_clip(kind: str, payload: dict[str, Any]):
    from ....director_timeline_w46.contracts import BatchClip

    clip_kind = {
        "imageClip": "image",
        "videoClip": "video",
        "audioClip": "audio",
        "sfxClip": "sfx",
        "cameraClip": "camera",
    }.get(kind, "image")
    data = dict(payload or {})
    if data.get("kind") or data.get("assetId") is not None or "visualClips" in data:
        data.setdefault("kind", clip_kind)
        return BatchClip.model_validate(data)
    clip_id = str(data.get("id") or "").strip()
    fields: dict[str, Any] = {
        "kind": clip_kind,
        "assetId": data.get("assetId") or data.get("asset_id"),
        "start": float(data.get("start") or 0.0),
        "length": float(data.get("length") or 0.1),
        "label": str(data.get("label") or clip_kind.title()),
        "role": data.get("role"),
        "volume": float(data.get("volume") or 1.0),
        "muted": bool(data.get("muted") or False),
        "legacyClipId": clip_id or None,
        "motion_type": data.get("motion_type") or data.get("motionType"),
        "rig": data.get("rig"),
        "text": str(data.get("text") or ""),
    }
    if clip_id:
        fields["id"] = clip_id
    return BatchClip.model_validate(fields)


def _master_batch_window_start(master: Any, batch_id: str) -> float:
    """Scene-absolute start of the given batch's execution window."""
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    cursor = 0.0
    for batch in blocks:
        if str(getattr(batch, "id", "")) == str(batch_id):
            return cursor
        dur = getattr(batch, "duration", None)
        planned = float(
            getattr(dur, "plannedDuration", None) or getattr(dur, "timelineVisibleDuration", None) or 0.0
        )
        cursor += max(0.1, planned)
    return 0.0


def _append_master_clip(master: Any, clip: Any, start: float, attr: str):
    target = _start_containing_batch(master, float(start or 0.0))
    # BATCH-LOCAL COORDINATE LAW: BatchClip.start is stored batch-local (0 =
    # the owning batch's window start). Tool payloads arrive scene-absolute.
    window_start = _master_batch_window_start(master, str(getattr(target, "id", "")))
    local_start = max(0.0, float(start or 0.0) - window_start)
    try:
        clip = clip.model_copy(update={"start": local_start})
    except Exception:  # noqa: BLE001 - non-pydantic doubles in tests
        try:
            clip.start = local_start
        except Exception:  # noqa: BLE001
            pass
    setattr(target, attr, list(getattr(target, attr, None) or []) + [clip])
    return target


def _master_visual_count(master: Any) -> int:
    return sum(len(getattr(b, "visualClips", None) or []) for b in getattr(master, "batchBlocks", None) or [])


def _revision_stale(expected: Any, actual: int) -> CoDirectorError:
    return CoDirectorError(
        CONCURRENT_MODIFICATION,
        "Timeline revision changed since this proposal was built. Refresh workspace and retry.",
        details={"timelineRevision": actual, "expectedTimelineRevision": expected},
        recoverable=True,
        recommended_action="refresh_timeline_context",
    )


def _check_revision(args: dict[str, Any], workspace: dict[str, Any]) -> None:
    if "timelineRevision" not in args:
        return
    expected = args.get("timelineRevision")
    actual = int(workspace.get("timelineRevision") or 0)
    try:
        if int(expected) != actual:
            raise _revision_stale(expected, actual)
    except (TypeError, ValueError) as exc:
        raise _argument_error("timelineRevision must be an integer.", timelineRevision=expected) from exc


def _reload_master(ctx: ToolContext, scene_id: str) -> SceneTimelineMaster:
    payload = store.load_master(ctx.db, ctx.project_id, scene_id)
    if not payload.get("ok"):
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    return SceneTimelineMaster.model_validate(payload["master"])


def _persist_revision_bump(
    ctx: ToolContext,
    scene_id: str,
    workspace: dict[str, Any],
    revision_before: int,
) -> int:
    master = _reload_master(ctx, scene_id)
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        master,
        workspace=workspace,
        bump_revision=True,
    )
    return revision_before + 1


def _receipt(
    ctx: ToolContext,
    *,
    tool_id: str,
    scene_id: str,
    revision_before: int,
    revision_after: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "toolId": tool_id,
        "projectId": ctx.project_id,
        "sceneId": scene_id,
        "revisionBefore": revision_before,
        "revisionAfter": revision_after,
    }
    if extra:
        payload.update(extra)
    return payload


def build_timeline_context(db: Any, project_id: str, scene_id: str) -> dict[str, Any]:
    bundle = service.load_timeline_bundle(db, project_id, scene_id)
    if not bundle.get("ok"):
        return bundle
    master: SceneTimelineMaster = bundle["master"]
    workspace = bundle["workspace"]
    batches = [
        {
            "id": b.id,
            "label": b.label,
            "order": b.order,
            "status": b.status,
            "plannedDuration": b.duration.plannedDuration,
            "generatorId": b.generatorId,
            "hasApprovedClip": b.approvedClip is not None,
            "promptCount": len(b.promptSegments),
            "anchorCount": len(b.sourceAnchors),
            "referenceCount": len(b.references),
        }
        for b in sorted(master.batchBlocks, key=lambda x: x.order)
    ]
    empty_tracks = {
        "batchBlocks": len(master.batchBlocks) == 0,
        "imageClips": _master_visual_count(master) == 0,
        "promptSegments": not any(
            getattr(b, "promptSegments", None) for b in getattr(master, "batchBlocks", None) or []
        ),
        "videoClips": _master_visual_count(master) == 0,
        "honestMessage": (
            "Timeline tracks are empty — add a Batch or clip before generating."
            if not master.batchBlocks
            else "Batch Blocks present."
        ),
    }
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "playhead": float(bundle.get("playhead") or 0.0),
        "settings": dict(workspace.get("settings") or {}),
        "guidancePriority": workspace.get("guidancePriority"),
        "timelineRevision": int(workspace.get("timelineRevision") or 1),
        "batchesSummary": batches,
        "batchCount": len(batches),
        "mode": master.mode,
        "emptyTracks": empty_tracks,
        "optionalRefsPolicyNote": store.OPTIONAL_REFS_POLICY_NOTE,
        "removedItemCount": len(workspace.get("removedItems") or []),
        "mock": False,
    }


_LAYOUT_PRESETS = {"large", "balanced", "timeline_focus"}
_TRACK_DENSITIES = {"compact", "comfortable", "expanded"}
_CAMERA_MOTION_TYPES = {
    "static",
    "dolly_in",
    "dolly_out",
    "push",
    "pull",
    "pan",
    "tilt",
    "orbit",
    "crane",
    "rail",
    "handheld",
    "drone",
}
_CAMERA_RIGS = {"tripod", "dolly", "crane", "steadicam", "handheld", "drone", "rail", "gimbal", "virtual"}
_FOLLOW_POLICIES = {"follow_audio", "manual"}
_MASK_TYPES = {"include", "exclude", "replace"}
_MASK_TOOLS = {"brush", "erase"}
_SELECTION_SOURCES = {"videoClip", "repair"}
_INPAINT_STRATEGIES = {
    "native",
    "keyframe_repair",
    "range_replacement",
    "frame_repair_propagation",
    "complete_batch_retake",
}


def _coerce_float(value: Any, *, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise _argument_error(f"{name} must be a number.", parameter=name, value=value) from exc


def _layout_state(workspace: dict[str, Any]) -> dict[str, Any]:
    ws = store.normalize_timeline_workspace(workspace)
    raw = ws.get("layoutIntent") if isinstance(ws.get("layoutIntent"), dict) else {}
    viewer_preset = str(raw.get("viewerPreset") or "large").strip()
    if viewer_preset not in _LAYOUT_PRESETS:
        viewer_preset = "large"
    track_density = str(raw.get("trackDensity") or "compact").strip()
    if track_density not in _TRACK_DENSITIES:
        track_density = "compact"
    try:
        zoom = max(0.5, min(3.0, float(raw.get("zoom") if raw.get("zoom") is not None else 1.0)))
    except (TypeError, ValueError):
        zoom = 1.0
    fullscreen = bool(raw.get("fullscreen"))
    return {
        "viewerPreset": viewer_preset,
        "fullscreen": fullscreen,
        "zoom": round(zoom, 2),
        "trackDensity": track_density,
    }


def _set_layout_state(workspace: dict[str, Any], **patch: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    ws = store.normalize_timeline_workspace(workspace)
    state = _layout_state(ws)
    next_state = {**state, **patch}
    viewer_preset = str(next_state.get("viewerPreset") or "large").strip()
    if viewer_preset not in _LAYOUT_PRESETS:
        raise _argument_error(
            f"viewerPreset must be one of: {', '.join(sorted(_LAYOUT_PRESETS))}.",
            parameter="viewerPreset",
            viewerPreset=viewer_preset,
        )
    track_density = str(next_state.get("trackDensity") or "compact").strip()
    if track_density not in _TRACK_DENSITIES:
        raise _argument_error(
            f"trackDensity must be one of: {', '.join(sorted(_TRACK_DENSITIES))}.",
            parameter="trackDensity",
            trackDensity=track_density,
        )
    zoom = _coerce_float(next_state.get("zoom"), name="zoom")
    if zoom < 0.5 or zoom > 3.0:
        raise _argument_error("zoom must be between 0.5 and 3.", parameter="zoom", zoom=zoom)
    normalized = {
        "viewerPreset": viewer_preset,
        "fullscreen": bool(next_state.get("fullscreen")),
        "zoom": round(zoom, 2),
        "trackDensity": track_density,
    }
    ws["layoutIntent"] = normalized
    return ws, normalized


def _normalize_lipsync_state(lipsync: LipSyncTracks | dict[str, Any] | None) -> LipSyncTracks:
    if isinstance(lipsync, LipSyncTracks):
        return parse_lipsync_tracks(lipsync.model_dump_json())
    if isinstance(lipsync, dict):
        return parse_lipsync_tracks(json.dumps(lipsync))
    return LipSyncTracks.default()


def _track_summary(track: LipSyncTrack) -> dict[str, Any]:
    return {
        "trackId": track.id,
        "slot": track.slot,
        "label": track.label,
        "enabled": track.enabled,
        "audioAssetId": track.audio_asset_id,
        "characterId": track.character_id,
        "characterName": track.character_name,
        "clipCount": len(track.clips or []),
        "hasMaskPath": bool(track.track_path),
        "protected": track.slot == 1,
        "clips": [
            {
                "clipId": clip.id,
                "label": clip.label,
                "start": clip.start,
                "length": clip.length,
                "status": clip.status,
                "audioAssetId": clip.audio_asset_id,
                "characterId": clip.character_id,
                "characterName": clip.character_name,
                "followPolicy": clip.follow_policy,
            }
            for clip in (track.clips or [])
        ],
    }


def _find_lipsync_track(tracks: list[LipSyncTrack], track_id: str | None) -> tuple[int, LipSyncTrack]:
    if track_id:
        for index, track in enumerate(tracks):
            if track.id == track_id:
                return index, track
        raise _target_not_found("Lip Sync track not found.", trackId=track_id)
    return 0, tracks[0]


def _find_lipsync_clip(tracks: list[LipSyncTrack], clip_id: str) -> tuple[int, int, LipSyncTrack, LipSyncClip]:
    for track_index, track in enumerate(tracks):
        for clip_index, clip in enumerate(track.clips or []):
            if clip.id == clip_id:
                return track_index, clip_index, track, clip
    raise _target_not_found("Lip Sync clip not found.", clipId=clip_id)


def _validate_lipsync_state(scene: Any, lipsync: Any) -> list[dict[str, Any]]:
    tracks = _normalize_lipsync_state(lipsync).tracks
    findings: list[dict[str, Any]] = []
    if not tracks:
        return [
            {
                "severity": "error",
                "code": "lipsync_missing_default_track",
                "message": "Timeline must keep Lip Sync 1 available.",
                "fixProposal": "Add or restore the default lip sync track.",
            }
        ]
    for track in tracks:
        resolved_audio = track.audio_asset_id or next((clip.audio_asset_id for clip in track.clips if clip.audio_asset_id), None)
        resolved_character = track.character_id or track.character_name or next(
            ((clip.character_id or clip.character_name) for clip in track.clips if clip.character_id or clip.character_name),
            None,
        )
        if track.enabled and not resolved_audio:
            findings.append(
                {
                    "severity": "error",
                    "code": "lipsync_track_missing_audio",
                    "trackId": track.id,
                    "message": f"{track.label} is enabled but has no dialogue audio.",
                    "fixProposal": "Bind a dialogue audio asset before executing lip sync.",
                }
            )
        if track.enabled and not resolved_character:
            findings.append(
                {
                    "severity": "warning",
                    "code": "lipsync_track_missing_character",
                    "trackId": track.id,
                    "message": f"{track.label} is enabled but has no character binding yet.",
                    "fixProposal": "Bind a character so approvals are reviewable.",
                }
            )
        for clip in track.clips or []:
            clip_audio = clip.audio_asset_id or track.audio_asset_id or scene.lipsync_audio_asset_id or scene.audio_asset_id
            if not clip_audio:
                findings.append(
                    {
                        "severity": "error",
                        "code": "lipsync_clip_missing_audio",
                        "trackId": track.id,
                        "clipId": clip.id,
                        "message": f"{clip.label} has no dialogue audio binding.",
                        "fixProposal": "Bind the clip or track to a dialogue audio asset.",
                    }
                )
            if not (clip.character_id or clip.character_name or track.character_id or track.character_name):
                findings.append(
                    {
                        "severity": "warning",
                        "code": "lipsync_clip_missing_character",
                        "trackId": track.id,
                        "clipId": clip.id,
                        "message": f"{clip.label} has no character binding yet.",
                        "fixProposal": "Bind a character to keep track ownership clear.",
                    }
                )
            if str(clip.follow_policy or "follow_audio") not in _FOLLOW_POLICIES:
                findings.append(
                    {
                        "severity": "error",
                        "code": "lipsync_clip_invalid_follow_policy",
                        "trackId": track.id,
                        "clipId": clip.id,
                        "message": f"{clip.label} has an unsupported follow policy.",
                        "fixProposal": "Use follow_audio or manual.",
                    }
                )
    return findings


def _batch_absolute_start(master: SceneTimelineMaster, batch_id: str) -> float:
    total = 0.0
    for batch in sorted(master.batchBlocks, key=lambda item: item.order):
        if batch.id == batch_id:
            return total
        total += max(0.1, float(batch.duration.plannedDuration or 0.0))
    return total


def _parse_mask_strokes(raw: str | None) -> list[dict[str, Any]]:
    if not raw or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _argument_error("maskStrokesJson must be valid JSON.", parameter="maskStrokesJson") from exc
    if not isinstance(parsed, list):
        raise _argument_error("maskStrokesJson must decode to a list.", parameter="maskStrokesJson")
    strokes: list[dict[str, Any]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise _argument_error("Each mask stroke must be an object.", parameter="maskStrokesJson", index=index)
        tool = str(item.get("tool") or "brush").strip()
        if tool not in _MASK_TOOLS:
            raise _argument_error(
                f"mask stroke tool must be one of: {', '.join(sorted(_MASK_TOOLS))}.",
                parameter="maskStrokesJson",
                index=index,
                tool=tool,
            )
        strokes.append(
            {
                "id": str(item.get("id") or f"stroke-{index + 1}"),
                "tool": tool,
                "at": float(item.get("at") or 0.0),
                "x": float(item.get("x") or 0.0),
                "y": float(item.get("y") or 0.0),
            }
        )
    return strokes


def _resolve_camera_clip(
    args: dict[str, Any],
    *,
    duration: float,
    existing: dict[str, Any] | None = None,
) -> CameraClip:
    from uuid import uuid4

    source = dict(existing or {})
    motion_id = str(args.get("motionId") if "motionId" in args else source.get("motion_id") or "").strip() or None
    rig_id = str(args.get("rigId") if "rigId" in args else source.get("rig_id") or "").strip() or None
    motion_entry = get_motion_entry(motion_id) if motion_id else None
    rig_entry = get_rig_entry(rig_id) if rig_id else None
    if motion_id and motion_entry is None:
        raise _argument_error("Unknown camera motionId.", parameter="motionId", motionId=motion_id)
    if rig_id and rig_entry is None:
        raise _argument_error("Unknown camera rigId.", parameter="rigId", rigId=rig_id)

    motion_type = str(args.get("motionType") if "motionType" in args else source.get("motion_type") or "static").strip()
    if motion_entry:
        motion_type = motion_entry.native_motion_type or motion_entry.workflow_motion_type or motion_type
    if motion_type not in _CAMERA_MOTION_TYPES:
        raise _argument_error(
            f"motionType must be one of: {', '.join(sorted(_CAMERA_MOTION_TYPES))}.",
            parameter="motionType",
            motionType=motion_type,
        )

    rig = str(args.get("rig") if "rig" in args else source.get("rig") or "tripod").strip()
    if rig_entry:
        rig = rig_entry.native_rig or rig_entry.workflow_rig or rig
    if rig not in _CAMERA_RIGS:
        raise _argument_error(
            f"rig must be one of: {', '.join(sorted(_CAMERA_RIGS))}.",
            parameter="rig",
            rig=rig,
        )

    start = _coerce_float(args.get("start") if "start" in args else source.get("start", 0.0), name="start")
    length = _coerce_float(args.get("length") if "length" in args else source.get("length", 2.0), name="length")
    if start < 0:
        raise _argument_error("start must be >= 0.", parameter="start", start=start)
    if length <= 0:
        raise _argument_error("length must be > 0.", parameter="length", length=length)

    speed = args.get("speed") if "speed" in args else source.get("speed")
    if speed is None and motion_entry:
        speed = motion_entry.defaults.speed
    if speed is None and rig_entry:
        speed = rig_entry.defaults.speed
    intensity = args.get("intensity") if "intensity" in args else source.get("intensity")
    if intensity is None and motion_entry:
        intensity = motion_entry.defaults.intensity
    if intensity is None and rig_entry:
        intensity = rig_entry.defaults.intensity
    subject_lock = args.get("subjectLock") if "subjectLock" in args else source.get("subject_lock")
    if subject_lock is None and motion_entry:
        subject_lock = motion_entry.defaults.subjectLock
    if subject_lock is None and rig_entry:
        subject_lock = rig_entry.defaults.subjectLock

    label = str(args.get("label") if "label" in args else source.get("label") or "").strip()
    if not label:
        if motion_entry:
            label = motion_entry.label
        else:
            label = motion_type.replace("_", " ").title()

    clip = CameraClip(
        id=str(source.get("id") or f"cam_{uuid4().hex[:8]}"),
        start=max(0.0, min(start, max(0.0, duration - 0.1))),
        length=max(0.1, min(length, duration)),
        motion_type=motion_type,  # type: ignore[arg-type]
        motion_id=motion_entry.id if motion_entry else motion_id,
        speed=float(speed if speed is not None else 1.0),
        distance=_coerce_float(args.get("distance") if "distance" in args else source.get("distance", 1.0), name="distance"),
        ease=str(args.get("ease") if "ease" in args else source.get("ease") or "ease_in_out"),
        shake=_coerce_float(args.get("shake") if "shake" in args else source.get("shake", 0.0), name="shake"),
        blend=_coerce_float(args.get("blend") if "blend" in args else source.get("blend", 0.5), name="blend"),
        intensity=(float(intensity) if intensity is not None else None),
        subject_lock=(float(subject_lock) if subject_lock is not None else None),
        stabilization=(
            str(args.get("stabilization") if "stabilization" in args else source.get("stabilization") or "").strip()
            or None
        ),
        rig=rig,  # type: ignore[arg-type]
        rig_id=rig_entry.id if rig_entry else rig_id,
        custom_motion_label=(
            str(args.get("customMotionLabel") if "customMotionLabel" in args else source.get("custom_motion_label") or "").strip()
            or None
        ),
        custom_rig_label=(
            str(args.get("customRigLabel") if "customRigLabel" in args else source.get("custom_rig_label") or "").strip()
            or None
        ),
        execution_strategy=(
            str(args.get("executionStrategy") if "executionStrategy" in args else source.get("execution_strategy") or "").strip()
            or None
        ),
        label=label,
        preset_id=str(args.get("presetId") if "presetId" in args else source.get("preset_id") or "").strip() or None,
    )
    return clip


async def get_workspace(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(ctx, args)
    context = build_timeline_context(ctx.db, ctx.project_id, scene_id)
    if not context.get("ok"):
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    bundle = _require_bundle(ctx, {**args, "sceneId": scene_id})
    master = bundle["master"]
    result = {
        **context,
        "master": master.model_dump(),
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.get_workspace",
            scene_id=scene_id,
            revision_before=int(context["timelineRevision"]),
            revision_after=int(context["timelineRevision"]),
        ),
    }
    # ADDITIVE: the live Timeline V2 document is the owner for V2 scenes. The W46
    # master block above is unchanged; V2 truth is exposed alongside it.
    v2_block = build_timeline_v2_read_block(ctx.db, ctx.project_id, scene_id)
    if v2_block:
        result["timelineV2"] = v2_block
    return result


async def get_playhead(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    revision = int(bundle["workspace"].get("timelineRevision") or 1)
    playhead = float(bundle.get("playhead") or 0.0)
    # SINGLE-STORE: durationSec reads Master window durations (fallback: scene
    # row duration_sec), never the retired legacy directorTimeline.duration_sec.
    scene_row = store.get_scene(ctx.db, ctx.project_id, scene_id)
    duration_sec = _master_scene_duration(
        bundle["master"],
        fallback=float(getattr(scene_row, "duration_sec", None) or 0.0),
    )
    return {
        "playhead": playhead,
        "durationSec": duration_sec,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.get_playhead",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def get_settings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    workspace = bundle["workspace"]
    revision = int(workspace.get("timelineRevision") or 1)
    return {
        "settings": dict(workspace.get("settings") or {}),
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.get_settings",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def get_guidance_priority(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    workspace = bundle["workspace"]
    revision = int(workspace.get("timelineRevision") or 1)
    return {
        "guidancePriority": workspace.get("guidancePriority"),
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.get_guidance_priority",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


def _resolve_scene_take_arg(master: SceneTimelineMaster, args: dict[str, Any]):
    from ....director_timeline_w46.scene_takes import scene_take_display

    tid = str(args.get("takeId") or "").strip()
    label = str(args.get("takeLabel") or "").strip()
    takes = list(getattr(master, "sceneTakes", None) or [])
    if tid:
        hit = next((t for t in takes if t.id == tid), None)
        if hit is not None:
            return hit
    if label:
        want = label.lower().removeprefix("take ").strip()
        hit = next((t for t in takes if str(t.label or "").lower() == want or scene_take_display(t.label).lower() == label.lower()), None)
        if hit is not None:
            return hit
    return None


async def inspect_scene_takes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....director_timeline_w46.scene_takes import list_scene_takes_payload

    bundle = _require_bundle(ctx, args)
    master: SceneTimelineMaster = bundle["master"]
    scene_id = bundle["sceneId"]
    revision = int(bundle["workspace"].get("timelineRevision") or 1)
    payload = list_scene_takes_payload(master)
    return {
        **payload,
        "timelineRevision": revision,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.inspect_scene_takes",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def inspect_batches(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    context = build_timeline_context(ctx.db, ctx.project_id, _scene_id(ctx, args))
    if not context.get("ok"):
        raise _target_not_found("Scene timeline not found.")
    result = {
        "batches": context["batchesSummary"],
        "batchCount": context["batchCount"],
        "timelineRevision": context["timelineRevision"],
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.inspect_batches",
            scene_id=context["sceneId"],
            revision_before=int(context["timelineRevision"]),
            revision_after=int(context["timelineRevision"]),
        ),
    }
    # ADDITIVE: V2 scenes report their live shots/segments alongside the W46
    # batch summary. Non-V2 scenes keep the exact previous payload.
    v2_block = build_timeline_v2_read_block(ctx.db, ctx.project_id, context["sceneId"])
    if v2_block:
        result["timelineV2"] = v2_block
    return result


async def preflight(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    master: SceneTimelineMaster = bundle["master"]
    scene_id = bundle["sceneId"]
    revision = int(bundle["workspace"].get("timelineRevision") or 1)
    findings = orchestrator.run_preflight(
        master,
        lipsync_tracks=bundle.get("lipsyncTracks"),
        db=ctx.db,
        project_id=ctx.project_id,
        scene_id=scene_id,
    )
    blocking = [f for f in findings if f.get("severity") == "error"]
    return {
        "ok": len(blocking) == 0,
        "findings": findings,
        "blockingCount": len(blocking),
        "optionalRefsPolicyNote": store.OPTIONAL_REFS_POLICY_NOTE,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.preflight",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def explain_asset_reference_name(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    revision = int(bundle["workspace"].get("timelineRevision") or 1)
    name = str(args.get("name") or args.get("displayTag") or "").strip()
    if not name:
        raise _argument_error("name or displayTag is required.", parameter="name")
    clip = find_master_visual_by_tag(bundle["master"], name)
    parsed = parse_tag_number(name if name.startswith("@") else f"@{name.lstrip('@')}")
    explanation = {
        "input": name,
        "normalizedTag": format_display_tag(parsed) if parsed else None,
        "format": "@ImageN — stable display tag for timeline image clips (N is monotonic, never renumbered).",
        "matchedClipId": clip.id if clip else None,
        "matchedAssetId": getattr(clip, "assetId", None) if clip else None,
        "policyNote": store.OPTIONAL_REFS_POLICY_NOTE,
    }
    return {
        **explanation,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.explain_asset_reference_name",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


_FOCUS_TARGETS = {
    "scenePrompt",
    "batch",
    "trackItem",
    "preflightFinding",
    "viewer",
    "playhead",
    "inspectorField",
    "queueJob",
}


async def focus_ui(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Return a shared UI focus directive for TimelineEditorShell (SA52)."""
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    revision = int(bundle["workspace"].get("timelineRevision") or 1)
    target = str(args.get("target") or "").strip()
    if target not in _FOCUS_TARGETS:
        raise _argument_error(
            f"target must be one of: {', '.join(sorted(_FOCUS_TARGETS))}",
            parameter="target",
            target=target,
        )
    ui_focus = {
        "target": target,
        "sceneId": scene_id,
        "selectionKind": args.get("selectionKind"),
        "selectionId": args.get("selectionId"),
        "fieldId": args.get("fieldId"),
        "playheadSec": args.get("playheadSec"),
        "findingCode": args.get("findingCode"),
        "jobId": args.get("jobId"),
        "takeId": args.get("takeId"),
        "takeLabel": args.get("takeLabel"),
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "message": f"Focus Timeline UI target “{target}” using the shared selection model.",
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.focus_ui",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def inspect_layout(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    workspace = bundle["workspace"]
    revision = int(workspace.get("timelineRevision") or 1)
    layout = _layout_state(workspace)
    return {
        **layout,
        "source": "workspaceIntent",
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.inspect_layout",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def inspect_lipsync(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    workspace = bundle["workspace"]
    revision = int(workspace.get("timelineRevision") or 1)
    tracks = _normalize_lipsync_state(bundle.get("lipsyncTracks")).tracks
    protected_track_id = tracks[0].id if tracks else None
    return {
        "trackCount": len(tracks),
        "protectedTrackId": protected_track_id,
        "tracks": [_track_summary(track) for track in tracks],
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.inspect_lipsync",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


async def validate_lipsync(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    workspace = bundle["workspace"]
    revision = int(workspace.get("timelineRevision") or 1)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    findings = _validate_lipsync_state(scene, bundle.get("lipsyncTracks"))
    blocking = [item for item in findings if item.get("severity") == "error"]
    return {
        "ok": len(blocking) == 0,
        "blockingCount": len(blocking),
        "findings": findings,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.validate_lipsync",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
        ),
    }


def _preview_mutation(ctx: ToolContext, args: dict[str, Any], *, summary: str, lines: list[str]) -> ToolPreview:
    return ToolPreview(
        summary=summary,
        lines=lines,
        resourceKind="scene",
        resourceId=str(args.get("sceneId") or ctx.scene_id or ""),
    )


def preview_set_playhead(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    playhead = float(args.get("playhead") or args.get("time") or 0.0)
    return _preview_mutation(
        ctx,
        args,
        summary=f"Move playhead to {playhead:.2f}s.",
        lines=["Updates Director Timeline playhead only.", "Does not mutate Batch Blocks."],
    )


def apply_set_playhead(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    playhead = float(args.get("playhead") or args.get("time") or 0.0)
    if playhead < 0:
        raise _argument_error("playhead must be >= 0.", playhead=playhead)
    # SINGLE-STORE: save_master persists Master + workspace only. The playhead
    # lives on the workspace — a director_tl.playhead assignment is a dead write.
    workspace["playhead"] = playhead
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "playhead": playhead,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.set_playhead",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
        ),
    }


def preview_update_settings(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    keys = ", ".join(sorted(k for k in args.keys() if k not in {"sceneId", "timelineRevision"}))
    return _preview_mutation(
        ctx,
        args,
        summary=f"Update timeline workspace settings ({keys or 'patch'}).",
        lines=["Persists display/snap/track density prefs in director_json.", "Does not change theme."],
    )


def apply_update_settings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    settings = dict(workspace.get("settings") or {})
    for key in ("trackDensity", "displayMode", "showFilenames", "showThumbnails", "snapEnabled"):
        if key in args:
            settings[key] = args[key]
    if isinstance(args.get("settings"), dict):
        settings.update(args["settings"])
    workspace = store.normalize_timeline_workspace(workspace)
    workspace["settings"] = settings
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "settings": settings,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.update_settings",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
        ),
    }


def preview_set_guidance_priority(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    priority = str(args.get("guidancePriority") or "visual_first")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Set guidance priority to {priority}.",
        lines=[
            "Stored on the scene timeline workspace.",
            "Passed into execution snapshots when generating.",
        ],
    )


def apply_set_guidance_priority(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    priority = str(args.get("guidancePriority") or "").strip()
    allowed = {"visual_first", "prompt_first", "balanced", "custom"}
    if priority not in allowed:
        raise _argument_error(
            f"guidancePriority must be one of: {', '.join(sorted(allowed))}.",
            guidancePriority=priority,
        )
    workspace = store.normalize_timeline_workspace(workspace)
    workspace["guidancePriority"] = priority
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "guidancePriority": priority,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.set_guidance_priority",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
        ),
    }


_REMOVE_ITEM_KINDS = (
    "batchBlock",
    "imageClip",
    "videoClip",
    "promptSegment",
    "audioClip",
    "sfxClip",
    "cameraClip",
)


def preview_remove_item(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    kind = str(args.get("itemKind") or "batchBlock")
    item_id = str(args.get("itemId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Remove {kind} {item_id} from the Timeline.",
        lines=[
            "Batch Blocks move to removedItems for restore.",
            "Track clips are removed from Timeline Master clip arrays.",
            "Does not delete library assets.",
        ],
    )


def apply_remove_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    kind = str(args.get("itemKind") or "batchBlock")
    item_id = str(args.get("itemId") or "").strip()
    if not item_id:
        raise _argument_error("itemId is required.", parameter="itemId")
    if kind not in _REMOVE_ITEM_KINDS:
        raise _argument_error(
            f"itemKind must be one of: {', '.join(_REMOVE_ITEM_KINDS)}",
            itemKind=kind,
        )
    master: SceneTimelineMaster = bundle["master"]
    if kind == "batchBlock":
        batch = next((b for b in master.batchBlocks if b.id == item_id), None)
        if not batch:
            raise _target_not_found("Batch Block not found.", itemId=item_id)
        master.batchBlocks = [b for b in master.batchBlocks if b.id != item_id]
        for i, b in enumerate(sorted(master.batchBlocks, key=lambda x: x.order)):
            b.order = i
        workspace = store.stash_removed_item(
            workspace,
            kind=kind,
            item_id=item_id,
            payload=batch.model_dump(),
        )
    else:
        payload: dict[str, Any] | None = None
        if kind in {"imageClip", "videoClip", "audioClip", "sfxClip", "cameraClip"}:
            batch, attr, match = _find_master_clip(master, item_id, kind)
            if match is None or batch is None or attr is None:
                raise _target_not_found("Clip not found.", itemId=item_id, itemKind=kind)
            payload = match.model_dump() if hasattr(match, "model_dump") else dict(match)
            setattr(
                batch,
                attr,
                [
                    c
                    for c in (getattr(batch, attr, None) or [])
                    if str(getattr(c, "id", "") or "") != str(item_id)
                    and str(getattr(c, "legacyClipId", "") or "") != str(item_id)
                ],
            )
        elif kind == "promptSegment":
            # SINGLE-STORE: find in Master batch.promptSegments only.
            match = None
            for batch in getattr(master, "batchBlocks", None) or []:
                for s in getattr(batch, "promptSegments", None) or []:
                    if str(getattr(s, "id", "") or "") == str(item_id) or str(
                        getattr(s, "legacyPromptSegmentId", "") or ""
                    ) == str(item_id):
                        match = s
                        break
                if match is not None:
                    break
            if match is None:
                raise _target_not_found("Timed Instruction not found.", itemId=item_id)
            payload = match.model_dump() if hasattr(match, "model_dump") else dict(match)
        workspace = store.stash_removed_item(
            workspace,
            kind=kind,
            item_id=item_id,
            payload=payload or {},
        )
    # SINGLE-STACK: remove Timed Prompt from Master batch.promptSegments directly.
    if kind == "promptSegment":
        for batch in getattr(master, "batchBlocks", None) or []:
            segs = list(getattr(batch, "promptSegments", None) or [])
            kept = [
                s
                for s in segs
                if str(getattr(s, "id", "") or "") != str(item_id)
                and str(getattr(s, "legacyPromptSegmentId", "") or "") != str(item_id)
            ]
            if len(kept) != len(segs):
                batch.promptSegments = kept
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        master,
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    removed = workspace.get("removedItems") or []
    # BOT2: Instant Update / STEP0 — verify destination readback (ids gone).
    verified = True
    remaining_ids: list[str] = []
    if kind == "promptSegment":
        try:
            # Re-load Master from persistence — do not trust in-memory only.
            rb = service.load_timeline_bundle(ctx.db, ctx.project_id, scene_id)
            rel_master = (rb or {}).get("master")
            remaining_ids = []
            for batch in getattr(rel_master, "batchBlocks", None) or []:
                for s in getattr(batch, "promptSegments", None) or []:
                    remaining_ids.append(str(getattr(s, "id", "") or ""))
                    remaining_ids.append(str(getattr(s, "legacyPromptSegmentId", "") or ""))
            verified = item_id not in remaining_ids
        except Exception:
            remaining_ids = []
            for batch in getattr(master, "batchBlocks", None) or []:
                for s in getattr(batch, "promptSegments", None) or []:
                    remaining_ids.append(str(getattr(s, "id", "") or ""))
            verified = item_id not in remaining_ids
        if not verified:
            raise _argument_error(
                f"Timed Prompt remove did not verify: {item_id} still present after save.",
                field="itemId",
                toolId="timeline.remove_item",
                itemId=item_id,
                remainingIds=remaining_ids,
            )
    elif kind in {"imageClip", "videoClip", "audioClip", "sfxClip", "cameraClip"}:
        rb = service.load_timeline_bundle(ctx.db, ctx.project_id, scene_id)
        rel_master = (rb or {}).get("master")
        _batch, _attr, still = _find_master_clip(rel_master, item_id, kind)
        verified = still is None
        if not verified:
            raise _argument_error(
                f"Clip remove did not verify: {item_id} still present on Master.",
                field="itemId",
                toolId="timeline.remove_item",
                itemId=item_id,
                itemKind=kind,
            )
    ui_focus = {
        "target": "inspectorField",
        "sceneId": scene_id,
        "selectionKind": "scene",
        "selectionId": scene_id,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "verified": verified,
        "itemId": item_id,
        "itemKind": kind,
        "removedItemId": removed[-1]["id"] if removed else item_id,
        "destinationSceneId": scene_id,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.remove_item",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={
                "itemKind": kind,
                "itemId": item_id,
                "verified": verified,
                "remainingPromptIds": remaining_ids if kind == "promptSegment" else None,
            },
        ),
    }


def preview_restore_removed_item(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    removed_id = str(args.get("removedItemId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Restore removed item {removed_id}.",
        lines=["Re-inserts stashed Batch Block or track clip.", "Preserves original ids when possible."],
    )


def apply_restore_removed_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    removed_id = str(args.get("removedItemId") or "").strip()
    if not removed_id:
        raise _argument_error("removedItemId is required.", parameter="removedItemId")
    items = list(workspace.get("removedItems") or [])
    match = next((i for i in items if i.get("id") == removed_id), None)
    if not match:
        raise _target_not_found("Removed item not found in restore stash.", removedItemId=removed_id)
    master: SceneTimelineMaster = bundle["master"]
    kind = str(match.get("kind") or "")
    payload = match.get("payload") or {}
    if kind == "batchBlock":
        from ....director_timeline_w46.contracts import BatchBlock

        batch = BatchBlock.model_validate(payload)
        if any(b.id == batch.id for b in master.batchBlocks):
            batch.order = max((b.order for b in master.batchBlocks), default=-1) + 1
        master.batchBlocks.append(batch)
        master.batchBlocks.sort(key=lambda b: b.order)
    else:
        from ....director_timeline_w46.contracts import TimelinePromptSegment

        if kind == "promptSegment":
            # SINGLE-STORE: restore into Master batch.promptSegments only.
            seg = TimelinePromptSegment.model_validate(payload)
            target = None
            for batch in getattr(master, "batchBlocks", None) or []:
                if any(
                    str(getattr(s, "id", "") or "") == str(seg.id)
                    or str(getattr(s, "legacyPromptSegmentId", "") or "") == str(seg.id)
                    for s in getattr(batch, "promptSegments", None) or []
                ):
                    target = batch
                    break
            if target is None:
                target = _start_containing_batch(master, float(getattr(seg, "start", 0.0) or 0.0))
            target.promptSegments = list(getattr(target, "promptSegments", None) or []) + [seg]
        elif kind in {"imageClip", "videoClip", "audioClip", "sfxClip", "cameraClip"}:
            clip = _payload_to_batch_clip(kind, payload if isinstance(payload, dict) else {})
            _append_master_clip(master, clip, float(getattr(clip, "start", 0.0) or 0.0), _clip_attr_for_kind(kind))
        else:
            raise _argument_error("Unsupported removed item kind.", kind=kind)
    workspace = store.normalize_timeline_workspace(workspace)
    workspace["removedItems"] = [i for i in items if i.get("id") != removed_id]
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        master,
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "restoredItemId": match.get("itemId"),
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.restore_removed_item",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"removedItemId": removed_id, "kind": kind},
        ),
    }


def preview_propose_add_batch(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    label = str(args.get("label") or "New Batch")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Add Batch “{label}”.",
        lines=["Creates a Draft Batch Block with default prompt segment.", "Persisted to timelineMaster."],
    )


def apply_propose_add_batch(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = (ctx, args)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Create Shot adds a shot. Batch blocks are no longer Timeline state.",
        "mock": False,
    }


def preview_propose_add_image_clip(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Add an Image clip to the Visual track.",
        lines=["Persists to Timeline Master visual clips.", "Does not invent library assets."],
    )


def apply_propose_add_image_clip(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....film_timeline.insertion import add_to_timeline

    bundle = _require_bundle(ctx, args)
    scene_id = bundle["sceneId"]
    asset_id = str(args.get("assetId") or "").strip()
    if not asset_id:
        raise _argument_error("assetId is required.", parameter="assetId")
    placed = add_to_timeline(
        ctx.db,
        ctx.project_id,
        scene_id,
        media_type="image",
        asset_id=asset_id,
        target_track_type="reference",
        label=str(args.get("label") or "Image"),
        shot_id=str(args.get("shotId") or "") or None,
    )
    return {"ok": bool(placed.get("ok")), "rendered": False, "filmTimeline": True, **placed}

def _timed_prompt_requested_coverage_sec(text: str) -> float | None:
    """Max end-time claimed by Timed Prompt text (markers and coverage phrases).

    BOT2 / Creator Spec Fidelity: refuse when coverage exceeds scene duration.
    Never treat a clamped length=scene_dur as success when text still claims longer.
    """
    import re as _re

    raw = str(text or "")
    max_end: float | None = None
    for m in _re.finditer(
        r"\[(\d+(?:\.\d+)?)\s*s\s*(?:[-–—to]+\s*(\d+(?:\.\d+)?)\s*s)?\]",
        raw,
        _re.I,
    ):
        a = float(m.group(1))
        b = float(m.group(2) or m.group(1))
        end = max(a, b)
        max_end = end if max_end is None else max(max_end, end)
    for m in _re.finditer(
        r"(?:covers?|full|spanning|across)\s+(?:the\s+)?(?:full\s+)?(\d+(?:\.\d+)?)\s*-?\s*seconds?\b"
        r"|\b(\d+(?:\.\d+)?)\s*-\s*second(?:\s+(?:multi-beat|narrative|dialogue|arc|prompt))?\b"
        r"|\b(\d+(?:\.\d+)?)\s+seconds?\s+(?:multi-beat|narrative|dialogue|arc)\b",
        raw,
        _re.I,
    ):
        val = next((float(g) for g in m.groups() if g is not None), None)
        if val is not None and val >= 1.0:
            max_end = val if max_end is None else max(max_end, val)
    return max_end


def preview_propose_add_prompt_segment(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Add a Timed Instruction to the Prompt track.",
        lines=["Persists to the Timed Prompt track.", "The Inspector shows the same prompt after save."],
    )



def _upsert_master_timed_prompt(
    master: Any,
    *,
    text: str,
    start: float,
    length: float,
    legacy_id: str | None = None,
    user_direction: str | None = None,
    production_prompt: str | None = None,
    dialogue: str | None = None,
    weight: float = 1.0,
    explicit_start: bool = True,
) -> tuple[Any, str]:
    """Write Timed Prompt into Master batch.promptSegments by start-containment.

    Root batch (contains start) owns scene-level prompt. Never clones into every window.
    Returns (target_batch, segment_id).
    """
    from ....director_timeline_w46.contracts import TimelinePromptSegment

    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    if not blocks:
        raise _argument_error(
            "Timeline Master has no execution windows yet. Rematerialize windows before adding a Timed Prompt.",
            field="text",
            toolId="timeline.propose_add_prompt_segment",
        )

    # Cumulative plannedDuration windows — start-containment (charter).
    cursor = 0.0
    target = blocks[0]
    for b in blocks:
        dur = getattr(b, "duration", None)
        planned = float(getattr(dur, "plannedDuration", None) or getattr(dur, "timelineVisibleDuration", None) or 0.0)
        planned = max(0.1, planned)
        end = cursor + planned
        if start + 1e-6 >= cursor and start < end - 1e-9:
            target = b
            break
        cursor = end
        target = b

    segs = list(getattr(target, "promptSegments", None) or [])
    # Transaction law (pre-dual-stack parity): more than one empty Timed Prompt
    # is ambiguous — refuse to add another beside them.
    empty_segs = [s for s in segs if not str(getattr(s, "text", "") or "").strip()]
    if len(empty_segs) >= 2:
        raise _argument_error(
            "This scene has more than one empty Timed Prompt. I will not add another beside them.",
            field="text",
            toolId="timeline.propose_add_prompt_segment",
        )
    # Prefer updating empty primary or matching legacy id
    hit = None
    if legacy_id:
        hit = next((s for s in segs if getattr(s, "legacyPromptSegmentId", None) == legacy_id or getattr(s, "id", None) == legacy_id), None)
    if hit is None and len(empty_segs) == 1:
        hit = empty_segs[0]
    if (
        hit is None
        and not explicit_start
        and segs
        and int(getattr(target, "order", 0) or 0) == 0
        and len(segs) == 1
    ):
        # Single root segment + no explicit start — scene-owned re-placement
        # replaces text. An explicit start on a multi-beat scene APPENDS
        # instead of destroying the existing segment.
        hit = segs[0]

    from ....director_timeline_w46.same_track_no_overlap import (
        SameTrackOverlapError,
        assert_master_prompt_candidate_fits,
        CD_LAYMAN_TRACK_OCCUPIED,
    )

    candidate_id = str(getattr(hit, "id", "") or "") or None
    try:
        assert_master_prompt_candidate_fits(
            master,
            {
                "id": candidate_id,
                "start": float(start),
                "length": float(length),
            },
        )
    except SameTrackOverlapError as exc:
        raise _argument_error(
            CD_LAYMAN_TRACK_OCCUPIED,
            field="start",
            toolId="timeline.propose_add_prompt_segment",
            code="SAME_TRACK_OVERLAP",
            detail=str(exc),
        ) from exc

    if hit is None:
        hit = TimelinePromptSegment(
            start=float(start),
            length=float(length),
            text=text,
            strength=float(weight),
            legacyPromptSegmentId=legacy_id,
            userDirection=user_direction,
            productionPrompt=production_prompt,
            dialogue=dialogue,
        )
        segs.append(hit)
    else:
        hit.text = text
        hit.start = float(start)
        hit.length = float(length)
        hit.strength = float(weight)
        if legacy_id:
            try:
                hit.legacyPromptSegmentId = legacy_id
            except Exception:
                pass
        if user_direction is not None:
            hit.userDirection = user_direction
        if production_prompt is not None:
            hit.productionPrompt = production_prompt
        if dialogue is not None:
            hit.dialogue = dialogue
    target.promptSegments = segs
    return target, str(getattr(hit, "id", "") or "")



def _master_prompt_text_by_id(master: Any, segment_id: str) -> str:
    for b in getattr(master, "batchBlocks", None) or []:
        for s in getattr(b, "promptSegments", None) or []:
            if str(getattr(s, "id", "") or "") == segment_id:
                return str(getattr(s, "text", "") or "")
            if str(getattr(s, "legacyPromptSegmentId", None) or "") == segment_id:
                return str(getattr(s, "text", "") or "")
    return ""



def _refuse_timed_prompt_while_rendering(master: Any, tool_id: str) -> None:
    from ....director_timeline_w46.scene_takes import take_render_is_live

    if take_render_is_live(master):
        raise _argument_error(
            "A take is rendering. The Timed Prompt stays as written until that take finishes.",
            field="text",
            toolId=tool_id,
        )


def apply_propose_add_prompt_segment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from hashlib import sha256

    authored = str(args.get("text") or "")
    if not authored.strip():
        raise _argument_error(
            "Timed Prompt text is required and must be non-empty after trim.",
            field="text",
            toolId="timeline.propose_add_prompt_segment",
        )
    authored_sha = sha256(authored.encode("utf-8")).hexdigest()
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    # SINGLE-STORE: the duration fence reads SceneTimelineMaster window
    # durations (fallback: scene row duration_sec). The retired legacy
    # directorTimeline.duration_sec is frozen COW data and fenced a 45s scene
    # at 5s — never a fence authority.
    master = bundle["master"]
    _refuse_timed_prompt_while_rendering(master, "timeline.propose_add_prompt_segment")
    scene_row = store.get_scene(ctx.db, ctx.project_id, scene_id)
    duration = _master_scene_duration(
        master,
        fallback=float(getattr(scene_row, "duration_sec", None) or 5.0),
    )
    # BOT2_DURATION_FENCE: Timeline scene duration beats CD estimate / coverage claim.
    # REFUSE when requested length OR text coverage exceeds scene duration.
    # Never silently clamp (Creator Spec Fidelity / MATRIX Case C).
    start_arg = float(args["start"]) if args.get("start") is not None else 0.0
    length_arg = float(args["length"]) if args.get("length") is not None else None
    coverage = _timed_prompt_requested_coverage_sec(authored)
    over_bits: list[str] = []
    if length_arg is not None and length_arg > duration + 1e-6:
        over_bits.append(f"length={length_arg:g}s")
    if length_arg is not None and (start_arg + length_arg) > duration + 1e-6:
        over_bits.append(f"start+length={start_arg:g}+{length_arg:g}s")
    if coverage is not None and coverage > duration + 1e-6:
        over_bits.append(f"text coverage ends at {coverage:g}s")
    if over_bits:
        detail = ", ".join(over_bits)
        raise _argument_error(
            f"Timed Prompt requested coverage exceeds this scene's duration {duration:g}s "
            f"({detail}). Shorten the prompt to fit the scene, or extend/split the scene "
            f"before placing it. I will not silently compress a longer Timed Prompt into "
            f"{duration:g}s.",
            field="length",
            toolId="timeline.propose_add_prompt_segment",
        )
    # SINGLE-STORE: Master is sole SoT — write batch.promptSegments directly.
    # Do NOT call reconcile_legacy_to_master (forbidden on live CD path).
    # Do NOT write director_tl.prompt_segments (legacy store retired).
    start = float(args["start"]) if args.get("start") is not None else 0.0
    length = float(args.get("length") or min(2.0, duration))
    batch_target, master_seg_id = _upsert_master_timed_prompt(
        master,
        text=authored,
        start=max(0.0, start),
        length=max(0.1, length),
        legacy_id=None,
        user_direction=str(args.get("userDirection")) if args.get("userDirection") is not None else None,
        production_prompt=str(args.get("productionPrompt")) if args.get("productionPrompt") is not None else None,
        dialogue=str(args.get("dialogue")) if args.get("dialogue") is not None else None,
        weight=float(args.get("weight") if args.get("weight") is not None else 1.0),
        explicit_start=args.get("start") is not None,
    )
    segment_id = master_seg_id
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        master,
        workspace=workspace,
        bump_revision=True,
    )
    wrote = True
    revision_after = revision_before + 1
    if wrote:
        try:
            from ....production_events import ACTOR_CODIRECTOR, record_production_event

            record_production_event(
                ctx.db,
                project_id=ctx.project_id,
                scene_id=scene_id,
                event_type="timeline.prompt_added",
                actor=ACTOR_CODIRECTOR,
                actor_detail="tool:timeline.propose_add_prompt_segment",
                subject_kind="prompt_segment",
                subject_id=segment_id,
                summary=f"Timed prompt added at {round(start, 3)}s for {round(length, 3)}s",
                payload={"segmentId": segment_id, "start": start, "length": length},
            )
        except Exception:  # noqa: BLE001 - event recording never breaks the operation
            pass

    stored_text = ""
    stored_sha = ""
    verified = False
    try:
        reloaded = service.load_timeline_bundle(ctx.db, ctx.project_id, scene_id)
        rel_master = reloaded.get("master") if isinstance(reloaded, dict) else None
        if rel_master is None and isinstance(reloaded, dict):
            rel_master = (reloaded.get("bundle") or {}).get("master")
        stored_text = _master_prompt_text_by_id(rel_master or master, segment_id)
        stored_sha = sha256(stored_text.encode("utf-8")).hexdigest() if stored_text else ""
        verified = bool(
            str(reloaded.get("sceneId") or scene_id) == scene_id
            and stored_text.strip()
            and stored_sha == authored_sha
        )
    except Exception:  # noqa: BLE001 - verify failure is reported, not hidden
        verified = False

    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "promptSeg",
        "selectionId": segment_id,
        "openRightTab": "inspector",
    }
    return {
        "ok": bool(verified),
        "verified": verified,
        "segmentId": segment_id,
        "timelineRevision": revision_after,
        "authoredSha256": authored_sha,
        "storedSha256": stored_sha,
        "destinationSceneId": scene_id,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "mock": False,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_add_prompt_segment",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={
                "segmentId": segment_id,
                "textLen": len(authored),
                "textSha256": authored_sha,
                "storedSha256": stored_sha,
                "verified": verified,
            },
        ),
    }


def preview_build_shot(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    length = float(args.get("length") or 5.0)
    return _preview_mutation(
        ctx,
        args,
        summary=f"Add image clip (asset {args.get('assetId') or '?'}) for {length}s" + (" with matched timed prompt" if args.get("prompt") or args.get("productionPrompt") or args.get("dialogue") else ""),
        lines=["Sequential placement after the last clip when start is omitted.", "Stores userDirection separately from the refined production prompt.", "Does not invent library assets."],
    )


def apply_build_shot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Place an image as a Film Timeline reference. Does not render."""
    from ....film_timeline.insertion import add_to_timeline
    from ....film_timeline.orchestrator import update_timed_prompt

    bundle = _require_bundle(ctx, args)
    scene_id = str(bundle["sceneId"])
    asset_id = str(args.get("assetId") or "").strip()
    if not asset_id:
        raise _argument_error("assetId is required.", parameter="assetId")
    placed = add_to_timeline(
        ctx.db,
        ctx.project_id,
        scene_id,
        media_type="image",
        asset_id=asset_id,
        target_track_type="reference",
        label=str(args.get("label") or "Image"),
        shot_id=str(args.get("shotId") or "") or None,
    )
    prompt = str(args.get("prompt") or args.get("text") or "").strip()
    shot_id = str(args.get("shotId") or "")
    if prompt and shot_id:
        update_timed_prompt(ctx.db, ctx.project_id, scene_id, shot_id, prompt)
    return {"ok": bool(placed.get("ok")), "rendered": False, "filmTimeline": True, **placed}

def preview_propose_generate_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scope = str(args.get("scope") or "full")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Generate scene batches (scope={scope}).",
        lines=["Runs preflight first.", "Submits generation jobs with immutable execution snapshots."],
    )


def apply_propose_generate_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = (ctx, args)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Generate Shot renders a Timeline shot. Writing a Timed Prompt does not render.",
        "mock": False,
    }


def preview_propose_repair_range(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = str(args.get("batchBlockId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Add repair range on batch {batch_id}.",
        lines=["Honest InPaint strategy disclosure.", "Overlap policy enforced server-side."],
    )


def apply_propose_repair_range(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    batch_id = str(args.get("batchBlockId") or "")
    if not batch_id:
        raise _argument_error("batchBlockId is required.", parameter="batchBlockId")
    result = orchestrator.add_repair_range(
        ctx.db,
        ctx.project_id,
        scene_id,
        batch_id,
        {
            "start": args.get("start", 0),
            "length": args.get("length", 1),
            "label": args.get("label") or "Co-Director repair",
            "inPaintStrategy": args.get("inPaintStrategy") or "range_replacement",
        },
        policy=args.get("policy"),
    )
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    return {
        **result,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_repair_range",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"batchBlockId": batch_id},
        ),
    }


def preview_propose_cancel(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    action = str(args.get("action") or "stop_remaining_scene_jobs")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Cancel scene jobs ({action}).",
        lines=["Preserves completed batches when configured.", "Hosted cancel support disclosed honestly."],
    )


def apply_propose_cancel(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    result = orchestrator.cancel_scene(
        ctx.db,
        ctx.project_id,
        scene_id,
        CancelRequest(
            action=args.get("action") or "stop_remaining_scene_jobs",
            batchBlockIds=list(args.get("batchBlockIds") or []),
        ),
    ).model_dump()
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    return {
        **result,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_cancel",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
        ),
    }


def preview_propose_retake(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = str(args.get("batchBlockId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Retake batch {batch_id}.",
        lines=["Creates a new immutable execution snapshot.", "Prior snapshots remain preserved."],
    )


def apply_propose_retake(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = (ctx, args)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Regenerate a segment or Continue Shot. Batch retake is no longer a Timeline action.",
        "mock": False,
    }


def preview_attach_optional_reference(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    role = str(args.get("role") or "supporting")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Attach optional {role} reference to batch.",
        lines=["Non-blocking supporting reference.", store.OPTIONAL_REFS_POLICY_NOTE],
    )


def apply_attach_optional_reference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    batch_id = str(args.get("batchBlockId") or "")
    if not batch_id:
        raise _argument_error("batchBlockId is required.", parameter="batchBlockId")
    master: SceneTimelineMaster = bundle["master"]
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        raise _target_not_found("Batch Block not found.", batchBlockId=batch_id)
    ref = {
        "role": str(args.get("role") or "supporting"),
        "assetId": args.get("assetId"),
        "label": args.get("label") or "",
        "required": False,
        "optional": True,
    }
    batch.references = list(batch.references or []) + [ref]
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        master,
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "batchBlockId": batch_id,
        "reference": ref,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.attach_optional_reference",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"batchBlockId": batch_id},
        ),
    }


def _find_batch_or_error(master: SceneTimelineMaster, batch_id: str):
    batch = next((item for item in master.batchBlocks if item.id == batch_id), None)
    if not batch:
        raise _target_not_found("Batch Block not found.", batchBlockId=batch_id)
    return batch


def _find_repair_or_error(batch: Any, repair_id: str):
    repair = next((item for item in (batch.repairRanges or []) if item.id == repair_id), None)
    if not repair:
        raise _target_not_found("Inpaint repair range not found.", repairId=repair_id, batchBlockId=batch.id)
    return repair


def _default_inpaint_label(batch: Any, repair_start: float, repair_length: float) -> str:
    return f"{batch.label} Inpaint {repair_start:.1f}-{repair_start + repair_length:.1f}s"


def _build_inpaint_metadata(master: SceneTimelineMaster, batch: Any, repair: Any, args: dict[str, Any]) -> dict[str, Any]:
    requested = str(args.get("requestedStrategy") or args.get("inPaintStrategy") or repair.inPaintStrategy or "range_replacement")
    if requested not in _INPAINT_STRATEGIES:
        raise _argument_error(
            f"requestedStrategy must be one of: {', '.join(sorted(_INPAINT_STRATEGIES))}.",
            parameter="requestedStrategy",
            requestedStrategy=requested,
        )
    disclosure = disclose_inpaint_strategy(args.get("generatorId") or batch.generatorId, requested)  # type: ignore[arg-type]
    mask_type = str(args.get("maskType") or "include").strip()
    if mask_type not in _MASK_TYPES:
        raise _argument_error(
            f"maskType must be one of: {', '.join(sorted(_MASK_TYPES))}.",
            parameter="maskType",
            maskType=mask_type,
        )
    active_tool = str(args.get("activeTool") or "brush").strip()
    if active_tool not in _MASK_TOOLS:
        raise _argument_error(
            f"activeTool must be one of: {', '.join(sorted(_MASK_TOOLS))}.",
            parameter="activeTool",
            activeTool=active_tool,
        )
    selection_source = str(args.get("selectionSource") or "repair").strip()
    if selection_source not in _SELECTION_SOURCES:
        raise _argument_error(
            f"selectionSource must be one of: {', '.join(sorted(_SELECTION_SOURCES))}.",
            parameter="selectionSource",
            selectionSource=selection_source,
        )
    absolute_start = _batch_absolute_start(master, batch.id) + float(repair.start or 0.0)
    current = repair.metadata.get("inpaint") if isinstance(repair.metadata, dict) else None
    return {
        "inpaint": {
            **(current if isinstance(current, dict) else {}),
            "prompt": str(args.get("prompt") or "").strip(),
            "maskType": mask_type,
            "feather": int(args.get("feather") or 8),
            "generatorId": str(args.get("generatorId") or batch.generatorId or "") or None,
            "requestedStrategy": requested,
            "resolvedStrategy": disclosure["strategy"],
            "strategyDisclosure": disclosure,
            "preservationLocks": {
                "preserveAudio": bool(args.get("preserveAudio", True)),
                "preserveMotion": bool(args.get("preserveMotion", True)),
                "preserveComposition": bool(args.get("preserveComposition", True)),
            },
            "mask": {
                "activeTool": active_tool,
                "revision": int(args.get("maskRevision") or 0),
                "strokes": _parse_mask_strokes(args.get("maskStrokesJson")),
            },
            "selectionSource": selection_source,
            "range": {
                "start": absolute_start,
                "length": float(repair.length or 0.0),
                "relativeStart": float(repair.start or 0.0),
            },
            "updatedAt": _now(),
        }
    }


def preview_propose_layout_preset(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    preset = str(args.get("preset") or "balanced")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Change timeline layout preset to {preset}.",
        lines=["After approval, Co-Director focuses the Viewer layout.", "Intent is persisted on the scene workspace and mirrored to the web client."],
    )


def apply_propose_layout_preset(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    ws, layout = _set_layout_state(workspace, viewerPreset=str(args.get("preset") or "balanced"))
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=ws,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "viewerPreset": layout["viewerPreset"],
        "trackDensity": layout["trackDensity"],
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        **layout,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_layout_preset",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"preset": layout["viewerPreset"]},
        ),
    }


def preview_propose_viewer_fullscreen(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    enabled = bool(args.get("enabled"))
    return _preview_mutation(
        ctx,
        args,
        summary=f"{'Enter' if enabled else 'Exit'} timeline viewer fullscreen.",
        lines=["Approval emits a Viewer directive for the current browser session.", "The chosen fullscreen intent is also stored on the scene workspace."],
    )


def apply_propose_viewer_fullscreen(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    ws, layout = _set_layout_state(workspace, fullscreen=bool(args.get("enabled")))
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=ws,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "fullscreen": layout["fullscreen"],
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        **layout,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_viewer_fullscreen",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"enabled": layout["fullscreen"]},
        ),
    }


def preview_propose_layout_reset(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Reset the timeline workspace layout.",
        lines=["Restores Viewer size to Large, exits fullscreen, and resets zoom.", "Leaves project media and Batch Blocks unchanged."],
    )


def apply_propose_layout_reset(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    ws, layout = _set_layout_state(workspace, viewerPreset="large", fullscreen=False, zoom=1.0, trackDensity="compact")
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=ws,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "layoutReset": True,
        "viewerPreset": layout["viewerPreset"],
        "fullscreen": layout["fullscreen"],
        "zoom": layout["zoom"],
        "trackDensity": layout["trackDensity"],
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        **layout,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_layout_reset",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
        ),
    }


def preview_propose_zoom(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    target = "delta" if args.get("delta") is not None else "zoom"
    return _preview_mutation(
        ctx,
        args,
        summary=f"Adjust timeline zoom via {target}.",
        lines=["Viewer/track zoom is clamped between 0.5x and 3x.", "Approval emits a timeline UI directive for the web client."],
    )


def apply_propose_zoom(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    current = _layout_state(workspace)
    if args.get("zoom") is not None:
        zoom = _coerce_float(args.get("zoom"), name="zoom")
    elif args.get("delta") is not None:
        zoom = current["zoom"] + _coerce_float(args.get("delta"), name="delta")
    else:
        raise _argument_error("zoom or delta is required.", parameter="zoom")
    ws, layout = _set_layout_state(workspace, zoom=max(0.5, min(3.0, zoom)))
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=ws,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "zoom": layout["zoom"],
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        **layout,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_zoom",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"zoom": layout["zoom"]},
        ),
    }


def preview_propose_add_camera(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    """Phase 0: CAMERA lane removed — Timed Prompt is sole camera authority."""
    return _preview_mutation(
        ctx,
        args,
        summary="Camera track removed — write camera direction in Timed Prompt.",
        lines=[
            "The Timeline Camera track is no longer a creator surface.",
            "Write shot movement and motion direction in Timed Prompt.",
            "Do not add a Camera clip.",
        ],
    )


def apply_propose_add_camera(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Phase 0: refuse — dual camera authority must not reappear."""
    raise _argument_error(
        "timeline.propose_add_camera is disabled. Timed Prompt is the sole camera authority — "
        "write camera direction in a Timed Prompt clip instead of adding a Camera clip.",
        parameter="tool",
        toolId="timeline.propose_add_camera",
    )


def preview_propose_update_camera(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    """Phase 0: CAMERA lane removed — Timed Prompt is sole camera authority."""
    return _preview_mutation(
        ctx,
        args,
        summary="Camera track removed — update camera direction in Timed Prompt.",
        lines=[
            "The Timeline Camera track is no longer a creator surface.",
            "Write or edit camera direction inside Timed Prompt.",
            "Do not update Camera clips.",
        ],
    )


def apply_propose_update_camera(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Phase 0: refuse — dual camera authority must not reappear."""
    raise _argument_error(
        "timeline.propose_update_camera is disabled. Timed Prompt is the sole camera authority — "
        "edit camera direction in Timed Prompt instead of updating a Camera clip.",
        parameter="tool",
        toolId="timeline.propose_update_camera",
    )


def preview_propose_add_lipsync_track(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Add a new Lip Sync track.",
        lines=["Creates a secondary lip sync lane after approval.", "Lip Sync 1 remains protected and cannot be removed."],
    )


def apply_propose_add_lipsync_track(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    lipsync = _normalize_lipsync_state(bundle.get("lipsyncTracks"))
    track = LipSyncTrack(slot=len(lipsync.tracks) + 1, label=f"Lip Sync {len(lipsync.tracks) + 1}", enabled=False)
    lipsync.tracks.append(track)
    lipsync = _normalize_lipsync_state(lipsync)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    scene.lipsync_tracks_json = dumps_lipsync_tracks(lipsync)
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "lipsyncTrack",
        "selectionId": track.id,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "trackId": track.id,
        "track": _track_summary(track),
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_add_lipsync_track",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"trackId": track.id},
        ),
    }


def preview_propose_remove_lipsync_track(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    track_id = str(args.get("trackId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Remove Lip Sync track {track_id}.",
        lines=["Removes one secondary lip sync lane.", "Protected Lip Sync 1 cannot be removed."],
    )


def apply_propose_remove_lipsync_track(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    lipsync = _normalize_lipsync_state(bundle.get("lipsyncTracks"))
    track_id = str(args.get("trackId") or "").strip()
    if not track_id:
        raise _argument_error("trackId is required.", parameter="trackId")
    track_index, track = _find_lipsync_track(lipsync.tracks, track_id)
    if track_index == 0 or track.slot == 1:
        raise _argument_error("Lip Sync 1 is protected and cannot be removed.", trackId=track_id)
    lipsync.tracks = [item for item in lipsync.tracks if item.id != track_id]
    lipsync = _normalize_lipsync_state(lipsync)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    scene.lipsync_tracks_json = dumps_lipsync_tracks(lipsync)
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    return {
        "ok": True,
        "removedTrackId": track_id,
        "removedTrackLabel": track.label,
        "timelineRevision": revision_after,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_remove_lipsync_track",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"trackId": track_id},
        ),
    }


def preview_propose_add_lipsync_clip(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Add a Lip Sync clip.",
        lines=["Adds a draft clip to the selected Lip Sync lane.", "New clips inherit track audio/character bindings when available."],
    )


def apply_propose_add_lipsync_clip(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from uuid import uuid4

    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    lipsync = _normalize_lipsync_state(bundle.get("lipsyncTracks"))
    _, track = _find_lipsync_track(lipsync.tracks, str(args.get("trackId") or "").strip() or None)
    clips = sorted(list(track.clips or []), key=lambda item: item.start)
    last = clips[-1] if clips else None
    # SINGLE-STORE: placement fence reads Master window durations (fallback:
    # scene row duration_sec), never the frozen legacy duration_sec.
    duration = _master_scene_duration(
        bundle["master"],
        fallback=float(getattr(scene, "duration_sec", None) or 5.0),
    )
    start = (
        _coerce_float(args.get("start"), name="start")
        if args.get("start") is not None
        else max(0.0, min((last.start + last.length) if last else 0.0, max(0.0, duration - 0.25)))
    )
    length = _coerce_float(args.get("length") if args.get("length") is not None else min(2.0, duration), name="length")
    if length <= 0:
        raise _argument_error("length must be > 0.", parameter="length", length=length)
    clip = LipSyncClip(
        id=f"lsc_{uuid4().hex[:8]}",
        start=start,
        length=min(duration, max(0.1, length)),
        label=str(args.get("label") or "Lip Sync Clip"),
        status="draft",
        character_id=track.character_id,
        character_name=track.character_name,
        audio_asset_id=track.audio_asset_id or scene.lipsync_audio_asset_id or scene.audio_asset_id,
        follow_policy="follow_audio",
    )
    track.enabled = True
    track.audio_asset_id = clip.audio_asset_id or track.audio_asset_id
    track.clips = clips + [clip]
    lipsync = _normalize_lipsync_state(lipsync)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    scene.lipsync_tracks_json = dumps_lipsync_tracks(lipsync)
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "lipsyncClip",
        "selectionId": clip.id,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "clipId": clip.id,
        "trackId": track.id,
        "clip": clip.model_dump(),
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_add_lipsync_clip",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"trackId": track.id, "clipId": clip.id},
        ),
    }


def preview_propose_bind_lipsync_clip(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    clip_id = str(args.get("clipId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Bind Lip Sync clip {clip_id}.",
        lines=["Connects the clip to a character, dialogue audio, and follow policy.", "The clip's lane stays approval-gated through ProposalService."],
    )


def apply_propose_bind_lipsync_clip(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    lipsync = _normalize_lipsync_state(bundle.get("lipsyncTracks"))
    clip_id = str(args.get("clipId") or "").strip()
    if not clip_id:
        raise _argument_error("clipId is required.", parameter="clipId")
    track_index, clip_index, track, clip = _find_lipsync_clip(lipsync.tracks, clip_id)
    follow_policy = str(args.get("followPolicy") or clip.follow_policy or "follow_audio").strip()
    if follow_policy not in _FOLLOW_POLICIES:
        raise _argument_error(
            f"followPolicy must be one of: {', '.join(sorted(_FOLLOW_POLICIES))}.",
            parameter="followPolicy",
            followPolicy=follow_policy,
        )
    clip.character_id = str(args.get("characterId") or clip.character_id or "").strip() or None
    clip.character_name = str(args.get("characterName") or clip.character_name or "").strip() or None
    clip.audio_asset_id = str(args.get("audioAssetId") or clip.audio_asset_id or "").strip() or None
    clip.follow_policy = follow_policy
    track.enabled = True
    if clip.character_id:
        track.character_id = clip.character_id
    if clip.character_name:
        track.character_name = clip.character_name
    if clip.audio_asset_id:
        track.audio_asset_id = clip.audio_asset_id
    track.clips[clip_index] = clip
    lipsync.tracks[track_index] = track
    lipsync = _normalize_lipsync_state(lipsync)
    scene = store.get_scene(ctx.db, ctx.project_id, scene_id)
    if not scene:
        raise _target_not_found("Scene timeline not found.", sceneId=scene_id)
    scene.lipsync_tracks_json = dumps_lipsync_tracks(lipsync)
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "lipsyncClip",
        "selectionId": clip.id,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "trackId": track.id,
        "clipId": clip.id,
        "clip": clip.model_dump(),
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_bind_lipsync_clip",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"trackId": track.id, "clipId": clip.id},
        ),
    }


def preview_propose_open_inpaint(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Open the Timeline Re-Take workspace.",
        lines=["Approval emits a Viewer directive so the web client opens video Re-Take.", "The selected video clip is preserved on the scene workspace."],
    )


def apply_propose_open_inpaint(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = store.normalize_timeline_workspace(bundle["workspace"])
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    selection_kind = str(args.get("selectionKind") or "").strip()
    selection_id = str(args.get("selectionId") or "").strip()
    if not selection_kind or not selection_id:
        raise _argument_error("selectionKind and selectionId are required.", parameter="selectionKind")
    if selection_kind not in {"videoClip", "repair"}:
        raise _argument_error("selectionKind must be videoClip or repair.", selectionKind=selection_kind)
    if selection_kind == "videoClip":
        if not any(
            str(clip.id) == selection_id
            for _batch, clip in iter_master_visual_clips(bundle["master"])
        ):
            raise _target_not_found("Video clip not found.", selectionId=selection_id)
    else:
        if not any(selection_id == repair.id for batch in bundle["master"].batchBlocks for repair in (batch.repairRanges or [])):
            raise _target_not_found("Repair range not found.", selectionId=selection_id)
    workspace["inpaintIntent"] = {
        "open": True,
        "selectionKind": selection_kind,
        "selectionId": selection_id,
        "playheadSec": args.get("playheadSec"),
        "mode": "retake",
    }
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        workspace=workspace,
        bump_revision=True,
    )
    revision_after = revision_before + 1
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "selectionKind": selection_kind,
        "selectionId": selection_id,
        "playheadSec": args.get("playheadSec"),
        "openInpaint": False,
        "openRetake": True,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "selectionKind": selection_kind,
        "selectionId": selection_id,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_open_inpaint",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"selectionKind": selection_kind, "selectionId": selection_id},
        ),
    }


def preview_propose_create_inpaint_mask(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Save inpaint mask metadata.",
        lines=["Creates or updates a repair range and stores mask metadata on that range.", "No silent native inpaint fallback is allowed; strategy disclosure is persisted."],
    )


def apply_propose_create_inpaint_mask(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    master = bundle["master"]
    batch_id = str(args.get("batchBlockId") or "").strip()
    if not batch_id:
        raise _argument_error("batchBlockId is required.", parameter="batchBlockId")
    batch = _find_batch_or_error(master, batch_id)
    repair_id = str(args.get("repairId") or "").strip() or None
    if repair_id:
        repair = _find_repair_or_error(batch, repair_id)
    else:
        start = _coerce_float(args.get("start") if args.get("start") is not None else 0.0, name="start")
        length = _coerce_float(args.get("length") if args.get("length") is not None else 1.0, name="length")
        label = str(args.get("label") or _default_inpaint_label(batch, start, length)).strip()
        result = orchestrator.add_repair_range(
            ctx.db,
            ctx.project_id,
            scene_id,
            batch_id,
            {
                "start": start,
                "length": length,
                "label": label,
                "inPaintStrategy": args.get("requestedStrategy") or args.get("inPaintStrategy") or "range_replacement",
            },
            policy=args.get("policy"),
        )
        if not result.get("ok"):
            raise _argument_error("Unable to create inpaint repair range.", batchBlockId=batch_id, result=result)
        master = _reload_master(ctx, scene_id)
        batch = _find_batch_or_error(master, batch_id)
        repair = next(
            (
                item
                for item in (batch.repairRanges or [])
                if abs(float(item.start or 0.0) - start) < 0.001 and abs(float(item.length or 0.0) - length) < 0.001
            ),
            None,
        )
        if not repair:
            repair = batch.repairRanges[-1]
    metadata = _build_inpaint_metadata(master, batch, repair, args)
    repair.label = str(args.get("label") or repair.label or _default_inpaint_label(batch, repair.start, repair.length)).strip()
    repair.inPaintStrategy = metadata["inpaint"]["resolvedStrategy"]  # type: ignore[assignment]
    repair.metadata = metadata
    result = orchestrator.touch_batch_config(
        ctx.db,
        ctx.project_id,
        scene_id,
        batch.id,
        {
            **({"generatorId": args.get("generatorId")} if args.get("generatorId") else {}),
            "repairRanges": [item.model_dump() for item in batch.repairRanges],
        },
    )
    if not result.get("ok"):
        raise _argument_error("Unable to save inpaint mask metadata.", batchBlockId=batch_id, result=result)
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "selectionKind": "repair",
        "selectionId": repair.id,
        "openInpaint": True,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "batchBlockId": batch.id,
        "repairId": repair.id,
        "resolvedStrategy": metadata["inpaint"]["resolvedStrategy"],
        "strategyDisclosure": metadata["inpaint"]["strategyDisclosure"],
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_create_inpaint_mask",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"batchBlockId": batch.id, "repairId": repair.id},
        ),
    }


def preview_propose_execute_inpaint(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = str(args.get("batchBlockId") or "")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Execute inpaint for batch {batch_id}.",
        lines=["Queues batch generation using the approved inpaint repair metadata.", "The repair range is marked queued with an immutable execution snapshot id."],
    )


def apply_propose_execute_inpaint(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = (ctx, args)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Regenerate the Film Timeline segment. Inpaint no longer submits a batch.",
        "mock": False,
    }

def preview_propose_approve_inpaint(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Approve an inpaint candidate.",
        lines=["Approves a batch candidate and records the approval on the selected repair range.", "No silent swap occurs without explicit approval."],
    )


def apply_propose_approve_inpaint(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    batch_id = str(args.get("batchBlockId") or "").strip()
    repair_id = str(args.get("repairId") or "").strip()
    candidate_id = str(args.get("candidateId") or "").strip()
    if not batch_id or not repair_id or not candidate_id:
        raise _argument_error("batchBlockId, repairId, and candidateId are required.")
    result = orchestrator.approve_candidate(ctx.db, ctx.project_id, scene_id, batch_id, candidate_id)
    if not result.get("ok"):
        raise _argument_error("Unable to approve inpaint candidate.", batchBlockId=batch_id, candidateId=candidate_id, result=result)
    master = _reload_master(ctx, scene_id)
    batch = _find_batch_or_error(master, batch_id)
    repair = _find_repair_or_error(batch, repair_id)
    repair.status = "approved"
    repair.candidateId = candidate_id
    repair.executionSnapshotId = (result.get("approvedClip") or {}).get("executionSnapshotId")
    inpaint_meta = repair.metadata.get("inpaint") if isinstance(repair.metadata, dict) else {}
    if not isinstance(inpaint_meta, dict):
        inpaint_meta = {}
    inpaint_meta["lastApprovedCandidateId"] = candidate_id
    repair.metadata = {**repair.metadata, "inpaint": inpaint_meta}
    orchestrator.touch_batch_config(
        ctx.db,
        ctx.project_id,
        scene_id,
        batch_id,
        {"repairRanges": [item.model_dump() for item in batch.repairRanges]},
    )
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "repair",
        "selectionId": repair.id,
        "openInpaint": True,
        "openRightTab": "inspector",
    }
    return {
        **result,
        "repairId": repair.id,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_approve_inpaint",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"batchBlockId": batch_id, "repairId": repair.id, "candidateId": candidate_id},
        ),
    }


def preview_propose_restore_inpaint(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Restore the prior inpaint-approved candidate.",
        lines=["Re-approves the previously approved batch candidate when available.", "Requires existing lineage recorded on the repair metadata."],
    )


def apply_propose_restore_inpaint(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    master = bundle["master"]
    batch_id = str(args.get("batchBlockId") or "").strip()
    repair_id = str(args.get("repairId") or "").strip()
    if not batch_id or not repair_id:
        raise _argument_error("batchBlockId and repairId are required.")
    batch = _find_batch_or_error(master, batch_id)
    repair = _find_repair_or_error(batch, repair_id)
    inpaint_meta = repair.metadata.get("inpaint") if isinstance(repair.metadata, dict) else {}
    previous = inpaint_meta.get("previousApprovedClip") if isinstance(inpaint_meta, dict) else None
    candidate_id = str(args.get("candidateId") or (previous or {}).get("candidateId") or "").strip()
    if not candidate_id:
        raise _argument_error("No previous approved candidate is recorded for this repair.", repairId=repair_id)
    result = orchestrator.approve_candidate(ctx.db, ctx.project_id, scene_id, batch_id, candidate_id)
    if not result.get("ok"):
        raise _argument_error("Unable to restore the prior approved candidate.", candidateId=candidate_id, result=result)
    master = _reload_master(ctx, scene_id)
    batch = _find_batch_or_error(master, batch_id)
    repair = _find_repair_or_error(batch, repair_id)
    repair.status = "restored"
    repair.candidateId = candidate_id
    repair.executionSnapshotId = (result.get("approvedClip") or {}).get("executionSnapshotId")
    if isinstance(inpaint_meta, dict):
        inpaint_meta["lastRestoredCandidateId"] = candidate_id
        repair.metadata = {**repair.metadata, "inpaint": inpaint_meta}
    orchestrator.touch_batch_config(
        ctx.db,
        ctx.project_id,
        scene_id,
        batch_id,
        {"repairRanges": [item.model_dump() for item in batch.repairRanges]},
    )
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    ui_focus = {
        "target": "trackItem",
        "sceneId": scene_id,
        "selectionKind": "repair",
        "selectionId": repair.id,
        "openInpaint": True,
        "openRightTab": "inspector",
    }
    return {
        **result,
        "repairId": repair.id,
        "restoredCandidateId": candidate_id,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_restore_inpaint",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"batchBlockId": batch_id, "repairId": repair.id, "candidateId": candidate_id},
        ),
    }


def preview_propose_new_scene_take(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_mutation(
        ctx,
        args,
        summary="Create a new whole-scene Take and render every batch from start to finish.",
        lines=[
            "Uses the scene's current production configuration (snapshot at launch).",
            "This is New Take, not Re-Take. Earlier Takes stay intact.",
        ],
    )


def apply_propose_new_scene_take(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....director_timeline_w46.scene_takes import start_new_take

    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    result = start_new_take(ctx.db, ctx.project_id, scene_id)
    if not result.get("ok"):
        raise _argument_error(str(result.get("message") or result.get("error") or "New Take failed."), result=result)
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    take = result.get("take") or {}
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "takeId": take.get("id"),
        "takeLabel": take.get("label"),
        "openRightTab": "inspector",
    }
    return {
        **result,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_new_scene_take",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"takeId": take.get("id"), "takeLabel": take.get("label")},
        ),
    }


def preview_propose_make_scene_take_current(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    label = str(args.get("takeLabel") or args.get("takeId") or "the selected take")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Make {label} the current whole-scene Take.",
        lines=["Preview Monitor and Publish will use this Take.", "Other Takes stay in history."],
    )


def apply_propose_make_scene_take_current(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....director_timeline_w46.scene_takes import make_current_take

    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision_before = int(workspace.get("timelineRevision") or 1)
    take = _resolve_scene_take_arg(bundle["master"], args)
    if take is None:
        raise _argument_error("Name a Take (for example Take B).", parameter="takeLabel")
    result = make_current_take(ctx.db, ctx.project_id, scene_id, take.id)
    if not result.get("ok"):
        raise _argument_error(str(result.get("message") or "Could not make that Take current."), result=result)
    revision_after = _persist_revision_bump(ctx, scene_id, workspace, revision_before)
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "takeId": take.id,
        "takeLabel": take.label,
        "openRightTab": "inspector",
    }
    return {
        **result,
        "timelineRevision": revision_after,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_make_scene_take_current",
            scene_id=scene_id,
            revision_before=revision_before,
            revision_after=revision_after,
            extra={"takeId": take.id, "takeLabel": take.label},
        ),
    }


def preview_propose_preview_scene_take(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    label = str(args.get("takeLabel") or args.get("takeId") or "the selected take")
    return _preview_mutation(
        ctx,
        args,
        summary=f"Load {label} into the Preview Monitor.",
        lines=["Does not change the current Take or published master."],
    )


def apply_propose_preview_scene_take(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = _require_bundle(ctx, args)
    workspace = bundle["workspace"]
    _check_revision(args, workspace)
    scene_id = bundle["sceneId"]
    revision = int(workspace.get("timelineRevision") or 1)
    take = _resolve_scene_take_arg(bundle["master"], args)
    if take is None:
        raise _argument_error("Name a Take to preview (for example Take B).", parameter="takeLabel")
    ui_focus = {
        "target": "viewer",
        "sceneId": scene_id,
        "takeId": take.id,
        "takeLabel": take.label,
        "openRightTab": "inspector",
    }
    return {
        "ok": True,
        "takeId": take.id,
        "takeLabel": take.label,
        "previewOnly": True,
        "uiFocus": ui_focus,
        "_uiFocus": ui_focus,
        "timelineRevision": revision,
        "_evidence": _receipt(
            ctx,
            tool_id="timeline.propose_preview_scene_take",
            scene_id=scene_id,
            revision_before=revision,
            revision_after=revision,
            extra={"takeId": take.id, "takeLabel": take.label},
        ),
    }

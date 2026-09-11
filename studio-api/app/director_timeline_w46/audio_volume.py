"""Canonical in-process volume/mute command for Director Timeline audio/SFX clips.

This module is the approved write path for Co-Director and UI volume changes:
- volume is the single gain authority (0.0-1.0, persisted clip-level)
- muted is an independent boolean that never rewrites volume
- effective gain = 0 if muted else clamp(volume, 0, 1)
- a volume change applied to a muted clip unmutes it (product rule, mirrors the
  Timeline UI); an explicit ``muted=`` argument in the same call always wins
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..director_timeline import DirectorTimeline, TimelineClip, dumps_director_timeline_preserving_embedded, parse_director_timeline
from ..db import Scene


TRACK_KIND_MAP: dict[str, str] = {
    "music": "audio",
    "audio": "audio",
    "sfx": "sfx",
}


def _clamp_volume(value: float | None) -> float:
    if value is None:
        return 1.0
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def _percent_to_volume(percent: float | None) -> float | None:
    if percent is None:
        return None
    try:
        return _clamp_volume(float(percent) / 100.0)
    except (TypeError, ValueError):
        return None


def _apply_to_clip(clip: TimelineClip, *, volume: float | None, muted: bool | None) -> bool:
    changed = False
    if volume is not None and abs(clip.volume - volume) > 1e-9:
        clip.volume = volume
        changed = True
    if muted is not None:
        # Explicit mute instruction always wins.
        if clip.muted != muted:
            clip.muted = muted
            changed = True
    elif volume is not None and clip.muted:
        # Canonical product rule: setting the volume on a muted clip unmutes it
        # (mirrors the Timeline UI handler, which unmutes on any volume write,
        # even when the target equals the current value). Mute toggles never
        # rewrite volume.
        clip.muted = False
        changed = True
    return changed


def set_timeline_audio_volume(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    clip_id: Optional[str] = None,
    track: Optional[str] = None,
    volume_percent: Optional[float] = None,
    muted: Optional[bool] = None,
) -> dict[str, Any]:
    """Canonical volume/mute write path for Director Timeline audio/SFX clips.

    Loads the scene's persisted DirectorTimeline, applies the requested change
    to the targeted clip(s), and writes the blob back via the same
    `dumps_director_timeline_preserving_embedded` path used by the legacy
    PUT /projects/{project_id}/scenes/{scene_id}/director endpoint so embedded
    W46 timelineMaster / timelineWorkspace state is preserved.

    Args:
        db: SQLAlchemy session.
        project_id: Project id.
        scene_id: Scene id.
        clip_id: Exact clip id to change. If omitted, ``track`` must be provided
            and the change applies to every clip on that track.
        track: ``"music"``/``"audio"`` or ``"sfx"``. Required when ``clip_id``
            is omitted; ignored when ``clip_id`` is provided.
        volume_percent: 0-100, mapped to 0.0-1.0 and clamped. ``None`` leaves
            volume unchanged.
        muted: ``True``/``False`` to set mute state. ``None`` leaves mute
            unchanged. Muting never rewrites the stored ``volume``.

    Returns:
        dict with ``ok``, ``updatedClips`` summaries, and the count changed.
    """
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        return {"ok": False, "error": "SCENE_NOT_FOUND"}

    tl = parse_director_timeline(
        scene.director_json,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )

    target_volume = _percent_to_volume(volume_percent)

    updated: list[dict[str, Any]] = []
    changed = False

    if clip_id:
        audio_ids = {c.id for c in tl.audio_clips}
        for clip in tl.audio_clips + tl.sfx_clips:
            if clip.id == clip_id:
                if _apply_to_clip(clip, volume=target_volume, muted=muted):
                    changed = True
                track_name = "audio" if clip.id in audio_ids else "sfx"
                updated.append({
                    "id": clip.id,
                    "track": track_name,
                    "volume": clip.volume,
                    "muted": clip.muted,
                })
                break
        else:
            return {"ok": False, "error": "CLIP_NOT_FOUND"}
    else:
        kind = TRACK_KIND_MAP.get(track or "")
        if kind == "audio":
            target_clips = tl.audio_clips
            track_name = "audio"
        elif kind == "sfx":
            target_clips = tl.sfx_clips
            track_name = "sfx"
        else:
            return {"ok": False, "error": "TRACK_REQUIRED"}

        for clip in target_clips:
            if _apply_to_clip(clip, volume=target_volume, muted=muted):
                changed = True
            updated.append({
                "id": clip.id,
                "track": track_name,
                "volume": clip.volume,
                "muted": clip.muted,
            })

    if changed:
        scene.director_json = dumps_director_timeline_preserving_embedded(tl, scene.director_json)
        db.add(scene)
        db.commit()

    return {"ok": True, "changed": changed, "updatedClips": updated}

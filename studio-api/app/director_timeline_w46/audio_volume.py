"""Canonical in-process volume/mute command for Timeline Master audio/SFX clips.

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

from .master_clip_mutate import clip_matches, flatten_attr
from .service import load_timeline_bundle
from . import store as timeline_store


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


def _apply_to_clip(clip: Any, *, volume: float | None, muted: bool | None) -> bool:
    changed = False
    if volume is not None and abs(float(getattr(clip, "volume", 1.0) or 1.0) - volume) > 1e-9:
        clip.volume = volume
        changed = True
    if muted is not None:
        if bool(getattr(clip, "muted", False)) != muted:
            clip.muted = muted
            changed = True
    elif volume is not None and bool(getattr(clip, "muted", False)):
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
    """Canonical volume/mute write path for Master audio/SFX clips."""
    bundle = load_timeline_bundle(db, project_id, scene_id)
    if not bundle.get("ok"):
        return {"ok": False, "error": "SCENE_NOT_FOUND"}
    master = bundle["master"]

    target_volume = _percent_to_volume(volume_percent)
    audio_clips = flatten_attr(master, "audioClips")
    sfx_clips = flatten_attr(master, "sfxClips")

    updated: list[dict[str, Any]] = []
    changed = False

    if clip_id:
        audio_ids = {str(getattr(c, "id", "") or "") for c in audio_clips}
        audio_legacy = {str(getattr(c, "legacyClipId", "") or "") for c in audio_clips}
        found = False
        for clip in audio_clips + sfx_clips:
            if not clip_matches(clip, clip_id):
                continue
            found = True
            if _apply_to_clip(clip, volume=target_volume, muted=muted):
                changed = True
            cid = str(getattr(clip, "id", "") or "")
            legacy = str(getattr(clip, "legacyClipId", "") or "")
            track_name = "audio" if (cid in audio_ids or legacy in audio_legacy) else "sfx"
            updated.append({
                "id": legacy or cid,
                "track": track_name,
                "volume": clip.volume,
                "muted": clip.muted,
            })
            break
        if not found:
            return {"ok": False, "error": "CLIP_NOT_FOUND"}
    else:
        kind = TRACK_KIND_MAP.get(track or "")
        if kind == "audio":
            target_clips = audio_clips
            track_name = "audio"
        elif kind == "sfx":
            target_clips = sfx_clips
            track_name = "sfx"
        else:
            return {"ok": False, "error": "TRACK_REQUIRED"}

        for clip in target_clips:
            if _apply_to_clip(clip, volume=target_volume, muted=muted):
                changed = True
            cid = str(getattr(clip, "legacyClipId", None) or getattr(clip, "id", "") or "")
            updated.append({
                "id": cid,
                "track": track_name,
                "volume": clip.volume,
                "muted": clip.muted,
            })

    if changed:
        timeline_store.save_master(db, project_id, scene_id, master, bump_revision=True)

    return {"ok": True, "changed": changed, "updatedClips": updated}

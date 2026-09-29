"""The only Timeline media insertion command."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .contracts import FilmTimeline, MediaClip, PendingPlacement, ReferenceAsset
from .store import require_film, save_film

log = logging.getLogger("adept.film_timeline")

_AUDIO_ROLES = {
    "voice": "voice",
    "dialogue": "dialogue",
    "narration": "narration",
    "music": "music",
    "ambience": "ambience",
    "audio": "generic",
}
_DIRECT = {
    "image": "reference",
    "video": "video",
    "sfx": "sfx",
    **{key: "audio" for key in _AUDIO_ROLES},
}


def _lane(media_type: str, target: str | None) -> tuple[str, str] | None:
    explicit = (target or "").strip().lower()
    kind = (media_type or "").strip().lower()
    if explicit in {"video", "sfx", "reference"}:
        return explicit, ""
    if explicit in _AUDIO_ROLES:
        return "audio", _AUDIO_ROLES[explicit]
    if explicit == "audio":
        return "audio", _AUDIO_ROLES.get(kind, "generic")
    if kind in {"video", "sfx", "reference"}:
        return kind, ""
    if kind in _AUDIO_ROLES:
        return "audio", _AUDIO_ROLES[kind]
    if kind == "audio":
        return "audio", "generic"
    return None


def add_to_timeline(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    media_type: str,
    asset_id: str,
    target_track_type: str | None = None,
    start_time: float = 0.0,
    duration_sec: float | None = None,
    shot_id: str | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asset = str(asset_id or "").strip()
    if not asset:
        return {"ok": False, "error": "ASSET_ID_REQUIRED", "message": "Choose a saved asset before adding it to Timeline."}
    routed = _lane(media_type, target_track_type)
    if routed is None:
        film = require_film(db, project_id, scene_id)
        pending = PendingPlacement(assetId=asset, label=label or "", reason="ambiguous_media")
        film.pendingPlacements.append(pending)
        save_film(db, project_id, scene_id, film)
        return {
            "ok": False,
            "error": "AMBIGUOUS_TRACK",
            "message": "Choose Audio or SFX for this clip.",
            "pendingPlacementId": pending.id,
        }
    lane, role = routed

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    meta = dict(metadata or {})
    meta["mediaType"] = media_type
    if role:
        meta["role"] = role
    if lane == "reference":
        ref = ReferenceAsset(
            type="image",
            assetId=asset,
            label=label or "Reference",
            source="add-to-timeline",
            inherited=False,
        )
        if shot is None:
            film.references.append(ref)
        else:
            shot.state.references.append(ref)
        save_film(db, project_id, scene_id, film)
        log.info(
            "film-timeline insert reference project=%s scene=%s shot=%s asset=%s",
            project_id,
            scene_id,
            shot.id if shot else "",
            asset,
        )
        return {"ok": True, "lane": "reference", "reference": ref.model_dump(), "film": film.model_dump()}

    clip = MediaClip(
        trackType=lane,  # type: ignore[arg-type]
        role=role,
        assetId=asset,
        label=label or lane.title(),
        startSec=float(start_time or 0),
        durationSec=float(duration_sec or 0),
        shotId=shot.id if shot else None,
        metadata=meta,
    )
    _bucket(film, lane).append(clip)
    save_film(db, project_id, scene_id, film)
    log.info(
        "film-timeline insert project=%s scene=%s shot=%s lane=%s asset=%s clip=%s",
        project_id,
        scene_id,
        shot.id if shot else "",
        lane,
        asset,
        clip.id,
    )
    return {"ok": True, "lane": lane, "clip": clip.model_dump(), "film": film.model_dump()}


def update_clip(
    db: Session,
    project_id: str,
    scene_id: str,
    clip_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    clip = _find_clip(film, clip_id)
    if clip is None:
        return {"ok": False, "error": "CLIP_NOT_FOUND", "message": "That Timeline clip is not on this scene."}
    for key in ("startSec", "durationSec", "trimInSec", "trimOutSec", "volume", "fadeInSec", "fadeOutSec", "muted", "label"):
        if key in patch and patch[key] is not None:
            setattr(clip, key, patch[key])
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "clip": clip.model_dump(), "film": film.model_dump()}


def delete_clip(db: Session, project_id: str, scene_id: str, clip_id: str) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    for name in ("videoClips", "audio", "sfx"):
        rows = getattr(film, name)
        kept = [item for item in rows if item.id != clip_id]
        if len(kept) != len(rows):
            setattr(film, name, kept)
            save_film(db, project_id, scene_id, film)
            return {"ok": True, "film": film.model_dump()}
    return {"ok": False, "error": "CLIP_NOT_FOUND", "message": "That Timeline clip is not on this scene."}


def _bucket(film: FilmTimeline, lane: str) -> list[MediaClip]:
    if lane == "video":
        return film.videoClips
    if lane == "sfx":
        return film.sfx
    return film.audio


def _find_clip(film: FilmTimeline, clip_id: str) -> MediaClip | None:
    for name in ("videoClips", "audio", "sfx"):
        for clip in getattr(film, name):
            if clip.id == clip_id:
                return clip
    return None


def _shot(film: FilmTimeline, shot_id: str | None):
    if shot_id:
        for shot in film.shots:
            if shot.id == shot_id:
                return shot
        return None
    if len(film.shots) == 1:
        return film.shots[0]
    return film.shots[-1] if film.shots else None

"""Ingest a Timeline-published scene master into MAGI (VIDEO + AUDIO only).

Never imports batch clips, candidate takes, or continuity production artifacts.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..db import Asset
from .media import probe_media
from .sequence.store import get_sequence, save_sequence

FINISHING_ROLES = frozenset(
    {
        "published_master",
        "published_master_audio",
        "music",
        "sfx",
        "finishing_output",
    }
)
_BATCH_NAME_RE = re.compile(r"\bbatch\s*\d+\b", re.IGNORECASE)

ProbeFn = Callable[[str | Path], dict[str, Any]]


def _clip_id(prefix: str) -> str:
    return f"clip_{prefix}_{uuid.uuid4().hex[:8]}"


def is_production_artifact(clip: dict[str, Any]) -> bool:
    role = str(clip.get("ingestRole") or "").strip()
    if role in FINISHING_ROLES:
        return False
    if clip.get("batchBlockId") or clip.get("generationId") or clip.get("takeId"):
        return True
    if _BATCH_NAME_RE.search(str(clip.get("name") or "")):
        return True
    return True


def _keep_finishing_clip(clip: dict[str, Any], scene_id: str, tracks_by_id: dict[str, Any]) -> bool:
    role = str(clip.get("ingestRole") or "").strip()
    track = tracks_by_id.get(str(clip.get("trackId") or "")) or {}
    track_kind = str(track.get("kind") or "")
    clip_scene = str(clip.get("sceneId") or "").strip()
    if clip_scene and clip_scene != scene_id:
        return False
    if track_kind in {"music", "sfx"}:
        return True
    if role not in {"music", "sfx", "finishing_output"}:
        return False
    if role in {"music", "sfx"} and track_kind not in {role, "audio"}:
        return role == "finishing_output"
    return True


def bound_published_master(
    db: Session,
    project_id: str,
    requested_scene_id: str,
) -> dict[str, Any] | None:
    """If MAGI already holds the authoritative published master, return it.

    Clip labels are not proof of publication. The clip's sceneId must resolve
    through Timeline scenePublish.publishedAssetId and match the clip asset.
    """
    current = get_sequence(project_id)
    video = next(
        (
            clip
            for clip in (current.get("clips") or [])
            if str(clip.get("ingestRole") or "") == "published_master"
        ),
        None,
    )
    if not video:
        return None
    bound_scene = str(video.get("sceneId") or "").strip()
    asset_id = str(video.get("assetId") or "").strip()
    if not bound_scene or not asset_id:
        return None
    resolved = resolve_published_master_id(db, project_id, bound_scene)
    if not resolved.get("ok"):
        return None
    if str(resolved["publishedAssetId"]) != asset_id:
        return None
    audio = next(
        (
            clip
            for clip in (current.get("clips") or [])
            if str(clip.get("ingestRole") or "") == "published_master_audio"
            and str(clip.get("assetId") or "") == asset_id
        ),
        None,
    )
    return {
        "ok": True,
        "idempotent": True,
        "alignedSceneId": bound_scene,
        "requestedSceneId": requested_scene_id,
        "sequence": current,
        "publishedAssetId": asset_id,
        "hasAudio": bool(audio),
        "durationFrames": int(video.get("durationFrames") or 0),
    }


def resolve_published_master_id(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    import json

    from ..director_timeline_w46.store import load_master
    from ..scene_service import get_scene

    scene = get_scene(db, project_id, scene_id)
    film_asset = ""
    if scene is not None:
        try:
            raw = json.loads(scene.director_json or "{}")
        except json.JSONDecodeError:
            raw = {}
        film = raw.get("filmTimeline") if isinstance(raw, dict) else None
        if isinstance(film, dict) and film.get("version"):
            film_asset = str(film.get("publishedAssetId") or "").strip()
    if film_asset:
        asset = (
            db.query(Asset)
            .filter(Asset.id == film_asset, Asset.project_id == project_id)
            .one_or_none()
        )
        if asset:
            return {"ok": True, "asset": asset, "publishedAssetId": film_asset}

    payload = load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return {
            "ok": False,
            "error": payload.get("error") or "SCENE_NOT_FOUND",
            "message": "That scene was not found.",
        }
    master = payload.get("master") or {}
    pub = master.get("scenePublish") or {}
    asset_id = str(pub.get("publishedAssetId") or "").strip()
    if not asset_id:
        return {
            "ok": False,
            "error": "PUBLISHED_MASTER_REQUIRED",
            "message": "This scene has no published master. Publish the scene on Timeline first.",
        }
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.project_id == project_id)
        .one_or_none()
    )
    if not asset:
        return {
            "ok": False,
            "error": "ASSET_OWNERSHIP",
            "message": f"Published master '{asset_id}' is not in this project.",
        }
    return {"ok": True, "asset": asset, "publishedAssetId": asset_id}


def probe_published_master(asset: Asset, *, probe: ProbeFn | None = None) -> dict[str, Any]:
    fn = probe or probe_media
    path = str(getattr(asset, "path", "") or "").strip()
    facts: dict[str, Any] = {}
    # Explicit probe hooks (tests / injected) always run. Default probe needs a real file.
    if probe is not None or (path and Path(path).is_file()):
        try:
            facts = fn(path) or {}
        except Exception:
            facts = {}
    fps = float(facts.get("fps") or 24) or 24.0
    duration = float(facts.get("duration") or 0)
    frames = int(facts.get("frames") or 0)
    if frames <= 0 and duration > 0:
        frames = max(1, int(round(duration * fps)))
    if frames <= 0:
        frames = max(1, int(round(fps)))
    return {
        "fps": fps,
        "duration": duration,
        "frames": frames,
        "width": int(facts.get("width") or 0),
        "height": int(facts.get("height") or 0),
        "hasAudio": bool(facts.get("hasAudio")),
        "probed": bool(facts),
    }


def _already_current(sequence: dict[str, Any], scene_id: str, asset_id: str) -> bool:
    clips = list(sequence.get("clips") or [])
    tracks_by_id = {str(t.get("id")): t for t in (sequence.get("tracks") or [])}
    if any(is_production_artifact(c) and str(c.get("ingestRole") or "") not in FINISHING_ROLES for c in clips):
        if not any(
            str(c.get("ingestRole") or "") == "published_master"
            and str(c.get("assetId") or "") == asset_id
            and str(c.get("sceneId") or "") == scene_id
            for c in clips
        ):
            return False
        leftover = [c for c in clips if is_production_artifact(c)]
        leftover = [
            c
            for c in leftover
            if str(c.get("ingestRole") or "")
            not in {"published_master", "published_master_audio", "music", "sfx", "finishing_output", "graphic"}
            and not str(c.get("id") or "").startswith("gfx_")
            and str((tracks_by_id.get(str(c.get("trackId") or "")) or {}).get("kind") or "")
            not in {"music", "sfx", "objects", "graphics"}
        ]
        if leftover:
            return False
    video = next(
        (
            c
            for c in clips
            if str(c.get("ingestRole") or "") == "published_master"
            and str(c.get("sceneId") or "") == scene_id
            and str(c.get("assetId") or "") == asset_id
        ),
        None,
    )
    return bool(video)


def ingest_published_master(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    probe: ProbeFn | None = None,
) -> dict[str, Any]:
    resolved = resolve_published_master_id(db, project_id, scene_id)
    if not resolved.get("ok"):
        if resolved.get("error") == "PUBLISHED_MASTER_REQUIRED":
            bound = bound_published_master(db, project_id, scene_id)
            if bound:
                return bound
        return resolved
    asset: Asset = resolved["asset"]
    asset_id = resolved["publishedAssetId"]
    facts = probe_published_master(asset, probe=probe)
    current = get_sequence(project_id)
    tracks = list(current.get("tracks") or [])
    tracks_by_id = {str(t.get("id")): t for t in tracks}
    video_track = next((t for t in tracks if t.get("kind") == "video"), None)
    audio_track = next((t for t in tracks if t.get("kind") == "audio"), None)
    if not video_track or not audio_track:
        return {
            "ok": False,
            "error": "INVALID_SEQUENCE",
            "message": "MAGI sequence is missing VIDEO or AUDIO tracks.",
        }

    if _already_current(current, scene_id, asset_id):
        return {
            "ok": True,
            "idempotent": True,
            "sequence": current,
            "publishedAssetId": asset_id,
            "hasAudio": facts["hasAudio"],
            "durationFrames": facts["frames"],
        }

    kept = [c for c in (current.get("clips") or []) if _keep_finishing_clip(c, scene_id, tracks_by_id)]
    frames = max(1, int(facts["frames"]))
    name = asset.tag or asset.filename or "Published Scene Master"
    video_clip = {
        "id": _clip_id("pubv"),
        "trackId": video_track["id"],
        "assetId": asset_id,
        "name": name,
        "startFrame": 0,
        "durationFrames": frames,
        "inPoint": 0,
        "outPoint": frames,
        "sceneId": scene_id,
        "ingestRole": "published_master",
    }
    clips = [video_clip]
    if facts["hasAudio"]:
        clips.append(
            {
                "id": _clip_id("puba"),
                "trackId": audio_track["id"],
                "assetId": asset_id,
                "name": f"{name} — Audio",
                "startFrame": 0,
                "durationFrames": frames,
                "inPoint": 0,
                "outPoint": frames,
                "sceneId": scene_id,
                "ingestRole": "published_master_audio",
            }
        )
    clips.extend(kept)
    fps = max(1, int(round(float(facts["fps"]) or float(current.get("frameRate") or 24))))
    next_seq = {
        **current,
        "frameRate": fps,
        "durationFrames": max(int(current.get("durationFrames") or 0), frames),
        "playheadFrame": 0,
        "clips": clips,
        "finishing": {
            **(current.get("finishing") if isinstance(current.get("finishing"), dict) else {}),
            "activeSceneId": scene_id,
        },
    }
    saved = save_sequence(project_id, next_seq)
    return {
        "ok": True,
        "idempotent": False,
        "sequence": saved,
        "publishedAssetId": asset_id,
        "hasAudio": facts["hasAudio"],
        "durationFrames": frames,
        "width": facts["width"],
        "height": facts["height"],
        "fps": facts["fps"],
    }

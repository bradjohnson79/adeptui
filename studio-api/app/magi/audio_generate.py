"""MAGI → Audio Studio generation with job truth and sequence placement."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job
from ..generation_tools import ops
from . import jobs as magi_jobs
from .finishing import finishing_of, merge_finishing
from .sequence.store import get_sequence, save_sequence


def _duration_for_range(project_id: str, body: dict[str, Any]) -> float:
    if body.get("duration"):
        try:
            return max(1.0, float(body["duration"]))
        except (TypeError, ValueError):
            pass
    sequence = get_sequence(project_id)
    fps = max(int(sequence.get("frameRate") or 24), 1)
    range_mode = str(body.get("range") or "entire")
    clip_id = body.get("clipId") or body.get("selectedClipId")
    if range_mode in {"clip", "selected"} and clip_id:
        clip = next((c for c in (sequence.get("clips") or []) if c.get("id") == clip_id), None)
        if clip:
            return max(1.0, min(int(clip.get("durationFrames") or fps) / fps, 16.0))
    clips = [c for c in (sequence.get("clips") or []) if c.get("assetId")]
    if clips:
        end = max(int(c.get("startFrame") or 0) + int(c.get("durationFrames") or 0) for c in clips)
        return max(1.0, min(end / fps, 16.0))
    return 8.0


def enqueue_audio(
    db: Session,
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    kind = str(body.get("kind") or "music")
    prompt = str(body.get("prompt") or "")
    user_prompt = prompt
    range_mode = str(body.get("range") or "entire")
    duration = _duration_for_range(project_id, body)
    kinds = ["music", "sfx"] if kind in {"all", "music+sfx", "both"} else [kind]
    job_ids: list[str] = []
    for one in kinds:
        fingerprint = f"audio|{one}|{range_mode}|{body.get('clipId') or ''}|{user_prompt[:80]}"
        existing = magi_jobs.find_active_duplicate(db, project_id, "magi_audio_generate", fingerprint)
        if existing is not None:
            job_ids.append(existing.id)
            continue
        job = magi_jobs.enqueue_job(
            db,
            project_id=project_id,
            kind="magi_audio_generate",
            params={
                "kind": one,
                "prompt": user_prompt,
                "userPrompt": user_prompt,
                "range": range_mode,
                "clipId": body.get("clipId") or body.get("selectedClipId"),
                "duration": duration,
                "fingerprint": fingerprint,
            },
            message=f"Queued {one} generation",
        )
        job_ids.append(job.id)
        if job.status == "queued":
            magi_jobs.start_background(job.id, lambda jid: magi_jobs.run_with_session(jid, run_audio_job))
    return {
        "ok": True,
        "queued": True,
        "kind": kind,
        "prompt": user_prompt,
        "range": range_mode,
        "duration": duration,
        "jobIds": job_ids,
        "jobId": job_ids[0] if job_ids else None,
        "duplicate": len(job_ids) > 0 and len(set(job_ids)) < len(kinds),
        "assets": "separate" if len(kinds) > 1 else "single",
        "message": (
            "Music and SFX are two separate jobs and two Library assets."
            if len(kinds) > 1
            else f"{kinds[0]} generation queued."
        ),
    }


def run_audio_job(db: Session, job: Job) -> dict[str, Any]:
    params = json.loads(job.params_json or "{}")
    kind = str(params.get("kind") or "music")
    prompt = str(params.get("userPrompt") or params.get("prompt") or "")
    duration = float(params.get("duration") or 8)
    job.stage = "Generating"
    job.message = f"Generating {kind}"
    db.commit()
    result = ops.run_audio_generate(
        db,
        project_id=job.project_id,
        kind=kind,
        prompt=prompt or (f"ambient {kind}"),
        duration_sec=duration,
    )
    asset_id = result.get("assetId")
    if not asset_id:
        raise RuntimeError("Audio Studio did not return an audio asset.")
    _place_on_sequence(job.project_id, kind, str(asset_id), params)
    current_audio = finishing_of(get_sequence(job.project_id)).get("audio") or {}
    last_ids = [str(item) for item in (current_audio.get("lastJobIds") or []) if item]
    if job.id not in last_ids:
        last_ids.append(job.id)
    finishing_patch = {
        "audio": {
            "range": params.get("range") or "entire",
            "prompt": prompt,
            "lastJobIds": last_ids,
            **({"musicAssetId": asset_id} if kind == "music" else {}),
            **({"sfxAssetId": asset_id} if kind == "sfx" else {}),
        }
    }
    merge_finishing(job.project_id, finishing_patch)
    return {
        "ok": True,
        "assetId": asset_id,
        "kind": kind,
        "prompt": prompt,
        "m29": result.get("m29"),
        "jobId": result.get("m29", {}).get("jobId") if isinstance(result.get("m29"), dict) else result.get("jobId"),
        "message": f"{kind} ready",
        "sourcePreserved": True,
    }


def _place_on_sequence(project_id: str, kind: str, asset_id: str, params: dict[str, Any]) -> None:
    sequence = get_sequence(project_id)
    tracks = list(sequence.get("tracks") or [])
    wanted = "A2" if kind == "music" else "A3"
    track = next((t for t in tracks if t.get("label") == wanted), None)
    if track is None:
        track = {
            "id": f"trk_{wanted.lower()}_{uuid.uuid4().hex[:6]}",
            "kind": "audio",
            "label": wanted,
            "order": len(tracks),
        }
        tracks.append(track)
        sequence["tracks"] = tracks
    if track is None:
        return
    fps = max(int(sequence.get("frameRate") or 24), 1)
    duration_frames = max(int(round(float(params.get("duration") or 8) * fps)), fps)
    clip_id = params.get("clipId")
    start = 0
    if clip_id:
        host = next((c for c in (sequence.get("clips") or []) if c.get("id") == clip_id), None)
        if host:
            start = int(host.get("startFrame") or 0)
            duration_frames = int(host.get("durationFrames") or duration_frames)
    clips = list(sequence.get("clips") or [])
    clips.append(
        {
            "id": f"clip_audio_{uuid.uuid4().hex[:8]}",
            "trackId": track["id"],
            "assetId": asset_id,
            "name": f"{kind.title()} — MAGI",
            "startFrame": start,
            "durationFrames": duration_frames,
            "inPoint": 0,
            "outPoint": duration_frames,
        }
    )
    sequence["clips"] = clips
    save_sequence(project_id, sequence)

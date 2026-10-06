"""Persisted Voice Creator generation jobs with honest stage progress."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import CharacterProfileRow, CharacterTraitRow

JOB_TRAIT_KEY = "voice_generate_job"
_LIVE = frozenset({"queued", "running"})

ProgressCb = Callable[[dict[str, Any]], None]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_percent(
    *,
    phase: str,
    sample_count: int,
    completed_samples: int,
) -> int:
    """Bounded stage percent. Never 100 until phase is complete."""
    n = max(1, int(sample_count or 1))
    done = max(0, min(int(completed_samples or 0), n))
    if phase == "complete":
        return 100
    if phase == "preparing":
        return 6
    if phase == "analyzing_voice":
        return 12
    if phase == "preparing_model":
        return 18
    span = 74
    base = 18
    if phase == "generating_sample":
        return min(92, base + int(span * done / n) + max(1, int((span / n) * 0.3)))
    if phase in {"finalizing_audio", "saving"}:
        credited = base + int(span * done / n)
        return 96 if done >= n else min(95, max(credited, 20))
    if phase == "failed":
        return min(92, base + int(span * done / n))
    return 8


def phase_label(phase: str, *, sample_index: int = 0, sample_count: int = 0) -> str:
    labels = {
        "queued": "Preparing recording",
        "preparing": "Preparing recording",
        "analyzing_voice": "Analyzing voice",
        "preparing_model": "Preparing model",
        "generating_sample": f"Generating sample {max(1, sample_index)} of {max(1, sample_count)}",
        "finalizing_audio": "Finalizing audio",
        "saving": "Saving to Library",
        "complete": "Voice samples ready",
        "failed": "Voice generation failed",
    }
    return labels.get(phase, "Generating voice samples")


def empty_job() -> dict[str, Any]:
    return {
        "jobId": None,
        "status": "idle",
        "phase": "idle",
        "label": "",
        "percent": 0,
        "sampleCount": 0,
        "completedSamples": 0,
        "sampleIndex": 0,
        "mode": None,
        "voiceId": None,
        "candidates": [],
        "error": None,
        "startedAt": None,
        "updatedAt": None,
    }


def _load_row(db: Session, character_id: str) -> CharacterTraitRow | None:
    return (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == JOB_TRAIT_KEY,
        )
        .order_by(CharacterTraitRow.id.desc())
        .first()
    )


def load_job(db: Session, character_id: str) -> dict[str, Any]:
    row = _load_row(db, character_id)
    if row is None or not str(row.value or "").strip():
        return empty_job()
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return empty_job()
    if not isinstance(data, dict):
        return empty_job()
    out = empty_job()
    out.update(data)
    return out


def save_job(db: Session, profile: CharacterProfileRow, job: dict[str, Any]) -> dict[str, Any]:
    job["updatedAt"] = _now()
    row = _load_row(db, profile.id)
    payload = json.dumps(job, ensure_ascii=False)
    if row is None:
        db.add(
            CharacterTraitRow(
                id=str(uuid.uuid4()),
                character_profile_id=profile.id,
                character_version_id=profile.active_version_id,
                category="voice_studio",
                key=JOB_TRAIT_KEY,
                value=payload,
                importance="canonical",
                canonical=True,
                provenance="VOICE_STUDIO",
            )
        )
    else:
        row.value = payload
        row.character_version_id = profile.active_version_id
    db.commit()
    return job


def update_job(db: Session, character_id: str, job_id: str, **fields: Any) -> dict[str, Any]:
    from .service import get_profile_by_id

    profile = db.get(CharacterProfileRow, character_id)
    if profile is None:
        get_profile_by_id(db, character_id)
        profile = db.get(CharacterProfileRow, character_id)
    job = load_job(db, character_id)
    if job.get("jobId") and job.get("jobId") != job_id:
        return job
    job.update({k: v for k, v in fields.items() if v is not None or k in {"error", "candidates", "voiceId"}})
    phase = str(job.get("phase") or "")
    job["percent"] = derive_percent(
        phase=phase,
        sample_count=int(job.get("sampleCount") or 0),
        completed_samples=int(job.get("completedSamples") or 0),
    )
    job["label"] = phase_label(
        phase,
        sample_index=int(job.get("sampleIndex") or 0),
        sample_count=int(job.get("sampleCount") or 0),
    )
    if profile is not None:
        save_job(db, profile, job)
    return job


def _public_error(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("error") or exc.detail)
        return str(detail or exc)
    return str(exc) or "Voice generation failed."


def start_job(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    mode: str,
    payload: dict[str, Any],
    sample_count: int,
) -> dict[str, Any]:
    from .service import require_owned_profile

    profile = require_owned_profile(db, project_id, character_id)
    current = load_job(db, character_id)
    if str(current.get("status") or "") in _LIVE:
        return current
    job = empty_job()
    job.update(
        {
            "jobId": str(uuid.uuid4()),
            "status": "queued",
            "phase": "preparing",
            "mode": mode,
            "sampleCount": max(1, min(int(sample_count or 1), 6)),
            "completedSamples": 0,
            "sampleIndex": 0,
            "percent": 6,
            "label": phase_label("preparing"),
            "startedAt": _now(),
        }
    )
    save_job(db, profile, job)
    thread = threading.Thread(
        target=_run_job,
        args=(project_id, character_id, job["jobId"], mode, payload),
        daemon=True,
        name=f"voice-generate-{job['jobId'][:8]}",
    )
    thread.start()
    return job


def _as_clone_body(payload: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    from .schemas import VoiceConsentCreate

    raw = payload.get("consent") or {}
    consent = VoiceConsentCreate.model_validate(raw) if isinstance(raw, dict) else raw
    return SimpleNamespace(
        name=payload.get("name") or "Cloned voice",
        reference_path=payload.get("reference_path") or payload.get("referencePath") or "",
        reference_asset_id=payload.get("reference_asset_id") or payload.get("referenceAssetId") or "",
        transcript=payload.get("transcript") or "",
        test_line=payload.get("test_line") or payload.get("testLine") or "",
        testLine=payload.get("testLine") or payload.get("test_line") or "",
        candidateCount=payload.get("sampleCount") or payload.get("candidateCount") or 1,
        sampleCount=payload.get("sampleCount") or payload.get("candidateCount") or 1,
        consent=consent,
    )


def _run_job(
    project_id: str,
    character_id: str,
    job_id: str,
    mode: str,
    payload: dict[str, Any],
) -> None:
    from ..db import SessionLocal
    from .voice_creator import clone_with_workspace, generate_voice_candidates

    db = SessionLocal()
    try:
        update_job(db, character_id, job_id, status="running", phase="preparing")

        def progress(update: dict[str, Any]) -> None:
            update_job(db, character_id, job_id, **update)

        if mode == "clone":
            result = clone_with_workspace(
                db,
                project_id,
                character_id,
                _as_clone_body(payload),
                progress_cb=progress,
            )
        else:
            result = generate_voice_candidates(
                db,
                project_id,
                character_id,
                request_body=payload,
                progress_cb=progress,
            )
        candidates = list(result.get("candidates") or [])
        ready = [c for c in candidates if (c.get("assetId") or c.get("asset_id") or (isinstance(c, str) and c))]
        if not ready:
            update_job(
                db,
                character_id,
                job_id,
                status="failed",
                phase="failed",
                error="Voice generation finished without audio.",
                candidates=candidates,
                voiceId=result.get("id"),
            )
            return
        update_job(
            db,
            character_id,
            job_id,
            status="complete",
            phase="complete",
            completedSamples=int(result.get("sampleCount") or len(ready)),
            candidates=candidates,
            voiceId=result.get("id"),
            error=None,
        )
    except Exception as exc:
        update_job(
            db,
            character_id,
            job_id,
            status="failed",
            phase="failed",
            error=_public_error(exc),
        )
    finally:
        db.close()

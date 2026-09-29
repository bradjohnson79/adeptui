"""Load and save FilmTimeline. Production reads this document only."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..runtime_session import current_runtime_session_id
from ..scene_service import get_scene
from .contracts import FilmTimeline
from .migrate import migrate_master_dict

log = logging.getLogger("adept.film_timeline")
FILM_KEY = "filmTimeline"

#: Threshold for "float dust" normalization: values within this epsilon of a
#: whole second are rounded to int. Anything larger is a genuine frame-grid echo
#: that must not be silently guessed away.
_DUST_EPSILON = 1e-4


def _normalize_duration_dust(value: float) -> float | None:
    """Return the integer second if *value* is float dust; None otherwise."""
    nearest = round(value)
    if abs(value - nearest) <= _DUST_EPSILON:
        return float(nearest)
    return None


def _normalize_film_durations(film: FilmTimeline) -> int:
    """Platform-wide idempotent normalization (Law 36). Returns change count."""
    changes = 0

    shot_plan: dict[str, list[float]] = {}
    for shot in film.shots:
        shot_plan[shot.id] = list(shot.generationPlan or [])

    for shot in film.shots:
        # Shot-level duration
        cleaned = _normalize_duration_dust(shot.durationSec)
        if cleaned is not None and cleaned != shot.durationSec:
            log.info(
                "film-timeline normalize shot=%s durationSec %.6f → %g",
                shot.id, shot.durationSec, cleaned,
            )
            shot.durationSec = cleaned
            changes += 1

        # Generation plan
        cleaned_plan: list[float] = []
        for v in shot.generationPlan or []:
            c = _normalize_duration_dust(v)
            if c is not None:
                cleaned_plan.append(c)
            elif abs(v - round(v)) > 1.0:
                # Far from integer — likely frame-grid echo. Leave it.
                cleaned_plan.append(v)
            else:
                cleaned_plan.append(v)
        if cleaned_plan != list(shot.generationPlan or []):
            log.info(
                "film-timeline normalize shot=%s generationPlan %s → %s",
                shot.id, shot.generationPlan, cleaned_plan,
            )
            shot.generationPlan = cleaned_plan
            changes += 1

        # Segments
        for segment in shot.segments:
            c_dur = _normalize_duration_dust(segment.durationSec)
            c_req = _normalize_duration_dust(segment.requestedDurationSec)
            if c_dur is not None and c_dur != segment.durationSec:
                log.info(
                    "film-timeline normalize segment=%s durationSec %.6f → %g",
                    segment.id, segment.durationSec, c_dur,
                )
                segment.durationSec = c_dur
                changes += 1
            if c_req is not None and c_req != segment.requestedDurationSec:
                log.info(
                    "film-timeline normalize segment=%s requestedDurationSec %.6f → %g",
                    segment.id, segment.requestedDurationSec, c_req,
                )
                segment.requestedDurationSec = c_req
                changes += 1

    return changes


def _raw(scene) -> dict[str, Any]:
    try:
        parsed = json.loads(scene.director_json or "{}")
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _dialogue_tracks(db: Session, project_id: str) -> list[dict[str, Any]]:
    from ..db import Project

    project = db.get(Project, project_id)
    if project is None:
        return []
    try:
        settings = json.loads(project.settings_json or "{}")
    except Exception:
        return []
    timeline = settings.get("timeline") if isinstance(settings, dict) else None
    tracks = timeline.get("dialogueTracks") if isinstance(timeline, dict) else None
    return [item for item in (tracks or []) if isinstance(item, dict)]


def _interrupt_stale(film: FilmTimeline) -> bool:
    current = current_runtime_session_id()
    if film.renderSessionId and film.renderSessionId == current:
        return False
    changed = False
    for shot in film.shots:
        for segment in shot.segments:
            if segment.status in {"queued", "generating", "processing", "downloading"}:
                segment.status = "interrupted"
                segment.error = "This generation belonged to a previous session. Generate or Continue to start a new one."
                changed = True
    if changed:
        film.renderSessionId = None
    return changed


def load_film(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    scene = get_scene(db, project_id, scene_id)
    if scene is None:
        return {"ok": False, "error": "SCENE_NOT_FOUND"}
    raw = _raw(scene)
    existing = raw.get(FILM_KEY)
    created = False
    if isinstance(existing, dict) and existing.get("version"):
        film = FilmTimeline.model_validate(existing)
    else:
        master = raw.get("timelineMaster") if isinstance(raw.get("timelineMaster"), dict) else None
        film = migrate_master_dict(
            master,
            project_id=project_id,
            scene_id=scene_id,
            scene_name=scene.name or "Scene",
            scene_prompt=scene.prompt or "",
            scene_duration=float(scene.duration_sec or 10),
            generator_id=scene.engine or None,
            dialogue_tracks=_dialogue_tracks(db, project_id),
        )
        created = True
        log.info(
            "film-timeline migrate project=%s scene=%s shots=%s segments=%s",
            project_id,
            scene_id,
            len(film.shots),
            sum(len(shot.segments) for shot in film.shots),
        )
    if _interrupt_stale(film) or created:
        if _normalize_film_durations(film) and not created:
            log.info("film-timeline normalized float-dust durations project=%s scene=%s", project_id, scene_id)
        save_film(db, project_id, scene_id, film)
    return {"ok": True, "film": film, "projectId": project_id, "sceneId": scene_id}


#: SQLite has a single writer. Overlapping Timeline requests (the UI auto-syncs a
#: generating shot every 4s) and background writers can hold the write lock past
#: the driver's busy timeout. A bounded retry keeps a legitimately overlapping
#: save from surfacing as an HTTP 500. It is never a silent success: the payload
#: is re-applied after every rollback and the last attempt re-raises.
_SAVE_LOCK_ATTEMPTS = 5
_SAVE_LOCK_BACKOFF_SEC = 0.25
_SAVE_LOCK_BACKOFF_MAX_SEC = 2.0


def save_film(db: Session, project_id: str, scene_id: str, film: FilmTimeline) -> FilmTimeline:
    scene = get_scene(db, project_id, scene_id)
    if scene is None:
        raise ValueError("SCENE_NOT_FOUND")
    raw = _raw(scene)
    film.projectId = project_id
    film.sceneId = scene_id
    raw[FILM_KEY] = film.model_dump()
    payload = json.dumps(raw, ensure_ascii=False)
    scene.director_json = payload
    db.add(scene)
    _commit_film_payload(db, project_id, scene_id, payload)
    return film


def _commit_film_payload(db: Session, project_id: str, scene_id: str, payload: str) -> None:
    delay = _SAVE_LOCK_BACKOFF_SEC
    for attempt in range(1, _SAVE_LOCK_ATTEMPTS + 1):
        try:
            db.commit()
            return
        except OperationalError as exc:
            locked = "database is locked" in str(exc).lower()
            db.rollback()
            if not locked or attempt >= _SAVE_LOCK_ATTEMPTS:
                raise
            log.warning(
                "film-timeline save deferred by a locked database project=%s scene=%s attempt=%s",
                project_id,
                scene_id,
                attempt,
            )
            time.sleep(delay)
            delay = min(delay * 2, _SAVE_LOCK_BACKOFF_MAX_SEC)
            scene = get_scene(db, project_id, scene_id)
            if scene is None:
                raise ValueError("SCENE_NOT_FOUND")
            scene.director_json = payload
            db.add(scene)


def require_film(db: Session, project_id: str, scene_id: str) -> FilmTimeline:
    loaded = load_film(db, project_id, scene_id)
    if not loaded.get("ok"):
        raise ValueError(str(loaded.get("error") or "SCENE_NOT_FOUND"))
    return loaded["film"]

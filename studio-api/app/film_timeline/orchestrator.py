"""Shot generation. Timeline owns the request. Adapters own the provider."""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from ..runtime_session import current_runtime_session_id
from .contracts import FilmTimeline, ReferenceAsset, Segment, Shot, ShotState
from .duration import DurationUnsupported, coerce_whole_seconds, plan_duration
from .store import require_film, save_film
from .strategies import choose_strategy

log = logging.getLogger("adept.film_timeline")

_ACTIVE = {"queued", "generating", "processing", "downloading"}

#: Per-shot single-flight. The UI auto-syncs a generating shot every 4s and the
#: test harness polls it in parallel, so two syncs of one shot routinely overlap.
#: Without serialization a planned segment can be submitted twice and one
#: read-modify-write of the shot document can clobber the other
#: (Request Stability Law). Keyed by shot, ref-counted so the map stays empty.
_SHOT_LOCKS: dict[tuple[str, str, str], list] = {}
_SHOT_LOCKS_GUARD = threading.Lock()


@contextmanager
def _film_shot_lock(project_id: str, scene_id: str, shot_id: str):
    key = (project_id, scene_id, shot_id)
    with _SHOT_LOCKS_GUARD:
        entry = _SHOT_LOCKS.get(key)
        if entry is None:
            entry = [threading.RLock(), 0]
            _SHOT_LOCKS[key] = entry
        entry[1] += 1
    try:
        with entry[0]:
            yield
    finally:
        with _SHOT_LOCKS_GUARD:
            entry[1] -= 1
            if entry[1] <= 0:
                _SHOT_LOCKS.pop(key, None)


class FilmTimelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _registry():
    from ..director_timeline_w46.generation.registry import get_registry

    return get_registry()


def _shot(film: FilmTimeline, shot_id: str) -> Shot:
    for shot in film.shots:
        if shot.id == shot_id:
            return shot
    raise FilmTimelineError("SHOT_NOT_FOUND", "That shot is not on this scene.")


def create_shot(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    name: str | None = None,
    duration_sec: float = 10.0,
    timed_prompt: str = "",
    generator_id: str | None = None,
    inherit_scene: bool = True,
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    order = len(film.shots)
    chosen, legacy_options = _fold_legacy_production(generator_id or film.generatorId, None)
    shot = Shot(
        sceneId=scene_id,
        name=name or f"Shot {order + 1:02d}",
        order=order,
        durationSec=float(coerce_whole_seconds(duration_sec)),
        timedPrompt=timed_prompt,
        state=ShotState(sceneId=scene_id, modelId=chosen or film.generatorId),
    )
    if legacy_options and legacy_options.get("ltxMode"):
        shot.state.resolvedGeneration = {"ltxMode": legacy_options["ltxMode"]}
    shot.state.shotId = shot.id
    if inherit_scene:
        shot.state.references = [
            ref.model_copy(update={"id": ReferenceAsset().id, "inherited": True}) for ref in film.references
        ]
    if timed_prompt:
        shot.state.promptHistory.append(timed_prompt)
    film.shots.append(shot)
    save_film(db, project_id, scene_id, film)
    log.info("film-timeline create-shot project=%s scene=%s shot=%s", project_id, scene_id, shot.id)
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump()}


def set_shot_generator(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    generator_id: str,
    provider_options: dict | None = None,
) -> dict[str, Any]:
    """Persist the shot's model selection. This never submits or starts a job."""

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    generator_id, provider_options = _fold_legacy_production(generator_id, provider_options)
    try:
        canonical = _canonical_generator(generator_id or "")
    except Exception as exc:
        raise FilmTimelineError("MODEL_UNAVAILABLE", str(exc)) from exc
    _adapter(canonical)
    shot.state.modelId = canonical
    if provider_options:
        _apply_provider_options(shot, provider_options)
    save_film(db, project_id, scene_id, film)
    log.info(
        "film-timeline set-shot-model project=%s scene=%s shot=%s model=%s",
        project_id,
        scene_id,
        shot_id,
        canonical,
    )
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump()}


def new_shot(db: Session, project_id: str, scene_id: str, *, after_shot_id: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Cinematic cut. Scene references carry over. The previous shot chain does not."""

    film = require_film(db, project_id, scene_id)
    previous = None
    if after_shot_id:
        previous = _shot(film, after_shot_id)
    elif film.shots:
        previous = film.shots[-1]
    created = create_shot(
        db,
        project_id,
        scene_id,
        name=name,
        duration_sec=previous.durationSec if previous else 10,
        generator_id=(previous.state.modelId if previous else None) or film.generatorId,
        inherit_scene=True,
    )
    log.info(
        "film-timeline new-shot project=%s scene=%s shot=%s after=%s",
        project_id,
        scene_id,
        created["shot"]["id"],
        previous.id if previous else "",
    )
    return created


def update_timed_prompt(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    timed_prompt: str,
    *,
    model_prompt: str | None = None,
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    shot.timedPrompt = timed_prompt
    if timed_prompt and (not shot.state.promptHistory or shot.state.promptHistory[-1] != timed_prompt):
        shot.state.promptHistory.append(timed_prompt)
    if model_prompt is not None:
        shot.state.modelPrompt = model_prompt
    save_film(db, project_id, scene_id, film)
    log.info("film-timeline author-prompt project=%s scene=%s shot=%s", project_id, scene_id, shot_id)
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump(), "rendered": False}


def delete_timed_prompt(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    segment_id: str | None = None,
) -> dict[str, Any]:
    """Clear the shot Timed Prompt, and one segment prompt when that segment is selected."""
    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    if segment_id:
        segment = next((item for item in shot.segments if item.id == segment_id), None)
        if segment is None:
            return {"ok": False, "error": "SEGMENT_NOT_FOUND", "message": "That timed prompt is not on this shot."}
        segment.timedPrompt = ""
    shot.timedPrompt = ""
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump()}


def delete_segment(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    segment_id: str,
) -> dict[str, Any]:
    """Remove one generated video segment. Other segments and their continuity packets stay."""
    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    kept = [item for item in shot.segments if item.id != segment_id]
    if len(kept) == len(shot.segments):
        return {"ok": False, "error": "SEGMENT_NOT_FOUND", "message": "That video segment is not on this shot."}
    shot.segments = kept
    shot.state.segmentIds = [item for item in shot.state.segmentIds if item != segment_id]
    if shot.state.priorSegmentId == segment_id:
        shot.state.priorSegmentId = kept[-1].id if kept else None
    if segment_id in (shot.state.stitchSegmentIds or []):
        shot.state.stitchStatus = "stale"
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "film": film.model_dump()}


def attach_reference(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    asset_id: str,
    ref_type: str = "image",
    label: str = "",
    tag: str = "",
    scene_level: bool = False,
    reference_id: str = "",
    source: str = "",
    role: str = "",
) -> dict[str, Any]:
    from .references import canonical_tag, duplicate_tag, normalize_reference_type

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    kind = normalize_reference_type(ref_type)
    try:
        resolved_tag = canonical_tag(kind, tag or label) if kind in {"character", "environment", "prop", "video", "audio"} else ""
    except ValueError as exc:
        code = str(exc)
        message = "Type a tag for this reference." if code == "TAG_REQUIRED" else "Choose Character, Environment, Prop, Video, or Audio."
        raise FilmTimelineError(code if code in {"TAG_REQUIRED", "TAG_TYPE"} else "TAG_REQUIRED", message) from exc
    origin = str(source or "").strip() or "timeline"
    if origin.startswith("storyboard:"):
        from ..db import Asset

        asset = db.get(Asset, asset_id) if asset_id else None
        if asset is None or str(asset.project_id or "") != project_id:
            raise FilmTimelineError(
                "MISSING_FRAME",
                "A storyboard frame is missing from this project's Library.",
            )
    pool = [*film.references, *shot.state.references]
    existing = next((item for item in shot.state.references if reference_id and item.id == reference_id), None)
    if existing is None:
        existing = next((item for item in shot.state.references if item.assetId == asset_id), None)
    if resolved_tag and duplicate_tag(pool, resolved_tag, except_id=existing.id if existing else ""):
        raise FilmTimelineError("DUPLICATE_TAG", "That tag is already used on this shot.")
    if existing is not None:
        existing.type = kind  # type: ignore[assignment]
        existing.assetId = asset_id
        existing.label = label or existing.label
        existing.tag = resolved_tag or existing.tag
        existing.source = origin
        if role:
            existing.role = role
        ref = existing
    else:
        ref = ReferenceAsset(
            type=kind,  # type: ignore[arg-type]
            assetId=asset_id,
            label=label,
            tag=resolved_tag,
            role=role or "",
            source=origin,
            inherited=scene_level,
        )
        if scene_level:
            film.references.append(ref)
            for item in film.shots:
                item.state.references.append(ref.model_copy(update={"id": ReferenceAsset().id, "inherited": True}))
        else:
            shot.state.references.append(ref)
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "reference": ref.model_dump(), "film": film.model_dump(), "rendered": False}


async def cancel_shot(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    """Cancel the active Film Timeline job through the existing queue halt."""

    from ..queue_worker import job_queue
    from .references import apply_cancelled_segment

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    active = [segment for segment in shot.segments if segment.status in _ACTIVE]
    if not active:
        return {"ok": False, "error": "NOTHING_TO_CANCEL", "message": "Nothing is rendering.", "film": film.model_dump()}
    segment = active[-1]
    queue_job_id = str(segment.generationMetadata.get("queueJobId") or "")
    if queue_job_id and job_queue is not None:
        result = await job_queue.cancel_and_halt(queue_job_id)
        if result.get("cancelRejected"):
            return {
                "ok": False,
                "error": str(result.get("cancelReason") or "CANCEL_REJECTED"),
                "message": "This generator cannot cancel a running job. The remote generation continues until it finishes.",
                "film": film.model_dump(),
            }
        if not result.get("ok") and not result.get("confirmedStopped") and not result.get("alreadyCancelled"):
            return {
                "ok": False,
                "error": str(result.get("error") or "CANCEL_FAILED"),
                "message": "The render could not be cancelled. It is still running.",
                "film": film.model_dump(),
            }
    elif not queue_job_id:
        # Hosted provider job: no Adept queue row exists. Ask the adapter to
        # cancel at the provider (Seedance calls the real fal queue cancel);
        # never route the internal tgen_* id through the local job queue.
        adapter = _adapter(segment.generatorId or _generator_id(film, shot))
        raw = segment.generationMetadata.get("submission")
        if not isinstance(raw, dict):
            return {
                "ok": False,
                "error": "CANCEL_UNAVAILABLE",
                "message": "This render has no provider job to cancel.",
                "film": film.model_dump(),
            }
        from ..director_timeline_w46.generation.contracts import NormalizedJobSubmission

        try:
            adapter.cancel(NormalizedJobSubmission.model_validate(raw))
        except Exception:
            log.warning("film-timeline hosted cancel raised segment=%s", segment.id, exc_info=True)
        try:
            status = adapter.get_status(NormalizedJobSubmission.model_validate(raw))
        except Exception:
            status = None
        meta = (getattr(status, "providerMetadata", None) or {}) if status is not None else {}
        if meta.get("cancelRejected") or (status is not None and status.status in _ACTIVE):
            return {
                "ok": False,
                "error": str(meta.get("cancelReason") or "PROVIDER_CANCEL_UNSUPPORTED"),
                "message": "This generator cannot cancel a running job. The remote generation continues until it finishes.",
                "film": film.model_dump(),
            }
        if status is None or status.status != "cancelled":
            return {
                "ok": False,
                "error": "CANCEL_FAILED",
                "message": "The render could not be cancelled. It is still running.",
                "film": film.model_dump(),
            }
    # A whole-shot Re-Take still holds the picture it is replacing. Cancel
    # puts that picture back. A brand-new attempt has nothing to put back.
    if segment.generationMetadata.get("retakePreviousAssetId"):
        _restore_retake_asset(segment)
    else:
        apply_cancelled_segment(segment)
    if not any(item.status in _ACTIVE for item in shot.segments):
        shot.status = "ready" if any(item.status == "completed" for item in shot.segments) else "draft"
    save_film(db, project_id, scene_id, film)
    log.info("film-timeline cancel project=%s scene=%s shot=%s segment=%s", project_id, scene_id, shot_id, segment.id)
    return {"ok": True, "segment": segment.model_dump(), "shot": shot.model_dump(), "film": film.model_dump()}


def detach_reference(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    asset_id: str,
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    shot = next((item for item in film.shots if item.id == shot_id), None)
    film.references = [item for item in film.references if item.assetId != asset_id]
    if shot is not None:
        shot.state.references = [item for item in shot.state.references if item.assetId != asset_id]
        if shot.state.firstFrameAssetId == asset_id:
            shot.state.firstFrameAssetId = None
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "film": film.model_dump(), "rendered": False}


def _require_character_voice(db: Session, project_id: str, shot: Shot, film: FilmTimeline) -> None:
    """Fail before a job starts when Character Voice has no saved voice."""

    from .dialogue_authority import CHARACTER_VOICE, availability_message, normalize_mode, resolve_speakers

    if normalize_mode(shot.state.dialogueAuthority) != CHARACTER_VOICE:
        return
    speakers = resolve_speakers(db, project_id, shot, film.references)
    message = availability_message(speakers, has_character=bool(speakers))
    if message:
        raise FilmTimelineError("CHARACTER_VOICE_REQUIRED", message)


def _remember_dialogue_authority(shot: Shot, mode: str | None) -> None:
    """Store the dropdown. Missing means keep the shot's current authority."""

    if mode is None:
        return
    from .dialogue_authority import normalize_mode

    shot.state.dialogueAuthority = normalize_mode(mode)


def _remember_spoken_language(shot: Shot, code: str | None, custom: str | None = None) -> None:
    """Store the dropdown. Missing means keep the shot's current language."""

    if code is None:
        return
    from .spoken_language import normalize

    spoken = normalize(code, custom)
    shot.state.spokenLanguage = spoken.code
    shot.state.spokenLanguageCustom = spoken.custom


def _apply_provider_options(shot: Shot, provider_options: dict | None) -> None:
    """Store model-specific output settings in shot state for propagation."""
    if not provider_options:
        return
    if "h3Resolution" in provider_options:
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["h3Resolution"] = provider_options["h3Resolution"]
    if "ltxQuality" in provider_options:
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["ltxQuality"] = provider_options["ltxQuality"]
    if "ltxMode" in provider_options:
        from ..director_timeline_w46.generation.adapters.ltx_25_local import normalize_ltx_mode

        mode = normalize_ltx_mode(str(provider_options.get("ltxMode") or "text"))
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["ltxMode"] = mode
    if "ltxStartAssetId" in provider_options:
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["ltxStartAssetId"] = str(provider_options.get("ltxStartAssetId") or "").strip()
    if "ltxEndAssetId" in provider_options:
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["ltxEndAssetId"] = str(provider_options.get("ltxEndAssetId") or "").strip()
    if "seedanceResolution" in provider_options:
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["seedanceResolution"] = provider_options["seedanceResolution"]
    if isinstance(provider_options.get("h3Continuity"), dict):
        shot.state.resolvedGeneration = dict(shot.state.resolvedGeneration or {})
        shot.state.resolvedGeneration["h3Continuity"] = dict(provider_options["h3Continuity"])


def generate_shot(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    duration_sec: float | None = None,
    timed_prompt: str | None = None,
    generator_id: str | None = None,
    provider_options: dict | None = None,
    spoken_language: str | None = None,
    spoken_language_custom: str | None = None,
    dialogue_authority: str | None = None,
) -> dict[str, Any]:
    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        _remember_spoken_language(shot, spoken_language, spoken_language_custom)
        _remember_dialogue_authority(shot, dialogue_authority)
        if timed_prompt is not None:
            shot.timedPrompt = timed_prompt
            if timed_prompt and (not shot.state.promptHistory or shot.state.promptHistory[-1] != timed_prompt):
                shot.state.promptHistory.append(timed_prompt)
        generator_id, provider_options = _fold_legacy_production(generator_id, provider_options)
        if generator_id:
            shot.state.modelId = generator_id
        if duration_sec is not None:
            shot.durationSec = float(coerce_whole_seconds(duration_sec))
        if provider_options:
            _apply_provider_options(shot, provider_options)
        _require_character_voice(db, project_id, shot, film)
        return _submit_plan(db, project_id, scene_id, film, shot, continue_from=None)


def continue_shot(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    duration_sec: float,
    timed_prompt: str,
    generator_id: str | None = None,
    provider_options: dict | None = None,
    spoken_language: str | None = None,
    spoken_language_custom: str | None = None,
    dialogue_authority: str | None = None,
) -> dict[str, Any]:
    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        _remember_spoken_language(shot, spoken_language, spoken_language_custom)
        _remember_dialogue_authority(shot, dialogue_authority)
        prior = _last_completed(shot)
        if prior is None:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "Continue Shot needs a finished segment on this shot. Generate the shot first. Nothing already finished was changed.",
            )
        if not str(timed_prompt or "").strip():
            raise FilmTimelineError("PROMPT_REQUIRED", "Write the next Timed Prompt before continuing the shot.")
        shot.timedPrompt = timed_prompt
        shot.durationSec = float(coerce_whole_seconds(duration_sec))
        shot.state.promptHistory.append(timed_prompt)
        generator_id, provider_options = _fold_legacy_production(generator_id, provider_options)
        if generator_id:
            shot.state.modelId = generator_id
        if provider_options:
            _apply_provider_options(shot, provider_options)
        _require_character_voice(db, project_id, shot, film)
        shot.state.priorSegmentId = prior.id
        log.info(
            "film-timeline continue-shot project=%s scene=%s shot=%s prior=%s",
            project_id,
            scene_id,
            shot_id,
            prior.id,
        )
        return _submit_plan(db, project_id, scene_id, film, shot, continue_from=prior)


def prepend_shot(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    duration_sec: float,
    timed_prompt: str,
    generator_id: str | None = None,
    provider_options: dict | None = None,
    spoken_language: str | None = None,
    spoken_language_custom: str | None = None,
    dialogue_authority: str | None = None,
) -> dict[str, Any]:
    """Generate what happens immediately before the first picture.

    The new file is inserted at the start only after it exists. Forward Continue
    still reads the ending of the last picture.
    """

    from .continuity import opening_arrival_note, store_frame_at

    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        _remember_spoken_language(shot, spoken_language, spoken_language_custom)
        _remember_dialogue_authority(shot, dialogue_authority)
        first = _first_completed(shot)
        if first is None or not first.assetId:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "Create Previous Shot needs a finished picture on this shot. Nothing already finished was changed.",
            )
        if not str(timed_prompt or "").strip():
            raise FilmTimelineError("PROMPT_REQUIRED", "Write what happens immediately before this.")
        _require_character_voice(db, project_id, shot, film)
        shot.segments = [
            item
            for item in shot.segments
            if not (isinstance(item.generationMetadata.get("prepend"), dict) and item.status in {"failed", "cancelled"})
        ]
        start = float(first.trimInSec or 0)
        end = float(first.trimOutSec) if first.trimOutSec is not None else start + float(first.durationSec or 0)
        try:
            arrival = opening_arrival_note(db, project_id, first.assetId, start)
        except Exception:
            log.info("film-timeline prepend opening note skipped shot=%s", shot.id, exc_info=True)
            arrival = "At the end of this new shot, arrive at the picture that already opens the scene."
        try:
            opening_frame = store_frame_at(db, project_id, first.assetId, start, "prepend-opening")
        except Exception:
            log.info("film-timeline prepend opening frame skipped shot=%s", shot.id, exc_info=True)
            opening_frame = ""
        if not opening_frame:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "The opening of this scene could not be read, so the earlier shot was not started.",
            )
        db.commit()
        generator_id, provider_options = _fold_legacy_production(generator_id, provider_options)
        if generator_id:
            shot.state.modelId = generator_id
        if provider_options:
            _apply_provider_options(shot, provider_options)
        shot.timedPrompt = timed_prompt
        shot.state.promptHistory.append(timed_prompt)
        generated = float(coerce_whole_seconds(duration_sec))
        from .shot_identity import allocate_shot_number, backfill_shot_numbers

        backfill_shot_numbers(film)
        hold = Segment(
            order=max((item.order for item in shot.segments), default=-1) + 1,
            durationSec=generated,
            requestedDurationSec=generated,
            status="empty",
            timedPrompt=timed_prompt.strip(),
            generatorId=_generator_id(film, shot),
            shotNumber=allocate_shot_number(film),
            generationMetadata={
                "compositionHold": True,
                "prepend": {
                    "targetSegmentId": first.id,
                    "targetAssetId": first.assetId,
                    "openingStartSec": start,
                    "openingEndSec": end,
                    "openingStartFrame": int(round(start * 24)),
                    "openingEndFrame": int(round(end * 24)),
                    "openingFrameAssetId": opening_frame,
                    "arrival": arrival,
                },
            },
        )
        shot.segments.append(hold)
        film.renderSessionId = current_runtime_session_id()
        log.info(
            "film-timeline prepend-shot project=%s scene=%s shot=%s target=%s",
            project_id,
            scene_id,
            shot_id,
            first.id,
        )
        return _submit_one(db, project_id, scene_id, film, shot, hold)


def review_extend(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    duration_sec: float,
    timed_prompt: str,
    generator_id: str | None = None,
    provider_options: dict | None = None,
    spoken_language: str | None = None,
    spoken_language_custom: str | None = None,
    dialogue_authority: str | None = None,
) -> dict[str, Any]:
    """Review the prior segment with the existing Omni packet, then use Continue Shot."""
    from .continuity import ensure_segment_continuity

    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        prior = _last_completed(shot)
        if prior is None:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "Review & Extend needs a finished segment on this shot. Generate the shot first. Nothing already finished was changed.",
            )
        packet = ensure_segment_continuity(db, project_id, scene_id, shot, prior) or {}
        omni = packet.get("omni") if isinstance(packet, dict) else {}
        status = str(omni.get("status") or "unavailable") if isinstance(omni, dict) else "unavailable"
        meta = dict(prior.generationMetadata or {})
        meta["reviewExtend"] = {"reviewed": True, "omniStatus": status}
        prior.generationMetadata = meta
        save_film(db, project_id, scene_id, film)
    return continue_shot(
        db,
        project_id,
        scene_id,
        shot_id,
        duration_sec=duration_sec,
        timed_prompt=timed_prompt,
        generator_id=generator_id,
        provider_options=provider_options,
        spoken_language=spoken_language,
        spoken_language_custom=spoken_language_custom,
        dialogue_authority=dialogue_authority,
    )


def set_shot_spoken_language(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    code: str,
    custom: str | None = None,
) -> dict[str, Any]:
    """Persist spoken language. This never submits or starts a job."""

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    _remember_spoken_language(shot, code, custom)
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump()}


def dialogue_status(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    """Read who speaks. Does not submit a job."""

    from .dialogue_authority import availability_message, resolve_speakers

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    speakers = resolve_speakers(db, project_id, shot, film.references)
    message = ""
    if shot.state.dialogueAuthority == "character_voice":
        message = availability_message(speakers, has_character=bool(speakers))
    return {
        "ok": True,
        "dialogueAuthority": shot.state.dialogueAuthority,
        "voices": [
            {"name": item["name"], "provider": item["provider"], "voiceName": item["voiceName"], "ready": item["usable"]}
            for item in speakers
        ],
        "message": message,
    }


def set_shot_dialogue_authority(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    mode: str,
) -> dict[str, Any]:
    """Persist Dialogue. This never submits or starts a job."""

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    _remember_dialogue_authority(shot, mode)
    save_film(db, project_id, scene_id, film)
    status = dialogue_status(db, project_id, scene_id, shot_id)
    status["shot"] = shot.model_dump()
    status["film"] = film.model_dump()
    return status


def _fail_segmented_hold(segment: Segment, message: str) -> bool:
    """A held Re-Take never replaced the source, so failure only marks the hold."""

    if not isinstance(segment.generationMetadata.get("segmentedRetake"), dict):
        return False
    segment.generationMetadata["compositionHold"] = True
    segment.error = message
    return True


def _restore_retake_asset(segment: Segment) -> bool:
    previous = segment.generationMetadata.get("retakePreviousAssetId")
    if not previous:
        return False
    segment.assetId = str(previous)
    segment.status = "completed"
    segment.generationMetadata.pop("retakePreviousAssetId", None)
    segment.generationMetadata.pop("submission", None)
    segment.generationMetadata.pop("requestKey", None)
    from .continuity import restore_retake_continuity

    restore_retake_continuity(segment)
    return True


def retake_shot(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    mark_in: float | None,
    mark_out: float | None,
    timed_prompt: str | None = None,
) -> dict[str, Any]:
    from .retake import resolve_retake_segment

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    resolved = resolve_retake_segment(shot, mark_in, mark_out)
    if not resolved.get("ok"):
        raise FilmTimelineError(str(resolved.get("code") or "RETAKE_RANGE"), str(resolved.get("message") or "That range cannot be retaken."))
    if resolved.get("mode") == "partial":
        return _submit_segmented_retake(
            db,
            project_id,
            scene_id,
            shot_id,
            resolved,
            timed_prompt=timed_prompt,
        )
    segment = resolved["segment"]
    return regenerate_segment(
        db,
        project_id,
        scene_id,
        shot_id,
        segment.id,
        timed_prompt=timed_prompt,
        retake=True,
    )


def _submit_segmented_retake(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    resolved: dict,
    *,
    timed_prompt: str | None,
) -> dict[str, Any]:
    """Generate only the marked interval. The source segment stays until the join commits."""

    from .retake import generate_seconds

    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        source = next((item for item in shot.segments if item.id == resolved["segment"].id), None)
        if source is None or not source.assetId:
            raise FilmTimelineError("SEGMENT_NOT_FOUND", "That picture is no longer on this shot.")
        shot.segments = [
            item
            for item in shot.segments
            if not (isinstance(item.generationMetadata.get("segmentedRetake"), dict) and item.status in {"failed", "cancelled"})
        ]
        marked = float(resolved["marked"])
        generated = generate_seconds(marked)
        file_in = float(resolved["fileIn"])
        file_out = float(resolved["fileOut"])
        reference = "window" if file_in > 0.2 else "previous"
        entry_frame = ""
        boundary = "At the end of this new action, return to the picture that already follows this range."
        if source.assetId:
            from .continuity import exit_handback_note, store_frame_at

            try:
                boundary = exit_handback_note(db, project_id, source.assetId, file_out)
            except Exception:
                log.info("film-timeline retake exit note skipped shot=%s", shot.id, exc_info=True)
            if reference == "window":
                try:
                    entry_frame = store_frame_at(db, project_id, source.assetId, file_in, "retake-entry")
                except Exception:
                    log.info("film-timeline retake entry frame skipped shot=%s", shot.id, exc_info=True)
                    entry_frame = ""
            # Frame rows open a SQLite write. Release it before the job insert.
            db.commit()
        from .shot_identity import backfill_shot_numbers

        backfill_shot_numbers(film)
        hold = Segment(
            order=max((item.order for item in shot.segments), default=-1) + 1,
            durationSec=float(generated),
            requestedDurationSec=float(generated),
            status="empty",
            timedPrompt=(timed_prompt or "").strip() or source.timedPrompt,
            generatorId=source.generatorId or _generator_id(film, shot),
            shotNumber=int(source.shotNumber or 0),
            generationMetadata={
                "compositionHold": True,
                "segmentedRetake": {
                    "sourceSegmentId": source.id,
                    "fileIn": file_in,
                    "fileOut": file_out,
                    "marked": marked,
                    "generatedSec": float(generated),
                    "reference": reference,
                    "windowEndFrame": int(round(file_in * 24)) if reference == "window" else None,
                    "entryFrameAssetId": entry_frame,
                    "boundary": boundary,
                },
            },
        )
        shot.segments.append(hold)
        film.renderSessionId = current_runtime_session_id()
        result = _submit_one(db, project_id, scene_id, film, shot, hold)
        if isinstance(result, dict):
            result["mode"] = "partial"
            result["sourceSegmentId"] = source.id
        return result


def import_library_video(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    asset_id: str,
) -> dict[str, Any]:
    """Append a Library video as picture. The Library file is not copied or changed."""

    from ..db import Asset
    from ..media_clip import probe_video_duration

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    source_id = str(asset_id or "").strip()
    asset = db.get(Asset, source_id) if source_id else None
    if asset is None or str(asset.project_id or "") != project_id:
        raise FilmTimelineError("ASSET_NOT_FOUND", "That video is not in this project's Library.")
    if str(asset.kind or "") != "video":
        raise FilmTimelineError("VIDEO_REQUIRED", "Choose a video.")
    path = asset.path or ""
    duration = probe_video_duration(path) if path else None
    if not duration or duration <= 0:
        raise FilmTimelineError("DURATION_UNAVAILABLE", "That video has no readable length.")
    from .shot_identity import allocate_shot_number, backfill_shot_numbers

    backfill_shot_numbers(film)
    segment = Segment(
        order=max((item.order for item in shot.segments), default=-1) + 1,
        durationSec=float(duration),
        requestedDurationSec=float(duration),
        status="completed",
        assetId=source_id,
        origin="library",
        compositionRole="generated",
        timedPrompt="",
        shotNumber=allocate_shot_number(film),
    )
    shot.segments.append(segment)
    shot.state.segmentIds = [item.id for item in shot.segments]
    shot.state.stitchAssetId = None
    shot.state.stitchStatus = "stale"
    shot.state.stitchError = None
    shot.state.stitchSegmentIds = []
    save_film(db, project_id, scene_id, film)
    from .stitch import stitch_shot

    stitched = stitch_shot(db, project_id, scene_id, shot.id)
    film = require_film(db, project_id, scene_id)
    return {"ok": True, "segmentId": segment.id, "durationSec": float(duration), "film": film.model_dump(), "stitch": stitched}


def regenerate_segment(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    segment_id: str,
    *,
    timed_prompt: str | None = None,
    retake: bool = False,
) -> dict[str, Any]:
    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        segment = next((item for item in shot.segments if item.id == segment_id), None)
        if segment is None:
            raise FilmTimelineError("SEGMENT_NOT_FOUND", "That segment is not on this shot.")
        _require_character_voice(db, project_id, shot, film)
        if timed_prompt:
            segment.timedPrompt = timed_prompt
        if retake and segment.assetId:
            # The current picture stays on this same segment until the new
            # output is saved. The next shot is not marked stale until then.
            segment.generationMetadata["retakePreviousAssetId"] = segment.assetId
            packet = segment.generationMetadata.get("continuity")
            if isinstance(packet, dict):
                segment.generationMetadata["retakePreviousContinuity"] = packet
        else:
            from .continuity import invalidate_segment_continuity

            invalidate_segment_continuity(shot, segment.id)
            segment.status = "empty"
            segment.assetId = None
        segment.error = None
        segment.generationMetadata.pop("submission", None)
        segment.generationMetadata.pop("requestKey", None)
        segment.generationMetadata.pop("renderStatus", None)
        shot.state.stitchAssetId = None
        shot.state.stitchStatus = "stale"
        others = [item.id for item in shot.segments if item.id != segment.id]
        log.info(
            "film-timeline regenerate project=%s scene=%s shot=%s segment=%s kept=%s",
            project_id,
            scene_id,
            shot_id,
            segment_id,
            others,
        )
        return _submit_one(db, project_id, scene_id, film, shot, segment)


def sync_shot(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    """Observe in-flight jobs. Submit the next planned piece only in the same session.

    Overlapping auto-syncs of one shot are serialized: the second call re-reads
    the committed film, so a planned segment is submitted exactly once.
    """

    with _film_shot_lock(project_id, scene_id, shot_id):
        return _sync_shot_locked(db, project_id, scene_id, shot_id)


def _sync_shot_locked(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    _refresh_shot(db, shot, project_id, scene_id, film=film)
    save_film(db, project_id, scene_id, film)
    current = current_runtime_session_id()
    if film.renderSessionId == current:
        nxt = _next_planned(shot)
        if nxt is not None:
            return _submit_one(db, project_id, scene_id, film, shot, nxt)
        _maybe_stitch(db, project_id, scene_id, shot)
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
    return {"ok": True, "shot": shot.model_dump(), "film": film.model_dump()}


def _submit_plan(db, project_id, scene_id, film, shot: Shot, *, continue_from: Segment | None) -> dict[str, Any]:
    if continue_from is None and any(segment.status == "completed" for segment in shot.segments):
        return {
            "ok": False,
            "error": "SHOT_ALREADY_GENERATED",
            "message": "This shot already has picture. Continue Shot adds the next part. Regenerate replaces one part.",
            "film": film.model_dump(),
        }
    generator_id = _generator_id(film, shot)
    if not _h3_reference_ready(film, shot, generator_id, continue_from):
        raise FilmTimelineError(
            "REFERENCE_REQUIRED",
            "MiniMax H3 needs a reference before it can generate this shot. Add one, then try again.",
        )
    try:
        _hosted_start_frame_ready(film, shot, generator_id, continue_from)
    except FilmTimelineError as exc:
        return {"ok": False, "error": exc.code, "message": str(exc), "film": film.model_dump()}
    shot.state.modelId = generator_id
    adapter = _adapter(generator_id)
    try:
        pieces = plan_duration(shot.durationSec, adapter.capabilities)
    except DurationUnsupported as exc:
        save_film(db, project_id, scene_id, film)
        return {"ok": False, **exc.as_dict(), "film": film.model_dump()}
    from .shot_identity import (
        allocate_shot_number,
        backfill_shot_numbers,
        drop_released_attempts,
        release_uncommitted_shot_numbers,
    )

    release_uncommitted_shot_numbers(film)
    drop_released_attempts(film)
    backfill_shot_numbers(film)
    # One creator action — Generate, Continue — is one shot number, even when
    # the model window splits the request into more than one segment.
    shot_number = allocate_shot_number(film)
    start_order = (max((segment.order for segment in shot.segments), default=-1) + 1) if continue_from else 0
    if continue_from is None:
        # A new generate replaces only empty unsubmitted tail, never completed segments.
        shot.segments = [segment for segment in shot.segments if segment.status == "completed"]
        start_order = len(shot.segments)
    created: list[Segment] = []
    for offset, piece in enumerate(pieces):
        segment = Segment(
            order=start_order + offset,
            durationSec=piece,
            requestedDurationSec=piece,
            timedPrompt=shot.timedPrompt,
            generatorId=generator_id,
            shotNumber=shot_number,
            generationMetadata={"planned": True, "generationAttemptId": uuid.uuid4().hex},
        )
        shot.segments.append(segment)
        created.append(segment)
    shot.generationPlan = pieces
    shot.state.segmentIds = [segment.id for segment in shot.segments]
    # F2: a newly planned piece changes the composition. Any stitched take of the
    # previous segment set is no longer the current shot, so the monitor must not
    # present it and the next sync/stitch must rebuild it. Same invalidation as
    # regenerate_segment; segments themselves are never touched.
    shot.state.stitchAssetId = None
    shot.state.stitchStatus = "stale"
    shot.state.stitchError = None
    shot.state.modelId = generator_id
    film.renderSessionId = current_runtime_session_id()
    film.generatorId = generator_id
    first = created[0]
    return _submit_one(db, project_id, scene_id, film, shot, first)


def _submit_one(db, project_id, scene_id, film, shot: Shot, segment: Segment) -> dict[str, Any]:
    if segment.status in _ACTIVE and segment.generationMetadata.get("submission"):
        log.info(
            "film-timeline idempotent project=%s scene=%s shot=%s segment=%s job=%s",
            project_id,
            scene_id,
            shot.id,
            segment.id,
            segment.generationMetadata.get("jobId"),
        )
        return {"ok": True, "idempotent": True, "shot": shot.model_dump(), "segment": segment.model_dump(), "film": film.model_dump()}

    generator_id = segment.generatorId or _generator_id(film, shot)
    adapter = _adapter(generator_id)
    prepend = segment.generationMetadata.get("prepend")
    prepend = prepend if isinstance(prepend, dict) else None
    spec = segment.generationMetadata.get("segmentedRetake")
    spec = spec if isinstance(spec, dict) else None
    if prepend is not None:
        previous = next((item for item in shot.segments if item.id == prepend.get("targetSegmentId")), None)
        if previous is None:
            previous = _first_completed(shot)
    elif spec is not None:
        source = next((item for item in shot.segments if item.id == spec.get("sourceSegmentId")), None)
        if spec.get("reference") == "previous" and source is not None:
            previous = _previous_completed(shot, source)
        else:
            previous = source
        if previous is not None and spec.get("reference") != "window":
            from .continuity import ensure_segment_continuity

            ensure_segment_continuity(db, project_id, scene_id, shot, previous)
    else:
        previous = _previous_completed(shot, segment)
        if previous is not None:
            from .continuity import ensure_segment_continuity

            ensure_segment_continuity(db, project_id, scene_id, shot, previous)
    has_refs = bool(shot.state.references or film.references or shot.state.firstFrameAssetId)
    strategy = "reference_set"
    if previous is not None:
        strategy = choose_strategy(
            adapter.capabilities,
            has_previous_video=bool(previous.assetId),
            has_last_frame=bool(previous.lastFrameAssetId or previous.assetId),
            has_references=has_refs,
        )
    elif has_refs:
        strategy = choose_strategy(
            adapter.capabilities,
            has_previous_video=False,
            has_last_frame=bool(shot.state.firstFrameAssetId),
            has_references=True,
        )
    request = _build_request(db, project_id, scene_id, shot, segment, generator_id, strategy, previous, film)
    segment.generationMetadata["spokenLanguage"] = dict((request.providerOptions or {}).get("spokenLanguage") or {})
    segment.generationMetadata["dialogueAuthority"] = str(shot.state.dialogueAuthority or "native_model")
    # Apply shot-level output quality from Inspector (Megapixel / Quality / Seedance)
    if shot.state.resolvedGeneration:
        h3_res = shot.state.resolvedGeneration.get("h3Resolution")
        if h3_res and isinstance(h3_res, dict):
            segment.generationMetadata["h3Resolution"] = h3_res
            if request.providerOptions is None:
                request.providerOptions = {}
            request.providerOptions["h3Resolution"] = h3_res
        ltx_qual = shot.state.resolvedGeneration.get("ltxQuality")
        if ltx_qual:
            segment.generationMetadata["ltxQuality"] = ltx_qual
            if request.providerOptions is None:
                request.providerOptions = {}
            request.providerOptions["ltxQuality"] = ltx_qual
    request_key = _request_key(
        shot.id,
        segment,
        strategy,
        previous.id if previous else "",
        f"{shot.state.spokenLanguage}:{shot.state.spokenLanguageCustom}:{shot.state.dialogueAuthority}",
    )
    if segment.generationMetadata.get("requestKey") == request_key and segment.status in _ACTIVE:
        return {"ok": True, "idempotent": True, "shot": shot.model_dump(), "film": film.model_dump()}
    # H3 legal-canvas preflight: never submit Comfy with Scene canvas or non-table WxH.
    # ONE resolvedGeneration object is authority for preflight, request, adapter, Comfy.
    # Scene Picture Shape — Timeline generate authority (owner stamp C).
    scene_aspect = None
    try:
        from ..db import Scene as _SceneRow

        _scene_row = db.get(_SceneRow, scene_id)
        if _scene_row is not None and getattr(_scene_row, "project_id", None) == project_id:
            scene_aspect = getattr(_scene_row, "aspect_ratio", None)
    except Exception:
        scene_aspect = None
    if not scene_aspect:
        scene_aspect = getattr(request, "aspectRatio", None) or "16:9"

    if _h3(generator_id):
        from ..video_runtime.legal_canvas import SpecFidelityError, is_h3_legal_pixels, resolve_generation_dimensions

        try:
            # D1: a manual H3 megapixel tier overrides Auto at a NEW generation
            # boundary. D2: never resize an existing continuity chain — when a
            # prior completed Segment exists, keep inheriting its legalCanvas.
            manual_megapixels = None
            if previous is None:
                h3_resolution = (shot.state.resolvedGeneration or {}).get("h3Resolution")
                if isinstance(h3_resolution, dict) and str(h3_resolution.get("mode") or "").strip().lower() == "manual":
                    candidate = h3_resolution.get("megapixels")
                    if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                        manual_megapixels = candidate
            if manual_megapixels is not None:
                dims = resolve_generation_dimensions(
                    model=generator_id,
                    requested_quality=str(manual_megapixels),
                    requested_aspect=scene_aspect,
                    draft_mode=False,
                )
            else:
                requested = request.resolution
                # Ignore illegal Scene-shaped WxH on the request; Auto Quality 0.7 applies.
                if requested and "x" in str(requested).lower():
                    try:
                        _w_s, _h_s = str(requested).lower().split("x", 1)
                        _rw, _rh = int(_w_s), int(_h_s)
                    except ValueError:
                        _rw, _rh = 0, 0
                    if not (_rw > 0 and _rh > 0 and is_h3_legal_pixels(_rw, _rh)):
                        requested = None
                dims = resolve_generation_dimensions(
                    model=generator_id,
                    requested_quality=requested,
                    requested_aspect=scene_aspect,
                    draft_mode=False,
                )
            from ..video_runtime.h3_resolved_generation import stamp_resolved_generation

            resolved = stamp_resolved_generation({}, dims)
            request.resolution = f"{resolved['width']}x{resolved['height']}"
            request.aspectRatio = resolved.get("aspect") or "16:9"
            segment.generationMetadata["legalCanvas"] = dict(resolved)
            segment.generationMetadata["resolvedGeneration"] = dict(resolved)
            if request.providerOptions is None:
                request.providerOptions = {}
            request.providerOptions["resolvedGeneration"] = dict(resolved)
            # Whole-second duration only. The H3 fast renderer owns provider frames.
            if _is_local_h3(generator_id):
                request.providerOptions["requestedDurationSec"] = int(segment.durationSec)
                request.providerOptions["useH3FastRenderer"] = True
            else:
                # Canonical H3 frame owner (Director cutover): the retired
                # h3_ref2v_builder.frames_for_duration was only a thin wrapper
                # over snap_h3_timeline_duration - call the owner directly.
                from ..video_runtime.legal_canvas import snap_h3_timeline_duration

                _snap = snap_h3_timeline_duration(float(segment.durationSec))
                if not _snap.get("ok"):
                    raise SpecFidelityError(
                        str(_snap.get("message") or "MiniMax H3 duration is unsupported."),
                        code="ILLEGAL_DURATION",
                    )
                request.providerOptions["legalFrameCount"] = int(_snap["frames"])
                request.providerOptions["requestedDurationSec"] = int(segment.durationSec)
        except SpecFidelityError as exc:
            segment.status = "failed"
            segment.error = str(exc)
            shot.status = "failed"
            save_film(db, project_id, scene_id, film)
            return {
                "ok": False,
                "error": getattr(exc, "code", None) or "H3_RESOLUTION_UNSUPPORTED",
                "message": str(exc),
                "suggestions": list(getattr(exc, "suggestions", []) or []),
                "film": film.model_dump(),
            }
    # Non-H3 Timeline families: stamp resolvedGeneration with scene aspect (owner stamp).
    if (not _h3(generator_id)) and not (isinstance(request.providerOptions, dict) and request.providerOptions.get("resolvedGeneration")):
        from ..video_runtime.legal_canvas import SpecFidelityError

        if str(generator_id or "").startswith(("kling", "veo")):
            # Kling/Veo are provider-tier hosted models with no Adept pixel
            # canvas table. Stamp the scene picture shape and the provider
            # tier honestly — never invent pixel dimensions for the plan line.
            from ..video_runtime.legal_canvas import require_timeline_aspect

            try:
                aspect = require_timeline_aspect(scene_aspect)
            except SpecFidelityError as exc:
                segment.status = "failed"
                segment.error = str(exc)
                shot.status = "failed"
                save_film(db, project_id, scene_id, film)
                return {
                    "ok": False,
                    "error": getattr(exc, "code", None) or "ASPECT_UNSUPPORTED",
                    "message": str(exc),
                    "suggestions": list(getattr(exc, "suggestions", []) or []),
                    "film": film.model_dump(),
                }
            resolved = {
                "productId": generator_id,
                "aspect": aspect,
                "label": "720p",
                "source": "hosted_provider_tier",
            }
            request.aspectRatio = aspect
            request.resolution = "720p"
            segment.generationMetadata["resolvedGeneration"] = dict(resolved)
            if request.providerOptions is None:
                request.providerOptions = {}
            request.providerOptions["resolvedGeneration"] = dict(resolved)
        else:
            try:
                from ..video_runtime.legal_canvas import resolve_generation_dimensions
                from ..video_runtime.h3_resolved_generation import stamp_resolved_generation
                from ..video_runtime.workflow_resolver import is_ltx_25_generator

                quality = None
                if is_ltx_25_generator(generator_id):
                    quality = (
                        (shot.state.resolvedGeneration or {}).get("ltxQuality")
                        if isinstance(shot.state.resolvedGeneration, dict)
                        else None
                    ) or "720p"
                elif "seedance" in str(generator_id or ""):
                    quality = (
                        (shot.state.resolvedGeneration or {}).get("seedanceResolution")
                        if isinstance(shot.state.resolvedGeneration, dict)
                        else None
                    ) or "720p"
                else:
                    quality = request.resolution or "720p"
                dims = resolve_generation_dimensions(
                    model=generator_id,
                    requested_quality=quality,
                    requested_aspect=scene_aspect,
                    draft_mode=False,
                )
                resolved = stamp_resolved_generation({}, dims)
                if "seedance" in str(generator_id or ""):
                    # Hosted Seedance submits a tier token (480p/720p), never
                    # WxH pixels; the pixel canvas lives in resolvedGeneration.
                    request.resolution = str(quality or "720p")
                elif dims.get("width") and dims.get("height"):
                    request.resolution = f"{resolved['width']}x{resolved['height']}"
                request.aspectRatio = str(resolved.get("aspect") or scene_aspect)
                segment.generationMetadata["resolvedGeneration"] = dict(resolved)
                if request.providerOptions is None:
                    request.providerOptions = {}
                request.providerOptions["resolvedGeneration"] = dict(resolved)
            except SpecFidelityError as exc:
                segment.status = "failed"
                segment.error = str(exc)
                shot.status = "failed"
                save_film(db, project_id, scene_id, film)
                return {
                    "ok": False,
                    "error": getattr(exc, "code", None) or "ASPECT_UNSUPPORTED",
                    "message": str(exc),
                    "suggestions": list(getattr(exc, "suggestions", []) or []),
                    "film": film.model_dump(),
                }
            except Exception:
                pass

    # The request session may still hold the frame-insert write. The job row
    # uses its own connection, so release this one before that insert.
    db.commit()
    validation = adapter.validate(request)
    if not validation.ok:
        segment.status = "failed"
        segment.error = "; ".join(validation.errors) or "The model refused this shot."
        if _restore_retake_asset(segment):
            segment.error = f"{segment.error} The finished picture was kept."
        save_film(db, project_id, scene_id, film)
        return {"ok": False, "error": "VALIDATION_FAILED", "message": segment.error, "film": film.model_dump()}
    try:
        submission = adapter.submit(request)
    except Exception as exc:
        log.exception(
            "film-timeline submit failed project=%s scene=%s shot=%s segment=%s",
            project_id,
            scene_id,
            shot.id,
            segment.id,
        )
        segment.status = "failed"
        segment.error = _creator_failure(str(exc))
        if _restore_retake_asset(segment):
            segment.error = f"{segment.error} The finished picture was kept."
        save_film(db, project_id, scene_id, film)
        return {"ok": False, "error": "SUBMIT_FAILED", "message": segment.error, "film": film.model_dump()}
    segment.status = "queued"
    segment.generatorId = generator_id
    segment.continuationStrategy = strategy
    segment.generationMetadata.update(
        {
            "requestKey": request_key,
            "planned": True,
            "jobId": submission.internalJobId,
            "providerJobId": submission.providerJobId,
            "queueJobId": submission.queueJobId,
            "sessionId": current_runtime_session_id(),
            "submission": submission.model_dump(),
            "strategy": strategy,
            "plannedReferenceAssetIds": list(request.referenceAssetIds or []),
        }
    )
    snapshot = (request.providerOptions or {}).get("characterVoiceSnapshot")
    if isinstance(snapshot, list):
        segment.generationMetadata["characterVoiceSnapshot"] = snapshot
    anchor = str((request.providerOptions or {}).get("continuationStartAssetId") or "").strip()
    if anchor:
        segment.generationMetadata["continuationStartAssetId"] = anchor
        segment.generationMetadata["continuationAnchor"] = "start_image"
    film.renderSessionId = current_runtime_session_id()
    shot.status = "generating"
    save_film(db, project_id, scene_id, film)
    log.info(
        "film-timeline submit project=%s scene=%s shot=%s segment=%s job=%s strategy=%s",
        project_id,
        scene_id,
        shot.id,
        segment.id,
        submission.internalJobId,
        strategy,
    )
    return {
        "ok": True,
        "jobId": submission.internalJobId,
        "queueJobId": submission.queueJobId,
        "internalJobId": submission.internalJobId,
        "segment": segment.model_dump(),
        "shot": shot.model_dump(),
        "film": film.model_dump(),
    }


def adopt_finished_segments(db: Session, project_id: str, scene_id: str, film: FilmTimeline) -> bool:
    """Keep a picture that already finished. A new session must not drop that file."""

    from ..director_timeline_w46.generation.contracts import NormalizedJobSubmission

    changed = False
    for shot in film.shots:
        for segment in shot.segments:
            if segment.assetId:
                continue
            if segment.status not in {"queued", "generating", "processing", "downloading", "interrupted"}:
                continue
            raw = segment.generationMetadata.get("submission")
            if not isinstance(raw, dict):
                continue
            try:
                adapter = _adapter(segment.generatorId or _generator_id(film, shot))
                status = adapter.get_status(NormalizedJobSubmission.model_validate(raw))
            except Exception:
                continue
            if status.status != "completed":
                continue
            try:
                result = adapter.collect_result(NormalizedJobSubmission.model_validate(raw))
            except Exception:
                log.warning("film-timeline finished asset unread segment=%s", segment.id, exc_info=True)
                continue
            asset_id = (result.outputAssetIds or [None])[0]
            if not asset_id:
                continue
            segment.status = "completed"
            segment.assetId = asset_id
            segment.error = None
            if isinstance(segment.generationMetadata.get("prepend"), dict):
                from .stitch import commit_prepend

                if commit_prepend(db, project_id, scene_id, shot, segment):
                    changed = True
                    continue
            shot.status = "ready"
            changed = True
            log.info("film-timeline kept finished segment=%s asset=%s", segment.id, asset_id)
    return changed


def _refresh_shot(
    db: Session,
    shot: Shot,
    project_id: str = "",
    scene_id: str = "",
    film: FilmTimeline | None = None,
) -> None:
    from ..director_timeline_w46.generation.contracts import NormalizedJobSubmission

    for segment in shot.segments:
        raw = segment.generationMetadata.get("submission")
        if segment.status not in _ACTIVE or not isinstance(raw, dict):
            continue
        if segment.generationMetadata.get("sessionId") not in (None, current_runtime_session_id()):
            segment.status = "interrupted"
            segment.generationMetadata.pop("renderStatus", None)
            if not _fail_segmented_hold(segment, "That Re-Take was interrupted. The original picture was kept."):
                _restore_retake_asset(segment)
            continue
        try:
            adapter = _adapter(segment.generatorId or "")
            status = adapter.get_status(NormalizedJobSubmission.model_validate(raw))
        except Exception:
            log.warning("film-timeline status unread segment=%s", segment.id, exc_info=True)
            continue
        if status.status == "completed":
            try:
                result = adapter.collect_result(NormalizedJobSubmission.model_validate(raw))
            except Exception:
                segment.status = "failed"
                segment.error = "The finished video could not be saved."
                _stamp_render_status(segment, status)
                if not _fail_segmented_hold(segment, segment.error):
                    _restore_retake_asset(segment)
                continue
            new_asset = (result.outputAssetIds or [None])[0]
            if not new_asset and segment.generationMetadata.get("retakePreviousAssetId"):
                segment.status = "failed"
                segment.error = "The finished video could not be saved."
                _stamp_render_status(segment, status)
                _restore_retake_asset(segment)
                continue
            segment.status = "completed"
            segment.assetId = new_asset
            segment.error = None
            if isinstance(segment.generationMetadata.get("prepend"), dict) and project_id and scene_id:
                from .stitch import commit_prepend

                if commit_prepend(db, project_id, scene_id, shot, segment):
                    continue
            if isinstance(segment.generationMetadata.get("segmentedRetake"), dict) and project_id and scene_id:
                from .stitch import commit_segmented_retake

                commit_segmented_retake(db, project_id, scene_id, shot, segment)
                continue
            if segment.generationMetadata.get("retakePreviousAssetId"):
                from .continuity import mark_downstream_continuation_stale

                mark_downstream_continuation_stale(shot, segment.id)
                segment.generationMetadata.pop("continuity", None)
                segment.lastFrameAssetId = None
            segment.generationMetadata.pop("retakePreviousAssetId", None)
            segment.generationMetadata.pop("retakePreviousContinuity", None)
            handle = dict(result.providerMetadata or {})
            if handle:
                segment.generationMetadata["continuationHandle"] = handle
            # B-F2 (b): only on this fresh completion transition -- a piece that
            # was in flight is now on the shot, so a stitch taken before it does
            # not cover the completed set and is no longer the current take. The
            # next sync rebuilds it over every completed piece. A segment already
            # 'completed' never enters this branch, so polling cannot loop.
            if shot.state.stitchStatus == "ready" and not _stitch_covers_completed(shot):
                log.info(
                    "film-timeline stitch invalidated shot=%s segment=%s covered=%s",
                    shot.id,
                    segment.id,
                    list(shot.state.stitchSegmentIds or []),
                )
                _invalidate_stitch(shot)
            log.info("film-timeline complete shot=%s segment=%s asset=%s", shot.id, segment.id, segment.assetId)
            if project_id and scene_id and segment.assetId:
                from .continuity import ensure_segment_continuity

                ensure_segment_continuity(db, project_id, scene_id, shot, segment)
        elif status.status == "running":
            segment.status = "generating"
        elif status.status == "failed":
            segment.status = "failed"
            segment.error = _creator_failure(status.errorMessage)
            if not _fail_segmented_hold(segment, segment.error):
                _restore_retake_asset(segment)
        elif status.status == "cancelled":
            segment.status = "cancelled"
            if not _fail_segmented_hold(segment, "That Re-Take was cancelled. The original picture was kept."):
                _restore_retake_asset(segment)
        elif status.status == "blocked":
            segment.status = "failed"
            segment.error = _creator_failure(status.errorMessage) or "Generation is blocked."
            if not _fail_segmented_hold(segment, segment.error):
                _restore_retake_asset(segment)
        _stamp_render_status(segment, status)
    if film is not None:
        from .shot_identity import release_uncommitted_shot_numbers

        release_uncommitted_shot_numbers(film)
    _settle_shot_status(shot)


def _creator_failure(message: str | None) -> str:
    """Keep a short creator sentence. Drop stack traces, node ids, and raw codes."""

    text = " ".join(str(message or "").split())
    if not text:
        return "Generation failed. Completed segments were kept."
    lowered = text.lower()
    if any(token in lowered for token in ("traceback", "node ", "fps_mode", "jobid", "{", "}")):
        return "Generation failed. Completed segments were kept."
    if len(text) > 180:
        return "Generation failed. Completed segments were kept."
    return text


def _stamp_render_status(segment, status) -> None:
    from .render_status import creator_render_status

    telemetry = (getattr(status, "providerMetadata", None) or {}).get("progressTelemetry")
    segment.generationMetadata["renderStatus"] = creator_render_status(
        progress=float(getattr(status, "progress", 0.0) or 0.0),
        telemetry=telemetry if isinstance(telemetry, dict) else None,
        segment_status=segment.status,
    )


def _settle_shot_status(shot: Shot) -> None:
    if any(segment.status in _ACTIVE for segment in shot.segments):
        shot.status = "generating"
        return
    if any(segment.status == "failed" for segment in shot.segments):
        shot.status = "failed"
        return
    if any(segment.status == "completed" and segment.assetId for segment in shot.segments):
        shot.status = "ready"
        return
    shot.status = "draft"


def _completed_segments(shot: Shot) -> list[Segment]:
    return [
        segment
        for segment in sorted(shot.segments, key=lambda item: item.order)
        if segment.status == "completed" and segment.assetId and not segment.generationMetadata.get("compositionHold")
    ]


def composition_units(shot: Shot) -> list[list[Segment]]:
    """Completed track clips. A Re-Take head, replacement, and tail stay one unit."""

    units: list[list[Segment]] = []
    for segment in _completed_segments(shot):
        source = str(segment.sourceSegmentId or "").strip()
        previous = str(units[-1][0].sourceSegmentId or "").strip() if units else ""
        if source and previous == source:
            units[-1].append(segment)
            continue
        units.append([segment])
    return units


def apply_composition_move(
    shot: Shot,
    *,
    segment_id: str,
    direction: str | None = None,
    before_segment_id: str | None = None,
    after_segment_id: str | None = None,
) -> None:
    """Reorder composition units. Shot numbers stay where they were assigned."""

    if any(segment.status in _ACTIVE for segment in shot.segments):
        raise FilmTimelineError("COMPOSITION_BUSY", "Wait until the current shot finishes before moving clips.")
    units = composition_units(shot)
    index = next((i for i, unit in enumerate(units) if any(item.id == segment_id for item in unit)), None)
    if index is None:
        raise FilmTimelineError("SEGMENT_NOT_FOUND", "That clip is not on the track.")
    if direction == "earlier":
        if index == 0:
            raise FilmTimelineError("COMPOSITION_EDGE", "That clip is already first.")
        units[index - 1], units[index] = units[index], units[index - 1]
    elif direction == "later":
        if index == len(units) - 1:
            raise FilmTimelineError("COMPOSITION_EDGE", "That clip is already last.")
        units[index + 1], units[index] = units[index], units[index + 1]
    elif before_segment_id or after_segment_id:
        target_id = str(before_segment_id or after_segment_id)
        target = next((i for i, unit in enumerate(units) if any(item.id == target_id for item in unit)), None)
        if target is None:
            raise FilmTimelineError("SEGMENT_NOT_FOUND", "That place is not on the track.")
        if target == index:
            return
        unit = units.pop(index)
        if target > index:
            target -= 1
        units.insert(target if before_segment_id else target + 1, unit)
    else:
        raise FilmTimelineError("COMPOSITION_MOVE", "Choose an earlier or later place.")
    visible_ids = {item.id for unit in units for item in unit}
    ordered_visible = [item for unit in units for item in unit]
    others = [item for item in sorted(shot.segments, key=lambda item: item.order) if item.id not in visible_ids]
    merged = ordered_visible + others
    for position, item in enumerate(merged):
        item.order = position
    shot.segments = merged
    shot.state.segmentIds = [item.id for item in merged]


def mark_order_stale(shot: Shot) -> None:
    """Same clips, new order. Keep the recorded order so sync does not rebuild it."""

    shot.state.stitchStatus = "stale"
    shot.state.stitchAssetId = None
    shot.state.stitchError = None


def reorder_composition(
    db: Session,
    project_id: str,
    scene_id: str,
    shot_id: str,
    *,
    segment_id: str,
    direction: str | None = None,
    before_segment_id: str | None = None,
    after_segment_id: str | None = None,
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    apply_composition_move(
        shot,
        segment_id=segment_id,
        direction=direction,
        before_segment_id=before_segment_id,
        after_segment_id=after_segment_id,
    )
    mark_order_stale(shot)
    save_film(db, project_id, scene_id, film)
    return {"ok": True, "film": film.model_dump()}


def _order_only_rearrange(shot: Shot, completed: list[Segment]) -> bool:
    recorded = list(shot.state.stitchSegmentIds or [])
    completed_ids = [segment.id for segment in completed]
    return bool(recorded) and set(recorded) == set(completed_ids) and recorded != completed_ids


def _stitch_covers_completed(shot: Shot) -> bool:
    """A ready stitch is current only when its ordered pieces match the track."""

    if shot.state.stitchStatus != "ready":
        return False
    completed_ids = [segment.id for segment in _completed_segments(shot)]
    if not completed_ids:
        return False
    return list(shot.state.stitchSegmentIds or []) == completed_ids


def _invalidate_stitch(shot: Shot) -> None:
    """The composition moved on: the existing take is no longer the current shot."""

    shot.state.stitchStatus = "stale"
    shot.state.stitchAssetId = None
    shot.state.stitchSegmentIds = []
    shot.state.stitchError = None


def _maybe_stitch(db, project_id, scene_id, shot: Shot) -> None:
    # B-F2 (a): never stitch while the composition can still change. A stitch
    # taken while a re-taken/continued piece is in flight covers a partial
    # segment set, and the monitor prefers a 'ready' stitch -- live
    # shot_ed8c484c22a3 kept presenting 69ea756a (segments 0+1, 20.008s) as the
    # current shot after the re-taken piece had already been re-submitted.
    if any(segment.status in _ACTIVE for segment in shot.segments):
        return
    # Every non-completed piece must still be 'empty'/planned. Failed/cancelled/
    # interrupted pieces mean the composition is not settled either.
    if any(segment.status not in {"completed", "empty"} for segment in shot.segments):
        return
    completed = _completed_segments(shot)
    if len(completed) < 2:
        return
    # Same clips in a new order wait for the Stitch button. A new or removed
    # clip still joins itself, which is how continuation already behaves.
    if _order_only_rearrange(shot, completed):
        if shot.state.stitchStatus != "stale" or shot.state.stitchAssetId:
            film = require_film(db, project_id, scene_id)
            current = next((item for item in film.shots if item.id == shot.id), None)
            if current is not None:
                current.state.stitchStatus = "stale"
                current.state.stitchAssetId = None
                current.state.stitchError = None
                save_film(db, project_id, scene_id, film)
            shot.state.stitchStatus = "stale"
            shot.state.stitchAssetId = None
            shot.state.stitchError = None
        return
    # B-F2 (c): a 'ready' stitch that does not include every completed piece
    # (legacy take, or one taken before a later piece landed) is stale.
    if shot.state.stitchStatus == "ready":
        if _stitch_covers_completed(shot):
            return
        _invalidate_stitch(shot)
    if shot.state.stitchStatus not in {"none", "stale", "failed"}:
        return
    from .stitch import stitch_shot

    stitch_shot(db, project_id, scene_id, shot.id)


def _next_planned(shot: Shot) -> Segment | None:
    ordered = sorted(shot.segments, key=lambda item: item.order)
    for index, segment in enumerate(ordered):
        if segment.status != "empty" or not segment.generationMetadata.get("planned"):
            continue
        if index == 0:
            return segment
        previous = ordered[index - 1]
        if previous.status == "completed":
            return segment
        return None
    return None


def _first_completed(shot: Shot) -> Segment | None:
    """The finished picture the scene currently opens on. Holds are not on the scene yet."""

    completed = _completed_segments(shot)
    return completed[0] if completed else None


def _last_completed(shot: Shot) -> Segment | None:
    """The finished batch at the end of the shot, by timeline order.

    A newer render that is not the selected segment does not become the
    continuation source. Re-Take replaces that segment's asset; Continue
    reads the asset that is on the shot.
    """

    completed = _completed_segments(shot)
    if not completed:
        return None
    return completed[-1]


def _previous_completed(shot: Shot, segment: Segment) -> Segment | None:
    earlier = [item for item in shot.segments if item.order < segment.order and item.status == "completed"]
    if not earlier:
        return None
    return sorted(earlier, key=lambda item: item.order)[-1]


LOCAL_H3_R2V = "minimax-h3-i2v-local"




def _segment_legal_resolution(shot: Shot, segment: Segment, generator_id: str, previous: Segment | None) -> str | None:
    """The shot being generated keeps its own canvas. A predecessor is the fallback."""
    for source in (segment, previous):
        if source is None:
            continue
        canvas = (source.generationMetadata or {}).get("legalCanvas")
        if isinstance(canvas, dict) and canvas.get("width") and canvas.get("height"):
            return f"{int(canvas['width'])}x{int(canvas['height'])}"
    for prior in shot.segments:
        if prior.status != "completed":
            continue
        canvas = (prior.generationMetadata or {}).get("legalCanvas")
        if isinstance(canvas, dict) and canvas.get("width") and canvas.get("height"):
            return f"{int(canvas['width'])}x{int(canvas['height'])}"
    return legal_timeline_resolution(generator_id)


def legal_timeline_resolution(generator_id: str) -> str | None:
    """Film Timeline canvas. A scene's stored pixels are not a video canvas."""

    from ..video_runtime.legal_canvas import resolve_generation_dimensions

    token = generator_id or ""
    if _is_local_h3(token) or _h3(token) or "ltx" in token:
        dims = resolve_generation_dimensions(model=token, draft_mode=False)
        return f"{int(dims['width'])}x{int(dims['height'])}"
    return None


def _is_local_h3(generator_id: str) -> bool:
    token = generator_id or ""
    if token == "minimax-h3-base-optimized":
        return True
    return "minimax-h3" in token and "local" in token


def _canonical_generator(token: str) -> str:
    """Local MiniMax uses the reference-to-video adapter. Base Optimized keeps its own id."""
    raw = (token or "").strip().lower()
    if raw == "minimax-h3-base-optimized":
        return "minimax-h3-base-optimized"
    if _is_local_h3(token):
        return LOCAL_H3_R2V
    return _registry().resolve_id(token)


_LEGACY_LTX_PRODUCTION = {
    "text-to-video": "text",
    "text_to_video": "text",
    "txt2vid": "text",
    "t2v": "text",
    "one-frame": "one_frame",
    "one_frame": "one_frame",
    "one": "one_frame",
    "1-frame": "one_frame",
    "1_frame": "one_frame",
    "three-frame": "three_frame",
    "three_frame": "three_frame",
    "three": "three_frame",
    "3-frame": "three_frame",
    "3_frame": "three_frame",
}


def _fold_legacy_production(
    generator_id: str | None, provider_options: dict | None
) -> tuple[str | None, dict | None]:
    """Old top-level production ids are LTX 2.5 modes. New writes use the LTX id."""

    mode = _LEGACY_LTX_PRODUCTION.get(str(generator_id or "").strip().lower())
    if mode is None:
        return generator_id, provider_options
    options = dict(provider_options or {})
    options.setdefault("ltxMode", mode)
    return "ltx-2.5-distilled", options


def _h3_reference_ready(film: FilmTimeline, shot: Shot, generator_id: str, continue_from: Segment | None) -> bool:
    if not _is_local_h3(generator_id):
        return True
    if continue_from is not None and continue_from.assetId:
        return True
    if shot.state.firstFrameAssetId:
        return True
    return any(ref.assetId for ref in [*film.references, *shot.state.references])


def _hosted_start_frame_ready(
    film: FilmTimeline, shot: Shot, generator_id: str, continue_from: Segment | None
) -> None:
    """Kling/Veo execute image-to-video only. A bare text-to-video request has
    no fal route (fal_catalog.build_fal_arguments raises), so refuse it here —
    before any segment is planned — with the creator-facing fix."""
    token = str(generator_id or "")
    if not token.startswith(("kling", "veo")):
        return
    if continue_from is not None and continue_from.assetId:
        return
    if shot.state.firstFrameAssetId:
        return
    if any(ref.assetId for ref in [*film.references, *shot.state.references]):
        return
    label = "Kling" if token.startswith("kling") else "Veo"
    raise FilmTimelineError(
        "START_FRAME_REQUIRED",
        f"{label} starts from a picture. Add a reference or first frame to this shot, then try again.",
    )


def _generator_id(film: FilmTimeline, shot: Shot) -> str:
    token = shot.state.modelId or film.generatorId
    if not token:
        raise FilmTimelineError("MODEL_REQUIRED", "Choose a model for this shot.")
    try:
        return _canonical_generator(token)
    except Exception as exc:
        raise FilmTimelineError("MODEL_UNAVAILABLE", str(exc)) from exc


def _adapter(generator_id: str):
    try:
        return _registry().get(generator_id)
    except Exception as exc:
        raise FilmTimelineError("MODEL_UNAVAILABLE", str(exc)) from exc


def _h3(generator_id: str) -> bool:
    return "minimax-h3" in (generator_id or "")


def _continuity_options(previous: Segment | None) -> dict:
    """Prior segment fields the H3 fast renderer maps onto video and last-frame slots.

    Identity pictures stay on image slots. The finished prior segment is motion
    continuity, not a replacement for those pictures.
    """

    if previous is None:
        return {}
    packet = previous.generationMetadata.get("continuity")
    base = {
        "enabled": True,
        "priorAssetId": previous.assetId,
        "priorPrompt": previous.timedPrompt,
        "priorDurationSec": int(previous.durationSec or 0),
        "lastFrameAssetId": previous.lastFrameAssetId,
    }
    if not isinstance(packet, dict):
        return base
    base.update(
        {
            "lastFrameAssetId": previous.lastFrameAssetId or packet.get("lastFrameAssetId"),
            "tailFrameAssetIds": packet.get("tailFrameAssetIds") or [],
            "omniStatus": (packet.get("omni") or {}).get("status") if isinstance(packet.get("omni"), dict) else None,
            "seamStatus": (packet.get("seam") or {}).get("status") if isinstance(packet.get("seam"), dict) else None,
            "boundary": packet.get("boundary") or "",
        }
    )
    return base


def _request_key(shot_id: str, segment: Segment, strategy: str, previous_id: str, language: str = "") -> str:
    raw = "|".join(
        [
            shot_id,
            segment.timedPrompt,
            f"{int(segment.durationSec)}",
            segment.generatorId or "",
            strategy,
            previous_id,
            language,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


_LTX_DROPPED_ROLES = frozenset({"character", "place", "prop", "reference", "video", "audio", "prior_frame"})


def plan_ltx_generation(
    *,
    ltx_mode: str,
    ltx_start_asset_id: str,
    ltx_end_asset_id: str = "",
    opening_still: str,
    slots: list,
    start: str | None,
) -> dict[str, Any]:
    """Map a Timeline LTX shot onto text, one start image, or start plus end.

    Character, place, prop, and previous-clip slots are not generation inputs.
    A previous shot's final frame, when this segment continues it, is the start
    image. An end image is included only when the shot is in Start + End Frame
    and that end picture was saved. The unused start argument keeps the call
    site explicit. A stored three-frame mode is not converted into start+end.
    """

    from ..director_timeline_w46.generation.adapters.ltx_25_local import normalize_ltx_mode

    _ = start
    kept = [slot for slot in slots if str(slot.get("role") or "") not in _LTX_DROPPED_ROLES]
    mode_name = normalize_ltx_mode(ltx_mode)
    end_id = str(ltx_end_asset_id or "").strip()
    if mode_name == "three_frame":
        raise FilmTimelineError(
            "LTX_THREE_FRAME_UNSUPPORTED",
            "LTX 2.5 on Timeline does not take a third frame. Use Text to Video, Start Frame, or Start + End Frame.",
        )
    if str(opening_still or "").strip():
        if mode_name == "start_end" and end_id:
            return {
                "slots": kept,
                "start": str(opening_still).strip(),
                "end": end_id,
                "mode": "image_to_video",
                "ltxMode": "start_end",
            }
        return {
            "slots": kept,
            "start": str(opening_still).strip(),
            "end": None,
            "mode": "image_to_video",
            "ltxMode": "one_frame",
        }
    if mode_name == "start_end":
        chosen = str(ltx_start_asset_id or "").strip()
        if not chosen:
            raise FilmTimelineError(
                "LTX_START_FRAME_REQUIRED",
                "Choose a start picture for this LTX shot.",
            )
        if not end_id:
            raise FilmTimelineError(
                "LTX_END_FRAME_REQUIRED",
                "Choose an end picture for this LTX shot.",
            )
        return {
            "slots": kept,
            "start": chosen,
            "end": end_id,
            "mode": "image_to_video",
            "ltxMode": "start_end",
        }
    if mode_name == "one_frame":
        chosen = str(ltx_start_asset_id or "").strip()
        if not chosen:
            raise FilmTimelineError(
                "LTX_START_FRAME_REQUIRED",
                "Choose a start picture for this LTX shot.",
            )
        return {"slots": kept, "start": chosen, "end": None, "mode": "image_to_video", "ltxMode": "one_frame"}
    return {"slots": kept, "start": None, "end": None, "mode": "text_to_video", "ltxMode": "text"}


def _build_request(db, project_id, scene_id, shot: Shot, segment: Segment, generator_id: str, strategy: str, previous: Segment | None, film: FilmTimeline):
    from ..director_timeline_w46.generation.contracts import TimelineGenerationRequest

    from .director_refs import build_director_refs, make_ref_slot
    from .references import generation_role, provider_reference_slots

    caps = _adapter(generator_id).capabilities
    slots: list[dict] = []
    seen: set[str] = set()
    for ref in provider_reference_slots([*film.references, *shot.state.references], caps):
        if ref.assetId in seen:
            continue
        seen.add(ref.assetId)
        slots.append(
            make_ref_slot(
                role=generation_role(ref.type),
                asset_id=ref.assetId,
                label=ref.label or ref.tag,
            )
        )
    start = shot.state.firstFrameAssetId
    prepend_early = segment.generationMetadata.get("prepend")
    prepend_early = prepend_early if isinstance(prepend_early, dict) else None
    retake_early = segment.generationMetadata.get("segmentedRetake")
    retake_early = retake_early if isinstance(retake_early, dict) else None
    from .continuity import continuation_opening_frame

    opening_still = continuation_opening_frame(
        previous,
        prepend=prepend_early is not None,
        interior_retake=bool(retake_early and retake_early.get("reference") == "window"),
    )
    # API continuation starts from the previous still. The previous clip is not
    # sent: it replaces that start state and repeats the earlier spoken line.
    # Local H3 keeps its ending-tail video. A new shot has no opening still.
    api_continuation = bool(opening_still) and not _is_local_h3(generator_id)
    if (
        api_continuation
        and bool(getattr(caps, "supportsImageToVideo", False))
        and bool(getattr(caps, "supportsStartFrame", False))
    ):
        strategy = "last_frame_chain"
    if previous is not None:
        if strategy == "reference_video" and previous.assetId and previous.assetId not in seen and not api_continuation:
            slots.append(make_ref_slot(role="video", asset_id=previous.assetId, label="Previous segment"))
        # Standard H3 and Base Optimized share this still. It is the decoded
        # final frame of the current predecessor take, staged as a picture
        # before inference. The ending clip stays the video reference.
        if opening_still and opening_still not in seen:
            slots.append(make_ref_slot(role="prior_frame", asset_id=opening_still, label="Last frame"))
            seen.add(opening_still)
            start = opening_still
        else:
            frame = previous.lastFrameAssetId or previous.assetId
            if frame and strategy in {"last_frame_chain", "first_last_frame", "reference_set"} and frame not in seen:
                slots.append(make_ref_slot(role="prior_frame", asset_id=frame, label="Continue from"))
                start = frame if strategy != "reference_video" else start
    elif start and start not in seen:
        slots.append(make_ref_slot(role="prior_frame", asset_id=start, label="First frame"))
    ltx_plan = None
    interior_retake = bool(retake_early and retake_early.get("reference") == "window")
    if not interior_retake:
        from ..video_runtime.local_video_profiles import is_hunyuan_15_distilled
        from ..video_runtime.workflow_resolver import is_ltx_25_generator

        if is_ltx_25_generator(generator_id) or is_hunyuan_15_distilled(generator_id):
            stored_rg = shot.state.resolvedGeneration if isinstance(shot.state.resolvedGeneration, dict) else {}
            ltx_plan = plan_ltx_generation(
                ltx_mode=str(stored_rg.get("ltxMode") or "text"),
                ltx_start_asset_id=str(stored_rg.get("ltxStartAssetId") or ""),
                ltx_end_asset_id=str(stored_rg.get("ltxEndAssetId") or ""),
                opening_still=opening_still,
                slots=slots,
                start=start,
            )
            slots = ltx_plan["slots"]
            start = ltx_plan["start"]
            from ..db import Asset

            for frame_id, label in ((start, "start"), (ltx_plan.get("end"), "end")):
                if not frame_id:
                    continue
                frame = db.get(Asset, frame_id)
                if frame is None or frame.project_id != project_id or frame.kind != "image":
                    who = "Hunyuan" if is_hunyuan_15_distilled(generator_id) else "LTX"
                    raise FilmTimelineError(
                        "LTX_FRAME_INPUT_INVALID",
                        f"The {who} {label} frame must be a still image in this project's Library.",
                    )
            if is_hunyuan_15_distilled(generator_id) and str(ltx_plan.get("ltxMode") or "") == "start_end":
                raise FilmTimelineError(
                    "HUNYUAN_START_END_UNSUPPORTED",
                    "HunyuanVideo 1.5 Distilled uses Text to Video or a Start Frame. It does not take an end frame.",
                )
    # A Library import and an interior Re-Take can have picture with no character
    # or place. The gate counts image slots. The ending frame of that picture is
    # the image. Shots that already have a picture slot are left as they are.
    retake_picture = segment.generationMetadata.get("segmentedRetake")
    retake_picture = retake_picture if isinstance(retake_picture, dict) else None
    has_visual = any(
        str(slot.get("role") or "") not in {"video", "audio"} and str(slot.get("assetId") or "").strip()
        for slot in slots
    )
    prepend_picture = segment.generationMetadata.get("prepend")
    prepend_picture = prepend_picture if isinstance(prepend_picture, dict) else None
    if prepend_picture is not None:
        arrival = str(prepend_picture.get("openingFrameAssetId") or "")
        if arrival and arrival not in seen:
            slots.append(make_ref_slot(role="reference", asset_id=arrival, label="Arrival"))
            seen.add(arrival)
    if not has_visual and prepend_picture is None and _is_local_h3(generator_id):
        picture = ""
        if retake_picture is not None and retake_picture.get("reference") == "window":
            picture = str(retake_picture.get("entryFrameAssetId") or "")
        elif previous is not None:
            picture = str(previous.lastFrameAssetId or "")
        if picture and picture not in seen:
            slots.append(make_ref_slot(role="prior_frame", asset_id=picture, label="Previous picture"))
            seen.add(picture)

    prompt = segment.timedPrompt or shot.timedPrompt
    if shot.state.modelPrompt and segment.order == 0 and previous is None:
        prompt = shot.state.modelPrompt
    from .spoken_language import apply_to_prompt, normalize

    spoken = normalize(shot.state.spokenLanguage, shot.state.spokenLanguageCustom)
    prompt = apply_to_prompt(prompt, spoken)
    h3_mode = {}
    prepend_mode = segment.generationMetadata.get("prepend")
    prepend_mode = prepend_mode if isinstance(prepend_mode, dict) else None
    if prepend_mode is not None and _is_local_h3(generator_id):
        h3_mode = {
            "orientation": "prepend",
            "openingSeconds": 2,
            "openingStartFrame": prepend_mode.get("openingStartFrame") or 0,
            "openingEndFrame": prepend_mode.get("openingEndFrame"),
            "pairAudio": True,
            "includeLastFrame": False,
            "includeOmni": True,
            "continuation": False,
        }
    elif _is_local_h3(generator_id):
        stored = (shot.state.resolvedGeneration or {}).get("h3Continuity")
        if isinstance(stored, dict):
            h3_mode = dict(stored)
        elif previous is not None:
            # Ending tail, not the whole prior clip. The reference node keeps
            # the start of a long video and drops the ending.
            # The last still is already the prior-frame picture. Leaving this
            # flag off stops that same still from being appended a second time.
            h3_mode = {
                "tailSeconds": 2,
                "includeLastFrame": False,
                "pairAudio": True,
                "includeOmni": True,
                "continuation": True,
            }
    from .continuity import continuity_clause

    # Tail continuation carries its own ending sentence. The older whole-clip
    # note is only for the full-video baseline.
    if not h3_mode.get("continuation") and h3_mode.get("orientation") != "prepend":
        clause = continuity_clause(prompt, previous)
        if clause:
            prompt = f"{prompt}\n\n{clause}"
    hosted_api = not _is_local_h3(generator_id) and str(getattr(caps, "executionType", "") or "") == "api"
    creator_line = segment.timedPrompt or shot.timedPrompt or ""
    from .dialogue_authority import continue_dialogue_instruction, prompt_asks_to_speak

    speaks_this_shot = prompt_asks_to_speak(creator_line)
    if previous is not None and hosted_api and speaks_this_shot:
        spoken_clause = continue_dialogue_instruction(creator_line)
        if spoken_clause:
            prompt = f"{prompt}\n\n{spoken_clause}"
    if opening_still:
        from .continuity import opening_frame_clause

        prompt = f"{prompt}\n\n{opening_frame_clause(seedance_reference='mini' in str(generator_id or ''))}"
    mode = "text_to_video"
    if ltx_plan is not None:
        mode = ltx_plan["mode"]
    elif _is_local_h3(generator_id):
        mode = "reference"
    elif api_continuation and caps.supportsImageToVideo:
        mode = "image_to_video"
    elif strategy == "last_frame_chain" and start and caps.supportsImageToVideo and not caps.supportsVideoReferences:
        mode = "image_to_video"
    elif slots and (caps.supportsReferenceToVideo or not caps.supportsTextToVideo):
        mode = "reference"
    elif start and caps.supportsImageToVideo:
        mode = "image_to_video"
    # Director-native refs: assign pictureIndex on plain dicts so queue_worker
    # staging keeps 9/3/3 + @Name ordering. No CanonicalR2VRequest / W46 r2v import.
    if _is_local_h3(generator_id):
        from .dialogue_authority import CHARACTER_VOICE as _CHARACTER_VOICE
        from .dialogue_authority import normalize_mode as _normalize_dialogue_mode
        from .dialogue_authority import resolve_speakers as _resolve_speakers

        if _normalize_dialogue_mode(shot.state.dialogueAuthority) == _CHARACTER_VOICE:
            from .h3_fast_renderer import MAX_AUDIOS

            speakers = _resolve_speakers(db, project_id, shot, film.references)
            audio_slots = [slot for slot in slots if str(slot.get("role") or "") == "audio"]
            used = len(audio_slots)
            for speaker in speakers:
                asset_id = str(
                    ((speaker.get("voice") or {}).get("approvedVoiceReferenceAssetId") or "")
                )
                if not asset_id or asset_id in seen:
                    continue
                if used >= MAX_AUDIOS:
                    raise FilmTimelineError(
                        "CHARACTER_VOICE_REFERENCE_LIMIT",
                        "MiniMax H3 supports at most 3 audio references. "
                        "Reduce the number of voiced characters on this shot.",
                    )
                name = str(speaker.get("name") or "Character").strip() or "Character"
                slots.append(
                    make_ref_slot(role="audio", asset_id=asset_id, label=f"{name}'s voice")
                )
                seen.add(asset_id)
                used += 1
    refs = build_director_refs(slots, mapped_start_asset_id=start, generator_id=generator_id)
    assigned_slots = refs["slots"]
    continuity_opts = _continuity_options(previous)
    if prepend_mode is not None:
        continuity_opts = {
            "enabled": True,
            "priorAssetId": prepend_mode.get("targetAssetId") or (previous.assetId if previous else ""),
            "boundary": prepend_mode.get("arrival") or "",
        }
    retake_spec = segment.generationMetadata.get("segmentedRetake")
    if isinstance(retake_spec, dict) and retake_spec.get("reference") == "window":
        h3_mode = {
            **h3_mode,
            "tailSeconds": 2,
            "includeLastFrame": True,
            "pairAudio": True,
            "includeOmni": True,
            "continuation": True,
            "windowEndFrame": retake_spec.get("windowEndFrame"),
        }
        if retake_spec.get("entryFrameAssetId"):
            continuity_opts["lastFrameAssetId"] = retake_spec["entryFrameAssetId"]
        if retake_spec.get("boundary"):
            continuity_opts["boundary"] = retake_spec["boundary"]
    elif isinstance(retake_spec, dict) and retake_spec.get("boundary"):
        continuity_opts["boundary"] = retake_spec["boundary"]
    if h3_mode:
        continuity_opts = {**continuity_opts, "h3Continuity": h3_mode}
    request_seed = h3_mode.get("seed") if isinstance(h3_mode.get("seed"), int) and h3_mode.get("seed") >= 0 else None
    request = TimelineGenerationRequest(
        projectId=project_id,
        sceneId=scene_id,
        batchBlockId=segment.id,
        executionSnapshotId=segment.id,
        generatorId=generator_id,
        generationMode=mode,  # type: ignore[arg-type]
        prompt=prompt,
        seed=request_seed,
        startImageAssetId=(
            ltx_plan["start"]
            if ltx_plan is not None
            else (opening_still or (start if mode == "image_to_video" else None))
        ),
        endImageAssetId=(ltx_plan.get("end") if ltx_plan is not None else None),
        duration=int(segment.durationSec),
        resolution=_segment_legal_resolution(shot, segment, generator_id, previous),
        lastFrameAssetId=None if prepend_mode is not None else (previous.lastFrameAssetId if previous else None),
        videoReferenceAssetId=(
            None
            if api_continuation
            else (previous.assetId if previous and strategy == "reference_video" else None)
        ),
        continuityStrategy=strategy,
        referenceAssetIds=[
            str(slot.get("assetId") or "")
            for slot in assigned_slots
            if str(slot.get("role") or "") not in {"video", "audio"} and str(slot.get("assetId") or "").strip()
        ],
        providerOptions={
            # Keep key "r2v" as plain dict for one-release churn; also stamp directorRefs.
            "r2v": refs,
            "directorRefs": refs,
            "filmTimeline": True,
            "shotId": shot.id,
            "segmentId": segment.id,
            "originalGeneratorId": generator_id,
            "continuity": continuity_opts,
            "requestedDurationSec": int(segment.durationSec),
            **(
                {"continuationAnchor": "start_image", "continuationStartAssetId": opening_still}
                if api_continuation
                else {}
            ),
            "spokenLanguage": {
                "language": spoken.code,
                "label": spoken.label,
                "custom": spoken.custom,
                "source": "timeline",
                "authority": "explicit",
            },
            "dialogueAuthority": {"mode": shot.state.dialogueAuthority, "source": "timeline"},
            **({"ltxMode": ltx_plan["ltxMode"]} if ltx_plan is not None else {}),
            **({"useH3FastRenderer": True} if _is_local_h3(generator_id) else {}),
        },
    )
    from .dialogue_authority import (
        CHARACTER_VOICE,
        apply_to_request,
        availability_message,
        normalize_mode,
        resolve_speakers,
    )

    if normalize_mode(shot.state.dialogueAuthority) == CHARACTER_VOICE:
        speakers = resolve_speakers(db, project_id, shot, film.references)
        message = availability_message(speakers, has_character=bool(speakers))
        if message:
            raise FilmTimelineError("CHARACTER_VOICE_REQUIRED", message)
        opts = dict(request.providerOptions or {})
        opts["characterVoiceSnapshot"] = [
            {
                "characterId": str(item.get("characterId") or ""),
                "voiceProfileId": str((item.get("voice") or {}).get("activeVoiceProfileId") or ""),
                "provider": str(item.get("provider") or ""),
                "voiceName": str(item.get("voiceName") or ""),
                "providerVoiceId": str((item.get("voice") or {}).get("providerVoiceId") or ""),
                "approvedVoiceReferenceAssetId": str(
                    (item.get("voice") or {}).get("approvedVoiceReferenceAssetId") or ""
                ),
            }
            for item in speakers
        ]
        request.providerOptions = opts
        if hosted_api and speaks_this_shot:
            # The creator wrote this shot's line for the API model to say.
            # The speech-off lock made Continue keep the previous clip's line.
            return request
        if _is_local_h3(generator_id):
            missing_reference = next(
                (
                    item
                    for item in speakers
                    if item.get("usable")
                    and not str((item.get("voice") or {}).get("approvedVoiceReferenceAssetId") or "")
                ),
                None,
            )
            if missing_reference is not None:
                raise FilmTimelineError(
                    "CHARACTER_VOICE_REFERENCE_REQUIRED",
                    f"{missing_reference.get('name') or 'This character'} does not have an approved voice reference. "
                    "Save one from Voice Studio first.",
                )
        apply_to_request(request, shot, speakers)
    return request

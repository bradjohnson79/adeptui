"""Shot generation. Timeline owns the request. Adapters own the provider."""

from __future__ import annotations

import hashlib
import logging
import threading
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
    shot = Shot(
        sceneId=scene_id,
        name=name or f"Shot {order + 1:02d}",
        order=order,
        durationSec=float(coerce_whole_seconds(duration_sec)),
        timedPrompt=timed_prompt,
        state=ShotState(sceneId=scene_id, modelId=generator_id or film.generatorId),
    )
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
) -> dict[str, Any]:
    """Persist the shot's model selection. This never submits or starts a job."""

    film = require_film(db, project_id, scene_id)
    shot = _shot(film, shot_id)
    try:
        canonical = _canonical_generator(generator_id)
    except Exception as exc:
        raise FilmTimelineError("MODEL_UNAVAILABLE", str(exc)) from exc
    _adapter(canonical)
    shot.state.modelId = canonical
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
        ref = existing
    else:
        ref = ReferenceAsset(
            type=kind,  # type: ignore[arg-type]
            assetId=asset_id,
            label=label,
            tag=resolved_tag,
            source="timeline",
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
    job_id = str(segment.generationMetadata.get("queueJobId") or segment.generationMetadata.get("jobId") or "")
    if job_queue is not None and job_id:
        result = await job_queue.cancel_and_halt(job_id)
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
) -> dict[str, Any]:
    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        if timed_prompt is not None:
            shot.timedPrompt = timed_prompt
            if timed_prompt and (not shot.state.promptHistory or shot.state.promptHistory[-1] != timed_prompt):
                shot.state.promptHistory.append(timed_prompt)
        if generator_id:
            shot.state.modelId = generator_id
        if duration_sec is not None:
            shot.durationSec = float(coerce_whole_seconds(duration_sec))
        if provider_options:
            _apply_provider_options(shot, provider_options)
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
) -> dict[str, Any]:
    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        completed = [segment for segment in shot.segments if segment.status == "completed" and segment.assetId]
        if not completed:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "Continue Shot needs a finished segment on this shot. Generate the shot first. Nothing already finished was changed.",
            )
        if not str(timed_prompt or "").strip():
            raise FilmTimelineError("PROMPT_REQUIRED", "Write the next Timed Prompt before continuing the shot.")
        shot.timedPrompt = timed_prompt
        shot.durationSec = float(coerce_whole_seconds(duration_sec))
        shot.state.promptHistory.append(timed_prompt)
        if generator_id:
            shot.state.modelId = generator_id
        if provider_options:
            _apply_provider_options(shot, provider_options)
        shot.state.priorSegmentId = completed[-1].id
        log.info(
            "film-timeline continue-shot project=%s scene=%s shot=%s prior=%s",
            project_id,
            scene_id,
            shot_id,
            completed[-1].id,
        )
        return _submit_plan(db, project_id, scene_id, film, shot, continue_from=completed[-1])


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
) -> dict[str, Any]:
    """Review the prior segment with the existing Omni packet, then use Continue Shot."""
    from .continuity import ensure_segment_continuity

    with _film_shot_lock(project_id, scene_id, shot_id):
        film = require_film(db, project_id, scene_id)
        shot = _shot(film, shot_id)
        completed = [segment for segment in shot.segments if segment.status == "completed" and segment.assetId]
        if not completed:
            raise FilmTimelineError(
                "CONTINUITY_MISSING",
                "Review & Extend needs a finished segment on this shot. Generate the shot first. Nothing already finished was changed.",
            )
        prior = completed[-1]
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
    )


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
        if timed_prompt:
            segment.timedPrompt = timed_prompt
        if retake and segment.assetId:
            segment.generationMetadata["retakePreviousAssetId"] = segment.assetId
        from .continuity import invalidate_segment_continuity

        invalidate_segment_continuity(shot, segment.id)
        segment.status = "empty"
        segment.assetId = None
        segment.error = None
        segment.generationMetadata.pop("submission", None)
        segment.generationMetadata.pop("requestKey", None)
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
    _refresh_shot(db, shot, project_id, scene_id)
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
    shot.state.modelId = generator_id
    adapter = _adapter(generator_id)
    try:
        pieces = plan_duration(shot.durationSec, adapter.capabilities)
    except DurationUnsupported as exc:
        save_film(db, project_id, scene_id, film)
        return {"ok": False, **exc.as_dict(), "film": film.model_dump()}
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
            generationMetadata={"planned": True},
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
    request = _build_request(project_id, scene_id, shot, segment, generator_id, strategy, previous, film)
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
    request_key = _request_key(shot.id, segment, strategy, previous.id if previous else "")
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
            # H3 frame-grid: whole-second duration → legal 17k+5 frame count.
            # NEVER write frames/fps back as the segment/canonical duration.
            # Director cutover: when useDirector, the bridge owns H3 execution
            # frame construction. Skip legacy h3_ref2v_builder import and pass
            # only the canonical whole-second duration.
            if _is_local_h3(generator_id):
                request.providerOptions["requestedDurationSec"] = int(segment.durationSec)
                request.providerOptions["useDirector"] = True
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
        try:
            from ..video_runtime.legal_canvas import SpecFidelityError, resolve_generation_dimensions
            from ..video_runtime.h3_resolved_generation import stamp_resolved_generation
            from ..video_runtime.workflow_resolver import is_ltx_25_generator

            quality = None
            if is_ltx_25_generator(generator_id):
                quality = (
                    (shot.state.resolvedGeneration or {}).get("ltxQuality")
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
            if dims.get("width") and dims.get("height"):
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
        segment.error = str(exc)
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
        }
    )
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


def _refresh_shot(db: Session, shot: Shot, project_id: str = "", scene_id: str = "") -> None:
    from ..director_timeline_w46.generation.contracts import NormalizedJobSubmission

    for segment in shot.segments:
        raw = segment.generationMetadata.get("submission")
        if segment.status not in _ACTIVE or not isinstance(raw, dict):
            continue
        if segment.generationMetadata.get("sessionId") not in (None, current_runtime_session_id()):
            segment.status = "interrupted"
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
            except Exception as exc:
                segment.status = "failed"
                segment.error = f"The file could not be collected: {exc}"
                _restore_retake_asset(segment)
                continue
            segment.status = "completed"
            segment.assetId = (result.outputAssetIds or [None])[0]
            segment.error = None
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
            segment.error = status.errorMessage or "Generation failed. Completed segments were kept."
            _restore_retake_asset(segment)
        elif status.status == "cancelled":
            segment.status = "cancelled"
            _restore_retake_asset(segment)
        elif status.status == "blocked":
            segment.status = "failed"
            segment.error = status.errorMessage or "Generation is blocked."
            _restore_retake_asset(segment)
    _settle_shot_status(shot)


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
        if segment.status == "completed" and segment.assetId
    ]


def _stitch_covers_completed(shot: Shot) -> bool:
    """B-F2 (c): a 'ready' stitch is current only when it covers every completed piece."""

    if shot.state.stitchStatus != "ready":
        return False
    completed_ids = {segment.id for segment in _completed_segments(shot)}
    if not completed_ids:
        return False
    return set(shot.state.stitchSegmentIds or []) == completed_ids


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


def _previous_completed(shot: Shot, segment: Segment) -> Segment | None:
    earlier = [item for item in shot.segments if item.order < segment.order and item.status == "completed"]
    if not earlier:
        return None
    return sorted(earlier, key=lambda item: item.order)[-1]


LOCAL_H3_R2V = "minimax-h3-i2v-local"




def _segment_legal_resolution(shot: Shot, segment: Segment, generator_id: str, previous: Segment | None) -> str | None:
    """Continue/Retake inherit prior Segment legal size; otherwise H3/LTX registry."""
    for source in (previous, segment):
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
    return "minimax-h3" in token and "local" in token


def _canonical_generator(token: str) -> str:
    """Local MiniMax always uses the reference-to-video adapter."""
    if _is_local_h3(token):
        return LOCAL_H3_R2V
    return _registry().resolve_id(token)


def _h3_reference_ready(film: FilmTimeline, shot: Shot, generator_id: str, continue_from: Segment | None) -> bool:
    if not _is_local_h3(generator_id):
        return True
    if continue_from is not None and continue_from.assetId:
        return True
    if shot.state.firstFrameAssetId:
        return True
    return any(ref.assetId for ref in [*film.references, *shot.state.references])


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
    """Fields an adapter / H3 Director bridge may already understand.

    For MiniMax H3 Director Continue, ``priorAssetId`` + prior prompt/duration seed
    native Director continuity (segment cache + 2-group run). They are NOT R2V
    identity ``<Video K>`` refs — identity stays on image slots.
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
        }
    )
    return base


def _request_key(shot_id: str, segment: Segment, strategy: str, previous_id: str) -> str:
    raw = "|".join(
        [
            shot_id,
            segment.timedPrompt,
            f"{int(segment.durationSec)}",
            segment.generatorId or "",
            strategy,
            previous_id,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _build_request(project_id, scene_id, shot: Shot, segment: Segment, generator_id: str, strategy: str, previous: Segment | None, film: FilmTimeline):
    from ..director_timeline_w46.generation.contracts import TimelineGenerationRequest

    from .director_refs import build_director_refs, make_ref_slot
    from .references import provider_reference_slots

    role_for = {
        "character": "character",
        "environment": "place",
        "prop": "prop",
        "video": "video",
        "audio": "audio",
        "first_frame": "prior_frame",
        "storyboard": "reference",
        "image": "reference",
    }
    caps = _adapter(generator_id).capabilities
    slots: list[dict] = []
    seen: set[str] = set()
    for ref in provider_reference_slots([*film.references, *shot.state.references], caps):
        if ref.assetId in seen:
            continue
        seen.add(ref.assetId)
        slots.append(
            make_ref_slot(
                role=role_for.get(ref.type, "reference"),
                asset_id=ref.assetId,
                label=ref.label or ref.tag,
            )
        )
    start = shot.state.firstFrameAssetId
    if previous is not None:
        if strategy == "reference_video" and previous.assetId and previous.assetId not in seen:
            # Local H3 Director: prior MP4 is continuity state (native tail pin),
            # NOT an R2V <Video K> identity reference. Passing the full prior as
            # ref_video made Continue restart from the OPENING (job 56d1390b).
            if not _is_local_h3(generator_id):
                slots.append(make_ref_slot(role="video", asset_id=previous.assetId, label="Previous segment"))
        frame = previous.lastFrameAssetId or previous.assetId
        if frame and strategy in {"last_frame_chain", "first_last_frame", "reference_set"}:
            slots.append(make_ref_slot(role="prior_frame", asset_id=frame, label="Continue from"))
            start = frame if strategy != "reference_video" else start
    elif start and start not in seen:
        slots.append(make_ref_slot(role="prior_frame", asset_id=start, label="First frame"))

    prompt = segment.timedPrompt or shot.timedPrompt
    if shot.state.modelPrompt and segment.order == 0 and previous is None:
        prompt = shot.state.modelPrompt
    from .continuity import continuity_clause

    clause = continuity_clause(prompt, previous)
    if clause:
        prompt = f"{prompt}\n\n{clause}"
    mode = "text_to_video"
    if _is_local_h3(generator_id):
        mode = "reference"
    elif strategy == "last_frame_chain" and start and caps.supportsImageToVideo and not caps.supportsVideoReferences:
        mode = "image_to_video"
    elif slots and (caps.supportsReferenceToVideo or not caps.supportsTextToVideo):
        mode = "reference"
    elif start and caps.supportsImageToVideo:
        mode = "image_to_video"
    # Director-native refs: assign pictureIndex on plain dicts so queue_worker
    # staging keeps 9/3/3 + @Name ordering. No CanonicalR2VRequest / W46 r2v import.
    refs = build_director_refs(slots, mapped_start_asset_id=start, generator_id=generator_id)
    assigned_slots = refs["slots"]
    return TimelineGenerationRequest(
        projectId=project_id,
        sceneId=scene_id,
        batchBlockId=segment.id,
        executionSnapshotId=segment.id,
        generatorId=generator_id,
        generationMode=mode,  # type: ignore[arg-type]
        prompt=prompt,
        startImageAssetId=start if mode == "image_to_video" else None,
        duration=int(segment.durationSec),
        resolution=_segment_legal_resolution(shot, segment, generator_id, previous),
        lastFrameAssetId=previous.lastFrameAssetId if previous else None,
        videoReferenceAssetId=(
            None
            if previous and _is_local_h3(generator_id)
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
            "continuity": _continuity_options(previous),
            "requestedDurationSec": int(segment.durationSec),
            # Director cutover: local H3 Film Timeline always carries the flag
            # from request construction (also stamped again after legal-canvas).
            **({"useDirector": True} if _is_local_h3(generator_id) else {}),
        },
    )

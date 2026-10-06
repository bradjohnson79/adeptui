"""Long-form Review & Extend — one H3 continuation segment at a time.

Reuse law (docs/release-gate/timeline-extend/ADEPT_TIMELINE_MEDIA_INTELLIGENCE_AND_EXTEND.md):
this module orchestrates existing authorities only — it is not a second Timeline.

- Batch creation .......... service.add_batch (BatchBlock stays the stable container)
- Generation .............. orchestrator.generate_scene(scope="selected", batch_ids=[new])
- Ending anchors .......... continuity.extract_last_frame_png + the shot-end helpers
                            (last_frame_extract_seconds / last_frame_extract_frame)
- Continuity compile ...... longform_continuity.compile_longform_continuity
- Downstream invalidation . longform_continuity.mark_downstream_stale
- Perception .............. media_analyze.analyze_asset (never reimplemented here)
- H3 mode ................. longform_continuity.select_h3_mode (R2V when recurring
                            identity / environment matter, I2V when the last
                            frame is enough)

Clean native H3 path only: no Turbo LoRA default, no VDN, no SpeedCache, no Sage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..codirector.video_intelligence import media_analyze
from ..codirector.video_intelligence.contracts import TemporalContinuityPacket
from ..config import settings
from ..media_clip import probe_video_duration
from . import orchestrator, service, store
from .continuity import (
    extract_last_frame_png,
    last_frame_extract_frame,
    last_frame_extract_seconds,
)
from .contracts import (
    ExtendSegment,
    LongFormContinuityState,
    SceneTimelineMaster,
    TimelineVisualAnchor,
    _now,
)
from .longform_continuity import (
    compile_longform_continuity,
    mark_downstream_stale,
    select_h3_mode,
)

# Clean native H3 Timeline adapters (Route A :8192). The "i2v" row is the same
# canonical ref2va mechanism conditioned on the prior frame — never a Turbo /
# VDN / SpeedCache / Sage variant.
H3_R2V_GENERATOR_ID = "minimax-h3-t2v-local"
H3_I2V_GENERATOR_ID = "minimax-h3-i2v-local"

DEFAULT_EXTEND_DURATION_SEC = 5.0

# timelineActionError-style creator messages. Codes stay machine-stable; the
# message is what the Timeline surface shows.
CREATOR_ERRORS = {
    "SCENE_NOT_FOUND": "This scene could not be found.",
    "NO_PLAYABLE_SCENE_VIDEO": "There is no playable scene video to extend yet — finish at least one batch first.",
    "EXTEND_GENERATION_IN_FLIGHT": "A generation is already running for this scene. Wait for it to finish or cancel it first.",
    "EXTEND_IN_FLIGHT": "An Extend is already in progress for this scene.",
    "BATCH_CREATE_FAILED": "Adept could not add the next Batch Block for this Extend.",
    "ANCHOR_EXTRACT_FAILED": "Adept could not read the ending frame of the current scene video.",
    "EXTEND_GENERATION_FAILED": "The Extend generation could not be started.",
    "EXTEND_CANCELLED": "The Extend was cancelled. Earlier batches were left untouched.",
    "SEGMENT_NOT_FOUND": "That Extend segment could not be found.",
    "SEGMENT_HAS_NO_BATCH": "That Extend segment is not linked to a Batch Block.",
    "DURATION_EXCEEDS_GENERATOR": "That shot is longer than MiniMax H3 can run (15s). Shorten it or split it into batches.",
}


def _fail(code: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": code,
        "message": CREATOR_ERRORS.get(code, code),
        "mock": False,
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# (a) Current playable scene video — SAME project only.
# ---------------------------------------------------------------------------


def _resolve_current_playable(
    db: Session, project_id: str, master: SceneTimelineMaster
) -> dict[str, Any] | None:
    """Resolve the video the creator currently watches for this scene.

    Priority:
    1. sceneStitch — the joined full-scene preview — but only when it is
       already current against the approved takes (a stale stitch is fresher
       nowhere; the newest approved take wins instead).
    2. The highest-order approved take (approvedClip).
    3. The latest batch output (newest candidate asset, then batch video clips).

    Every candidate goes through scene_stitch.resolve_asset_file, which refuses
    assets from another project and missing files — extend never crosses the
    project boundary.
    """
    from .scene_stitch import collect_completed_sources, plan_stitch, resolve_asset_file

    sources = collect_completed_sources(master)
    source_asset_ids = [asset_id for _batch_id, asset_id in sources]

    stitch = master.sceneStitch
    if stitch and stitch.assetId:
        plan = plan_stitch(list(stitch.sourceAssetIds or []), source_asset_ids)
        if plan["mode"] == "already_current":
            path = resolve_asset_file(db, project_id, stitch.assetId)
            if path is not None:
                return {
                    "assetId": stitch.assetId,
                    "path": str(path),
                    "kind": "sceneStitch",
                    "batch": None,
                }

    if sources:
        batch_id, asset_id = sources[-1]
        path = resolve_asset_file(db, project_id, asset_id)
        if path is not None:
            batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
            return {"assetId": asset_id, "path": str(path), "kind": "approvedTake", "batch": batch}

    ordered = sorted(master.batchBlocks, key=lambda b: (int(b.order), b.createdAt or ""), reverse=True)
    for batch in ordered:
        candidates = [c for c in (batch.candidateVersions or []) if c.assetId]
        if candidates:
            latest = sorted(candidates, key=lambda c: c.createdAt or "")[-1]
            path = resolve_asset_file(db, project_id, str(latest.assetId))
            if path is not None:
                return {
                    "assetId": str(latest.assetId),
                    "path": str(path),
                    "kind": "batchOutput",
                    "batch": batch,
                }
        for clip in reversed(batch.visualClips or []):
            if clip.kind != "video" or not (clip.assetId or "").strip():
                continue
            path = resolve_asset_file(db, project_id, str(clip.assetId))
            if path is not None:
                return {
                    "assetId": str(clip.assetId),
                    "path": str(path),
                    "kind": "batchOutput",
                    "batch": batch,
                }
    return None


# ---------------------------------------------------------------------------
# (c) Scene reference bindings — CRS/ERS/PRS by canonical IDs, never chat names.
# ---------------------------------------------------------------------------

# scene_references reference_type -> long-form binding kind.
_BINDING_KIND_BY_TYPE = {
    "character": "crs",
    "environment": "ers",
    "location": "ers",
    "prop": "prs",
    "vehicle": "prs",
}


def _scene_reference_bindings(
    db: Session, project_id: str, scene_id: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Canonical scene reference bindings (scene scope + inherited ancestors).

    Returns (bindings, warning). Bindings carry bindingId/assetId/characterId —
    the generation path re-resolves them by ID at submit; alias text is display
    only and never reaches a prompt.
    """
    try:
        from ..scene_references import service as ref_service

        rows = ref_service.list_for_scope(db, project_id, "scene", scene_id, include_inherited=True)
    except Exception as exc:  # noqa: BLE001 - enrichment must not break extend
        return [], f"REFERENCE_BINDINGS_UNAVAILABLE:{str(exc)[:120]}"

    bindings: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("broken") or row.get("enabled") is False:
            continue
        kind = _BINDING_KIND_BY_TYPE.get(str(row.get("reference_type") or "").lower())
        if kind is None:
            continue  # style/lighting/motion etc. are not CRS/ERS/PRS state
        asset_id = str(row.get("asset_id") or "").strip()
        if not asset_id:
            continue
        bindings.append(
            {
                "bindingId": str(row.get("id") or "").strip() or None,
                "kind": kind,
                "assetId": asset_id,
                "characterId": (str(row.get("identity_id")).strip() or None) if row.get("identity_id") else None,
                "name": str(row.get("alias") or row.get("asset_name") or ""),
            }
        )
    return bindings, None


# ---------------------------------------------------------------------------
# (d) Ending anchors — existing extract stack only.
# ---------------------------------------------------------------------------


def _extract_ending_anchor(
    db: Session,
    project_id: str,
    video_path: str,
    *,
    source_batch: Any | None,
    token: str,
) -> dict[str, Any]:
    """Extract the ending anchor frame with the canonical continuity helpers.

    Stable end-region preference: when the playable source is a single approved
    batch, last_frame_extract_seconds / last_frame_extract_frame pick the
    planned shot end (latent-exact, skipping any appended reference-sheet tail)
    instead of the container EOF. When the source is the joined sceneStitch
    there is no single batch duration authority, so this falls back to the
    plain last-frame extract at EOF — same extract stack, documented here.
    """
    from ..db import Asset

    at_seconds = last_frame_extract_seconds(source_batch, video_path) if source_batch is not None else None
    at_frame = last_frame_extract_frame(source_batch, video_path) if source_batch is not None else None
    dest_dir = Path(settings.data_dir) / "assets" / project_id / "continuity"
    dest = dest_dir / f"{token}_extend_end.png"
    extract_last_frame_png(video_path, str(dest), at_seconds=at_seconds, at_frame=at_frame)
    frame_id = uuid4().hex
    frame = Asset(
        id=frame_id,
        project_id=project_id,
        tag="extend_end_frame",
        kind="image",
        filename=dest.name,
        path=str(dest),
    )
    db.add(frame)
    db.commit()
    return {
        "assetId": frame_id,
        "path": str(dest),
        "atSeconds": at_seconds,
        "atFrame": at_frame,
        "stableEndRegion": source_batch is not None,
    }


# ---------------------------------------------------------------------------
# (e) Legal H3 duration — never exceed generator max; honest snap, no silent 12s.
# ---------------------------------------------------------------------------


def legal_extend_duration(generator_id: str, requested: float | None) -> dict[str, Any]:
    """Snap the requested extend length onto the generator's legal grid.

    Default uses H3 creator seed (15s) when request is empty. MiniMax H3 max is 15s.
    Off-grid requests snap to the 17k+5 frame grid and the snap is disclosed.
    ``durationSec`` is the clean creator request; ``legalDurationSec``/frames are
    execution-only. Requests above 15s fail closed — never silently clamp to 8s.
    """
    from ..video_runtime.legal_canvas import is_minimax_h3_generator, snap_h3_timeline_duration

    if is_minimax_h3_generator(generator_id):
        snap = snap_h3_timeline_duration(
            float(requested) if requested and float(requested) > 0 else DEFAULT_EXTEND_DURATION_SEC
        )
        return {
            **snap,
            "requestedDurationSec": requested,
            "supportedDurations": [],
        }

    supported: list[float] = []
    try:
        from .generation.registry import get_registry

        caps = get_registry().capabilities(generator_id)
        supported = sorted(float(d) for d in (caps.supportedDurations or []) if d and float(d) > 0)
    except Exception:  # noqa: BLE001 - registry is in-memory; fall back to capability row
        supported = []

    max_dur: float | None = None
    try:
        from .generation.registry import get_registry

        caps = get_registry().capabilities(generator_id)
        if getattr(caps, "maxDurationSec", None):
            max_dur = float(caps.maxDurationSec)
    except Exception:  # noqa: BLE001
        max_dur = None
    if max_dur is None:
        max_dur = max(supported) if supported else None
    if max_dur is None:
        try:
            from .capabilities import get_generator

            gen = get_generator(generator_id)
            max_dur = float(gen.maxDurationSec) if gen and gen.maxDurationSec else None
        except Exception:  # noqa: BLE001
            max_dur = None
    if max_dur is None or max_dur <= 0:
        max_dur = DEFAULT_EXTEND_DURATION_SEC

    req = float(requested) if requested and float(requested) > 0 else DEFAULT_EXTEND_DURATION_SEC
    if req > max_dur + 1e-6:
        return {
            "ok": False,
            "durationSec": None,
            "requestedDurationSec": requested,
            "maxDurationSec": max_dur,
            "supportedDurations": supported,
            "snapped": False,
            "message": f"This shot is {req:g}s. The selected engine can run up to {max_dur:g}s. Shorten it or split it into batches.",
        }
    if supported:
        eligible = [d for d in supported if d <= req + 1e-6]
        applied = max(eligible) if eligible else min(supported)
    else:
        applied = req
    applied = min(applied, max_dur)
    return {
        "ok": True,
        "durationSec": applied,
        "requestedDurationSec": requested,
        "maxDurationSec": max_dur,
        "supportedDurations": supported,
        "snapped": abs(applied - req) > 1e-6,
    }


# ---------------------------------------------------------------------------
# Mode + prompt compile
# ---------------------------------------------------------------------------


def _select_mode(state: LongFormContinuityState) -> tuple[str, str]:
    """I2V when the last frame is enough; R2V when Korri/Anadriya + ERS matter."""
    characters = [c for c in (state.characters or []) if (c.label or c.characterId or c.crsAssetId)]
    multi_character = len(characters) >= 2
    has_ers = bool((state.environment or {}).get("ersAssetId"))
    identity_risk = any(bool(c.crsAssetId or c.characterId) for c in characters)
    mode = select_h3_mode(multi_character=multi_character, has_ers=has_ers, identity_risk=identity_risk)
    generator_id = H3_R2V_GENERATOR_ID if mode == "r2v" else H3_I2V_GENERATOR_ID
    return mode, generator_id


def _compile_segment_prompt(prompt_text: str, state: LongFormContinuityState) -> str:
    """Creator direction verbatim when present; otherwise compile from the
    Continuity Packet so an empty Extend still continues the reviewed scene."""
    if prompt_text:
        return prompt_text
    bits: list[str] = []
    if state.storyState:
        bits.append(f"Continue: {state.storyState}")
    labels = [c.label for c in (state.characters or []) if c.label]
    if labels:
        bits.append("Keep " + ", ".join(labels[:4]) + " consistent.")
    location = str((state.environment or {}).get("locationState") or "").strip()
    if location:
        bits.append(f"Same place: {location}.")
    if state.nextIntent:
        bits.append(state.nextIntent)
    return " ".join(bits).strip() or "Continue the scene from the last frame."


def _extend_question(prompt_text: str) -> str:
    """Timeline context for the perception pass (question is the only injection
    channel analyze_asset exposes — perception itself is never reimplemented)."""
    context = (
        "\nTimeline context: this is the current playable video of a scene the creator is about to Extend. "
        "Pay special attention to the ending state — who is on screen, where they are, what is in motion, "
        "and any unfinished dialogue — because the next generated segment must continue from it."
    )
    if prompt_text:
        context += f"\nCreator's direction for the continuation: {prompt_text}"
    return media_analyze.ANALYZE_QUESTION + context


def _latest_temporal_packet(master: SceneTimelineMaster) -> TemporalContinuityPacket | None:
    packets = list(master.temporalPackets or [])
    if not packets:
        return None
    latest = packets[-1]
    if isinstance(latest, TemporalContinuityPacket):
        return latest
    try:
        return TemporalContinuityPacket.model_validate(latest)
    except Exception:  # noqa: BLE001
        return None


def _is_cancellation(result: dict[str, Any], master: SceneTimelineMaster, batch_id: str) -> bool:
    def _blob_cancelled(blob: Any) -> bool:
        if not isinstance(blob, dict):
            return False
        for key in ("error", "status", "message"):
            if "cancel" in str(blob.get(key) or "").lower():
                return True
        return False

    if _blob_cancelled(result):
        return True
    for item in list(result.get("jobs") or []) + list(result.get("errors") or []):
        if _blob_cancelled(item):
            return True
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    return bool(batch is not None and batch.status == "Cancelled")


def _reload_master(db: Session, project_id: str, scene_id: str) -> SceneTimelineMaster | None:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return None
    return SceneTimelineMaster.model_validate(payload["master"])


def _find_segment(master: SceneTimelineMaster, segment_id: str) -> ExtendSegment | None:
    return next((s for s in master.extendSegments if s.segmentId == segment_id), None)


# ---------------------------------------------------------------------------
# review_and_extend — the timeline.extend service entry point.
# ---------------------------------------------------------------------------


def review_and_extend(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    prompt: str | None = None,
    duration_sec: float | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Retired. Continue Shot is the production continuation path."""
    _ = (db, project_id, scene_id, prompt, duration_sec, force)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Continue Shot is the production continuation path.",
        "mock": False,
    }

def retake_extend_segment(
    db: Session,
    project_id: str,
    scene_id: str,
    segment_id: str,
    *,
    prompt: str | None = None,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    """Retired. Regenerate the Film Timeline segment."""
    _ = (db, project_id, scene_id, segment_id, prompt, duration_sec)
    return {
        "ok": False,
        "error": "FILM_TIMELINE_REQUIRED",
        "message": "Regenerate the Film Timeline segment.",
        "mock": False,
    }


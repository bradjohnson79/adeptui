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
    """Review the current scene video and extend it by ONE legal H3 segment.

    The creator still sees one scene; Extend appends the next Batch Block and
    generates only that batch. Prior batches are never regenerated here.
    """
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])
    prompt_text = (prompt or "").strip()

    # One H3 generation resident at a time.
    if not force:
        if any(b.status in ("Generating", "Queued") for b in master.batchBlocks):
            return _fail("EXTEND_GENERATION_IN_FLIGHT")
        if any(s.status == "generating" for s in master.extendSegments):
            return _fail("EXTEND_IN_FLIGHT")

    # (a) current playable scene video — same project only.
    source = _resolve_current_playable(db, project_id, master)
    if source is None:
        return _fail("NO_PLAYABLE_SCENE_VIDEO")
    source_batch = source.get("batch")

    # (b) Media Intelligence on the full clip (cached unless force).
    probed = probe_video_duration(source["path"])
    packet = media_analyze.analyze_asset(
        db,
        project_id,
        source["assetId"],
        mode="full",
        question=_extend_question(prompt_text),
        duration_sec=float(probed) if probed and probed > 0 else 6.0,
        persist=True,
        force=force,
    )

    # (c) compile the Long-form Continuity Packet from existing authorities.
    bindings, bindings_warning = _scene_reference_bindings(db, project_id, scene_id)
    state = compile_longform_continuity(
        project_id=project_id,
        scene_id=scene_id,
        master=master,
        media_packet=packet,
        temporal=_latest_temporal_packet(master),
        next_intent=prompt_text,
        reference_bindings=bindings,
    )

    # (d) ending anchors. Anchor failure is disclosed, not hidden: the
    # ContinuityBridge prepared by add_batch may still supply the prior frame,
    # and adapter validation fails honestly if neither exists.
    anchor: dict[str, Any] | None = None
    anchor_error: str | None = None
    try:
        anchor = _extract_ending_anchor(
            db,
            project_id,
            source["path"],
            source_batch=source_batch,
            token=uuid4().hex[:12],
        )
    except Exception as exc:  # noqa: BLE001
        anchor_error = str(exc)[:300]

    # Mode + generator (clean native H3 only).
    h3_mode, generator_id = _select_mode(state)

    # (e) legal duration — honest snap, never above the generator max.
    duration = legal_extend_duration(generator_id, duration_sec)
    if duration.get("ok") is False:
        return _fail(
            "DURATION_EXCEEDS_GENERATOR",
            message=duration.get("message"),
            plannedDuration=duration.get("requestedDurationSec"),
            maxDurationSec=duration.get("maxDurationSec"),
        )

    # (e2) next Batch Block via the canonical service (also prepares the
    # outgoing ContinuityBridge from the last approved batch).
    batch_res = service.add_batch(
        db,
        project_id,
        scene_id,
        label=f"Extend {len(master.extendSegments) + 1}",
        planned_duration=float(duration.get("requestedDurationSec") or duration["durationSec"]),
        generator_id=generator_id,
    )
    if not batch_res.get("ok"):
        return _fail("BATCH_CREATE_FAILED", detail=str(batch_res.get("error") or "")[:200])
    batch_id = str(batch_res["batch"]["id"])

    # Wire the segment prompt + canonical reference bindings + ending anchor
    # onto the batch. touch_batch_config projects prompt segments back to the
    # legacy lane so submit-time reference compile resolves binding IDs.
    compiled_prompt = _compile_segment_prompt(prompt_text, state)
    binding_ids = [b["bindingId"] for b in bindings if b.get("bindingId")]
    prompt_segment: dict[str, Any] = {
        "start": 0.0,
        "length": float(duration.get("requestedDurationSec") or duration["durationSec"]),
        "text": compiled_prompt,
        "role": "primary",
        "userDirection": prompt_text or None,
        "referenceBindingIds": binding_ids,
    }
    anchors = []
    if anchor:
        anchors.append(
            TimelineVisualAnchor(
                kind="image",
                assetId=anchor["assetId"],
                label="Extend From",
                atTime=0.0,
            ).model_dump()
        )
    orchestrator.touch_batch_config(
        db,
        project_id,
        scene_id,
        batch_id,
        {
            "generatorId": generator_id,
            "promptSegments": [prompt_segment],
            "sourceAnchors": anchors,
        },
    )

    # (f) persist ExtendSegment + longFormContinuity on the master.
    master = _reload_master(db, project_id, scene_id) or master
    state.endingAnchors = list(state.endingAnchors or []) + ([dict(anchor, kind="extend_end")] if anchor else [])
    state.updatedAt = _now()
    segment = ExtendSegment(
        batchBlockId=batch_id,
        prompt=prompt_text,
        compiledPrompt=compiled_prompt,
        continuityRevision=int(state.revision or 0),
        inputAnchors=[anchor["assetId"]] if anchor else [],
        referenceAssetIds=[b["assetId"] for b in bindings],
        h3Mode=h3_mode,  # type: ignore[arg-type]
        durationSec=float(duration.get("requestedDurationSec") or duration["durationSec"]),
        status="planned",
    )
    master.longFormContinuity = state
    master.extendSegments.append(segment)
    master.lastMediaIntelligencePacketId = packet.packetId
    store.save_master(db, project_id, scene_id, master, touch_batches=False)

    # (g) generate ONLY the new batch — one H3 segment, prior batches untouched.
    segment.status = "generating"
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    result = orchestrator.generate_scene(db, project_id, scene_id, scope="selected", batch_ids=[batch_id])

    master = _reload_master(db, project_id, scene_id) or master
    segment = _find_segment(master, segment.segmentId) or segment

    if result.get("ok"):
        jobs = list(result.get("jobs") or [])
        segment.executionId = str(jobs[0].get("jobId") or jobs[0].get("id") or "") or None
        segment.status = "generating"
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return {
            "ok": True,
            "segment": segment.model_dump(),
            "batchId": batch_id,
            "generatorId": generator_id,
            "h3Mode": h3_mode,
            "durationSnap": duration,
            "endingAnchor": anchor,
            "anchorError": anchor_error,
            "bindingsWarning": bindings_warning,
            "longFormContinuity": state.model_dump(),
            "mediaIntelligence": {
                "packetId": packet.packetId,
                "availability": packet.availability,
                "reason": packet.reason,
            },
            "generation": result,
            "mock": False,
        }

    # (h) honest failure — surface the timelineActionError-style message.
    # (i) cancel — segment cancelled; prior batches untouched.
    if _is_cancellation(result, master, batch_id):
        segment.status = "cancelled"
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return _fail(
            "EXTEND_CANCELLED",
            segment=segment.model_dump(),
            batchId=batch_id,
            generation=result,
        )
    segment.status = "failed"
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    code = str(result.get("error") or "EXTEND_GENERATION_FAILED")
    return _fail(
        "EXTEND_GENERATION_FAILED",
        detail=code,
        generationMessage=str(result.get("message") or "")[:300],
        segment=segment.model_dump(),
        batchId=batch_id,
        generation=result,
    )


# ---------------------------------------------------------------------------
# Segment take replacement — downstream invalidation (Chapter 28).
# ---------------------------------------------------------------------------


def retake_extend_segment(
    db: Session,
    project_id: str,
    scene_id: str,
    segment_id: str,
    *,
    prompt: str | None = None,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    """Replace an earlier extend segment's take and invalidate downstream continuity.

    Only the segment's own batch is regenerated (scope="selected"); every later
    segment is marked stale via the canonical mark_downstream_stale authority.
    """
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])
    segment = _find_segment(master, segment_id)
    if segment is None:
        return _fail("SEGMENT_NOT_FOUND")
    if not segment.batchBlockId:
        return _fail("SEGMENT_HAS_NO_BATCH")
    batch = next((b for b in master.batchBlocks if b.id == segment.batchBlockId), None)
    if batch is None:
        return _fail("SEGMENT_HAS_NO_BATCH")

    prompt_text = (prompt if prompt is not None else segment.prompt or "").strip()
    duration: dict[str, Any] | None = None
    if duration_sec is not None:
        duration = legal_extend_duration(batch.generatorId or H3_R2V_GENERATOR_ID, duration_sec)
        if duration.get("ok") is False:
            return _fail(
                "DURATION_EXCEEDS_GENERATOR",
                message=duration.get("message"),
                plannedDuration=duration.get("requestedDurationSec"),
                maxDurationSec=duration.get("maxDurationSec"),
            )
    if prompt is not None or duration is not None:
        # Route batch edits through touch_batch_config so the prompt projection
        # back to the legacy lane keeps generation input and visible track as
        # one truth (direct batch edits would be clobbered by reconcile).
        # H3 17k+5 snap is request-scoped: request_builder snaps at generation
        # time and discloses. The batch plan keeps the creator's chosen
        # duration — never persist the snapped grid value.
        planned: float | None = None
        if duration is not None:
            planned = float(duration["durationSec"])
            from ..video_runtime.legal_canvas import is_minimax_h3_generator

            if is_minimax_h3_generator(batch.generatorId or H3_R2V_GENERATOR_ID) and duration.get(
                "requestedDurationSec"
            ):
                planned = float(duration["requestedDurationSec"])
        new_length = planned or float(
            batch.duration.plannedDuration or DEFAULT_EXTEND_DURATION_SEC
        )
        compiled = _compile_segment_prompt(
            prompt_text, master.longFormContinuity or LongFormContinuityState()
        )
        patch: dict[str, Any] = {
            "promptSegments": [
                {
                    "start": 0.0,
                    "length": new_length,
                    "text": compiled,
                    "role": "primary",
                    "userDirection": prompt_text or None,
                    "referenceBindingIds": list(batch.promptSegments[0].referenceBindingIds)
                    if batch.promptSegments
                    else [],
                }
            ],
        }
        if duration is not None:
            patch["plannedDuration"] = planned
        orchestrator.touch_batch_config(db, project_id, scene_id, batch.id, patch)
        master = _reload_master(db, project_id, scene_id) or master
        segment = _find_segment(master, segment_id) or segment
        segment.prompt = prompt_text
        segment.compiledPrompt = compiled
        if duration is not None:
            segment.durationSec = planned

    # Replacing an earlier take invalidates later continuity.
    mark_downstream_stale(master, from_segment_id=segment_id)
    segment = _find_segment(master, segment_id) or segment
    segment.status = "generating"
    store.save_master(db, project_id, scene_id, master, touch_batches=False)

    result = orchestrator.generate_scene(
        db, project_id, scene_id, scope="selected", batch_ids=[segment.batchBlockId]
    )

    master = _reload_master(db, project_id, scene_id) or master
    segment = _find_segment(master, segment_id) or segment
    if result.get("ok"):
        jobs = list(result.get("jobs") or [])
        segment.executionId = str(jobs[0].get("jobId") or jobs[0].get("id") or "") or None
        segment.status = "generating"
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return {
            "ok": True,
            "segment": segment.model_dump(),
            "batchId": segment.batchBlockId,
            "downstreamStale": True,
            "staleFromSegmentId": segment_id,
            "generation": result,
            "mock": False,
        }
    if _is_cancellation(result, master, segment.batchBlockId):
        segment.status = "cancelled"
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return _fail("EXTEND_CANCELLED", segment=segment.model_dump(), generation=result)
    segment.status = "failed"
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return _fail(
        "EXTEND_GENERATION_FAILED",
        detail=str(result.get("error") or "")[:200],
        segment=segment.model_dump(),
        generation=result,
    )

"""Embedded Co-Director temporal review. Timeline calls this; chat is irrelevant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .cadence import intended_text_from_batch, resolve_cadence, window_seconds
from .clip_extract import extract_window
from .compare import compare_intent_vs_actual
from .contracts import (
    CoDirectorContinuityPolicy,
    PacketSource,
    TemporalContinuityPacket,
)
from .gpu_lease import best_effort_free_generator, preflight_for_review
from .observability import emit
from .worker_client import perception_mode, run_perception

logger = logging.getLogger(__name__)


def _policy(master: Any) -> CoDirectorContinuityPolicy:
    raw = getattr(master, "coDirectorContinuityPolicy", None)
    if isinstance(raw, CoDirectorContinuityPolicy):
        return raw
    if isinstance(raw, dict):
        return CoDirectorContinuityPolicy.model_validate(raw)
    return CoDirectorContinuityPolicy()


def set_codirector_continuity_policy(master: Any, updates: dict[str, Any]) -> CoDirectorContinuityPolicy:
    current = _policy(master)
    data = current.model_dump()
    allowed = {
        "enabled",
        "reviewCadence",
        "protection",
        "fastVisionModel",
        "deepReview",
        "showDebugState",
        "rejectedPacketIds",
        "creatorNextBatchNote",
    }
    for key, value in (updates or {}).items():
        if key in allowed:
            data[key] = value
    policy = CoDirectorContinuityPolicy.model_validate(data)
    master.coDirectorContinuityPolicy = policy
    return policy


def find_packet_for_handoff(master: Any, source_batch_id: str, target_batch_id: str) -> TemporalContinuityPacket | None:
    packets = getattr(master, "temporalPackets", None) or []
    for item in reversed(list(packets)):
        pkt = item if isinstance(item, TemporalContinuityPacket) else TemporalContinuityPacket.model_validate(item)
        if pkt.source.batchId == source_batch_id and (pkt.source.targetBatchId or "") == target_batch_id:
            return pkt
    return None


def previous_batch(master: Any, target_batch_id: str):
    batches = sorted(getattr(master, "batchBlocks", None) or [], key=lambda b: int(getattr(b, "order", 0)))
    prev = None
    for batch in batches:
        if batch.id == target_batch_id:
            return prev
        prev = batch
    return None


def packet_blocks_submit(master: Any, target_batch_id: str) -> bool:
    """True when Continuity is ON, a predecessor exists, and no gate-ready packet exists."""
    policy = _policy(master)
    if not policy.enabled:
        return False
    pred = previous_batch(master, target_batch_id)
    if pred is None or not getattr(getattr(pred, "approvedClip", None), "assetId", None):
        return False
    packet = find_packet_for_handoff(master, pred.id, target_batch_id)
    return packet is None or not packet.is_gate_ready()


def persist_unavailable_packet(
    master: Any,
    *,
    project_id: str,
    scene_id: str,
    source_batch: Any,
    target_batch_id: str | None,
    reason: str,
    extras: dict[str, Any] | None = None,
) -> TemporalContinuityPacket:
    packet = _degraded(
        project_id=project_id,
        scene_id=scene_id,
        source_batch=source_batch,
        target_batch_id=target_batch_id,
        reason=reason,
        extras=extras,
    )
    _persist(master, packet, source_batch, target_batch_id)
    return packet


def _degraded(
    *,
    project_id: str,
    scene_id: str,
    source_batch: Any,
    target_batch_id: str | None,
    reason: str,
    extras: dict[str, Any] | None = None,
) -> TemporalContinuityPacket:
    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason=reason,
        source=PacketSource(
            projectId=project_id,
            sceneId=scene_id,
            batchId=source_batch.id,
            targetBatchId=target_batch_id,
            generatorId=getattr(source_batch, "generatorId", None),
        ),
        creatorMarker="Co-Director visual continuity unavailable",
        extras=extras or {},
    )
    emit("temporal_continuity_unavailable", packetId=packet.packetId, reason=reason, batchId=source_batch.id)
    return packet


def _intent_context(project_id: str, batch: Any, prior: TemporalContinuityPacket | None) -> dict[str, Any]:
    prompt = intended_text_from_batch(batch)
    scene_intent = ""
    camera_intent = ""
    spatial_text = ""
    cams = getattr(batch, "cameraInstructions", None) or []
    if cams:
        camera_intent = str(getattr(cams[0], "motion_type", "") or getattr(cams[0], "label", ""))
    try:
        from ...spatial_map.service import list_documents
        from ...db import SessionLocal

        db = SessionLocal()
        try:
            docs = list_documents(db, project_id) or []
            if docs:
                doc = docs[0]
                intent = getattr(doc, "sceneIntent", None) or getattr(doc, "scene_intent", None)
                if isinstance(intent, dict):
                    scene_intent = str(
                        intent.get("summary")
                        or intent.get("productionIntent")
                        or intent.get("action")
                        or ""
                    )
                elif intent is not None:
                    scene_intent = str(
                        getattr(intent, "summary", "")
                        or getattr(intent, "productionIntent", "")
                        or ""
                    )
                cameras = getattr(doc, "cameras", None) or []
                if cameras and not camera_intent:
                    cam = cameras[0]
                    if isinstance(cam, dict):
                        camera_intent = str(
                            cam.get("label") or cam.get("shotSize") or cam.get("movementType") or ""
                        )
                    else:
                        camera_intent = str(
                            getattr(cam, "label", "") or getattr(cam, "shotSize", "") or ""
                        )
                spatial_text = str(getattr(doc, "id", "") or "")
        finally:
            db.close()
    except Exception:
        pass
    prior_text = ""
    if prior is not None:
        prior_text = " ".join(prior.continuation.nextBatchDirectives)
    return {
        "prompt": prompt,
        "sceneIntent": scene_intent,
        "cameraIntent": camera_intent,
        "spatialMap": spatial_text,
        "priorContinuation": prior_text,
    }


def _asset_path(db: Any, asset_id: str) -> str | None:
    if db is None or not asset_id:
        return None
    try:
        from ...db import Asset

        asset = db.get(Asset, asset_id)
        path = getattr(asset, "path", None) if asset is not None else None
        if path and Path(str(path)).is_file():
            return str(path)
    except Exception:
        return None
    return None


def _should_deep_review(policy: CoDirectorContinuityPolicy, observation_confidence: float | None, multi_batch: bool) -> bool:
    if policy.deepReview == "off":
        return False
    if policy.deepReview == "on":
        return True
    if observation_confidence is not None and observation_confidence < 0.45:
        return True
    return bool(multi_batch)


def review_completed_batch(
    db: Any,
    project_id: str,
    scene_id: str,
    master: Any,
    source_batch: Any,
    *,
    target_batch_id: str | None,
) -> TemporalContinuityPacket:
    policy = _policy(master)
    existing = find_packet_for_handoff(master, source_batch.id, target_batch_id or "")
    if existing is not None and existing.is_gate_ready():
        return existing

    prompt = intended_text_from_batch(source_batch)
    cameras = getattr(source_batch, "cameraInstructions", None) or []
    camera_motion = str(getattr(cameras[0], "motion_type", "") if cameras else "")
    refs = getattr(source_batch, "references", None) or []
    character_ids = {
        str(ref.get("characterId") or ref.get("identityId") or "")
        for ref in refs
        if isinstance(ref, dict) and (ref.get("characterId") or ref.get("identityId"))
    }
    cadence = resolve_cadence(
        policy,
        prompt=prompt,
        camera_motion=camera_motion,
        character_count=len(character_ids),
        has_movement_layers=any(
            getattr(seg, "movementSegmentRef", None) for seg in (getattr(source_batch, "promptSegments", None) or [])
        ),
    )
    duration = None
    if getattr(source_batch, "duration", None) is not None:
        duration = source_batch.duration.generatedDuration or source_batch.duration.plannedDuration
    window = window_seconds(cadence, duration)
    emit(
        "review_started",
        batchId=source_batch.id,
        cadence=cadence,
        window=window,
        mode=perception_mode(),
    )

    clip = getattr(source_batch, "approvedClip", None)
    video_path = _asset_path(db, getattr(clip, "assetId", "") if clip else "")
    extras: dict[str, Any] = {"reviewCadence": cadence, "windowSec": window}

    if not video_path:
        packet = _degraded(
            project_id=project_id,
            scene_id=scene_id,
            source_batch=source_batch,
            target_batch_id=target_batch_id,
            reason="SOURCE_VIDEO_MISSING",
            extras=extras,
        )
        _persist(master, packet, source_batch, target_batch_id)
        return packet

    mode = perception_mode()
    if mode not in ("stub", "1", "true", "yes", "fail", "error"):
        extras["gpuLease"] = best_effort_free_generator()
        preflight = preflight_for_review()
        extras["gpuPreflight"] = preflight
        if not preflight.get("ok"):
            packet = _degraded(
                project_id=project_id,
                scene_id=scene_id,
                source_batch=source_batch,
                target_batch_id=target_batch_id,
                reason=str(preflight.get("reason") or "INSUFFICIENT_VRAM"),
                extras=extras,
            )
            _persist(master, packet, source_batch, target_batch_id)
            return packet
    else:
        extras["gpuLease"] = {"skipped": True, "reason": f"perception_mode={mode}"}

    review_path = video_path
    start = max(0.0, float(duration or window) - window)
    if cadence in ("interval_3", "interval_5") and duration and duration > window + 0.05:
        try:
            from ...config import settings

            dest = Path(settings.data_dir) / "assets" / project_id / "temporal" / f"{source_batch.id}_{cadence}.mp4"
            review_path = extract_window(video_path, str(dest), start_sec=start, duration_sec=window)
            extras["extractedClip"] = review_path
        except Exception as exc:
            extras["extractError"] = str(exc)[:240]
            review_path = video_path

    prior = None
    if target_batch_id:
        pred = previous_batch(master, source_batch.id)
        if pred is not None:
            prior = find_packet_for_handoff(master, pred.id, source_batch.id)

    packet = TemporalContinuityPacket(
        source=PacketSource(
            projectId=project_id,
            sceneId=scene_id,
            batchId=source_batch.id,
            targetBatchId=target_batch_id,
            generatorId=getattr(source_batch, "generatorId", None),
            startTime=start,
            endTime=start + window,
            reviewCadence=cadence,
            perceptionModelId=policy.fastVisionModel,
        ),
        extras=extras,
    )
    try:
        observation = run_perception(review_path, model_id=policy.fastVisionModel)
        packet.source.perceptionModelId = observation.modelId or policy.fastVisionModel
        context = _intent_context(project_id, source_batch, prior)
        packet = compare_intent_vs_actual(
            packet,
            observation,
            context=context,
            protection=policy.protection,
        )
        note = str(policy.creatorNextBatchNote or "").strip()
        if note:
            packet.continuation.nextBatchDirectives = list(packet.continuation.nextBatchDirectives or []) + [note]
        if _should_deep_review(policy, observation.confidence, bool(prior)):
            try:
                deep = run_perception(review_path, model_id="internvideo3-8b-instruct")
                packet.source.deepReviewInvoked = True
                packet.extras["deepReview"] = {"rawText": deep.rawText[:800], "modelId": deep.modelId}
            except Exception as exc:
                packet.extras["deepReviewUnavailable"] = str(exc)[:240]
        emit(
            "temporal_continuity_compiled",
            packetId=packet.packetId,
            availability=packet.availability,
            cadence=cadence,
            model=packet.source.perceptionModelId,
            deepReview=packet.source.deepReviewInvoked,
        )
    except Exception as exc:
        packet = _degraded(
            project_id=project_id,
            scene_id=scene_id,
            source_batch=source_batch,
            target_batch_id=target_batch_id,
            reason=str(exc)[:80],
            extras=extras,
        )
    _persist(master, packet, source_batch, target_batch_id)
    return packet


def _persist(master: Any, packet: TemporalContinuityPacket, source_batch: Any, target_batch_id: str | None) -> None:
    packets = list(getattr(master, "temporalPackets", None) or [])
    packets = [
        p
        for p in packets
        if not (
            getattr(getattr(p, "source", None), "batchId", None) == source_batch.id
            and getattr(getattr(p, "source", None), "targetBatchId", None) == target_batch_id
        )
    ]
    packets.append(packet)
    master.temporalPackets = packets
    for bridge in getattr(master, "continuityBridges", None) or []:
        if bridge.sourceBatchId == source_batch.id and (
            not target_batch_id or bridge.targetBatchId == target_batch_id
        ):
            state = dict(bridge.continuityState or {})
            state["temporalPacketId"] = packet.packetId
            state["temporalAvailability"] = packet.availability
            bridge.continuityState = state


def ensure_temporal_packet_before_submit(
    db: Any,
    project_id: str,
    scene_id: str,
    master: Any,
    target_batch_id: str,
) -> TemporalContinuityPacket | None:
    """MULTI-BATCH GOVERNANCE LAW. Never submit N+1 without a ready or degraded packet."""
    policy = _policy(master)
    if not policy.enabled:
        return None
    pred = previous_batch(master, target_batch_id)
    if pred is None or not getattr(getattr(pred, "approvedClip", None), "assetId", None):
        return None
    existing = find_packet_for_handoff(master, pred.id, target_batch_id)
    if existing is not None and existing.is_gate_ready():
        return existing
    return review_completed_batch(
        db,
        project_id,
        scene_id,
        master,
        pred,
        target_batch_id=target_batch_id,
    )

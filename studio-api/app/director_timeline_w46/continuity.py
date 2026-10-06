"""Timeline Auto-Extend helpers.

Extend = creator-facing Adept UI capability.
ContinuityBridge = internal Timeline handoff.

Do not invent an Extend track. Do not claim native continuation when Adept UI
performed last-frame I2V.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ..media_clip import extract_frame_png, ltx_latent_frame_count, probe_video_duration, shot_last_frame_seconds
from .contracts import (
    CURRENT_CONTINUITY_CONTEXT_VERSION,
    ContinuityBridge,
    ContinuityPolicy,
    ContinuityStrategy,
    SceneTimelineMaster,
)

LOCALITY = Literal["local", "api"]

# Paid/hosted generators must never run background continuity when Auto Continuity is Off.
API_GENERATOR_PREFIXES = ("seedance", "kling", "fal_", "veo", "runway")


def effective_tail_duration(configured_tail: float, actual_generated_duration: float | None) -> float:
    """Runtime window: min(configured, actual). Never assume a model is always 5s.

    Future 15s MiniMax batches use a rolling last-5s window with no schema change.
    A 3.2s clip with configured 5s uses 3.2s. Off (0) stays 0.
    """
    configured = max(0.0, float(configured_tail or 0.0))
    if configured <= 0:
        return 0.0
    actual = float(actual_generated_duration) if actual_generated_duration and actual_generated_duration > 0 else configured
    return min(configured, actual)


def default_policy_for_locality(locality: LOCALITY) -> ContinuityPolicy:
    if locality == "local":
        return ContinuityPolicy(
            autoContinuity=True,
            configuredTailDuration=5.0,
            locality="local",
            continuityAwareRetake=True,
        )
    return ContinuityPolicy(
        autoContinuity=False,
        configuredTailDuration=0.0,
        locality="api",
        continuityAwareRetake=False,
    )


def generator_locality(generator_id: str | None) -> LOCALITY:
    gid = (generator_id or "").strip().lower()
    if any(gid.startswith(p) or p in gid for p in API_GENERATOR_PREFIXES):
        return "api"
    return "local"


def should_prepare_bridge(policy: ContinuityPolicy, generator_id: str | None) -> bool:
    """No background continuity work when Auto Continuity is Off (API credit safety)."""
    if not policy.autoContinuity:
        return False
    if policy.configuredTailDuration <= 0:
        return False
    if generator_locality(generator_id) == "api" and not policy.autoContinuity:
        return False
    return True


def paid_continuity_forbidden(policy: ContinuityPolicy, generator_id: str | None) -> bool:
    """True when a paid-provider continuity job must not start."""
    return generator_locality(generator_id) == "api" and not policy.autoContinuity


def new_bridge(
    *,
    scene_id: str,
    source_batch_id: str,
    target_batch_id: str,
    source_take_id: str | None,
    configured_tail: float,
    actual_generated_duration: float | None,
) -> ContinuityBridge:
    effective = effective_tail_duration(configured_tail, actual_generated_duration)
    return ContinuityBridge(
        sceneId=scene_id,
        sourceBatchId=source_batch_id,
        targetBatchId=target_batch_id,
        sourceTakeId=source_take_id,
        contextVersion=CURRENT_CONTINUITY_CONTEXT_VERSION,
        configuredTailDuration=float(configured_tail or 0.0),
        effectiveTailDuration=effective,
        continuityStrategy="none",
        status="Waiting",
    )


def active_bridge_for_target(master: SceneTimelineMaster, target_batch_id: str) -> ContinuityBridge | None:
    bridges = [b for b in master.continuityBridges if b.targetBatchId == target_batch_id and b.status != "Superseded"]
    if not bridges:
        return None
    return sorted(bridges, key=lambda b: b.createdAt, reverse=True)[0]


def declare_strategy(used: ContinuityStrategy) -> ContinuityStrategy:
    """Adapters must persist the strategy they actually used."""
    return used


def empty_retake_memory() -> dict[str, Any]:
    return {
        "sequenceMemory": {},
        "incomingContinuity": {},
        "originalTakeIntent": {},
        "takeState": {},
        "userCorrection": {},
    }


def ensure_policy(master: SceneTimelineMaster, generator_id: str | None) -> ContinuityPolicy:
    """Apply locality defaults without overwriting an explicit API creator choice."""
    loc = generator_locality(generator_id)
    existing = master.continuityPolicy
    if loc == "local":
        master.continuityPolicy = default_policy_for_locality("local")
        return master.continuityPolicy
    if existing.locality != "api":
        master.continuityPolicy = default_policy_for_locality("api")
    else:
        master.continuityPolicy.locality = "api"
    return master.continuityPolicy


def next_batch_after(master: SceneTimelineMaster, source_batch_id: str):
    ordered = sorted(master.batchBlocks, key=lambda b: b.order)
    for idx, batch in enumerate(ordered):
        if batch.id == source_batch_id and idx + 1 < len(ordered):
            return ordered[idx + 1]
    return None


def extract_last_frame_png(
    video_path: str,
    dest_path: str,
    *,
    at_seconds: float | None = None,
    at_frame: int | None = None,
) -> None:
    extract_frame_png(video_path, dest_path, at_seconds=at_seconds, at_frame=at_frame)


def last_frame_extract_seconds(source: Any, video_path: str) -> float | None:
    """Use the requested shot end when Ingredients appended the reference sheet."""
    planned = None
    if source is not None and getattr(source, "duration", None) is not None:
        planned = (
            getattr(source.duration, "plannedDuration", None)
            or getattr(source.duration, "timelineVisibleDuration", None)
        )
    file_dur = probe_video_duration(video_path)
    if planned and float(planned) > 0 and file_dur and file_dur > float(planned) + 0.35:
        return shot_last_frame_seconds(float(planned))
    return None


def last_frame_extract_frame(source: Any, video_path: str) -> int | None:
    planned = None
    if source is not None and getattr(source, "duration", None) is not None:
        planned = (
            getattr(source.duration, "plannedDuration", None)
            or getattr(source.duration, "timelineVisibleDuration", None)
        )
    file_dur = probe_video_duration(video_path)
    if planned and float(planned) > 0 and file_dur and file_dur > float(planned) + 0.35:
        return max(0, ltx_latent_frame_count(float(planned)) - 1)
    return None


def _source_take_asset_id(source: Any, master: Any | None = None) -> str | None:
    """WAVE 3: CURRENT Take asset only for continuity prior_frame / lastFrame reads."""
    from .current_take import current_take_asset_id

    return current_take_asset_id(source, master)


def _approved_video_path(db: Any, source: Any, master: Any | None = None) -> str | None:
    from pathlib import Path

    from ..db import Asset

    asset_id = _source_take_asset_id(source, master)
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id) if db is not None else None
    video_path = getattr(asset, "path", None) if asset is not None else None
    if not video_path or not Path(str(video_path)).is_file():
        return None
    return str(video_path)


def bridge_source_stale(bridge: ContinuityBridge, source: Any, master: Any | None = None) -> bool:
    current_asset = str(_source_take_asset_id(source, master) or "").strip()
    if not source or not current_asset:
        return True
    state = bridge.continuityState or {}
    stored_asset = str(state.get("sourceAssetId") or "").strip()
    if stored_asset and current_asset and stored_asset != current_asset:
        return True
    if bridge.sourceTakeId and source.activeTakeId and bridge.sourceTakeId != source.activeTakeId:
        return True
    stored_take = str(state.get("sceneTakeId") or "").strip()
    if master is not None and stored_take:
        live_take = str(
            getattr(master, "activeSceneTakeId", "") or getattr(master, "currentSceneTakeId", "") or ""
        ).strip()
        if live_take and stored_take != live_take:
            return True
    return False


def bridge_extract_stale(bridge: ContinuityBridge, source: Any, video_path: str | None) -> bool:
    """True when an older last-frame used file EOF on a sheet-appended take."""
    if not source or not getattr(source, "duration", None):
        return False
    planned = getattr(source.duration, "plannedDuration", None)
    state = bridge.continuityState or {}
    extracted = state.get("extractedAtSeconds")
    file_dur = None
    if video_path:
        file_dur = probe_video_duration(video_path)
    elif state.get("sourceMediaDuration"):
        try:
            file_dur = float(state["sourceMediaDuration"])
        except (TypeError, ValueError):
            file_dur = None
    if not planned or not file_dur:
        return False
    if file_dur <= float(planned) + 0.35:
        return False
    if extracted is None:
        return True
    try:
        return float(extracted) > float(planned)
    except (TypeError, ValueError):
        return True


def analyze_bridge(db: Any, project_id: str, master: SceneTimelineMaster, bridge: ContinuityBridge) -> ContinuityBridge:
    """Fill last-frame (and optional tail) assets. Does not call paid providers."""
    from pathlib import Path
    from uuid import uuid4

    from ..config import settings
    from ..db import Asset

    bridge.status = "Analyzing"
    source = next((b for b in master.batchBlocks if b.id == bridge.sourceBatchId), None)
    source_asset_id = _source_take_asset_id(source, master) if source else None
    if not source or not source_asset_id:
        bridge.status = "Failed"
        bridge.error = "SOURCE_CLIP_MISSING"
        return bridge
    asset = db.get(Asset, source_asset_id) if db is not None else None
    video_path = getattr(asset, "path", None) if asset is not None else None
    if not video_path or not Path(str(video_path)).is_file():
        bridge.status = "Failed"
        bridge.error = "SOURCE_VIDEO_MISSING"
        return bridge
    try:
        dest_dir = Path(settings.data_dir) / "assets" / project_id / "continuity"
        dest = dest_dir / f"{bridge.bridgeId}_last.png"
        at_seconds = last_frame_extract_seconds(source, str(video_path))
        at_frame = last_frame_extract_frame(source, str(video_path))
        extract_last_frame_png(
            str(video_path),
            str(dest),
            at_seconds=at_seconds,
            at_frame=at_frame,
        )
        file_dur = probe_video_duration(str(video_path))
        planned = None
        if source.duration:
            planned = source.duration.plannedDuration or source.duration.timelineVisibleDuration
        frame_id = uuid4().hex
        frame = Asset(
            id=frame_id,
            project_id=project_id,
            tag="continuity_last_frame",
            kind="image",
            filename=dest.name,
            path=str(dest),
        )
        if db is not None:
            db.add(frame)
            db.commit()
        bridge.lastFrameAssetId = frame_id
        bridge.status = "Ready"
        bridge.error = None
        extracted = at_seconds
        if extracted is None and file_dur:
            extracted = max(0.0, float(file_dur) - 0.05)
        bridge.continuityState = {
            "contextVersion": bridge.contextVersion,
            "effectiveTailDuration": bridge.effectiveTailDuration,
            "lastFrameAssetId": frame_id,
            "sourceAssetId": source_asset_id,
            "sourceMediaDuration": file_dur,
            "extractedAtSeconds": extracted,
            "plannedDuration": planned,
        }
    except Exception as exc:
        bridge.status = "Failed"
        bridge.error = str(exc)[:500]
    return bridge


def prepare_outgoing_bridge(
    db: Any,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
    source_batch_id: str,
    *,
    admitted_preflight: dict | None = None,
    run_temporal: bool = True,
) -> ContinuityBridge | None:
    source = next((b for b in master.batchBlocks if b.id == source_batch_id), None)
    if not source:
        return None
    ensure_policy(master, source.generatorId)
    policy = master.continuityPolicy
    nxt = next_batch_after(master, source_batch_id)
    if nxt is None:
        return None
    if paid_continuity_forbidden(policy, nxt.generatorId or source.generatorId):
        return None
    if not should_prepare_bridge(policy, nxt.generatorId or source.generatorId):
        return None
    actual = None
    if _source_take_asset_id(source, master):
        actual = source.duration.generatedDuration or source.duration.plannedDuration
    existing = [
        b
        for b in master.continuityBridges
        if b.sourceBatchId == source_batch_id and b.targetBatchId == nxt.id and b.status not in ("Superseded",)
    ]
    ready = next((b for b in existing if b.status in ("Ready", "Applied")), None)
    if ready:
        video_path = _approved_video_path(db, source, master)
        if bridge_source_stale(ready, source, master) or bridge_extract_stale(ready, source, video_path):
            ready.status = "Superseded"
            ready.supersededAt = datetime.now(timezone.utc).isoformat()
            ready = None
        else:
            nxt.incomingBridgeId = ready.bridgeId
            if run_temporal:
                _run_temporal_review(
                    db,
                    project_id,
                    scene_id,
                    master,
                    source,
                    nxt.id,
                    admitted_preflight=admitted_preflight,
                )
            return ready
    pending = next((b for b in existing if b.status in ("Waiting", "Analyzing")), None)
    if pending:
        nxt.incomingBridgeId = pending.bridgeId
        return pending
    failed = next((b for b in existing if b.status == "Failed"), None)
    if failed:
        nxt.incomingBridgeId = failed.bridgeId
        return failed
    bridge = new_bridge(
        scene_id=scene_id,
        source_batch_id=source_batch_id,
        target_batch_id=nxt.id,
        source_take_id=source.activeTakeId,
        configured_tail=policy.configuredTailDuration,
        actual_generated_duration=actual,
    )
    analyze_bridge(db, project_id, master, bridge)
    master.continuityBridges.append(bridge)
    nxt.incomingBridgeId = bridge.bridgeId
    if run_temporal:
        _run_temporal_review(
            db,
            project_id,
            scene_id,
            master,
            source,
            nxt.id,
            admitted_preflight=admitted_preflight,
        )
    return bridge


def _run_temporal_review(
    db: Any,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
    source,
    target_batch_id: str,
    *,
    admitted_preflight: dict | None = None,
) -> None:
    """Sibling of last-frame extract. Failure must not fail the pixel bridge."""
    try:
        from ..codirector.video_intelligence.contracts import CoDirectorContinuityPolicy
        from ..codirector.video_intelligence.service import review_completed_batch

        policy = master.coDirectorContinuityPolicy
        if isinstance(policy, dict):
            policy = CoDirectorContinuityPolicy.model_validate(policy)
        if not policy.enabled:
            return
        review_completed_batch(
            db,
            project_id,
            scene_id,
            master,
            source,
            target_batch_id=target_batch_id,
            admitted_preflight=admitted_preflight,
        )
    except Exception as exc:
        try:
            from ..codirector.video_intelligence.service import persist_unavailable_packet

            persist_unavailable_packet(
                master,
                project_id=project_id,
                scene_id=scene_id,
                source_batch=source,
                target_batch_id=target_batch_id,
                reason=str(exc)[:80] or "REVIEW_FAILED",
            )
        except Exception:
            return


def bridge_blocks_submit(master: SceneTimelineMaster, target_batch_id: str) -> ContinuityBridge | None:
    """When Auto Continuity is on, next batch waits until the incoming bridge is Ready."""
    policy = master.continuityPolicy
    if not policy.autoContinuity:
        return None
    bridge = active_bridge_for_target(master, target_batch_id)
    if bridge is None:
        return None
    if bridge.status in ("Waiting", "Analyzing"):
        return bridge
    if bridge.status == "Failed":
        return bridge
    return None


def supersede_outgoing_bridges(master: SceneTimelineMaster, source_batch_id: str, *, now: str) -> list[str]:
    ids: list[str] = []
    for bridge in master.continuityBridges:
        if bridge.sourceBatchId == source_batch_id and bridge.status != "Superseded":
            bridge.status = "Superseded"
            bridge.supersededAt = now
            ids.append(bridge.bridgeId)
            target = next((b for b in master.batchBlocks if b.id == bridge.targetBatchId), None)
            if target and target.approvedClip:
                target.downstreamStale = True
                target.staleFromTakeId = bridge.sourceTakeId
    return ids


def set_continuity_policy(
    master: SceneTimelineMaster,
    *,
    generator_id: str | None,
    configured_tail: float,
) -> ContinuityPolicy:
    """Persist Off/3/5 for API. Local stays locked Auto Continuity ON / 5s."""
    loc = generator_locality(generator_id)
    if loc == "local":
        master.continuityPolicy = default_policy_for_locality("local")
        return master.continuityPolicy
    tail = float(configured_tail or 0.0)
    if tail not in (0.0, 3.0, 5.0):
        raise ValueError("API Auto Continuity window must be Off (0), 3, or 5 seconds.")
    master.continuityPolicy = ContinuityPolicy(
        autoContinuity=tail > 0,
        configuredTailDuration=tail,
        locality="api",
        continuityAwareRetake=tail > 0,
    )
    return master.continuityPolicy


def compile_retake_memory(
    *,
    master: SceneTimelineMaster,
    batch,
    user_correction: dict[str, Any] | None,
    incoming: ContinuityBridge | None,
) -> dict[str, Any]:
    """NEW TAKE = preserved scene state + incoming continuity + original intent + delta."""
    approved = next((c for c in batch.candidateVersions if c.approved), None)
    prior = approved or (batch.candidateVersions[-1] if batch.candidateVersions else None)
    prompt = " ".join(p.text for p in (batch.promptSegments or []) if p.text)
    incoming_payload: dict[str, Any] = {}
    if incoming is not None:
        incoming_payload = {
            "bridgeId": incoming.bridgeId,
            "lastFrameAssetId": incoming.lastFrameAssetId,
            "effectiveTailDuration": incoming.effectiveTailDuration,
            "contextVersion": incoming.contextVersion,
            "continuityStrategy": incoming.continuityStrategy,
            "sourceBatchId": incoming.sourceBatchId,
        }
    original_intent = dict(prior.originalTakeIntent) if prior and prior.originalTakeIntent else {
        "prompt": prompt,
        "generatorId": batch.generatorId,
        "plannedDuration": batch.duration.plannedDuration,
    }
    take_state = dict(prior.takeState) if prior and prior.takeState else {
        "approvedAssetId": batch.approvedClip.assetId if batch.approvedClip else None,
        "generatedDuration": batch.duration.generatedDuration,
    }
    sequence = dict(prior.sequenceMemory) if prior and prior.sequenceMemory else {
        "sceneId": batch.sceneId,
        "batchId": batch.id,
        "batchOrder": batch.order,
        "priorTakeId": prior.takeId if prior else None,
    }
    # Freeze temporal packet / directives from the prior APPROVED predecessor only.
    # Rejected takes and creator-rejected packets must not contaminate accepted state.
    temporal_freeze: dict[str, Any] = {}
    try:
        from ..codirector.video_intelligence.service import find_packet_for_handoff, previous_batch

        pred = previous_batch(master, batch.id)
        if pred is not None and getattr(getattr(pred, "approvedClip", None), "assetId", None):
            pkt = find_packet_for_handoff(master, pred.id, batch.id)
            if (
                pkt is not None
                and pkt.availability in ("ready", "low_confidence")
                and not getattr(pkt.continuation, "creatorRejected", False)
            ):
                temporal_freeze = {
                    "packetId": pkt.packetId,
                    "availability": pkt.availability,
                    "nextBatchDirectives": list(pkt.continuation.nextBatchDirectives or []),
                    "preserve": list(pkt.continuation.preserve or []),
                    "continue": list(pkt.continuation.continue_ or []),
                    "avoid": list(pkt.continuation.avoid or []),
                    "importantEvents": [
                        e.model_dump(mode="json") if hasattr(e, "model_dump") else e
                        for e in (pkt.importantEvents or [])[:8]
                    ],
                    "reviewWindowKind": (pkt.extras or {}).get("reviewWindowKind"),
                    "rollingSceneDigest": (
                        pkt.rollingSceneDigest.model_dump(mode="json", by_alias=True)
                        if pkt.rollingSceneDigest is not None
                        else getattr(master, "coDirectorRollingSceneDigest", None)
                    ),
                }
    except Exception:
        temporal_freeze = {}
    if temporal_freeze:
        incoming_payload["temporalContinuity"] = temporal_freeze
        sequence["temporalPacketId"] = temporal_freeze.get("packetId")
        sequence["temporalDirectivesFrozen"] = True
    uc = dict(user_correction or {})
    delta = str(uc.get("delta") or uc.get("prompt") or "").strip()
    if delta:
        uc["delta"] = delta
        uc.setdefault("prompt", delta)
    authored = str(original_intent.get("prompt") or prompt or "").strip()
    return {
        "sequenceMemory": sequence,
        "incomingContinuity": incoming_payload,
        "originalTakeIntent": original_intent,
        "takeState": take_state,
        "userCorrection": uc,
        "authoredPrompt": authored,
    }


def continue_without_continuity(master: SceneTimelineMaster, target_batch_id: str) -> ContinuityBridge | None:
    bridge = active_bridge_for_target(master, target_batch_id)
    if bridge is None:
        return None
    bridge.status = "Superseded"
    bridge.error = "CREATOR_CONTINUE_WITHOUT"
    from .contracts import _now

    bridge.supersededAt = _now()
    return bridge


"""Embedded Co-Director temporal review. Timeline calls this; chat is irrelevant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .cadence import intended_text_from_batch, resolve_cadence, review_window_kind, window_seconds
from .clip_extract import (
    cleanup_extracted_clip,
    extract_full_clip_review,
    extract_window,
    sample_timestamps_for_full_clip_review,
)
from .compare import compare_intent_vs_actual
from .contracts import (
    CoDirectorContinuityPolicy,
    PacketSource,
    TemporalContinuityPacket,
)
from .gpu_lease import best_effort_free_generator, preflight_for_review
from .observability import emit
from .worker_client import DEFAULT_QUESTION, normalize_perception_reason, perception_mode, run_perception

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
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Batch N+1 must not
    # submit before the Qwen packet for the CURRENT take's Batch N asset is
    # ready. Predecessor resolution MUST go through current_source_batch_asset_id
    # (current-take membership) — gating on approvedClip alone is the Take O
    # silent gate bypass. Fences: tests/test_timeline_architecture_guard.py
    """True when Continuity is ON, a predecessor render exists, and no gate-ready packet exists.

    The predecessor's rendered output is resolved the same way the review
    pipeline resolves it — current generated take first, approvedClip legacy
    fallback. Gating only on approvedClip let the sequential queue submit N+1
    with NO temporal packet whenever the predecessor asset lived in the take
    membership (silent gate bypass).
    """
    policy = _policy(master)
    if not policy.enabled:
        return False
    pred = previous_batch(master, target_batch_id)
    if pred is None or not current_source_batch_asset_id(pred):
        return False
    packet = find_packet_for_handoff(master, pred.id, target_batch_id)
    if packet is None or not packet.is_gate_ready():
        return True
    if is_packet_stale_for_batch(packet, pred):
        return True
    return False


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
    _stamp_reviewed_asset(packet, source_batch)
    emit("temporal_continuity_unavailable", packetId=packet.packetId, reason=reason, batchId=source_batch.id)
    return packet


def current_source_batch_asset_id(batch: Any) -> str:
    """The asset whose video a review of this batch must consume.

    Current take first, approvedClip fallback — the same resolution the review
    pipeline itself uses, so a packet can prove which asset it reviewed.
    """
    asset_id = ""
    try:
        from ...director_timeline_w46.current_take import current_take_asset_id

        asset_id = current_take_asset_id(batch) or ""
    except Exception:
        asset_id = ""
    if not asset_id:
        clip = getattr(batch, "approvedClip", None)
        asset_id = str(getattr(clip, "assetId", "") or "") if clip else ""
    return str(asset_id or "")


def _stamp_reviewed_asset(packet: TemporalContinuityPacket, source_batch: Any) -> None:
    """Stamp the packet with the exact asset its review consumed (if resolvable)."""
    try:
        asset_id = current_source_batch_asset_id(source_batch)
        if asset_id:
            packet.extras = dict(packet.extras or {})
            packet.extras["reviewedAssetId"] = asset_id
    except Exception:
        pass


def is_packet_stale_for_batch(packet: TemporalContinuityPacket | None, source_batch: Any) -> bool:
    """True when the packet cannot prove it reviewed the batch's current asset.

    Packets created before asset stamping carry no ``reviewedAssetId`` and are
    stale — they may describe a previous take's video (historical-take
    contamination). A stale packet is a historical record, not a valid
    continuity handoff for a new extension submission.

    REVISION AUTHORITY: a packet explicitly invalidated by a scene revision
    (``extras["invalidatedByRevision"]`` — set when the source batch's prompt
    materially changed) is stale regardless of asset identity: its directives
    were derived from the prior revision's intent.
    """
    if packet is None:
        return True
    try:
        if (packet.extras or {}).get("invalidatedByRevision"):
            return True
        reviewed = str((packet.extras or {}).get("reviewedAssetId") or "").strip()
        current = current_source_batch_asset_id(source_batch)
        if not current:
            return False  # nothing to compare; leave governance unchanged
        if not reviewed:
            return True  # legacy packet: cannot prove which take it reviewed
        return reviewed != current
    except Exception:
        return False


def invalidate_packets_for_source_batch(master: Any, source_batch_id: str) -> int:
    """Mark packets reviewed from ``source_batch_id`` invalidated by revision.

    REBUILD LAW (scene revision authority): when a batch's prompt materially
    changes, packets whose directives were derived from the OLD intent must
    not be woven into the new revision's continuation. The packet record
    stays (provenance), but it is marked stale so the submit gate forces a
    re-review against the current revision. Returns the number marked.
    """
    if master is None or not str(source_batch_id or "").strip():
        return 0
    marked = 0
    for packet in getattr(master, "temporalPackets", None) or []:
        try:
            src = getattr(packet, "source", None)
            if src is None or str(getattr(src, "batchId", "") or "") != str(source_batch_id):
                continue
            extras = getattr(packet, "extras", None)
            if extras is None:
                extras = {}
                packet.extras = extras
            if not extras.get("invalidatedByRevision"):
                extras["invalidatedByRevision"] = True
                marked += 1
        except Exception:
            continue
    return marked


def _character_identity_refs(project_id: str, batch: Any) -> list[dict[str, Any]]:
    """Collect approved Character Creator identity refs already on the batch / project."""
    refs: list[dict[str, Any]] = []
    for ref in getattr(batch, "references", None) or []:
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or ref.get("role") or "").lower()
        if kind not in {"characteridentity", "character", "identity", "motion_subject"} and not (
            ref.get("identityId") or ref.get("characterId")
        ):
            continue
        if ref.get("consumed") is False:
            continue
        identity_ids = ref.get("identityIds") or ([ref.get("identityId") or ref.get("characterId")] if (ref.get("identityId") or ref.get("characterId")) else [])
        asset_ids = ref.get("identityAssetIds") or ([ref.get("assetId")] if ref.get("assetId") else [])
        for i, iid in enumerate(identity_ids):
            if not iid:
                continue
            refs.append(
                {
                    "identityId": str(iid),
                    "characterId": str(iid),
                    "assetId": str(asset_ids[i]) if i < len(asset_ids) and asset_ids[i] else None,
                    "label": str(ref.get("label") or iid),
                    "source": "batch_reference",
                }
            )
    # Deduplicate
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in refs:
        key = str(item.get("identityId") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _intent_context(
    project_id: str,
    batch: Any,
    prior: TemporalContinuityPacket | None,
    *,
    master: Any | None = None,
) -> dict[str, Any]:
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
        if prior.importantEvents:
            early = [e.label for e in prior.importantEvents if getattr(e, "phase", "") in ("early", "mid")]
            if early:
                prior_text = (prior_text + " " + " ".join(f"[earlier: {x}]" for x in early[:4])).strip()
    pose_intended = None
    try:
        from ..pose_intelligence.persist import load_packet
        from ...db import SessionLocal

        db = SessionLocal()
        try:
            packet = load_packet(db, project_id)
            if packet is not None:
                pose_intended = packet.model_dump(mode="json")
        finally:
            db.close()
    except Exception:
        pose_intended = None
    rolling = None
    if master is not None:
        rolling = getattr(master, "coDirectorRollingSceneDigest", None)
    return {
        "prompt": prompt,
        "sceneIntent": scene_intent,
        "cameraIntent": camera_intent,
        "spatialMap": spatial_text,
        "priorContinuation": prior_text,
        "projectId": project_id,
        "poseIntended": pose_intended,
        "priorPacket": prior,
        "rollingSceneDigest": rolling,
        "characterIdentityRefs": _character_identity_refs(project_id, batch),
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


def _batch_video_path(db: Any, project_id: str, batch: Any) -> str | None:
    """Resolve the generated take file. Current take first; approvedClip is fallback."""
    asset_id = ""
    try:
        from ...director_timeline_w46.current_take import current_take_asset_id

        asset_id = current_take_asset_id(batch) or ""
    except Exception:
        asset_id = ""
    if not asset_id:
        clip = getattr(batch, "approvedClip", None)
        asset_id = getattr(clip, "assetId", "") if clip else ""
    return _asset_path(db, str(asset_id or ""))


def _internvideo3_available() -> bool:
    try:
        from .paths import INTERNVIDEO3_MARKERS, internvideo3_dir, model_present

        return bool(model_present(internvideo3_dir(), INTERNVIDEO3_MARKERS))
    except Exception:  # noqa: BLE001 — optional deep-review must never fail the packet
        return False


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
    force: bool = False,
    admitted_preflight: dict[str, Any] | None = None,
) -> TemporalContinuityPacket:
    policy = _policy(master)
    existing = find_packet_for_handoff(master, source_batch.id, target_batch_id or "")
    # Transient failures should be retryable so a one-off timeout/perception error
    # does not permanently poison the handoff. SOURCE_VIDEO_MISSING and
    # PERCEPTION_TIMEOUT (and other transient perception errors) are retried.
    _RETRYABLE_REASONS = frozenset(
        {
            "SOURCE_VIDEO_MISSING",
            "PERCEPTION_TIMEOUT",
            "PERCEPTION_FORCED_FAILURE",
            "INSUFFICIENT_VRAM",
            "COMFY_FREE_FAILED",
        }
    )
    retryable_missing = existing is not None and (
        existing.reason in _RETRYABLE_REASONS
    )
    # Historical-take guard: a packet that cannot prove it reviewed the source
    # batch's CURRENT asset (e.g. it reviewed a previous take's video, or was
    # created before asset stamping existed) must not be reused as this
    # transition's continuity handoff. Re-review the current asset.
    existing_stale = is_packet_stale_for_batch(existing, source_batch)
    if (
        existing is not None
        and existing.availability == "ready"
        and not force
        and not existing_stale
    ):
        return existing
    if (
        existing is not None
        and existing.is_gate_ready()
        and not force
        and not retryable_missing
        and not existing_stale
    ):
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
    duration = None
    if getattr(source_batch, "duration", None) is not None:
        duration = source_batch.duration.generatedDuration or source_batch.duration.plannedDuration
    cadence = resolve_cadence(
        policy,
        prompt=prompt,
        camera_motion=camera_motion,
        character_count=len(character_ids),
        has_movement_layers=any(
            getattr(seg, "movementSegmentRef", None) for seg in (getattr(source_batch, "promptSegments", None) or [])
        ),
        generated_duration=float(duration) if duration is not None else None,
    )
    window = window_seconds(cadence, duration)
    window_kind = review_window_kind(cadence)
    emit(
        "review_started",
        batchId=source_batch.id,
        cadence=cadence,
        window=window,
        mode=perception_mode(),
    )

    video_path = _batch_video_path(db, project_id, source_batch)
    extras: dict[str, Any] = {"reviewCadence": cadence, "windowSec": window, "reviewWindowKind": window_kind}

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
        if admitted_preflight is not None:
            extras["gpuLease"] = {"comfyFreeRequested": True, "handoffAdmitted": True}
            preflight = admitted_preflight
        else:
            extras["gpuLease"] = best_effort_free_generator()
            preflight = preflight_for_review()
        lease = extras["gpuLease"]
        extras["gpuPreflight"] = preflight
        free_failed = (not lease.get("comfyFreeRequested")) or bool(lease.get("comfyFreeError"))
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
        if free_failed and preflight.get("unknownVram"):
            packet = _degraded(
                project_id=project_id,
                scene_id=scene_id,
                source_batch=source_batch,
                target_batch_id=target_batch_id,
                reason="COMFY_FREE_FAILED",
                extras=extras,
            )
            _persist(master, packet, source_batch, target_batch_id)
            return packet
    else:
        extras["gpuLease"] = {"skipped": True, "reason": f"perception_mode={mode}"}

    review_path = video_path
    start = max(0.0, float(duration or window) - window)
    if window_kind == "full_clip":
        start = 0.0
        try:
            from ...config import settings

            dest = (
                Path(settings.data_dir)
                / "assets"
                / project_id
                / "temporal"
                / f"{source_batch.id}_fullclip.review512.mp4"
            )
            # Low-res full-clip extract reduces OOM risk for ~15s reviews without
            # changing TemporalContinuityPacket semantics.
            review_path = extract_full_clip_review(
                video_path,
                str(dest),
                duration_sec=float(window),
                width=512,
                fps=2,
            )
            extras["extractedClip"] = review_path
            extras["sampleTimestamps"] = sample_timestamps_for_full_clip_review(float(window))
            extras["reviewExtract"] = "full_clip_lowres"
        except Exception as exc:
            extras["extractError"] = str(exc)[:240]
            extras["sampleTimestamps"] = sample_timestamps_for_full_clip_review(float(window or duration or 5.0))
            review_path = video_path
    elif cadence in ("interval_3", "interval_5") and duration and duration > window + 0.05:
        try:
            from ...config import settings

            dest = Path(settings.data_dir) / "assets" / project_id / "temporal" / f"{source_batch.id}_{cadence}.mp4"
            review_path = extract_window(video_path, str(dest), start_sec=start, duration_sec=window)
            extras["extractedClip"] = review_path
            extras["reviewExtract"] = "tail_window"
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
    # Provenance: record the exact asset this review consumed so later
    # transitions can verify the packet describes the CURRENT take, not a
    # historical one (Timeline historical-take contamination guard).
    _stamp_reviewed_asset(packet, source_batch)
    try:
        # Full-clip reviews of ~15s shots need a longer perception timeout than
        # the default 180s (the Timeline Extension Duplication regression was
        # caused in part by a PERCEPTION_TIMEOUT on a 15s full-clip VideoChat3
        # review, which released the N+1 gate with zero continuity state).
        # The certify path already uses 420s; mirror it for full-clip reviews.
        perception_timeout = 420.0 if window_kind == "full_clip" else 180.0
        from .authority import authority_question_suffix

        observation = run_perception(
            review_path,
            model_id=policy.fastVisionModel,
            timeout_sec=perception_timeout,
            question=DEFAULT_QUESTION + "\n\n" + authority_question_suffix(source_batch),
        )
        packet.source.perceptionModelId = observation.modelId or policy.fastVisionModel
        context = _intent_context(project_id, source_batch, prior, master=master)
        packet = compare_intent_vs_actual(
            packet,
            observation,
            context=context,
            protection=policy.protection,
        )
        # Perception law: raw Qwen output must never become scene canon.
        # Reconcile the compiled packet against the batch's authoritative
        # entities/dialogue; unexpected detections are isolated as artifacts
        # (packet.extras["artifacts"]) and excluded from continuation content.
        from .authority import reconcile_packet_with_authority

        packet = reconcile_packet_with_authority(packet, source_batch)
        note = str(policy.creatorNextBatchNote or "").strip()
        if note:
            packet.continuation.nextBatchDirectives = list(packet.continuation.nextBatchDirectives or []) + [note]
        if _should_deep_review(policy, observation.confidence, bool(prior)):
            if not _internvideo3_available():
                packet.source.deepReviewInvoked = False
                packet.extras["deepReviewSkipped"] = {
                    "reason": "INTERNVIDEO3_NOT_INSTALLED",
                    "optional": True,
                    "modelId": "internvideo3-8b-instruct",
                }
            else:
                try:
                    deep = run_perception(review_path, model_id="internvideo3-8b-instruct")
                    packet.source.deepReviewInvoked = True
                    packet.extras["deepReview"] = {"rawText": deep.rawText[:800], "modelId": deep.modelId}
                except Exception as exc:
                    packet.source.deepReviewInvoked = False
                    reason = normalize_perception_reason(exc)
                    if reason == "MODEL_NOT_INSTALLED" or "INTERNVIDEO3" in str(exc).upper():
                        packet.extras["deepReviewSkipped"] = {
                            "reason": "INTERNVIDEO3_NOT_INSTALLED",
                            "optional": True,
                            "modelId": "internvideo3-8b-instruct",
                            "detail": str(exc)[:240],
                        }
                    else:
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
            reason=normalize_perception_reason(exc),
            extras=extras,
        )
    finally:
        cleanup_extracted_clip(str(extras.get("extractedClip") or ""), source_path=video_path)

    # ── Revision C — JEPA world-state augmentation ──────────────────────
    # VideoChat3 observes; V-JEPA adds complementary world-state signal.
    # Non-blocking — failure does NOT degrade the temporal packet.
    if packet.is_gate_ready() and review_path:
        try:
            from ..world_intelligence.temporal_world_review import augment_temporal_packet

            policy_raw = getattr(master, "coDirectorWorldIntelligencePolicy", None)
            world_policy = None
            if policy_raw is not None:
                from ..world_intelligence.contracts import CoDirectorWorldIntelligencePolicy

                if isinstance(policy_raw, CoDirectorWorldIntelligencePolicy):
                    world_policy = policy_raw
                elif isinstance(policy_raw, dict):
                    try:
                        world_policy = CoDirectorWorldIntelligencePolicy.model_validate(policy_raw)
                    except Exception:
                        pass

            # Attempt to find an approved world reference from the project
            ref_path = None
            ref_id = None
            try:
                from ..world_intelligence.service import _get_index

                index = _get_index()
                anchors = index.get_anchors(project_id=project_id, scene_id=scene_id)
                if anchors:
                    ref_id = anchors[0].assetId
                    from ...db import Asset

                    if db is not None:
                        asset = db.get(Asset, ref_id)
                        if asset and asset.path:
                            ref_path = str(asset.path)
            except Exception:
                pass

            packet = augment_temporal_packet(
                packet,
                clip_path=review_path,
                reference_image_path=ref_path,
                reference_asset_id=ref_id,
                world_policy=world_policy,
            )
            _attach_pose_observed_world(db, project_id, packet)
        except Exception as exc:
            logger.debug("JEPA world review skipped: %s", exc)
            packet.extras["worldReview"] = {"availability": "skipped", "reason": str(exc)[:120]}

    _persist(master, packet, source_batch, target_batch_id)
    return packet


def _attach_pose_observed_world(db: Any, project_id: str, packet: TemporalContinuityPacket) -> None:
    """Feed JEPA observed world into pose continuity review after Revision C augment."""
    world_raw = (packet.extras or {}).get("worldReview")
    if not isinstance(world_raw, dict) or world_raw.get("schemaVersion") != "world-state-v1":
        return
    try:
        from ..pose_intelligence.compare import review_intended_vs_observed
        from ..pose_intelligence.persist import load_packet
        from ..world_intelligence.contracts import WorldStatePacket

        intended = load_packet(db, project_id) if db is not None else None
        if intended is None:
            return
        observed_world = WorldStatePacket.model_validate(world_raw)
        observed_text = ""
        if packet.assessment is not None:
            observed_text = str(packet.assessment.observedState or "")
        review = review_intended_vs_observed(
            intended,
            observed_world=observed_world,
            observed_text=observed_text,
            project_id=project_id,
        )
        packet.extras["poseContinuityReview"] = review.model_dump(mode="json")
        packet.extras["poseStateKind"] = {
            "intended": "PoseCraft starting intent",
            "observed": "Generated video / world review is new evidence",
        }
    except Exception as exc:
        logger.debug("Pose observed-world review skipped: %s", exc)


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
            state["reviewWindowKind"] = (packet.extras or {}).get("reviewWindowKind")
            if packet.rollingSceneDigest is not None:
                try:
                    state["rollingDigest"] = packet.rollingSceneDigest.model_dump(mode="json", by_alias=True)
                except Exception:
                    pass
            if packet.importantEvents:
                try:
                    state["importantEvents"] = [e.model_dump(mode="json") for e in packet.importantEvents[:8]]
                except Exception:
                    pass
            bridge.continuityState = state
    if packet.rollingSceneDigest is not None and not getattr(packet.continuation, "creatorRejected", False):
        try:
            master.coDirectorRollingSceneDigest = packet.rollingSceneDigest.model_dump(mode="json", by_alias=True)
        except Exception:
            pass


def ensure_temporal_packet_before_submit(
    db: Any,
    project_id: str,
    scene_id: str,
    master: Any,
    target_batch_id: str,
) -> TemporalContinuityPacket | None:
    """MULTI-BATCH GOVERNANCE LAW. Never submit N+1 without a ready or degraded packet.

    The predecessor's rendered output is resolved exactly as the review
    pipeline resolves it — current generated take first, approvedClip legacy
    fallback. A packet that cannot prove it reviewed the predecessor's
    CURRENT asset is stale (historical-take contamination guard) and must not
    satisfy this gate — a fresh review of the current take is required instead.
    """
    policy = _policy(master)
    if not policy.enabled:
        return None
    pred = previous_batch(master, target_batch_id)
    if pred is None or not current_source_batch_asset_id(pred):
        return None
    existing = find_packet_for_handoff(master, pred.id, target_batch_id)
    if (
        existing is not None
        and existing.is_gate_ready()
        and not is_packet_stale_for_batch(existing, pred)
    ):
        return existing
    return review_completed_batch(
        db,
        project_id,
        scene_id,
        master,
        pred,
        target_batch_id=target_batch_id,
    )

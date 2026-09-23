"""Intent vs actual. Structured Co-Director job — not a chat turn."""

from __future__ import annotations

import logging
import re
from typing import Any

from .contracts import (
    Assessment,
    Continuation,
    ExitState,
    ImportantEvent,
    RollingSceneDigest,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
    VisualAnchor,
    _now,
)

logger = logging.getLogger(__name__)


def _intended_from_context(context: dict[str, Any]) -> str:
    parts = [
        str(context.get("prompt") or "").strip(),
        str(context.get("sceneIntent") or "").strip(),
        str(context.get("cameraIntent") or "").strip(),
        str(context.get("priorContinuation") or "").strip(),
    ]
    return "\n".join(p for p in parts if p) or "Continue the authored shot as planned."


def _phase_for_index(index: int, total: int) -> str:
    if total <= 1:
        return "unknown"
    ratio = index / max(1, total - 1)
    if ratio <= 0.33:
        return "early"
    if ratio <= 0.66:
        return "mid"
    return "late"


def _extract_important_events(
    observation: VideoPerceptionObservation,
    *,
    window_start: float,
    window_end: float,
) -> list[ImportantEvent]:
    """Capture events across the reviewed window, including early/mid clip."""
    events: list[ImportantEvent] = []
    completed = [str(x).strip() for x in (observation.completedActions or []) if str(x).strip()]
    unfinished = [
        str(x).strip()
        for x in (observation.unfinishedActions or [])
        if str(x).strip() and str(x).strip().lower().rstrip(",") not in {"[]", "{}", "null", "none"}
    ]
    span = max(0.1, float(window_end) - float(window_start))
    total = max(1, len(completed) + len(unfinished))
    for i, label in enumerate(completed):
        phase = _phase_for_index(i, total)
        approx = float(window_start) + (i / max(1, total)) * span * 0.85
        events.append(
            ImportantEvent(
                label=label[:180],
                approxTimeSec=round(approx, 3),
                phase=phase,  # type: ignore[arg-type]
                detail=f"completed:{phase}",
            )
        )
    for j, label in enumerate(unfinished):
        idx = len(completed) + j
        phase = _phase_for_index(idx, total) if completed else "late"
        events.append(
            ImportantEvent(
                label=label[:180],
                approxTimeSec=round(float(window_end) - 0.1, 3),
                phase=phase,  # type: ignore[arg-type]
                detail="unfinished_at_exit",
            )
        )
    # Sentence-level early/mid capture from prose so early events survive even when
    # completedActions is sparse (Continuity Challenge).
    prose = (observation.rawText or "").strip()
    json_at = prose.rfind("{")
    if json_at > 0:
        prose = prose[:json_at]
    sentences = [part.strip() for part in re.split(r"[.\n]+", prose) if part.strip()]
    motion = (
        "turn", "look", "walk", "dolly", "camera", "head", "gaze", "step", "facing",
        "wave", "point", "sit", "stand", "reach", "pick", "drop", "enter", "exit",
        "raise", "lower", "nod", "smile", "open", "close", "handoff", "pass",
    )
    for i, text in enumerate(sentences):
        low = text.lower()
        if not any(token in low for token in motion):
            continue
        phase = _phase_for_index(i, max(1, len(sentences)))
        # Skip near-duplicates of completed labels
        if any(label.lower() in low or low in label.lower() for label in completed):
            continue
        approx = float(window_start) + (i / max(1, len(sentences) - 1 or 1)) * span
        events.append(
            ImportantEvent(
                label=text[:180],
                approxTimeSec=round(approx, 3),
                phase=phase,  # type: ignore[arg-type]
                detail="prose_motion",
            )
        )
    # Deduplicate by lowercased label prefix
    out: list[ImportantEvent] = []
    seen: set[str] = set()
    for ev in events:
        key = ev.label.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out[:12]


def _extract_visual_anchors(observation: VideoPerceptionObservation, context: dict[str, Any]) -> list[VisualAnchor]:
    anchors: list[VisualAnchor] = []
    for ch in observation.characters or []:
        label = str(getattr(ch, "label", "") or "").strip() or "character"
        detail_parts = [
            str(getattr(ch, "screenPosition", "") or ""),
            str(getattr(ch, "poseState", "") or ""),
            str(getattr(ch, "actionState", "") or ""),
            str(getattr(ch, "expression", "") or ""),
        ]
        anchors.append(
            VisualAnchor(
                kind="character",
                label=label,
                detail="; ".join(p for p in detail_parts if p)[:240],
                identityId=getattr(ch, "characterId", None),
            )
        )
    scene = observation.scene
    for prop in list(getattr(scene, "majorProps", None) or [])[:6]:
        anchors.append(VisualAnchor(kind="prop", label=str(prop)[:120], detail="major_prop"))
    if getattr(scene, "lightingState", None):
        anchors.append(VisualAnchor(kind="environment", label="lighting", detail=str(scene.lightingState)[:180]))
    if getattr(scene, "environmentState", None):
        anchors.append(VisualAnchor(kind="environment", label="environment", detail=str(scene.environmentState)[:180]))
    cam = observation.camera
    cam_bits = [
        str(getattr(cam, "framing", "") or ""),
        str(getattr(cam, "shotSize", "") or ""),
        str(getattr(cam, "movementType", "") or ""),
    ]
    cam_detail = "; ".join(b for b in cam_bits if b)
    if cam_detail:
        anchors.append(VisualAnchor(kind="camera", label="camera", detail=cam_detail[:180]))
    # Character Creator identity refs from context (project-approved)
    for item in context.get("characterIdentityRefs") or []:
        if not isinstance(item, dict):
            continue
        anchors.append(
            VisualAnchor(
                kind="identity",
                label=str(item.get("label") or item.get("name") or "identity")[:120],
                detail="character_creator_approved",
                assetId=str(item.get("assetId") or "") or None,
                identityId=str(item.get("identityId") or item.get("characterId") or "") or None,
            )
        )
    return anchors[:16]


def _extract_exit_state(observation: VideoPerceptionObservation, continue_items: list[str]) -> ExitState:
    prose = (observation.rawText or "").strip()
    json_at = prose.rfind("{")
    if json_at > 0:
        prose = prose[:json_at]
    sentences = [part.strip() for part in prose.replace("\n", ". ").split(".") if part.strip()]
    summary = sentences[-1] if sentences else (continue_items[0] if continue_items else "")
    char_states = []
    for ch in observation.characters or []:
        label = str(getattr(ch, "label", "") or "character")
        bits = [
            str(getattr(ch, "poseState", "") or ""),
            str(getattr(ch, "actionState", "") or ""),
            str(getattr(ch, "screenPosition", "") or ""),
        ]
        detail = "; ".join(b for b in bits if b)
        char_states.append(f"{label}: {detail}" if detail else label)
    cam = observation.camera
    camera_state = "; ".join(
        str(x)
        for x in (
            getattr(cam, "framing", None),
            getattr(cam, "shotSize", None),
            getattr(cam, "movementType", None),
            getattr(cam, "movementDirection", None),
        )
        if x
    ) or None
    env = None
    if observation.scene is not None:
        env = str(getattr(observation.scene, "environmentState", None) or getattr(observation.scene, "lightingState", None) or "") or None
    return ExitState(
        summary=summary[:400],
        characterStates=char_states[:8],
        cameraState=camera_state,
        environmentState=env,
    )


def _uniq_keep_order(items: list[str], *, limit: int = 24) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def fold_rolling_scene_digest(
    packet: TemporalContinuityPacket,
    prior: TemporalContinuityPacket | None,
    *,
    master_digest: dict[str, Any] | RollingSceneDigest | None = None,
) -> RollingSceneDigest:
    """Accumulate preserve/continue/avoid + events across approved shots."""
    prior_digest = None
    if prior is not None and prior.rollingSceneDigest is not None:
        prior_digest = prior.rollingSceneDigest
    elif isinstance(master_digest, RollingSceneDigest):
        prior_digest = master_digest
    elif isinstance(master_digest, dict) and master_digest:
        try:
            prior_digest = RollingSceneDigest.model_validate(master_digest)
        except Exception:
            prior_digest = None

    preserve = list(packet.continuation.preserve or [])
    continue_items = list(packet.continuation.continue_ or [])
    avoid = list(packet.continuation.avoid or [])
    events = list(packet.importantEvents or [])
    anchors = list(packet.visualAnchors or [])
    source_ids: list[str] = []

    if prior_digest is not None:
        preserve = list(prior_digest.preserve or []) + preserve
        continue_items = list(getattr(prior_digest, "continue_", None) or []) + continue_items
        avoid = list(prior_digest.avoid or []) + avoid
        events = list(prior_digest.importantEvents or []) + events
        anchors = list(prior_digest.visualAnchors or []) + anchors
        source_ids.extend(list(prior_digest.sourcePacketIds or []))
    elif prior is not None and not getattr(prior.continuation, "creatorRejected", False):
        preserve = list(prior.continuation.preserve or []) + preserve
        continue_items = list(prior.continuation.continue_ or []) + continue_items
        avoid = list(prior.continuation.avoid or []) + avoid
        events = list(prior.importantEvents or []) + events
        anchors = list(prior.visualAnchors or []) + anchors
        source_ids.append(prior.packetId)

    if packet.packetId not in source_ids:
        source_ids.append(packet.packetId)

    # Deduplicate anchors by kind+label
    anchor_out: list[VisualAnchor] = []
    seen_a: set[str] = set()
    for a in anchors:
        key = f"{a.kind}:{a.label}:{a.identityId or ''}".lower()
        if key in seen_a:
            continue
        seen_a.add(key)
        anchor_out.append(a)

    event_out: list[ImportantEvent] = []
    seen_e: set[str] = set()
    for ev in events:
        key = ev.label.lower()[:80]
        if key in seen_e:
            continue
        seen_e.add(key)
        event_out.append(ev)

    return RollingSceneDigest(
        preserve=_uniq_keep_order(preserve),
        continue_=_uniq_keep_order(continue_items),
        avoid=_uniq_keep_order(avoid),
        importantEvents=event_out[-20:],
        visualAnchors=anchor_out[:20],
        exitState=packet.exitState or ExitState(),
        sourcePacketIds=source_ids[-12:],
        updatedAt=_now(),
    )


def compare_intent_vs_actual(
    packet: TemporalContinuityPacket,
    observation: VideoPerceptionObservation,
    *,
    context: dict[str, Any] | None = None,
    protection: str = "strong",
) -> TemporalContinuityPacket:
    ctx = context or {}
    intended = _intended_from_context(ctx)
    observed = (observation.rawText or "").strip() or "Visual review produced no description."
    unfinished = [
        item
        for item in list(observation.unfinishedActions or [])
        if str(item).strip().lower().rstrip(",") not in {"[]", "{}", "null", "none"}
    ]
    completed = list(observation.completedActions or [])
    differences: list[str] = []
    if unfinished:
        differences.append("Action remained unfinished at the end of this batch.")
    if observation.confidence is not None and observation.confidence < 0.45:
        differences.append("Visual confidence is low; do not invent missing facts.")

    preserve = [
        "Keep successful motion, screen geography, lighting, and wardrobe.",
        "Do not restart a walk cycle or recenter characters if they were already placed.",
    ]
    continue_items = [f"Finish: {item}" for item in unfinished]
    if not continue_items:
        prose = observed or ""
        json_at = prose.rfind("{")
        if json_at > 0:
            prose = prose[:json_at]
        last_seen = ""
        motion = ("turn", "look", "walk", "dolly", "camera", "head", "gaze", "step", "facing")
        sentences = [part.strip() for part in prose.replace("\n", ". ").split(".") if part.strip()]
        for text in reversed(sentences):
            low = text.lower()
            if any(token in low for token in motion):
                last_seen = text
                break
        if not last_seen and sentences:
            last_seen = sentences[-1]
        continue_items = [
            f"Continue: {last_seen}." if last_seen else "Continue the same beat without resetting the shot."
        ]
    avoid = [
        "Do not regenerate the whole previous batch.",
        "Do not restart the turn, walk, or camera move from the beginning.",
        "Do not treat this as a disconnected new generation.",
    ]
    if protection == "standard":
        preserve = ["Keep successful motion and lighting."]
        avoid = ["Do not regenerate the whole previous batch."]
    directives = []
    if unfinished:
        directives.append(
            "Begin by completing the unfinished action from the previous batch, then continue the next beat."
        )
    else:
        directives.append("Continue from the last successful frame with the same cinematic state.")

    packet.characters = list(observation.characters or [])
    packet.camera = observation.camera
    packet.scene = observation.scene
    packet.timing.completedBeats = completed
    packet.timing.activeBeats = []
    packet.timing.unfinishedBeats = unfinished
    pose_review = _apply_pose_intent(ctx, intended, observed, differences, preserve, continue_items, directives)

    window_start = float(getattr(packet.source, "startTime", 0.0) or 0.0)
    window_end = float(getattr(packet.source, "endTime", 0.0) or 0.0)
    if window_end <= window_start:
        tr = getattr(observation, "timeRange", None) or (0.0, 0.0)
        window_start, window_end = float(tr[0] or 0.0), float(tr[1] or 0.0) or window_start + 1.0

    packet.importantEvents = _extract_important_events(
        observation, window_start=window_start, window_end=window_end
    )
    packet.visualAnchors = _extract_visual_anchors(observation, ctx)
    packet.exitState = _extract_exit_state(observation, continue_items)

    # Surface early events into next-batch directives (Continuity Challenge).
    early_mid = [e for e in packet.importantEvents if e.phase in ("early", "mid")]
    for ev in early_mid[:3]:
        line = f"Remember earlier beat ({ev.phase}): {ev.label}"
        if line not in directives:
            directives.append(line)

    packet.assessment = Assessment(
        intendedState=intended,
        observedState=observed,
        differences=differences,
        severity="minor" if unfinished else "none",
        confidence=observation.confidence,
        confidenceCertainty="known" if observation.confidence is not None else "unknown",
    )
    packet.continuation = Continuation(
        preserve=preserve,
        continue_=continue_items,
        correct=[],
        avoid=avoid,
        nextBatchDirectives=directives,
    )
    packet.decision = "keep_and_continue"
    packet.observation = observation
    if unfinished:
        packet.creatorMarker = f"CD will finish: {unfinished[0]}"
    else:
        packet.creatorMarker = "CD kept the shot going"
    if observation.confidence is not None and observation.confidence < 0.45:
        packet.availability = "low_confidence"
        packet.reason = "LOW_CONFIDENCE"
    else:
        packet.availability = "ready"
        packet.reason = None
    if pose_review:
        packet.extras["poseContinuityReview"] = pose_review
        packet.extras["poseStateKind"] = {
            "intended": "PoseCraft starting intent",
            "observed": "Generated video is new evidence",
        }

    prior = ctx.get("priorPacket")
    master_digest = ctx.get("rollingSceneDigest")
    if prior is not None or master_digest is not None or packet.importantEvents:
        try:
            packet.rollingSceneDigest = fold_rolling_scene_digest(
                packet,
                prior if isinstance(prior, TemporalContinuityPacket) else None,
                master_digest=master_digest,
            )
        except Exception as exc:
            logger.debug("rolling digest fold skipped: %s", exc)
    return packet


def _apply_pose_intent(
    ctx: dict[str, Any],
    intended: str,
    observed: str,
    differences: list[str],
    preserve: list[str],
    continue_items: list[str],
    directives: list[str],
) -> dict[str, Any] | None:
    """Consume an intended PoseWorldStatePacket when present. Does not replace Revision A."""
    raw = ctx.get("poseIntended") or ctx.get("poseWorldState")
    if raw is None:
        return None
    try:
        from ..pose_intelligence.contracts import PoseWorldStatePacket
        from ..pose_intelligence.compare import review_intended_vs_observed
        from ..world_intelligence.contracts import WorldStatePacket

        packet = raw if isinstance(raw, PoseWorldStatePacket) else PoseWorldStatePacket.model_validate(raw)
        world_raw = ctx.get("observedWorld")
        world = None
        if world_raw is not None:
            world = world_raw if isinstance(world_raw, WorldStatePacket) else WorldStatePacket.model_validate(world_raw)
        review = review_intended_vs_observed(
            packet,
            observed_world=world,
            observed_text=observed,
            project_id=str(ctx.get("projectId") or packet.projectId or ""),
        )
        for risk in review.continuityRisk:
            if risk not in differences:
                differences.append(risk)
        for item in review.nextBatchGuidance:
            if item not in directives:
                directives.append(item)
        if packet.constraints.preserveSupportFoot:
            preserve.append(f"Preserve intended support: {packet.constraints.preserveSupportFoot.replace('_', ' ')}.")
        for contact in packet.interaction.handContact[:2]:
            preserve.append(f"Preserve intended contact: {contact}.")
            continue_items.append(f"INTENDED: {contact}")
        return review.model_dump(mode="json")
    except Exception as exc:
        logger.debug("Pose intent review skipped: %s", exc)
        return None

"""Intent vs actual. Structured Co-Director job — not a chat turn."""

from __future__ import annotations

import logging
from typing import Any

from .contracts import (
    Assessment,
    Continuation,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
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

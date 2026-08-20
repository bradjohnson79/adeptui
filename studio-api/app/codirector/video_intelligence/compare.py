"""Intent vs actual. Structured Co-Director job — not a chat turn."""

from __future__ import annotations

from typing import Any

from .contracts import (
    Assessment,
    Continuation,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
)


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
    unfinished = list(observation.unfinishedActions or [])
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
    continue_items = [f"Finish: {item}" for item in unfinished] or [
        "Continue the same beat without resetting the shot."
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
    return packet

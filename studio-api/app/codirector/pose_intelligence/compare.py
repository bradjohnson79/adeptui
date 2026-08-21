"""Pose-to-pose and intended-vs-observed comparison.

Observed video is new evidence. PoseCraft is starting intent.
Stale PoseCraft assumptions must not overwrite newer observed state.
"""

from __future__ import annotations

from typing import Any, Optional

from ..world_intelligence.contracts import WorldStatePacket
from .analyze import compare_worlds, solve_joints
from .contracts import (
    PoseChange,
    PoseContinuityReview,
    PoseSequenceState,
    PoseTransition,
    PoseWorldStatePacket,
)


def compare_pose_packets(
    first: PoseWorldStatePacket,
    second: PoseWorldStatePacket,
    *,
    first_figure: Any = None,
    second_figure: Any = None,
) -> PoseTransition:
    a_world = solve_joints(first_figure) if first_figure is not None else {}
    b_world = solve_joints(second_figure) if second_figure is not None else {}
    if a_world and b_world:
        changes, warnings, motion = compare_worlds(
            a_world, b_world, first.character, second.character, first.interaction, second.interaction
        )
    else:
        changes, warnings = _compare_without_fk(first, second)
        motion = second.motion
    planted = list(second.interaction.footContact)
    moving = [c.summary for c in changes if c.kind in {"foot_released", "contact_lost", "character_translated"}]
    return PoseTransition(
        fromPoseId=first.snapshotId or first.character.poseId or first.packetId,
        toPoseId=second.snapshotId or second.character.poseId or second.packetId,
        fromPacketId=first.packetId,
        toPacketId=second.packetId,
        changes=changes,
        plantedContacts=planted,
        movingContacts=moving,
        actionProgression=motion.transitionState or motion.outgoingMovement,
        plausibilityWarnings=warnings or list(second.warnings),
        nextStateSuggestion=motion.likelyContinuation,
        confidence=motion.confidence,
    )


def build_sequence(project_id: str, packets: list[PoseWorldStatePacket], figures: list[Any] | None = None) -> PoseSequenceState:
    transitions: list[PoseTransition] = []
    figs = figures or [None] * len(packets)
    for idx in range(len(packets) - 1):
        transitions.append(
            compare_pose_packets(
                packets[idx],
                packets[idx + 1],
                first_figure=figs[idx] if idx < len(figs) else None,
                second_figure=figs[idx + 1] if idx + 1 < len(figs) else None,
            )
        )
    warnings = [w for t in transitions for w in t.plausibilityWarnings]
    return PoseSequenceState(
        projectId=project_id,
        orderedPoseIds=[p.snapshotId or p.character.poseId or p.packetId for p in packets],
        orderedPacketIds=[p.packetId for p in packets],
        transitions=transitions,
        actionProgression="; ".join(t.actionProgression for t in transitions if t.actionProgression),
        momentum=packets[-1].motion.rotationDirection if packets else "",
        continuityWarnings=warnings,
        nextStateSuggestions=[t.nextStateSuggestion for t in transitions if t.nextStateSuggestion],
        confidence="known" if transitions else "uncertain",
        provenance="posecraft-snapshots",
    )


def review_intended_vs_observed(
    intended: PoseWorldStatePacket | None,
    *,
    observed_world: WorldStatePacket | None = None,
    observed_text: str = "",
    project_id: str = "",
) -> PoseContinuityReview:
    changes: list[PoseChange] = []
    risks: list[str] = []
    guidance: list[str] = []
    if intended is None:
        return PoseContinuityReview(
            projectId=project_id,
            observedWorld=observed_world,
            observedSummary=observed_text,
            nextBatchGuidance=["No PoseCraft intended state was available."],
        )

    observed = (observed_text or "").lower()
    for contact in intended.interaction.handContact:
        token = contact.split("→")[-1].strip().lower() if "→" in contact else contact.lower()
        lost = any(word in observed for word in ("detach", "release", "let go", "no longer touching", "off the"))
        if token and lost:
            changes.append(
                PoseChange(
                    kind="contact_lost",
                    summary=f"INTENDED {contact}. OBSERVED possible loss of that contact.",
                    severity="moderate",
                    confidence="uncertain",
                )
            )
            risks.append(f"Generation may have departed from intended PoseCraft contact: {contact}")
            guidance.append(
                f"Restore {contact} unless the action progression explicitly requires release."
            )
    for foot in intended.interaction.footContact:
        if "float" in observed or "off the ground" in observed or "no floor" in observed:
            changes.append(
                PoseChange(
                    kind="foot_released",
                    summary=f"INTENDED {foot}. OBSERVED possible loss of floor plant.",
                    severity="moderate",
                    confidence="uncertain",
                )
            )
            risks.append("Observed motion may have lost the intended support plant.")
            guidance.append(f"Preserve {foot} during the first motion phase.")
    if intended.constraints.preserveFacing and any(w in observed for w in ("turned around", "facing opposite", "spun")):
        changes.append(
            PoseChange(kind="facing_changed", summary="Facing may have reversed versus intended pose.", severity="minor")
        )
    if observed_world and observed_world.availability == "available":
        rec = observed_world.recommendation
        if rec.caution:
            risks.extend(rec.caution[:3])
        if rec.preserve:
            guidance.extend(rec.preserve[:3])
    if not guidance:
        guidance.append("Continue from the intended PoseCraft performance unless observed video completed the action.")
    return PoseContinuityReview(
        projectId=project_id or intended.projectId,
        intended=intended,
        observedWorld=observed_world,
        observedSummary=observed_text,
        changes=changes,
        continuityRisk=risks,
        nextBatchGuidance=guidance,
    )


def _compare_without_fk(first: PoseWorldStatePacket, second: PoseWorldStatePacket) -> tuple[list[PoseChange], list[str]]:
    changes: list[PoseChange] = []
    warnings: list[str] = []
    if first.character.primarySupport != second.character.primarySupport:
        changes.append(
            PoseChange(
                kind="support_changed",
                summary="Primary support changed",
                fromValue=first.character.primarySupport,
                toValue=second.character.primarySupport,
                severity="moderate",
            )
        )
    a_hands = set(first.interaction.handContact)
    b_hands = set(second.interaction.handContact)
    for item in b_hands - a_hands:
        changes.append(PoseChange(kind="contact_gained", summary=item))
    for item in a_hands - b_hands:
        changes.append(PoseChange(kind="contact_lost", summary=item, severity="moderate"))
        warnings.append(f"Potential physical discontinuity: {item} lost")
    yaw = abs(((second.character.facingDirection - first.character.facingDirection + 180) % 360) - 180)
    if yaw >= 75:
        warnings.append("Potential physical discontinuity: character orientation jumped unexpectedly")
        changes.append(PoseChange(kind="facing_changed", summary="Orientation jump", severity="major"))
    return changes, warnings

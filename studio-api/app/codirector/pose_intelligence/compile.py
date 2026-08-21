"""Compile pose intelligence into provider-neutral motion conditioning."""

from __future__ import annotations

from typing import Any

from .contracts import PoseMotionConditioningPacket, PoseWorldStatePacket


def compile_pose_motion_conditioning(
    packet: PoseWorldStatePacket | None,
    *,
    supports_prompt_continuation: bool = True,
) -> dict[str, Any]:
    if packet is None or not packet.is_actionable():
        return {
            "applied": False,
            "reason": (packet.reason if packet else "NO_PACKET") or "UNAVAILABLE",
            "promptPrefix": "",
            "packetId": getattr(packet, "packetId", None),
        }
    if not supports_prompt_continuation:
        return {
            "applied": False,
            "reason": "GENERATOR_NO_PROMPT_CONTINUATION",
            "promptPrefix": "",
            "packetId": packet.packetId,
            "conditioning": build_conditioning_packet(packet).model_dump(mode="json"),
        }

    cond = build_conditioning_packet(packet)
    lines = ["Co-Director pose continuity (intended physical performance):"]
    if cond.subjectIdentity:
        lines.append(f"- Subject: {cond.subjectIdentity}")
    origin = packet.character.worldOrigin
    if origin and (abs(origin.x) > 1e-6 or abs(origin.z) > 1e-6):
        lines.append(f"- World origin: {origin.x:+.1f} m east, {origin.z:+.1f} m south.")
    if cond.poseState:
        lines.append(f"- Pose: {cond.poseState}")
    if cond.actionState:
        lines.append(f"- Action: {cond.actionState}")
    for item in cond.plantedLimbs:
        lines.append(f"- Planted: {item}")
    for item in cond.contactPoints:
        lines.append(f"- Contact: {item}")
    for item in cond.preserveConstraints:
        lines.append(f"- Preserve: {item}")
    for item in cond.prohibitedDiscontinuities[:4]:
        lines.append(f"- Avoid: {item}")
    if cond.expectedNextMotion:
        lines.append(f"- Continue: {cond.expectedNextMotion}")
    prefix = "\n".join(lines).strip()
    return {
        "applied": True,
        "reason": None,
        "promptPrefix": prefix,
        "packetId": packet.packetId,
        "conditioningPacketId": cond.packetId,
        "conditioning": cond.model_dump(mode="json"),
    }


def build_conditioning_packet(packet: PoseWorldStatePacket) -> PoseMotionConditioningPacket:
    ch = packet.character
    ix = packet.interaction
    subject = ch.figureName or ch.characterId or "character"
    pose_state = f"{ch.stance}; support {ch.primarySupport.replace('_', ' ')}; balance {ch.balance}"
    action = packet.motion.transitionState or packet.motion.outgoingMovement or ch.poseLabel or ch.stance
    orientation = f"facing {ch.facingDirection:.0f}°, torso y {ch.torsoOrientation.y:.0f}°"
    planted = []
    if ch.primarySupport not in {"none", "uncertain"}:
        planted.append(ch.primarySupport.replace("_", " "))
    planted.extend(ix.footContact)
    moving = [packet.motion.movingLimb] if packet.motion.movingLimb else []
    preserve = list(packet.constraints.preserveContact)
    if packet.constraints.preserveSupportFoot:
        preserve.append(f"support {packet.constraints.preserveSupportFoot.replace('_', ' ')}")
    if packet.constraints.preserveFacing:
        preserve.append("facing")
    return PoseMotionConditioningPacket(
        projectId=packet.projectId,
        sourcePosePacketId=packet.packetId,
        subjectIdentity=subject,
        characterId=ch.characterId,
        poseState=pose_state,
        actionState=action,
        bodyOrientation=orientation,
        plantedLimbs=list(dict.fromkeys([p for p in planted if p])),
        movingLimbs=[m for m in moving if m],
        contactPoints=list(ix.handContact) + list(ix.bodyToObject),
        objectInteractions=list(ix.heldObjects),
        expectedNextMotion=packet.motion.likelyContinuation or packet.motion.outgoingMovement,
        momentum=packet.motion.rotationDirection or packet.motion.motionDirection,
        cameraRelativeDirection="",
        preserveConstraints=list(dict.fromkeys(preserve))[:8],
        allowedReleaseConditions=[
            "Hand may release after the authored turn or step begins.",
        ],
        prohibitedDiscontinuities=list(packet.constraints.forbiddenDiscontinuity),
        styleOverride="Honor creator stylization; do not correct an intentional pose.",
        confidence="known" if packet.availability == "available" else "uncertain",
        sourceProvenance="posecraft-intended",
        creatorFacingSummary=packet.creatorFacingSummary,
    )

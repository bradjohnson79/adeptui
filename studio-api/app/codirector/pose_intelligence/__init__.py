"""Revision C Phase 2 — PoseCraft pose intelligence.

Kinematic / contact analysis is always available.
V-JEPA is reused from world_intelligence for visual comparison only.
This package does not create a second JEPA worker.
"""

from .contracts import (
    POSE_PACKET_SCHEMA,
    ContactEdge,
    ContactGraph,
    PoseContinuityReview,
    PoseMotionConditioningPacket,
    PoseSequenceState,
    PoseWorldStatePacket,
)

__all__ = [
    "POSE_PACKET_SCHEMA",
    "ContactEdge",
    "ContactGraph",
    "PoseContinuityReview",
    "PoseMotionConditioningPacket",
    "PoseSequenceState",
    "PoseWorldStatePacket",
]

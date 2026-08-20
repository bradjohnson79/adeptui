"""Co-Director temporal video intelligence (Revision A).

Perception reports what happened. Co-Director compare decides what that
means. Timeline generation adapters consume a TemporalContinuityPacket.
Video understanding models never submit generation.
"""

from .contracts import (
    PACKET_SCHEMA,
    CoDirectorContinuityPolicy,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
)
from .service import (
    ensure_temporal_packet_before_submit,
    find_packet_for_handoff,
    packet_blocks_submit,
    persist_unavailable_packet,
    review_completed_batch,
    set_codirector_continuity_policy,
)

__all__ = [
    "PACKET_SCHEMA",
    "CoDirectorContinuityPolicy",
    "TemporalContinuityPacket",
    "VideoPerceptionObservation",
    "ensure_temporal_packet_before_submit",
    "find_packet_for_handoff",
    "packet_blocks_submit",
    "persist_unavailable_packet",
    "review_completed_batch",
    "set_codirector_continuity_policy",
]

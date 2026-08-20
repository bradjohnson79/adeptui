"""Revision A + Revision C temporal world-state integration.

VideoChat3 observes temporal continuity.
V-JEPA evaluates world-state consistency against approved references.

Both signals feed into Co-Director reasoning for next-batch decisions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from ..video_intelligence.contracts import TemporalContinuityPacket

from .contracts import WorldStatePacket, CoDirectorWorldIntelligencePolicy
from .service import is_available
from .worker_client import compare_images, schedule_cuda_probe

logger = logging.getLogger(__name__)


def augment_temporal_packet(
    packet: TemporalContinuityPacket,
    clip_path: Optional[str] = None,
    reference_image_path: Optional[str] = None,
    reference_asset_id: Optional[str] = None,
    world_policy: Optional[CoDirectorWorldIntelligencePolicy] = None,
) -> TemporalContinuityPacket:
    """Add JEPA world-state comparison as complementary signal.

    This attaches a serialized WorldStatePacket into the temporal
    packet's extras under "worldReview".

    The world review is NON-BLOCKING — if JEPA is unavailable or
    fails, the temporal packet is returned unchanged. This never
    blocks Batch N+1.
    """
    schedule_cuda_probe()
    availability = is_available(probe=False)
    if not availability.get("available", False):
        packet.extras["worldReview"] = {
            "availability": "unavailable",
            "reason": availability.get("reason") or "NOT_PROBED",
        }
        return packet

    if not clip_path or not Path(clip_path).is_file():
        return packet

    # Extract first frame from clip as reference comparison
    frame_path = _extract_first_frame(clip_path)
    if not frame_path:
        return packet

    try:
        if reference_image_path:
            # Compare against approved world reference
            world_packet = compare_images(
                image_a_path=reference_image_path,
                image_b_path=frame_path,
                asset_id_a=reference_asset_id,
                asset_id_b=packet.source.batchId,
                use_cache=True,
            )
        else:
            # No reference - compare clip to itself for consistency check
            world_packet = compare_images(
                image_a_path=frame_path,
                image_b_path=frame_path,
                use_cache=True,
            )

        # Attach as extras — never replaces TemporalContinuityPacket
        packet.extras["worldReview"] = world_packet.model_dump(mode="json")

        # Add a summary advisory to the continuation context
        _add_world_advisory(packet, world_packet)

    except Exception as exc:
        logger.debug("JEPA world review unavailable: %s", exc)
        packet.extras["worldReview"] = {"availability": "unavailable", "reason": str(exc)[:120]}

    _cleanup_frame(frame_path)
    return packet


def _extract_first_frame(clip_path: str) -> Optional[str]:
    """Extract the first frame from a video clip for JEPA analysis."""
    import subprocess
    import tempfile

    try:
        fd, frame_path = tempfile.mkstemp(suffix=".jpg", prefix="jepa_frame_")
        import os
        os.close(fd)

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",
                frame_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not Path(frame_path).is_file():
            return None
        return frame_path
    except Exception as exc:
        logger.debug("Frame extraction failed: %s", exc)
        return None


def _cleanup_frame(frame_path: Optional[str]) -> None:
    """Clean up extracted frame."""
    if frame_path and Path(frame_path).is_file():
        try:
            Path(frame_path).unlink()
        except OSError:
            pass


def _add_world_advisory(packet: TemporalContinuityPacket, world_packet: WorldStatePacket) -> None:
    """Translate world-state signals into continuation advisory text."""
    if not world_packet.is_actionable():
        return

    rec = world_packet.recommendation
    if rec.consistent and not rec.caution and not rec.review_:
        packet.continuation.preserve.append("Environment/world state remains consistent.")
    elif rec.consistent and rec.caution:
        packet.continuation.preserve.append(rec.caution[0])
    elif not rec.consistent and rec.review_:
        # Compile() only reads preserve / continue / avoid / nextBatchDirectives.
        caution_text = rec.review_[0] if rec.review_ else "World-state changed notably."
        if caution_text not in packet.continuation.nextBatchDirectives:
            packet.continuation.nextBatchDirectives.append(caution_text)
        if caution_text not in packet.continuation.avoid:
            packet.continuation.avoid.append(caution_text)

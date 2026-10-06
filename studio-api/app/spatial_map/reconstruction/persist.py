"""Trait-store persistence for SpatialReconstructionPacket."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .contracts import SpatialReconstructionPacket, _now

logger = logging.getLogger(__name__)

PACKET_CATEGORY = "spatial_reconstruction"


def save_reconstruction_packet(
    db: Session,
    packet: SpatialReconstructionPacket,
) -> SpatialReconstructionPacket:
    from ..ers_persistence import _upsert_trait

    packet.updatedAt = _now()
    payload = packet.model_dump_json()
    keys = [k for k in (packet.executionId, packet.packetId) if k]
    for key in dict.fromkeys(keys):
        _upsert_trait(
            db,
            project_id=packet.projectId,
            category=PACKET_CATEGORY,
            key=key,
            value=payload,
            provenance="spatial_reconstruction_compiler",
        )
    return packet


def load_reconstruction_packet(
    db: Session,
    project_id: str,
    execution_id: str,
) -> SpatialReconstructionPacket | None:
    from ..ers_persistence import _load_trait_value

    raw = _load_trait_value(
        db,
        project_id=project_id,
        category=PACKET_CATEGORY,
        key=execution_id,
    )
    if not raw:
        return None
    try:
        return SpatialReconstructionPacket.model_validate_json(raw)
    except Exception as exc:
        logger.warning("Failed to load reconstruction packet %s: %s", execution_id, exc)
        return None

"""Write accepted reconstruction onto Spatial Map only after the visual gate."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..schemas import EnvironmentalAnchor, Vec3Meters
from .contracts import SpatialReconstructionPacket
from .persist import load_reconstruction_packet, save_reconstruction_packet

PROVISIONAL_LAYOUT_NOTE = (
    "Layout size is a relative estimate (1 square = 1 meter) until a real-world size is confirmed."
)


def accepted_map_fields(packet: SpatialReconstructionPacket) -> dict[str, Any]:
    if not packet.sanity.ok:
        raise ValueError("Reconstructed layout failed geometry checks and cannot be written to Spatial Map.")
    width = float(packet.layout.widthProvisionalM or packet.layout.widthCells or 0)
    depth = float(packet.layout.depthProvisionalM or packet.layout.depthCells or 0)
    if width <= 0 or depth <= 0:
        raise ValueError("Reconstructed layout has no usable extent.")
    anchors: list[dict[str, Any]] = []
    for feature in packet.features:
        if feature.cellColumn is None or feature.cellRow is None:
            continue
        x = (int(feature.cellColumn) + 0.5) - (packet.layout.widthCells / 2.0)
        z = (int(feature.cellRow) + 0.5) - (packet.layout.depthCells / 2.0)
        anchors.append(
            EnvironmentalAnchor(
                label=feature.userIntentLabel or feature.type or "Feature",
                kind=feature.type or "landmark",
                positionMeters=Vec3Meters(x=x, y=0.0, z=z),
                notes=feature.notes,
            ).model_dump()
        )
    provisional = packet.scale.mode != "anchored"
    fields: dict[str, Any] = {
        "widthMeters": width,
        "depthMeters": depth,
        "metersPerCell": float(packet.scale.metersPerCell or 1.0),
        "environmentalAnchors": anchors,
        "scaleMode": packet.scale.mode,
        "scaleConfidence": packet.scale.confidence,
        "provisionalLayout": provisional,
    }
    if provisional:
        fields["layoutNote"] = PROVISIONAL_LAYOUT_NOTE
        fields["providerHonesty"] = "approximate_translation"
    return fields


def mark_packet_assigned(db: Session, packet: SpatialReconstructionPacket) -> SpatialReconstructionPacket:
    packet.assignedToMap = True
    return save_reconstruction_packet(db, packet)


def load_packet_for_execution(
    db: Session,
    project_id: str,
    execution_id: str,
) -> SpatialReconstructionPacket | None:
    return load_reconstruction_packet(db, project_id, execution_id)

"""Project-scoped persistence for pose intelligence packets.

Uses ProjectTraitRow so reload/reopen returns the same creator-facing state.
Never stores embeddings or latent vectors.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import (
    PoseMotionConditioningPacket,
    PoseSequenceState,
    PoseWorldStatePacket,
)

CATEGORY = "pose_intelligence"
PROVENANCE = "co_director_pose_intelligence"


def latest_key() -> str:
    return "latest"


def snapshot_key(snapshot_id: str) -> str:
    return f"snapshot:{snapshot_id}"


def figure_key(figure_id: str, revision: int) -> str:
    return f"figure:{figure_id}:rev:{revision}"


def compare_key(from_id: str, to_id: str) -> str:
    return f"compare:{from_id}:{to_id}"


def handoff_key(kind: str) -> str:
    return f"handoff:{kind}"


def conditioning_key() -> str:
    return "conditioning:latest"


def _upsert(db: Session, project_id: str, key: str, payload: dict[str, Any]) -> None:
    from ...spatial_map.ers_persistence import _upsert_trait

    _upsert_trait(
        db,
        project_id=project_id,
        category=CATEGORY,
        key=key,
        value=json.dumps(payload, ensure_ascii=False),
        provenance=PROVENANCE,
    )


def _load(db: Session, project_id: str, key: str) -> dict[str, Any] | None:
    from ...spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=CATEGORY, key=key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_packet(
    db: Session,
    project_id: str,
    packet: PoseWorldStatePacket,
    *,
    snapshot_id: str = "",
    extra_keys: Optional[list[str]] = None,
) -> None:
    payload = {
        "packet": packet.model_dump(mode="json"),
        "projectId": project_id,
        "snapshotId": snapshot_id or packet.snapshotId or "",
        "packetId": packet.packetId,
    }
    keys = {latest_key()}
    if snapshot_id or packet.snapshotId:
        keys.add(snapshot_key(snapshot_id or str(packet.snapshotId)))
    if packet.character.figureId:
        keys.add(figure_key(packet.character.figureId, packet.character.poseRevision))
    for key in extra_keys or []:
        keys.add(key)
    for key in keys:
        _upsert(db, project_id, key, payload)


def load_packet(
    db: Session,
    project_id: str,
    *,
    snapshot_id: str = "",
    figure_id: str = "",
    revision: int | None = None,
    fallback_latest: bool = True,
) -> PoseWorldStatePacket | None:
    keys: list[str] = []
    if snapshot_id:
        keys.append(snapshot_key(snapshot_id))
    if figure_id and revision is not None:
        keys.append(figure_key(figure_id, revision))
    if fallback_latest and not snapshot_id:
        keys.append(latest_key())
    elif fallback_latest and not keys:
        keys.append(latest_key())
    for key in keys:
        data = _load(db, project_id, key)
        if not data:
            continue
        raw = data.get("packet")
        if not isinstance(raw, dict):
            continue
        try:
            packet = PoseWorldStatePacket.model_validate(raw)
        except Exception:
            continue
        if packet.projectId and packet.projectId != project_id:
            continue
        return packet
    return None


def save_sequence(db: Session, project_id: str, sequence: PoseSequenceState) -> None:
    _upsert(
        db,
        project_id,
        "sequence:latest",
        {"sequence": sequence.model_dump(mode="json"), "projectId": project_id},
    )


def load_sequence(db: Session, project_id: str) -> PoseSequenceState | None:
    data = _load(db, project_id, "sequence:latest")
    if not data or not isinstance(data.get("sequence"), dict):
        return None
    try:
        seq = PoseSequenceState.model_validate(data["sequence"])
    except Exception:
        return None
    if seq.projectId and seq.projectId != project_id:
        return None
    return seq


def save_conditioning(
    db: Session,
    project_id: str,
    packet: PoseMotionConditioningPacket,
) -> None:
    _upsert(
        db,
        project_id,
        conditioning_key(),
        {"conditioning": packet.model_dump(mode="json"), "projectId": project_id},
    )


def load_conditioning(db: Session, project_id: str) -> PoseMotionConditioningPacket | None:
    data = _load(db, project_id, conditioning_key()) or _load(db, project_id, handoff_key("timeline"))
    if not data or not isinstance(data.get("conditioning"), dict):
        return None
    try:
        packet = PoseMotionConditioningPacket.model_validate(data["conditioning"])
    except Exception:
        return None
    if packet.projectId and packet.projectId != project_id:
        return None
    return packet


def save_handoff(db: Session, project_id: str, kind: str, payload: dict[str, Any]) -> None:
    body = dict(payload)
    body["projectId"] = project_id
    _upsert(db, project_id, handoff_key(kind), body)


def load_handoff(db: Session, project_id: str, kind: str) -> dict[str, Any] | None:
    data = _load(db, project_id, handoff_key(kind))
    if not data:
        return None
    if str(data.get("projectId") or "") not in {"", project_id}:
        return None
    return data

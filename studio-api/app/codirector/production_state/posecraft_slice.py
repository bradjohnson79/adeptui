"""Assemble a compact PoseCraft reference slice from the canonical scene.

Does not duplicate 17-joint Euler maps into Working Context.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .working_context import PoseCraftFigureRef, PoseCraftSlice


def _loads(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _figure_dict(figure: Any) -> dict[str, Any]:
    if isinstance(figure, dict):
        return figure
    if hasattr(figure, "model_dump"):
        try:
            return figure.model_dump()
        except Exception:
            pass
    return {
        "id": getattr(figure, "id", ""),
        "name": getattr(figure, "name", ""),
        "archetypeId": getattr(figure, "archetypeId", ""),
        "characterId": getattr(figure, "characterId", "") or "",
        "poseId": getattr(figure, "poseId", "") or "",
        "poseLabel": getattr(figure, "poseLabel", "") or "",
        "position": getattr(figure, "position", {}) or {},
        "rotationY": getattr(figure, "rotationY", 0.0) or 0.0,
    }


def build_posecraft_slice(db: Session, project_id: str) -> PoseCraftSlice:
    from ...db import Project
    from ..pose_intelligence.persist import load_packet

    project = db.get(Project, project_id)
    if project is None:
        return PoseCraftSlice()
    doc = _loads(getattr(project, "posecraft_document_json", "") or "")
    scene = doc.get("currentScene") if isinstance(doc.get("currentScene"), dict) else doc
    if not isinstance(scene, dict):
        scene = {}
    figures_raw = scene.get("figures") or []
    # The handoff asset is the SELECTED Snapshot's frozen PNG. Snapshots live on
    # the document (doc.snapshots) and are keyed by selectedSnapshotId; the PNG
    # library id is `imageAssetId` (posecraft/schemas.py), never `snapshotAssetId`.
    snapshots = doc.get("snapshots") if isinstance(doc.get("snapshots"), list) else []
    selected_snapshot_id = str(doc.get("selectedSnapshotId") or "")
    selected_snapshot: dict[str, Any] = {}
    for raw_snap in snapshots:
        if not isinstance(raw_snap, dict):
            continue
        if selected_snapshot_id and str(raw_snap.get("snapshotId") or "") == selected_snapshot_id:
            selected_snapshot = raw_snap
            break
    if not selected_snapshot and snapshots and isinstance(snapshots[0], dict):
        selected_snapshot = snapshots[0]
    selected_snapshot_asset_id = str(selected_snapshot.get("imageAssetId") or "")
    packet = None
    try:
        packet = load_packet(db, project_id)
    except Exception:
        packet = None
    packet_id = str(getattr(packet, "packetId", "") or "") if packet is not None else ""
    packet_ids = [packet_id] if packet_id else []

    figures: list[PoseCraftFigureRef] = []
    for raw in figures_raw:
        fig = _figure_dict(raw)
        fid = str(fig.get("id") or "")
        if not fid:
            continue
        pos = fig.get("position") or {}
        figures.append(
            PoseCraftFigureRef(
                figureId=fid,
                characterId=str(fig.get("characterId") or ""),
                name=str(fig.get("name") or ""),
                archetypeId=str(fig.get("archetypeId") or fig.get("modelId") or ""),
                modelId=str(fig.get("modelId") or fig.get("archetypeId") or ""),
                posePresetId=str(fig.get("poseId") or ""),
                posePresetName=str(fig.get("poseLabel") or ""),
                jointStateRef=f"posecraft://{project_id}/figures/{fid}/pose",
                worldPosition={
                    "x": float(pos.get("x") or 0.0),
                    "z": float(pos.get("z") or 0.0),
                },
                worldOrientation={"y": float(fig.get("rotationY") or 0.0)},
                contacts=list(getattr(packet, "interaction", None).footContact if packet is not None and getattr(packet, "interaction", None) else [])
                if packet is not None
                else [],
                poseWorldStatePacketId=packet_id,
                snapshotAssetId=selected_snapshot_asset_id,
            )
        )

    origin = scene.get("worldOriginMeters") or doc.get("worldOriginMeters") or {}
    if not isinstance(origin, dict):
        origin = {}
    return PoseCraftSlice(
        sceneId=str(scene.get("id") or scene.get("sceneId") or ""),
        revision=int(scene.get("revision") or 0),
        activeFigureIds=[f.figureId for f in figures],
        snapshotAssetId=selected_snapshot_asset_id,
        worldOriginMeters={k: float(v) for k, v in origin.items() if isinstance(v, (int, float))},
        poseWorldStatePacketIds=packet_ids,
        figures=figures,
    )


def resolve_figure_for_character(
    slice_: PoseCraftSlice,
    *,
    character_id: str = "",
    name: str = "",
) -> PoseCraftFigureRef | None:
    cid = (character_id or "").strip().lower()
    label = (name or "").strip().lower()
    if cid:
        for fig in slice_.figures:
            if (fig.characterId or "").strip().lower() == cid:
                return fig
    if label:
        for fig in slice_.figures:
            if (fig.name or "").strip().lower() == label:
                return fig
        for fig in slice_.figures:
            if label in (fig.name or "").strip().lower():
                return fig
    return None

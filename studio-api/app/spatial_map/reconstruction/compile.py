"""Compile relative layout onto a 1-cell = 1 provisional meter grid.

Meter numbers without scaleEvidence stay provisional. Tests may use a 3×15
cell ratio fixture for corridors — that is not certified real-world meters.
"""

from __future__ import annotations

from typing import Any

from .contracts import (
    EvidenceKind,
    FeatureRecord,
    ReconstructionCamera,
    ReconstructionLayout,
    ScaleRecord,
    SpatialReconstructionPacket,
    UnknownRegion,
    _now,
)
from .sanity import validate_geometry_sanity

# Corridor ratio fixture used by tests. Not claimed real-world meters.
CORRIDOR_RATIO_CELLS = (3, 15)


def _clamp_cells(value: int, lo: int = 2, hi: int = 40) -> int:
    return max(lo, min(hi, int(value)))


def compile_relative_layout(geo: dict[str, Any]) -> ReconstructionLayout:
    env = str(geo.get("environmentType") or "uncertain")
    aspect = float(geo.get("sourceAspect") or 1.0)
    conf = float(geo.get("environmentConfidence") or 0.4)
    if env == "corridor":
        width_cells, depth_cells = CORRIDOR_RATIO_CELLS
        if aspect < 1.0:
            width_cells, depth_cells = depth_cells, width_cells
    elif env == "wide_interior":
        width_cells, depth_cells = 12, 6
    elif env == "exterior":
        width_cells, depth_cells = 12, 12
    elif env == "room":
        width_cells, depth_cells = 8, 8
        if aspect >= 1.25:
            width_cells = _clamp_cells(round(8 * aspect))
        elif aspect <= 0.8:
            depth_cells = _clamp_cells(round(8 / max(aspect, 0.4)))
    else:
        width_cells, depth_cells = 8, 8
    return ReconstructionLayout(
        environmentType=env,  # type: ignore[arg-type]
        widthCells=int(width_cells),
        depthCells=int(depth_cells),
        widthProvisionalM=float(width_cells),
        depthProvisionalM=float(depth_cells),
        sourceAspect=aspect,
        evidence="inferred",
        confidence=conf,
    )


def compile_scale(scale_evidence: dict[str, Any] | None = None) -> ScaleRecord:
    evidence = scale_evidence or {}
    if evidence.get("anchorKind") and evidence.get("meters"):
        return ScaleRecord(
            mode="anchored",
            evidenceKind="observed",
            confidence=float(evidence.get("confidence") or 0.8),
            anchorKind=str(evidence.get("anchorKind") or ""),
            anchorNote=str(evidence.get("anchorNote") or ""),
            metersPerCell=1.0,
        )
    return ScaleRecord(
        mode="provisional",
        evidenceKind="inferred",
        confidence=0.2,
        anchorKind="",
        anchorNote="Relative geometry on a 1-square = 1-meter grid without a measured scale anchor.",
        metersPerCell=1.0,
    )


def compile_packet(
    *,
    project_id: str,
    execution_id: str,
    source_asset_ids: list[str],
    geo: dict[str, Any],
    features: list[FeatureRecord] | None = None,
    unknown_regions: list[UnknownRegion] | None = None,
    scene_intent: dict[str, Any] | None = None,
    user_intent_summary: str = "",
    scale_evidence: dict[str, Any] | None = None,
    map_id: str = "",
) -> SpatialReconstructionPacket:
    layout = compile_relative_layout(geo)
    vanish = geo.get("vanishingPoint")
    camera = ReconstructionCamera(
        orientation="forward",
        vanishingPoint=tuple(vanish) if vanish else None,
        evidence="inferred",
        confidence=float(geo.get("environmentConfidence") or 0.4),
    )
    feats = list(features or [])
    unknowns = list(unknown_regions or [])
    if layout.environmentType in {"uncertain", "exterior"}:
        unknowns.append(
            UnknownRegion(
                reason="Regions beyond the visible frame stay unknown.",
                evidence="unknown",
                notes="No hidden rooms were invented from a single image.",
            )
        )
    # Scene Intent is user intent, never observed fact.
    intent = dict(scene_intent or {})
    refs = [dict(item) for item in (geo.get("references") or []) if isinstance(item, dict)]
    inferred_ids = {
        str(item.get("assetId") or "").strip()
        for item in refs
        if str(item.get("evidenceClass") or item.get("evidence") or "").upper() == "INFERRED"
        and str(item.get("assetId") or "").strip()
    }
    observed_ids = [
        str(a).strip()
        for a in source_asset_ids
        if str(a).strip() and str(a).strip() not in inferred_ids
    ]
    packet = SpatialReconstructionPacket(
        projectId=project_id,
        executionId=execution_id,
        mapId=map_id,
        sourceAssetIds=observed_ids,
        references=refs,
        environmentType=layout.environmentType,
        camera=camera,
        layout=layout,
        scale=compile_scale(scale_evidence),
        features=feats,
        unknownRegions=unknowns,
        userIntentSummary=user_intent_summary,
        sceneIntent=intent,
        createdAt=_now(),
        updatedAt=_now(),
    )
    packet.sanity = validate_geometry_sanity(packet)
    return packet


def evidence_for_feature(*, visible: bool, inferred: bool) -> EvidenceKind:
    if visible:
        return "observed"
    if inferred:
        return "inferred"
    return "unknown"

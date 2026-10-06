"""Spatial Reconstruction Compiler orchestrator.

perception → packet → sanity → structural guide.
The guide is render authority only. Map assignment waits for the visual gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from .contracts import SpatialReconstructionPacket, _now
from .guide import persist_guide_asset
from .perceive import perceive_source
from .persist import load_reconstruction_packet, save_reconstruction_packet
from .sanity import validate_geometry_sanity

COMPILER_STAGES = (
    "analyzing",
    "estimating",
    "building_layout",
    "preparing_render",
    "generating",
    "validating",
    "assigning",
)

STAGE_COPY = {
    "analyzing": "Analyzing the location…",
    "estimating": "Estimating the layout…",
    "building_layout": "Building the spatial layout…",
    "preparing_render": "Preparing the Atlas renderer…",
    "generating": "Generating the Atlas Shot…",
    "validating": "Validating the Atlas…",
    "assigning": "Saving Spatial Map…",
    "retrying": "Retrying top-down reconstruction…",
}

TERMINAL_RECONSTRUCTION_ERROR = (
    "Atlas reconstruction could not produce a reliable top-down result from this source image."
)


class GeometrySanityError(RuntimeError):
    """Packet failed the geometry sanity gate. Do not render or assign."""


@dataclass
class ReconstructionPrepareResult:
    packet: SpatialReconstructionPacket
    guide_asset_id: str
    stage: str
    message: str
    rebuilt_packet: bool = True
    rebuilt_guide: bool = True
    stage_timings_ms: dict[str, float] | None = None


def _reuse_packet(
    db: Session,
    *,
    project_id: str,
    execution_id: str,
    source_asset_id: str,
    reuse_execution_id: str,
    reuse_packet_id: str,
) -> SpatialReconstructionPacket | None:
    prior = None
    if reuse_execution_id:
        prior = load_reconstruction_packet(db, project_id, reuse_execution_id)
    if prior is None and reuse_packet_id:
        prior = load_reconstruction_packet(db, project_id, reuse_packet_id)
    if prior is None:
        return None
    sources = [str(s) for s in (prior.sourceAssetIds or [])]
    if source_asset_id and source_asset_id not in sources:
        return None
    reused = prior.model_copy(deep=True)
    reused.executionId = execution_id
    reused.assignedToMap = False
    reused.updatedAt = _now()
    return reused


def prepare_reconstruction_for_atlas(
    db: Session,
    *,
    project_id: str,
    execution_id: str,
    source_asset_id: str,
    scene_intent: dict[str, Any] | None = None,
    user_intent_summary: str = "",
    require_models: bool = False,
    map_id: str = "",
    reuse_execution_id: str = "",
    reuse_packet_id: str = "",
    reuse_guide_asset_id: str = "",
    click_id: str = "",
    retry_index: int = 0,
) -> ReconstructionPrepareResult:
    if db is None:
        raise RuntimeError("Atlas reconstruction needs the project database.")
    timings: dict[str, float] = {}
    from .perf import StageTimer, record_compiler_execution, record_gpu_sample, record_stage

    reused = _reuse_packet(
        db,
        project_id=project_id,
        execution_id=execution_id,
        source_asset_id=source_asset_id,
        reuse_execution_id=reuse_execution_id,
        reuse_packet_id=reuse_packet_id,
    )
    if reused is not None and (reused.guideAssetId or reuse_guide_asset_id):
        if reuse_guide_asset_id and not reused.guideAssetId:
            reused.guideAssetId = reuse_guide_asset_id
        save_reconstruction_packet(db, reused)
        if click_id:
            record_compiler_execution(
                db,
                project_id,
                click_id,
                execution_id=execution_id,
                source_asset_id=source_asset_id,
                rebuilt_packet=False,
                rebuilt_guide=False,
                retry_index=retry_index,
            )
            record_stage(db, project_id, click_id, "reuse_packet_guide", 0.0)
        return ReconstructionPrepareResult(
            packet=reused,
            guide_asset_id=reused.guideAssetId,
            stage="preparing_render",
            message=STAGE_COPY["preparing_render"],
            rebuilt_packet=False,
            rebuilt_guide=False,
            stage_timings_ms={"reuse": 0.0},
        )

    if click_id:
        record_gpu_sample(db, project_id, click_id, label="compiler_start")
    timer = StageTimer()
    packet = perceive_source(
        db,
        project_id=project_id,
        execution_id=execution_id,
        source_asset_id=source_asset_id,
        scene_intent=scene_intent,
        user_intent_summary=user_intent_summary,
        require_models=require_models,
        map_id=map_id,
    )
    timings["perceive"] = timer.ms()
    if click_id:
        record_stage(db, project_id, click_id, "perceive", timings["perceive"])

    timer = StageTimer()
    packet.sanity = validate_geometry_sanity(packet)
    timings["sanity"] = timer.ms()
    if click_id:
        record_stage(db, project_id, click_id, "sanity", timings["sanity"])
    if not packet.sanity.ok:
        save_reconstruction_packet(db, packet)
        if click_id:
            record_compiler_execution(
                db,
                project_id,
                click_id,
                execution_id=execution_id,
                source_asset_id=source_asset_id,
                rebuilt_packet=True,
                rebuilt_guide=False,
                retry_index=retry_index,
            )
        detail = "; ".join(packet.sanity.errors) or "the reconstructed layout is not usable"
        raise GeometrySanityError(
            f"Atlas reconstruction stopped before rendering: {detail}."
        )

    timer = StageTimer()
    persist_guide_asset(db, packet)
    timings["guideRaster"] = timer.ms()
    save_reconstruction_packet(db, packet)
    if click_id:
        record_stage(db, project_id, click_id, "guideRaster", timings["guideRaster"])
        record_compiler_execution(
            db,
            project_id,
            click_id,
            execution_id=execution_id,
            source_asset_id=source_asset_id,
            rebuilt_packet=True,
            rebuilt_guide=True,
            retry_index=retry_index,
        )
        record_gpu_sample(db, project_id, click_id, label="compiler_ready")
    return ReconstructionPrepareResult(
        packet=packet,
        guide_asset_id=packet.guideAssetId,
        stage="preparing_render",
        message=STAGE_COPY["preparing_render"],
        rebuilt_packet=True,
        rebuilt_guide=True,
        stage_timings_ms=timings,
    )

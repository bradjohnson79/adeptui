"""Media Intelligence API routes — the CREATE/Studio-API path (1F/3F/T2V gates).

Thin HTTP layer over the existing building blocks:

- ``media_analyze.analyze_asset`` / ``diagnose_asset`` (Phase C — imported,
  never re-implemented) produce the frozen ``MediaIntelligencePacket``.
- ``inspection_report`` (this mission) adds the deterministic diagnostics
  stage + the shared CREATE inspection report.
- ``media_persist`` provides the project-scoped packet cache (Ch 7, 41-42).
- ``resolve_project_asset_path`` enforces project isolation fail-closed
  (403 on project mismatch, 404 on missing asset/file — Ch 41).

No GPU work happens in this module; perception runs inside the isolated
worker spawned by ``worker_client`` (Phase C). ``GET /status`` is a pure
filesystem marker probe — it never imports torch or touches a runtime.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import get_db
from ...project_security.asset_file import resolve_project_asset_path
from . import media_persist, paths
from .inspection_report import (
    DIAGNOSTIC_VERSION,
    build_inspection_report,
    enrich_packet_diagnostics,
    packet_has_current_diagnostics,
)
from .media_analyze import analyze_asset, diagnose_asset
from .media_packet import (
    ANALYSIS_VERSION,
    INTERNVIDEO3_MODEL_ID,
    MEDIA_PACKET_SCHEMA,
    QWEN_OMNI_MODEL_ID,
    VIDEOCHAT3_MODEL_ID,
    CreateDiagnosticContext,
    CreateSurface,
    MediaIntelligencePacket,
    TimelineAnalysisContext,
)
from .worker_client import perception_mode

router = APIRouter(prefix="/media-intelligence", tags=["codirector-media-intelligence"])


class AnalyzeBody(BaseModel):
    projectId: str
    assetId: str
    mode: str = "full"
    surface: CreateSurface = "general"
    createContext: Optional[CreateDiagnosticContext] = None
    question: Optional[str] = None
    force: bool = False
    sceneId: Optional[str] = None
    executionId: Optional[str] = None
    rangeStartSec: Optional[float] = None
    rangeEndSec: Optional[float] = None
    playheadSec: Optional[float] = None


class DiagnoseBody(BaseModel):
    projectId: str
    assetId: str
    surface: CreateSurface = "general"
    createContext: Optional[CreateDiagnosticContext] = None
    force: bool = False


def _resolve_reference_path(
    db: Session, project_id: str, ctx: Optional[CreateDiagnosticContext]
) -> Optional[str]:
    """Resolve ``createContext.referenceAssetIds[0]`` (1F source / 3F START)
    inside the SAME project.

    Fail closed: a cross-project or missing reference raises (403/404). We
    never silently analyze without the declared reference — that would
    produce a report whose referenceAdherence section looks unverifiable
    when the caller actually supplied a bad id.
    """
    if ctx is None or not ctx.referenceAssetIds:
        return None
    _ref_asset, ref_path = resolve_project_asset_path(db, project_id, ctx.referenceAssetIds[0])
    return str(ref_path)


def _finalize_packet(
    db: Session,
    project_id: str,
    resolved_path: Path,
    packet: MediaIntelligencePacket,
    *,
    surface: CreateSurface,
    create_context: Optional[CreateDiagnosticContext],
) -> MediaIntelligencePacket:
    """Attach CREATE surface context + deterministic diagnostics, then persist.

    Additive orchestration over ``analyze_asset``'s packet — Phase C's
    perception logic, availability semantics, and cache fingerprint are not
    modified. Idempotent: a fresh cache hit already carries this version's
    diagnostics, so no ffmpeg re-decode happens.
    """
    changed = False

    ctx = create_context
    if ctx is None and surface != "general":
        ctx = CreateDiagnosticContext(surface=surface)
    if ctx is not None and packet.createContext != ctx:
        # Latest-request-wins for surface framing (the cache fingerprint does
        # not include create context).
        packet.createContext = ctx
        changed = True

    if not packet_has_current_diagnostics(packet):
        reference_path = _resolve_reference_path(db, project_id, ctx)
        enrich_packet_diagnostics(packet, resolved_path, reference_path=reference_path)
        changed = True

    if changed:
        media_persist.save_packet(db, project_id, packet)
    return packet


@router.post("/analyze")
def api_analyze(body: AnalyzeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Analyze one project asset -> the frozen Media Intelligence Packet JSON."""
    _asset, resolved = resolve_project_asset_path(db, body.projectId, body.assetId)
    kwargs: dict[str, Any] = {
        "mode": body.mode,
        "force": body.force,
        "scene_id": body.sceneId,
        "execution_id": body.executionId,
        "range_start_sec": body.rangeStartSec,
        "range_end_sec": body.rangeEndSec,
        "playhead_sec": body.playheadSec,
    }
    if body.question:
        kwargs["question"] = body.question
    packet = analyze_asset(db, body.projectId, body.assetId, **kwargs)
    if body.sceneId or body.rangeEndSec is not None or body.playheadSec is not None:
        packet.timelineContext = TimelineAnalysisContext(
            projectId=body.projectId,
            sceneId=body.sceneId or "",
            clipAssetId=body.assetId,
            executionId=body.executionId,
            rangeStartSec=float(body.rangeStartSec or 0.0),
            rangeEndSec=body.rangeEndSec,
            playheadSec=body.playheadSec,
        )
    packet = _finalize_packet(
        db,
        body.projectId,
        resolved,
        packet,
        surface=body.surface,
        create_context=body.createContext,
    )
    return packet.model_dump(mode="json")


@router.get("/packet")
def api_packet(projectId: str, assetId: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the cached packet for THIS asset under THIS project (asset-strict)."""
    packet = media_persist.load_packet(db, projectId, assetId)
    if packet is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "PACKET_NOT_FOUND", "projectId": projectId, "assetId": assetId},
        )
    return packet.model_dump(mode="json")


@router.post("/diagnose")
def api_diagnose(body: DiagnoseBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Engineering ``diagnose asset <assetId>`` path -> shared inspection report."""
    _asset, resolved = resolve_project_asset_path(db, body.projectId, body.assetId)
    packet = diagnose_asset(db, body.projectId, body.assetId, force=body.force)
    packet = _finalize_packet(
        db,
        body.projectId,
        resolved,
        packet,
        surface=body.surface,
        create_context=body.createContext,
    )
    return build_inspection_report(packet)


@router.get("/status")
def api_status() -> dict[str, Any]:
    """Service/model availability. Pure filesystem marker probes — no torch
    import, no GPU query, no runtime contact."""
    return {
        "ok": True,
        "schemaVersion": MEDIA_PACKET_SCHEMA,
        "analysisVersion": ANALYSIS_VERSION,
        "diagnosticVersion": DIAGNOSTIC_VERSION,
        "perceptionMode": perception_mode(),
        "models": {
            "qwenOmni": {
                "modelId": QWEN_OMNI_MODEL_ID,
                "installed": paths.qwen_omni_model_present(),
            },
            "videoChat3": {
                "modelId": VIDEOCHAT3_MODEL_ID,
                "installed": paths.model_present(paths.videochat3_dir(), paths.VIDEOCHAT3_MARKERS),
            },
            "internVideo3": {
                "modelId": INTERNVIDEO3_MODEL_ID,
                "installed": paths.model_present(paths.internvideo3_dir(), paths.INTERNVIDEO3_MARKERS),
            },
        },
        "deterministicDiagnostics": {
            "ffmpeg": bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")),
            "ffprobe": bool(shutil.which("ffprobe") or shutil.which("ffprobe.exe")),
        },
    }

"""Perception for Spatial Reconstruction — DINO / depth / SAM + pixel geometry.

Frozen PerceptionPacket is not mutated. Depth is kept as a derived asset when
models are present. Missing models never invent a fake depth map.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset
from .compile import compile_packet, evidence_for_feature
from .contracts import FeatureRecord, SpatialReconstructionPacket, UnknownRegion
from .geometry import pixel_geometry

logger = logging.getLogger(__name__)


class PerceptionModelsMissing(RuntimeError):
    """Required stills-perception models are not installed."""


def _load_source_pixels(db: Session, project_id: str, asset_id: str) -> tuple[Any, int, int, str]:
    from PIL import Image
    import numpy as np

    asset = db.get(Asset, asset_id) if db is not None else None
    if asset is None or str(asset.project_id or "") != project_id:
        raise RuntimeError("The location image is not in this project.")
    path = str(asset.path or "").strip()
    if not path or not Path(path).is_file():
        raise RuntimeError("The location image file is missing.")
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img)
    return arr, int(arr.shape[1]), int(arr.shape[0]), path


def _features_from_detections(
    detections: list[dict[str, Any]],
    layout_width: int,
    layout_depth: int,
) -> list[FeatureRecord]:
    opening_labels = {"door", "window", "opening", "doorway"}
    features: list[FeatureRecord] = []
    for item in detections:
        label = str(item.get("label") or "").strip().lower()
        box = item.get("box") if isinstance(item.get("box"), dict) else {}
        cx = float(box.get("x") or box.get("cx") or 0.5)
        cy = float(box.get("y") or box.get("cy") or 0.5)
        if cx > 1.5 or cy > 1.5:
            # Pixel boxes — normalize later if width known; skip unsafe coords.
            continue
        col = min(max(int(cx * layout_width), 0), max(layout_width - 1, 0))
        row = min(max(int(cy * layout_depth), 0), max(layout_depth - 1, 0))
        kind = "opening" if any(tok in label for tok in opening_labels) else "fixture"
        features.append(
            FeatureRecord(
                type=kind,
                wall="north" if row <= 1 else "south" if row >= layout_depth - 2 else "",
                distanceRatio=cy,
                cellColumn=col,
                cellRow=row,
                evidence=evidence_for_feature(visible=True, inferred=False),
                confidence=float(item.get("confidence") or item.get("score") or 0.5),
                notes=label,
            )
        )
    return features


def _try_perception_models(image_path: str, *, require_models: bool) -> dict[str, Any]:
    from ...codirector.perception.paths import geometry_models_present

    if not geometry_models_present():
        if require_models:
            raise PerceptionModelsMissing(
                "Depth and structure models are not installed. "
                "Atlas reconstruction cannot invent geometry from a missing depth model."
            )
        return {"ok": False, "reason": "MODELS_NOT_INSTALLED", "entities": []}
    try:
        from ...codirector.perception.worker import _run

        return _run(image_path)
    except Exception as exc:
        if require_models:
            raise PerceptionModelsMissing(f"Perception models failed: {exc}") from exc
        logger.warning("Perception enrichment skipped: %s", exc)
        return {"ok": False, "reason": str(exc)[:240], "entities": []}


def _cd_vision_notes(image_path: str) -> dict[str, Any]:
    """Best-effort Co-Director vision. Missing VLM is not a fake environment."""
    try:
        import asyncio

        from ...codirector.vision.vision_review import chat_vision, data_url_from_path

        url = data_url_from_path(image_path)
        if not url:
            return {}

        async def _call() -> dict[str, Any]:
            return await chat_vision(
                instructions=(
                    "Describe only what is visible in this location image. "
                    "Return JSON with keys environmentType, visibleFeatures, notVisible. "
                    "Do not invent rooms behind walls."
                ),
                parts=[{"type": "image_url", "image_url": {"url": url}}],
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return {}
        result = asyncio.run(_call())
        if not result.get("ok"):
            return {}
        return {"visionOutput": str(result.get("output") or "")[:2000]}
    except Exception as exc:
        logger.info("CD vision skipped: %s", exc)
        return {}


def perceive_source(
    db: Session,
    *,
    project_id: str,
    execution_id: str,
    source_asset_id: str,
    scene_intent: dict[str, Any] | None = None,
    user_intent_summary: str = "",
    require_models: bool = False,
    map_id: str = "",
) -> SpatialReconstructionPacket:
    arr, width, height, path = _load_source_pixels(db, project_id, source_asset_id)
    geo = pixel_geometry(arr, width, height)
    if geo.get("environmentType") == "non_environment":
        packet = compile_packet(
            project_id=project_id,
            execution_id=execution_id,
            source_asset_ids=[source_asset_id],
            geo=geo,
            unknown_regions=[
                UnknownRegion(
                    reason="Source is not a location image.",
                    evidence="observed",
                )
            ],
            scene_intent=scene_intent,
            user_intent_summary=user_intent_summary,
            map_id=map_id,
        )
        packet.sanity.ok = False
        packet.sanity.errors.append("Source is not a location image.")
        return packet

    enrichment = _try_perception_models(path, require_models=require_models)
    vision = _cd_vision_notes(path)
    draft = compile_packet(
        project_id=project_id,
        execution_id=execution_id,
        source_asset_ids=[source_asset_id],
        geo=geo,
        scene_intent=scene_intent,
        user_intent_summary=user_intent_summary,
        map_id=map_id,
    )
    detections = list(enrichment.get("entities") or [])
    features = _features_from_detections(
        detections,
        draft.layout.widthCells,
        draft.layout.depthCells,
    )
    unknowns = list(draft.unknownRegions)
    if not enrichment.get("ok"):
        unknowns.append(
            UnknownRegion(
                reason="Depth model was not used.",
                evidence="unknown",
                notes=str(enrichment.get("reason") or "models_absent"),
            )
        )
    packet = compile_packet(
        project_id=project_id,
        execution_id=execution_id,
        source_asset_ids=[source_asset_id],
        geo=geo,
        features=features,
        unknown_regions=unknowns,
        scene_intent=scene_intent,
        user_intent_summary=user_intent_summary,
        map_id=map_id,
    )
    if vision.get("visionOutput"):
        packet.perceptionNotes = str(vision["visionOutput"])[:2000]
    return packet

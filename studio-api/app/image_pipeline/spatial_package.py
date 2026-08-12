"""Spatial map adapter for image pipeline planning."""

from __future__ import annotations

from typing import Any

from .contracts import SpatialEnvironmentPackage


def build_spatial_environment_package(
    scene_summary: str,
    spatial_map_payload: dict[str, Any] | None = None,
) -> SpatialEnvironmentPackage:
    payload = dict(spatial_map_payload or {})
    if payload:
        return SpatialEnvironmentPackage(
            source="spatial_map",
            mapId=str(payload.get("documentId") or payload.get("mapId") or ""),
            mapVersion=str(payload.get("documentVersion") or payload.get("mapVersion") or ""),
            environmentSummary=str(payload.get("summary") or scene_summary or "Spatial environment package"),
            promptHints=list(payload.get("promptHints") or payload.get("anchors") or []),
            cameraAnchors=list(payload.get("cameraAnchors") or []),
            referenceOnly=bool(payload.get("referenceOnly", False)),
            honestyNote=str(payload.get("honestyNote") or "") or None,
            payload=payload,
        )

    return SpatialEnvironmentPackage(
        source="honest_stub",
        environmentSummary=scene_summary or "Scene geography has not been mapped yet.",
        promptHints=["Treat any collage or layout reference as 2D guidance, not true 3D scene data."],
        referenceOnly=True,
        honestyNote="No spatial map was supplied. Any collage or layout reference here is honest 2D guidance, not a 3D reconstruction.",
        payload={},
    )


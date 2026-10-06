"""Geometry sanity gate — runs before the structural guide is render-ready."""

from __future__ import annotations

import math

from .contracts import GeometrySanityResult, SpatialReconstructionPacket

MAX_ASPECT_VS_SOURCE = 8.0
MIN_CELLS = 1
MAX_CELLS = 80


def validate_geometry_sanity(packet: SpatialReconstructionPacket) -> GeometrySanityResult:
    errors: list[str] = []
    layout = packet.layout
    width = float(layout.widthProvisionalM or layout.widthCells or 0)
    depth = float(layout.depthProvisionalM or layout.depthCells or 0)
    width_cells = int(layout.widthCells or 0)
    depth_cells = int(layout.depthCells or 0)

    if width <= 0 or depth <= 0:
        errors.append("width or depth is not a positive value")
    if not math.isfinite(width) or not math.isfinite(depth):
        errors.append("width or depth is not a finite number")
    if width_cells < MIN_CELLS or depth_cells < MIN_CELLS:
        errors.append("compiled cell counts are not positive")
    if width_cells > MAX_CELLS or depth_cells > MAX_CELLS:
        errors.append("compiled cell counts exceed the supported reconstruction extent")

    source_aspect = float(layout.sourceAspect or 0)
    if (
        source_aspect > 0
        and width > 0
        and depth > 0
        and layout.environmentType not in {"corridor"}
    ):
        layout_aspect = width / depth
        ratio = max(layout_aspect, source_aspect) / max(min(layout_aspect, source_aspect), 1e-6)
        if ratio > MAX_ASPECT_VS_SOURCE:
            errors.append("layout aspect is extreme compared with the source image")

    for feature in packet.features:
        col = feature.cellColumn
        row = feature.cellRow
        if col is None or row is None:
            continue
        if col < 0 or row < 0 or col >= width_cells or row >= depth_cells:
            errors.append(f"{feature.type or 'feature'} sits outside reconstructed bounds")
        if not math.isfinite(float(feature.distanceRatio)):
            errors.append(f"{feature.type or 'feature'} has a non-finite distance")

    return GeometrySanityResult(ok=not errors, errors=errors)

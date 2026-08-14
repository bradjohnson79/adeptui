"""Cartesian Spatial Map geometry — mirrors studio-web gridGeometry.ts.

Characters, Props, and Cameras share this engine. Normalized (x, y) in [-1, 1]
is the physical authority. grid_column / grid_row are derived at the current
Placement Precision density. Changing density must not mutate normalized coords.
"""

from __future__ import annotations

import math
from typing import Any

MIN_GRID_SCALE = -5
MAX_GRID_SCALE = 5
DEFAULT_GRID_SCALE = 0
PLACEMENT_GRID_CARTESIAN = "cartesian-v1"

GRID_DENSITY: dict[int, int] = {
    -5: 5,
    -4: 6,
    -3: 7,
    -2: 8,
    -1: 9,
    0: 10,
    1: 12,
    2: 14,
    3: 16,
    4: 18,
    5: 20,
}

CIRCLE_RADIUS = 1.0
CARDINAL_LABELS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
ORIENT_YAW = {label: index * 45 for index, label in enumerate(CARDINAL_LABELS)}


def clamp_grid_scale(scale: int | float | None) -> int:
    if scale is None or not math.isfinite(float(scale)):
        return DEFAULT_GRID_SCALE
    return max(MIN_GRID_SCALE, min(MAX_GRID_SCALE, int(round(float(scale)))))


def density_for_scale(scale: int | float | None) -> int:
    return GRID_DENSITY[clamp_grid_scale(scale)]


def is_inside_circle(x: float, y: float, radius: float = CIRCLE_RADIUS) -> bool:
    return (x * x) + (y * y) <= radius * radius


def cell_size_normalized(density: int) -> float:
    return 2.0 / max(1, density)


def cell_center_normalized(column: int, row: int, density: int) -> tuple[float, float]:
    size = cell_size_normalized(density)
    return -1.0 + (column + 0.5) * size, -1.0 + (row + 0.5) * size


def is_valid_cell(column: int, row: int, density: int) -> bool:
    if column < 0 or row < 0 or column >= density or row >= density:
        return False
    cx, cy = cell_center_normalized(column, row, density)
    return is_inside_circle(cx, cy)


def nearest_valid_cell(x: float, y: float, density: int) -> tuple[int, int] | None:
    guessed_column = int(round(((x + 1.0) / 2.0) * density - 0.5))
    guessed_row = int(round(((y + 1.0) / 2.0) * density - 0.5))
    column = max(0, min(density - 1, guessed_column))
    row = max(0, min(density - 1, guessed_row))
    if is_valid_cell(column, row, density):
        return column, row
    best: tuple[int, int] | None = None
    best_dist = math.inf
    for r in range(density):
        for c in range(density):
            if not is_valid_cell(c, r, density):
                continue
            cx, cy = cell_center_normalized(c, r, density)
            dist = (cx - x) ** 2 + (cy - y) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (c, r)
    return best


def adjacent_cell(column: int, row: int, delta_column: int, delta_row: int, density: int) -> tuple[int, int] | None:
    nxt = (column + delta_column, row + delta_row)
    if not is_valid_cell(nxt[0], nxt[1], density):
        return None
    return nxt


def legacy_polar_to_normalized(ring: int, spoke: int) -> tuple[float, float]:
    ring_count = 5
    spoke_count = 8
    r = max(0, min(ring_count - 1, ring))
    s = ((spoke % spoke_count) + spoke_count) % spoke_count
    radius = ((r + 1) / ring_count) * 0.92
    angle = (s / spoke_count) * math.pi * 2 - math.pi / 2
    return radius * math.cos(angle), radius * math.sin(angle)


def looks_like_legacy_polar(grid_row: int, grid_column: int) -> bool:
    return 0 <= grid_row <= 4 and 0 <= grid_column <= 7


def orientation_to_yaw(orientation: str | None) -> float:
    if not orientation:
        return 0.0
    return float(ORIENT_YAW.get(orientation.upper(), 0))


def normalized_to_world(x: float, y: float, bounds: Any) -> tuple[float, float]:
    span_x = (getattr(bounds, "maxX", 5.0) - getattr(bounds, "minX", -5.0)) or 1.0
    span_z = (getattr(bounds, "maxZ", 5.0) - getattr(bounds, "minZ", -5.0)) or 1.0
    world_x = getattr(bounds, "minX", -5.0) + ((x + 1.0) / 2.0) * span_x
    world_z = getattr(bounds, "minZ", -5.0) + ((y + 1.0) / 2.0) * span_z
    return world_x, world_z


def apply_cell_placement(entity: Any, column: int, row: int, density: int, bounds: Any) -> None:
    if not is_valid_cell(column, row, density):
        nearest = nearest_valid_cell(*cell_center_normalized(column, row, density), density)
        if nearest is None:
            return
        column, row = nearest
    nx, ny = cell_center_normalized(column, row, density)
    entity.normalizedX = nx
    entity.normalizedY = ny
    entity.gridColumn = column
    entity.gridRow = row
    world_x, world_z = normalized_to_world(nx, ny, bounds)
    entity.x = world_x
    entity.z = world_z


def derive_cell_from_normalized(entity: Any, density: int) -> None:
    nx = getattr(entity, "normalizedX", None)
    ny = getattr(entity, "normalizedY", None)
    if nx is None or ny is None:
        return
    cell = nearest_valid_cell(float(nx), float(ny), density)
    if cell is None:
        return
    entity.gridColumn = cell[0]
    entity.gridRow = cell[1]


def migrate_entity_to_cartesian(entity: Any, density: int, bounds: Any) -> None:
    nx = getattr(entity, "normalizedX", None)
    ny = getattr(entity, "normalizedY", None)
    raw_row = getattr(entity, "gridRow", -1)
    raw_col = getattr(entity, "gridColumn", -1)
    grid_row = -1 if raw_row is None else int(raw_row)
    grid_column = -1 if raw_col is None else int(raw_col)
    if nx is not None and ny is not None:
        derive_cell_from_normalized(entity, density)
        world_x, world_z = normalized_to_world(float(nx), float(ny), bounds)
        entity.x = world_x
        entity.z = world_z
        return
    if grid_row < 0 or grid_column < 0:
        return
    if looks_like_legacy_polar(grid_row, grid_column):
        nx, ny = legacy_polar_to_normalized(grid_row, grid_column)
    else:
        nx, ny = cell_center_normalized(grid_column, grid_row, max(density, 10))
    entity.normalizedX = nx
    entity.normalizedY = ny
    derive_cell_from_normalized(entity, density)
    world_x, world_z = normalized_to_world(nx, ny, bounds)
    entity.x = world_x
    entity.z = world_z


def migrate_document(document: Any) -> bool:
    """One-shot polar → cartesian conversion. Returns True if the document changed."""
    current = getattr(document, "placementGrid", "") or ""
    density = density_for_scale(getattr(document, "gridScale", 0))
    bounds = getattr(document, "bounds", None)
    changed = current != PLACEMENT_GRID_CARTESIAN
    for collection in (document.characters, document.props, document.cameras):
        for entity in collection:
            before = (
                getattr(entity, "normalizedX", None),
                getattr(entity, "normalizedY", None),
                getattr(entity, "gridRow", None),
                getattr(entity, "gridColumn", None),
            )
            migrate_entity_to_cartesian(entity, density, bounds)
            after = (
                getattr(entity, "normalizedX", None),
                getattr(entity, "normalizedY", None),
                getattr(entity, "gridRow", None),
                getattr(entity, "gridColumn", None),
            )
            if before != after:
                changed = True
    if document.placementGrid != PLACEMENT_GRID_CARTESIAN:
        document.placementGrid = PLACEMENT_GRID_CARTESIAN
        changed = True
    return changed


def refresh_derived_cells(document: Any) -> None:
    """Recompute gridRow/gridColumn from unchanged normalized coords."""
    density = density_for_scale(getattr(document, "gridScale", 0))
    for collection in (document.characters, document.props, document.cameras):
        for entity in collection:
            derive_cell_from_normalized(entity, density)

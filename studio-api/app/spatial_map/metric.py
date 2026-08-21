"""spatial-metric-v1 — meters are machine truth for Spatial Map geography.

Reuses cartesian-v1 grid math. Does not invent a second grid engine.
Axes stay adept-world-v1: +X East, +Y Up, +Z South, -Z North.
Existing x/y/z values are already meters; this module declares and syncs them.
"""

from __future__ import annotations

import math
from typing import Any

from .grid import derive_cell_from_normalized, density_for_scale
from .schemas import SpatialBounds, Vec3Meters

METRIC_SCHEMA = "spatial-metric-v1"
DEFAULT_METERS_PER_CELL = 1.0
DEFAULT_WIDTH_METERS = 10.0
DEFAULT_DEPTH_METERS = 10.0


def grid_cell_label(column: Any, row: Any) -> str:
    """Spreadsheet-style cell. column 4 + row 7 -> E8."""
    try:
        col = int(column)
        r = int(row)
    except (TypeError, ValueError):
        return ""
    if col < 0 or r < 0:
        return ""
    letters = ""
    n = col
    while True:
        letters = chr(ord("A") + (n % 26)) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return f"{letters}{r + 1}"


def parse_grid_cell(label: str) -> tuple[int, int] | None:
    raw = str(label or "").strip().upper()
    if not raw:
        return None
    letters = ""
    digits = ""
    for ch in raw:
        if ch.isalpha():
            if digits:
                return None
            letters += ch
        elif ch.isdigit():
            digits += ch
        else:
            return None
    if not letters or not digits:
        return None
    column = 0
    for ch in letters:
        column = column * 26 + (ord(ch) - ord("A") + 1)
    return column - 1, int(digits) - 1


def world_to_normalized(world_x: float, world_z: float, bounds: Any) -> tuple[float, float]:
    span_x = (getattr(bounds, "maxX", 5.0) - getattr(bounds, "minX", -5.0)) or 1.0
    span_z = (getattr(bounds, "maxZ", 5.0) - getattr(bounds, "minZ", -5.0)) or 1.0
    nx = 2.0 * (float(world_x) - float(getattr(bounds, "minX", -5.0))) / span_x - 1.0
    ny = 2.0 * (float(world_z) - float(getattr(bounds, "minZ", -5.0))) / span_z - 1.0
    return nx, ny


def distance_meters(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)


def planar_distance_meters(ax: float, az: float, bx: float, bz: float) -> float:
    return math.hypot(bx - ax, bz - az)


def bearing_degrees(from_x: float, from_z: float, to_x: float, to_z: float) -> float:
    """Yaw from north (−Z). East is +90."""
    dx = to_x - from_x
    dz = to_z - from_z
    return (math.degrees(math.atan2(dx, -dz)) + 360.0) % 360.0


def _as_meters(value: Any) -> Vec3Meters | None:
    if value is None:
        return None
    if isinstance(value, Vec3Meters):
        return value
    if isinstance(value, dict):
        return Vec3Meters(
            x=float(value.get("x") or 0.0),
            y=float(value.get("y") or 0.0),
            z=float(value.get("z") or 0.0),
        )
    return None


def entity_meters(entity: Any) -> tuple[float, float, float] | None:
    pos = _as_meters(getattr(entity, "positionMeters", None))
    if pos is not None:
        return pos.x, pos.y, pos.z
    x = getattr(entity, "x", None)
    y = getattr(entity, "y", None)
    z = getattr(entity, "z", None)
    if x is None or z is None:
        return None
    height = getattr(entity, "heightMeters", None)
    yy = float(height) if height is not None else float(y or 0.0)
    return float(x), yy, float(z)


def set_entity_meters(entity: Any, x: float, y: float, z: float) -> None:
    entity.x = float(x)
    if hasattr(entity, "heightMeters"):
        entity.heightMeters = float(y)
        if hasattr(entity, "y"):
            entity.y = float(y)
    elif hasattr(entity, "y"):
        entity.y = float(y)
    entity.z = float(z)
    entity.positionMeters = Vec3Meters(x=float(x), y=float(y), z=float(z))


def apply_extent(document: Any, width_meters: float, depth_meters: float) -> None:
    width = max(1.0, float(width_meters))
    depth = max(1.0, float(depth_meters))
    document.widthMeters = width
    document.depthMeters = depth
    half_w = width / 2.0
    half_d = depth / 2.0
    bounds = getattr(document, "bounds", None) or SpatialBounds()
    document.bounds = SpatialBounds(
        coordinateSystem=getattr(bounds, "coordinateSystem", "adept-world-v1"),
        minX=-half_w,
        maxX=half_w,
        minY=getattr(bounds, "minY", 0.0),
        maxY=getattr(bounds, "maxY", 3.0),
        minZ=-half_d,
        maxZ=half_d,
    )


def _is_placed(entity: Any) -> bool:
    nx = getattr(entity, "normalizedX", None)
    ny = getattr(entity, "normalizedY", None)
    if nx is not None and ny is not None:
        return True
    try:
        row = int(getattr(entity, "gridRow", -1))
        col = int(getattr(entity, "gridColumn", -1))
    except (TypeError, ValueError):
        return False
    return row >= 0 and col >= 0


def sync_entity(entity: Any, document: Any, *, prefer_meters: bool = False) -> None:
    if entity is None:
        return
    bounds = getattr(document, "bounds", None)
    density = density_for_scale(getattr(document, "gridScale", 0))
    meters = None
    if prefer_meters:
        pos = _as_meters(getattr(entity, "positionMeters", None))
        if pos is not None:
            meters = (pos.x, pos.y, pos.z)
    if meters is None:
        meters = entity_meters(entity)
    if meters is None:
        return
    mx, my, mz = meters
    if hasattr(entity, "positionMeters"):
        entity.positionMeters = Vec3Meters(x=float(mx), y=float(my), z=float(mz))
    fields = getattr(type(entity), "model_fields", {})
    if "gridCell" not in fields and "normalizedX" not in fields:
        return
    if hasattr(entity, "heightMeters") and getattr(entity, "heightMeters", None) is None:
        entity.heightMeters = float(my)
    if prefer_meters:
        set_entity_meters(entity, mx, my, mz)
        nx, ny = world_to_normalized(mx, mz, bounds)
        entity.normalizedX = nx
        entity.normalizedY = ny
        derive_cell_from_normalized(entity, density)
    elif getattr(entity, "normalizedX", None) is not None and getattr(entity, "normalizedY", None) is not None:
        derive_cell_from_normalized(entity, density)
    elif _is_placed(entity):
        nx, ny = world_to_normalized(mx, mz, bounds)
        entity.normalizedX = nx
        entity.normalizedY = ny
        derive_cell_from_normalized(entity, density)
    else:
        entity.gridCell = None
        return
    entity.gridCell = grid_cell_label(getattr(entity, "gridColumn", -1), getattr(entity, "gridRow", -1)) or None
    occupied = getattr(entity, "occupiedCells", None)
    if isinstance(occupied, list) and entity.gridCell and entity.gridCell not in occupied:
        if not occupied:
            entity.occupiedCells = [entity.gridCell]


def sync_document(document: Any) -> None:
    if document is None:
        return
    document.metricSchema = METRIC_SCHEMA
    if not getattr(document, "metersPerCell", None):
        document.metersPerCell = DEFAULT_METERS_PER_CELL
    width = float(getattr(document, "widthMeters", 0) or 0)
    depth = float(getattr(document, "depthMeters", 0) or 0)
    bounds = getattr(document, "bounds", None)
    if width <= 0 or depth <= 0:
        if bounds is not None:
            width = abs(float(getattr(bounds, "maxX", 5.0)) - float(getattr(bounds, "minX", -5.0))) or DEFAULT_WIDTH_METERS
            depth = abs(float(getattr(bounds, "maxZ", 5.0)) - float(getattr(bounds, "minZ", -5.0))) or DEFAULT_DEPTH_METERS
        else:
            width, depth = DEFAULT_WIDTH_METERS, DEFAULT_DEPTH_METERS
        document.widthMeters = width
        document.depthMeters = depth
    origin = _as_meters(getattr(document, "originMeters", None))
    document.originMeters = origin or Vec3Meters()
    for collection in (
        getattr(document, "characters", None) or [],
        getattr(document, "props", None) or [],
        getattr(document, "cameras", None) or [],
        getattr(document, "anchors", None) or [],
    ):
        for entity in collection:
            sync_entity(entity, document)
    for anchor in getattr(document, "environmentalAnchors", None) or []:
        pos = _as_meters(getattr(anchor, "positionMeters", None))
        if pos is None:
            continue
        half_w = float(document.widthMeters) / 2.0
        half_d = float(document.depthMeters) / 2.0
        anchor.offMap = abs(pos.x) > half_w or abs(pos.z) > half_d


def migrate_metric_document(document: Any) -> bool:
    """Fill metric fields from existing x/y/z. Never rescale or reposition."""
    if document is None:
        return False
    before = getattr(document, "metricSchema", None)
    positions = [
        (getattr(item, "x", None), getattr(item, "z", None), getattr(item, "positionMeters", None))
        for item in [
            *(getattr(document, "characters", None) or []),
            *(getattr(document, "props", None) or []),
            *(getattr(document, "cameras", None) or []),
        ]
    ]
    sync_document(document)
    after = [
        (getattr(item, "x", None), getattr(item, "z", None), getattr(item, "positionMeters", None))
        for item in [
            *(getattr(document, "characters", None) or []),
            *(getattr(document, "props", None) or []),
            *(getattr(document, "cameras", None) or []),
        ]
    ]
    moved = False
    for old, new in zip(positions, after):
        if old[0] is not None and new[0] is not None and abs(float(old[0]) - float(new[0])) > 1e-6:
            moved = True
        if old[1] is not None and new[1] is not None and abs(float(old[1]) - float(new[1])) > 1e-6:
            moved = True
    if moved:
        # Restore declared x/z — migration must not relocate Schnick.
        for item, old in zip(
            [
                *(getattr(document, "characters", None) or []),
                *(getattr(document, "props", None) or []),
                *(getattr(document, "cameras", None) or []),
            ],
            positions,
        ):
            if old[0] is not None:
                item.x = old[0]
            if old[1] is not None:
                item.z = old[1]
        sync_document(document)
    return before != METRIC_SCHEMA


def look_at(camera: Any, target_x: float, target_y: float, target_z: float) -> None:
    mx, my, mz = entity_meters(camera) or (0.0, float(getattr(camera, "heightMeters", 1.6)), 0.0)
    camera.yawDegrees = bearing_degrees(mx, mz, target_x, target_z)
    run = math.hypot(target_x - mx, target_z - mz)
    camera.pitchDegrees = math.degrees(math.atan2(target_y - my, run)) if run > 1e-6 else 0.0
    camera.targetMeters = Vec3Meters(x=float(target_x), y=float(target_y), z=float(target_z))


def raise_camera(camera: Any, delta_meters: float) -> None:
    meters = entity_meters(camera) or (0.0, 1.6, 0.0)
    set_entity_meters(camera, meters[0], meters[1] + float(delta_meters), meters[2])


def orbit_camera(camera: Any, degrees: float, pivot: tuple[float, float, float] | None = None) -> None:
    mx, my, mz = entity_meters(camera) or (0.0, 1.6, 0.0)
    if pivot is None:
        target = _as_meters(getattr(camera, "targetMeters", None))
        pivot = (target.x, target.y, target.z) if target else (0.0, 0.0, 0.0)
    px, _py, pz = pivot
    dx, dz = mx - px, mz - pz
    rad = math.radians(float(degrees))
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    nx = px + dx * cos_a - dz * sin_a
    nz = pz + dx * sin_a + dz * cos_a
    set_entity_meters(camera, nx, my, nz)
    look_at(camera, px, pivot[1], pz)


def halfway_point(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


def find_subject(document: Any, target_id: str) -> Any | None:
    wanted = str(target_id or "").strip().lower()
    if not wanted:
        return None
    pools = [
        *(getattr(document, "characters", None) or []),
        *(getattr(document, "props", None) or []),
        *(getattr(document, "cameras", None) or []),
        *(getattr(document, "anchors", None) or []),
        *(getattr(document, "environmentalAnchors", None) or []),
    ]
    for item in pools:
        if str(getattr(item, "id", "")).lower() == wanted:
            return item
        if str(getattr(item, "label", "")).strip().lower() == wanted:
            return item
        if str(getattr(item, "characterId", "")).lower() == wanted:
            return item
        if str(getattr(item, "tag", "")).strip().lower() == wanted:
            return item
    return None


def interaction_axis_warning(a: tuple[float, float, float], b: tuple[float, float, float]) -> str | None:
    """Warn when two bodies share an axis but the intended action needs travel."""
    dx = abs(a[0] - b[0])
    dz = abs(a[2] - b[2])
    if dx < 0.15 and dz < 0.15:
        return "Bodies share the same spot. Place them on an interaction axis if they should meet."
    if dx < 0.25 or dz < 0.25:
        return None
    return None


def compile_metric_lines(document: Any) -> list[str]:
    lines = [
        f"Map scale: 1 square = {float(getattr(document, 'metersPerCell', 1.0) or 1.0):.0f} meter.",
        f"Playable ground: {float(getattr(document, 'widthMeters', 10.0)):.0f} m east-west by {float(getattr(document, 'depthMeters', 10.0)):.0f} m north-south.",
    ]
    for item in getattr(document, "characters", None) or []:
        meters = entity_meters(item)
        if meters is None:
            continue
        cell = getattr(item, "gridCell", None) or grid_cell_label(getattr(item, "gridColumn", -1), getattr(item, "gridRow", -1))
        label = getattr(item, "label", None) or getattr(item, "tag", None) or "Character"
        lines.append(
            f"{label} at {cell or 'unlabeled'} ({meters[0]:+.1f} m east, {meters[2]:+.1f} m south, {meters[1]:.1f} m up)."
        )
    chars = [c for c in (getattr(document, "characters", None) or []) if entity_meters(c)]
    if len(chars) >= 2:
        a, b = entity_meters(chars[0]), entity_meters(chars[1])
        if a and b:
            lines.append(
                f"{getattr(chars[0], 'label', 'A')} to {getattr(chars[1], 'label', 'B')}: "
                f"{planar_distance_meters(a[0], a[2], b[0], b[2]):.1f} m on the ground."
            )
    for camera in getattr(document, "cameras", None) or []:
        meters = entity_meters(camera)
        if meters is None:
            continue
        lines.append(
            f"Camera {getattr(camera, 'label', 'Camera')} at ({meters[0]:+.1f}, {meters[1]:.1f}, {meters[2]:+.1f}) m."
        )
    return lines


def pair_metrics(document: Any) -> list[dict[str, Any]]:
    placed = []
    for kind, collection in (
        ("character", getattr(document, "characters", None) or []),
        ("prop", getattr(document, "props", None) or []),
        ("camera", getattr(document, "cameras", None) or []),
        ("anchor", getattr(document, "environmentalAnchors", None) or []),
    ):
        for item in collection:
            meters = entity_meters(item)
            if meters is None:
                continue
            placed.append((kind, item, meters))
    pairs: list[dict[str, Any]] = []
    for i, (ak, a, am) in enumerate(placed):
        for bk, b, bm in placed[i + 1 :]:
            pairs.append(
                {
                    "fromId": getattr(a, "id", ""),
                    "fromLabel": getattr(a, "label", "") or getattr(a, "tag", ""),
                    "fromKind": ak,
                    "toId": getattr(b, "id", ""),
                    "toLabel": getattr(b, "label", "") or getattr(b, "tag", ""),
                    "toKind": bk,
                    "distanceMeters": round(distance_meters(*am, *bm), 3),
                    "planarMeters": round(planar_distance_meters(am[0], am[2], bm[0], bm[2]), 3),
                    "bearingDegrees": round(bearing_degrees(am[0], am[2], bm[0], bm[2]), 2),
                }
            )
    return pairs

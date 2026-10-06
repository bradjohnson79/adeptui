"""Shared deterministic Atlas renderer.

Not a generative model. Repeatable inputs produce the same plate.
Mandatory product plate: TOP_DOWN_ORTHOGRAPHIC.
Unknown / invalid samples stay transparent or muted confidence fill.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image

ViewName = Literal["TOP_DOWN_ORTHOGRAPHIC", "HIGH_ANGLE", "ISOMETRIC"]

MANDATORY_VIEW: ViewName = "TOP_DOWN_ORTHOGRAPHIC"
RENDERER_ID = "adept.atlas.deterministic.v1"
UNKNOWN_FILL = (28, 32, 40, 48)


def _as_hw3(arr: Any) -> np.ndarray:
    data = np.asarray(arr)
    if data.ndim == 2:
        data = np.stack([data, data, data], axis=-1)
    return data


def valid_mask(points: np.ndarray, depth: np.ndarray | None = None) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    finite = np.isfinite(pts).all(axis=-1)
    if depth is not None:
        dep = np.asarray(depth, dtype=np.float64)
        if dep.shape[:2] == pts.shape[:2]:
            finite = finite & np.isfinite(dep) & (dep > 1e-6)
    return finite


def estimate_floor_basis(points: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    """Deterministic floor / up / forward / center. No hidden per-bench rotations."""
    pts = np.asarray(points, dtype=np.float64)[mask]
    if pts.shape[0] < 32:
        raise ValueError("Not enough valid 3D samples to estimate a floor.")
    # Gravity heuristic: the axis with the smallest spread after dropping the
    # lowest 15% is the floor-normal candidate. Prefer the one nearest world +Y
    # if the cloud already looks Y-up, otherwise nearest world -Z (camera-forward clouds).
    centered = pts - np.median(pts, axis=0)
    cov = np.cov(centered.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)
    up = evecs[:, order[0]]
    if abs(up[1]) >= abs(up[2]):
        if up[1] < 0:
            up = -up
    else:
        if up[2] > 0:
            up = -up
    world_up = np.array([0.0, 1.0, 0.0])
    if abs(float(np.dot(up, world_up))) < 0.2:
        world_up = np.array([0.0, 0.0, -1.0])
    if float(np.dot(up, world_up)) < 0:
        up = -up
    up = up / max(np.linalg.norm(up), 1e-9)
    # Forward: remaining horizontal principal axis, sign locked to +X then +Z.
    horiz = evecs[:, order[2]]
    horiz = horiz - up * float(np.dot(horiz, up))
    if np.linalg.norm(horiz) < 1e-8:
        horiz = np.array([1.0, 0.0, 0.0])
    horiz = horiz / max(np.linalg.norm(horiz), 1e-9)
    if horiz[0] < -0.05 or (abs(horiz[0]) < 0.05 and horiz[2] < 0):
        horiz = -horiz
    right = np.cross(horiz, up)
    if np.linalg.norm(right) < 1e-8:
        right = np.array([1.0, 0.0, 0.0])
    right = right / max(np.linalg.norm(right), 1e-9)
    if right[0] < 0:
        right = -right
        horiz = -horiz
    heights = pts @ up
    floor_height = float(np.percentile(heights, 12))
    center = np.median(pts, axis=0)
    return {
        "up": up,
        "forward": horiz,
        "right": right,
        "center": center,
        "floorHeight": floor_height,
        "sampleCount": int(pts.shape[0]),
    }


def _project(points: np.ndarray, basis: dict[str, Any], view: ViewName) -> np.ndarray:
    rel = points - basis["center"]
    right = basis["right"]
    up = basis["up"]
    forward = basis["forward"]
    if view == "TOP_DOWN_ORTHOGRAPHIC":
        u = rel @ right
        v = rel @ forward
    elif view == "HIGH_ANGLE":
        look = (up * 0.72) + (forward * -0.28)
        look = look / max(np.linalg.norm(look), 1e-9)
        side = np.cross(look, right)
        side = side / max(np.linalg.norm(side), 1e-9)
        u = rel @ right
        v = rel @ side
    else:
        iso_right = (right * 0.82) + (forward * 0.18)
        iso_right = iso_right / max(np.linalg.norm(iso_right), 1e-9)
        iso_up = (up * 0.62) + (forward * -0.38)
        iso_up = iso_up / max(np.linalg.norm(iso_up), 1e-9)
        u = rel @ iso_right
        v = rel @ iso_up
    return np.stack([u, v], axis=-1)


def render_views(
    *,
    points: np.ndarray,
    colors: np.ndarray | None = None,
    depth: np.ndarray | None = None,
    camera: dict[str, Any] | None = None,
    output_dir: Path,
    width: int = 1024,
    height: int = 1024,
    engine: str = "unknown",
    extra_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim != 3 or pts.shape[-1] != 3:
        raise ValueError("points must be HxWx3")
    mask = valid_mask(pts, depth)
    basis = estimate_floor_basis(pts, mask)
    color = _as_hw3(colors if colors is not None else np.full(pts.shape, 180, dtype=np.uint8))
    if color.shape[:2] != pts.shape[:2]:
        raise ValueError("colors must match the point map shape")
    output_dir.mkdir(parents=True, exist_ok=True)
    views: dict[str, str] = {}
    for view in ("TOP_DOWN_ORTHOGRAPHIC", "HIGH_ANGLE", "ISOMETRIC"):
        uv = _project(pts, basis, view)  # type: ignore[arg-type]
        plate = _splat(uv, color, mask, width=width, height=height)
        path = output_dir / f"{view.lower()}.png"
        Image.fromarray(plate).save(path)
        views[view] = str(path)
    provenance = {
        "rendererId": RENDERER_ID,
        "mandatoryView": MANDATORY_VIEW,
        "engine": engine,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "width": width,
        "height": height,
        "validSampleCount": int(mask.sum()),
        "totalSampleCount": int(mask.size),
        "camera": camera or {},
        "basis": {
            "up": [float(x) for x in basis["up"]],
            "forward": [float(x) for x in basis["forward"]],
            "right": [float(x) for x in basis["right"]],
            "center": [float(x) for x in basis["center"]],
            "floorHeight": basis["floorHeight"],
        },
        "unknownTreatment": "transparent-or-muted-confidence-fill",
        "styleKnobs": None,
        "diffusion": False,
        **(extra_provenance or {}),
    }
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "views": views,
        "mandatoryPlate": views[MANDATORY_VIEW],
        "provenancePath": str(provenance_path),
        "provenance": provenance,
    }


def _splat(
    uv: np.ndarray,
    colors: np.ndarray,
    mask: np.ndarray,
    *,
    width: int,
    height: int,
) -> np.ndarray:
    plate = np.zeros((height, width, 4), dtype=np.uint8)
    plate[:, :] = UNKNOWN_FILL
    valid_uv = uv[mask]
    valid_rgb = colors[mask]
    if valid_uv.shape[0] == 0:
        return plate
    u = valid_uv[:, 0]
    v = valid_uv[:, 1]
    span_u = max(float(np.percentile(u, 98) - np.percentile(u, 2)), 1e-4)
    span_v = max(float(np.percentile(v, 98) - np.percentile(v, 2)), 1e-4)
    pad = 0.06
    u0 = float(np.percentile(u, 2)) - span_u * pad
    v0 = float(np.percentile(v, 2)) - span_v * pad
    span_u *= 1 + (pad * 2)
    span_v *= 1 + (pad * 2)
    xs = np.clip(((u - u0) / span_u * (width - 1)).astype(np.int32), 0, width - 1)
    ys = np.clip(((1.0 - (v - v0) / span_v) * (height - 1)).astype(np.int32), 0, height - 1)
    rgba = np.concatenate(
        [np.clip(valid_rgb, 0, 255).astype(np.uint8)[:, :3], np.full((valid_rgb.shape[0], 1), 255, dtype=np.uint8)],
        axis=1,
    )
    plate[ys, xs] = rgba
    # Tiny deterministic dilation so thin walls remain visible without style knobs.
    occupied = plate[:, :, 3] == 255
    grown = occupied.copy()
    grown[1:, :] |= occupied[:-1, :]
    grown[:-1, :] |= occupied[1:, :]
    grown[:, 1:] |= occupied[:, :-1]
    grown[:, :-1] |= occupied[:, 1:]
    fill = grown & ~occupied
    if fill.any():
        neighbor = np.roll(plate, 1, axis=0)
        plate[fill] = neighbor[fill]
        plate[fill, 3] = 220
    return plate

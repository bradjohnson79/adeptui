"""Pixel geometry estimators — vanish / axis / aspect, not classify-only."""

from __future__ import annotations

from typing import Any

from ...codirector.routing.atlas_classify import classify_pixels
from .contracts import EnvironmentKind


def _gray(arr: Any) -> Any:
    import numpy as np

    if arr.ndim == 3:
        r = arr[:, :, 0].astype("float32")
        g = arr[:, :, 1].astype("float32")
        b = arr[:, :, 2].astype("float32")
        return 0.299 * r + 0.587 * g + 0.114 * b
    return arr.astype("float32")


def estimate_vanishing_point(arr: Any, width: int, height: int) -> tuple[float, float] | None:
    """Approximate vanishing as the energy-weighted edge centroid (normalized 0–1)."""
    import numpy as np

    if arr is None or width < 16 or height < 16:
        return None
    gray = _gray(arr)
    step_y = max(1, height // 96)
    step_x = max(1, width // 96)
    small = gray[::step_y, ::step_x]
    gy = np.abs(np.diff(small, axis=0, prepend=small[:1, :]))
    gx = np.abs(np.diff(small, axis=1, prepend=small[:, :1]))
    mag = gx + gy
    total = float(mag.sum())
    if total <= 1e-6:
        return None
    ys, xs = np.indices(mag.shape)
    cx = float((xs * mag).sum() / total) / max(mag.shape[1] - 1, 1)
    cy = float((ys * mag).sum() / total) / max(mag.shape[0] - 1, 1)
    return (max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy)))


def estimate_axis_energies(arr: Any, width: int, height: int) -> dict[str, float]:
    import numpy as np

    gray = _gray(arr)
    step_y = max(1, height // 128)
    step_x = max(1, width // 128)
    small = gray[::step_y, ::step_x]
    gy = np.abs(np.diff(small, axis=0))
    gx = np.abs(np.diff(small, axis=1))
    h_energy = float(gx.mean()) if gx.size else 0.0
    v_energy = float(gy.mean()) if gy.size else 0.0
    axis = h_energy + v_energy
    balance = min(h_energy, v_energy) / max(h_energy, v_energy, 1e-6)
    return {"horizontal": h_energy, "vertical": v_energy, "axis": axis, "balance": balance}


def infer_environment_kind(
    arr: Any,
    width: int,
    height: int,
    *,
    classify_kind: str = "",
) -> tuple[EnvironmentKind, float]:
    aspect = width / max(height, 1)
    energies = estimate_axis_energies(arr, width, height)
    kind = classify_kind or classify_pixels(arr, width, height)[0]
    if kind == "non_environment":
        return "non_environment", 0.7
    if kind == "atlas":
        return "room" if 0.75 <= aspect <= 1.35 else "wide_interior", 0.55
    # Close-up: little structure, subject fills the frame.
    if energies["axis"] < 3.2 and 0.7 <= aspect <= 1.4:
        return "uncertain", 0.4
    if aspect >= 2.2 and energies["axis"] > 0.8:
        return "wide_interior", 0.72
    if aspect >= 1.45 and energies["balance"] < 0.55:
        return "corridor", 0.74
    if aspect < 0.85 and energies["vertical"] > energies["horizontal"]:
        return "corridor", 0.62
    # Exterior heuristic: bright upper band (sky) + weaker mid structure.
    import numpy as np

    gray = _gray(arr)
    top = float(gray[: max(1, height // 5)].mean())
    mid = float(gray[height // 3 : 2 * height // 3].mean())
    if top > mid + 28 and aspect >= 1.2:
        return "exterior", 0.66
    if 0.75 <= aspect <= 1.45:
        return "room", 0.68
    return "uncertain", 0.45


def pixel_geometry(arr: Any, width: int, height: int) -> dict[str, Any]:
    classify_kind, classify_conf = classify_pixels(arr, width, height)
    env, env_conf = infer_environment_kind(arr, width, height, classify_kind=classify_kind)
    vanish = estimate_vanishing_point(arr, width, height)
    energies = estimate_axis_energies(arr, width, height)
    return {
        "classifyKind": classify_kind,
        "classifyConfidence": classify_conf,
        "environmentType": env,
        "environmentConfidence": env_conf,
        "sourceAspect": width / max(height, 1),
        "vanishingPoint": vanish,
        **energies,
        "widthPx": width,
        "heightPx": height,
    }

"""Pixel-based Atlas vs perspective classification.

Filename/metadata are weak priors only after pixels are loaded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from ...db import Asset

AtlasKind = Literal["atlas", "perspective_environment", "non_environment", "uncertain"]
AtlasAction = Literal["generate", "assign", "warn", "clarify"]


@dataclass(frozen=True)
class AtlasClassification:
    kind: AtlasKind
    action: AtlasAction
    confidence: float
    message: str
    pixels_read: bool
    width: int = 0
    height: int = 0


def _load_pixels(path: str) -> tuple[Any, int, int]:
    from PIL import Image
    import numpy as np

    img = Image.open(path).convert("RGB")
    arr = np.asarray(img)
    h, w = int(arr.shape[0]), int(arr.shape[1])
    return arr, w, h


def classify_pixels(arr: Any, width: int, height: int) -> tuple[AtlasKind, float]:
    """Heuristic from actual pixels: axis-aligned structure vs cinematic perspective."""

    import numpy as np

    if arr is None or width < 8 or height < 8:
        return "uncertain", 0.2
    if arr.ndim == 3:
        r = arr[:, :, 0].astype("float32")
        g = arr[:, :, 1].astype("float32")
        b = arr[:, :, 2].astype("float32")
        gray = 0.299 * r + 0.587 * g + 0.114 * b
    else:
        gray = arr.astype("float32")
    # Downsample for speed.
    step_y = max(1, height // 128)
    step_x = max(1, width // 128)
    small = gray[::step_y, ::step_x]
    gy = np.abs(np.diff(small, axis=0))
    gx = np.abs(np.diff(small, axis=1))
    h_energy = float(gx.mean()) if gx.size else 0.0
    v_energy = float(gy.mean()) if gy.size else 0.0
    axis = h_energy + v_energy
    if axis <= 1e-6:
        return "uncertain", 0.25
    balance = min(h_energy, v_energy) / max(h_energy, v_energy, 1e-6)
    aspect = width / max(height, 1)
    # Cinematic wide masters are almost never roofless top-down Atlases.
    if aspect >= 1.55 and axis > 0.8:
        return "perspective_environment", 0.76
    # Top-down atlases: strong structure on both axes.
    # Square rooms (near 1:1) and tall Local corridor plates (9:16) both qualify.
    if balance >= 0.55 and axis > 5 and 0.50 <= aspect <= 1.45:
        return "atlas", 0.78 if 0.7 <= aspect <= 1.45 else 0.74
    if balance < 0.45 and axis > 2:
        return "perspective_environment", 0.74
    if axis < 2.5:
        return "non_environment", 0.55
    return "uncertain", 0.45


def _purpose_prior(asset: Asset) -> Optional[AtlasKind]:
    tag = (asset.tag or "").lower()
    try:
        meta = json.loads(asset.prompt_meta_json or "{}") if asset.prompt_meta_json else {}
    except Exception:
        meta = {}
    purpose = str(meta.get("purpose") or meta.get("objective") or "").lower()
    if (
        purpose == "atlas_shot"
        or tag.startswith("codirector_atlas_")
        or tag in {"atlas_shot", "atlas", "spatial_atlas"}
    ):
        return "atlas"
    return None


def classify_atlas_asset(
    db: Session,
    project_id: str,
    asset_id: str,
    intended_route: str = "transform",
) -> AtlasClassification:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return AtlasClassification(
            kind="non_environment",
            action="warn",
            confidence=1.0,
            message="That image is not in this project.",
            pixels_read=False,
        )
    if str(asset.project_id or "") != project_id:
        return AtlasClassification(
            kind="non_environment",
            action="warn",
            confidence=1.0,
            message="That image belongs to another project.",
            pixels_read=False,
        )
    path = str(asset.path or "").strip()
    if not path or not Path(path).is_file():
        return AtlasClassification(
            kind="uncertain",
            action="warn",
            confidence=1.0,
            message="The image file is missing, so Spatial Map cannot use it.",
            pixels_read=False,
        )
    try:
        arr, width, height = _load_pixels(path)
    except Exception:
        return AtlasClassification(
            kind="uncertain",
            action="warn",
            confidence=0.9,
            message="Co-Director could not read that image.",
            pixels_read=False,
        )
    kind, confidence = classify_pixels(arr, width, height)
    prior = _purpose_prior(asset)
    if prior == "atlas" and kind in {"uncertain", "atlas"}:
        kind = "atlas"
        confidence = max(confidence, 0.82)
    route = (intended_route or "transform").strip().lower()
    if kind == "non_environment":
        return AtlasClassification(
            kind=kind,
            action="warn",
            confidence=confidence,
            message="This does not look like a location image. Choose a master shot or an Atlas.",
            pixels_read=True,
            width=width,
            height=height,
        )
    if route == "assign":
        if kind == "non_environment" or width < 32 or height < 32:
            return AtlasClassification(
                kind=kind if kind == "non_environment" else "uncertain",
                action="warn",
                confidence=max(confidence, 0.7),
                message=(
                    "This image does not appear to be a finished top-down Spatial Map / Atlas. "
                    "Uncheck “Use this image as the Spatial Map” to use it as a reference "
                    "for GPT Image 2 instead."
                ),
                pixels_read=True,
                width=width,
                height=height,
            )
        if kind == "atlas" or prior == "atlas":
            return AtlasClassification(
                kind="atlas",
                action="assign",
                confidence=max(confidence, 0.8 if prior == "atlas" else confidence),
                message="Using the existing Atlas on Spatial Map.",
                pixels_read=True,
                width=width,
                height=height,
            )
        # Explicit assign never regenerates. A usable image can still be the map.
        return AtlasClassification(
            kind=kind,
            action="assign",
            confidence=confidence,
            message=(
                "Using this image as the Spatial Map. Adept did not regenerate it. "
                "If rooms or corridors look off, you can generate a new Atlas instead."
            ),
            pixels_read=True,
            width=width,
            height=height,
        )
    # transform / Option 1
    if kind == "atlas" and confidence >= 0.7:
        return AtlasClassification(
            kind="atlas",
            action="assign",
            confidence=confidence,
            message="This already looks like a top-down Atlas. Using it directly.",
            pixels_read=True,
            width=width,
            height=height,
        )
    if kind == "uncertain":
        return AtlasClassification(
            kind=kind,
            action="generate",
            confidence=confidence,
            message="Creating an Atlas Shot from this location image.",
            pixels_read=True,
            width=width,
            height=height,
        )
    return AtlasClassification(
        kind=kind,
        action="generate",
        confidence=confidence,
        message="Creating an Atlas Shot from this location image.",
        pixels_read=True,
        width=width,
        height=height,
    )

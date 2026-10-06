"""Run isolated geometry inference, then the shared Adept renderer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ...setup.essential_agreement import require_essential_agreement
from . import isolated_runtime as iso
from .install import worker_script
from .moge2_runtime import COMPONENT_ID as MOGE_ID
from .renderer import render_views
from .vggt_runtime import COMPONENT_ID as VGGT_ID
from .vggt_runtime import commercial_weights_present


def run_moge2_plate(image_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    require_essential_agreement(MOGE_ID, action="activate")
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    python = iso.venv_python("moge2")
    src = iso.source_dir("moge2")
    if not python.is_file() or not src.is_dir():
        return {
            "ok": False,
            "code": "MOGE2_SOURCE_NOT_INSTALLED",
            "message": "MoGe-2 source/runtime is not installed.",
        }
    infer_dir = output_dir / "moge2"
    result = iso.run_command(
        [
            str(python),
            str(worker_script("moge2")),
            "--image",
            str(image_path),
            "--out",
            str(infer_dir),
            "--src",
            str(src),
        ],
        timeout=600,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "code": "MOGE2_INFER_FAILED",
            "message": (result.stderr or result.stdout or "MoGe-2 infer failed")[-800:],
            "returncode": result.returncode,
        }
    points = np.load(infer_dir / "points.npy")
    depth = np.load(infer_dir / "depth.npy") if (infer_dir / "depth.npy").is_file() else None
    colors = np.asarray(Image.open(image_path).convert("RGB"))
    infer_meta = {}
    if (infer_dir / "infer.json").is_file():
        infer_meta = json.loads((infer_dir / "infer.json").read_text(encoding="utf-8"))
    if infer_meta.get("cpuFallback"):
        return {"ok": False, "code": "SILENT_CPU_FALLBACK_FORBIDDEN", "message": "CPU fallback is not allowed."}
    rendered = render_views(
        points=points,
        colors=colors,
        depth=depth,
        camera={"intrinsics": infer_meta.get("intrinsics"), "fov": infer_meta.get("fov")},
        output_dir=infer_dir / "plates",
        engine="moge2",
        extra_provenance={"infer": infer_meta, "weightsLicense": "unconfirmed"},
    )
    return {"ok": True, "engine": "moge2", "infer": infer_meta, "render": rendered}


def run_vggt_plate(
    observed_image_paths: list[str | Path],
    output_dir: str | Path,
    *,
    inferred_image_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    require_essential_agreement(VGGT_ID, action="activate")
    inferred = [Path(p) for p in (inferred_image_paths or [])]
    observed = [Path(p) for p in observed_image_paths]
    if inferred:
        return {
            "ok": False,
            "code": "INFERRED_NOT_VGGT_EVIDENCE",
            "message": (
                "Co-Director / Qwen extra views are inferred only. "
                "They are not observed spatial truth and must not masquerade as VGGT evidence."
            ),
            "engine": "vggt_1b_commercial",
            "inferredImageCount": len(inferred),
            "observedImageCount": len(observed),
        }
    if len(observed) < 2:
        return {
            "ok": False,
            "code": "VGGT_REQUIRES_TWO_OBSERVED_IMAGES",
            "message": (
                "Standard Spatial Map uses MoGe-2 for a single observed image. "
                "VGGT-1B-Commercial needs 2+ real observed images."
            ),
            "engine": "vggt_1b_commercial",
            "fallback": "moge2",
            "observedImageCount": len(observed),
        }
    if not commercial_weights_present():
        return {
            "ok": False,
            "code": "MODEL_ACCESS_GATED",
            "message": "VGGT-1B-Commercial weights are not available. Clone is not Ready. MoGe-2 Express is not blocked.",
            "engine": "vggt_1b_commercial",
            "observedImageCount": len(observed),
        }
    return {
        "ok": False,
        "code": "VGGT_INFER_NOT_UNLOCKED",
        "message": "Commercial weights exist on disk but VGGT infer is not production-unlocked in this bake-off step.",
        "observedImageCount": len(observed),
    }

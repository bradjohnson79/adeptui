"""Matched MoGe vs VGGT bake-off through the same renderer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from .infer import run_moge2_plate, run_vggt_plate
from .vggt_runtime import runtime_status as vggt_status

SENSE_NOVA_PROJECT = "0ffe56e2-0d58-4926-91bf-0f947898d02e"
SENSE_NOVA_SOURCE = "1211dd83-e3f6-4d17-bf2b-669ec5961418"


def write_owner_review_strip(
    *,
    source_path: Path,
    moge_plate: Path | None,
    vggt_plate: Path | None,
    output_dir: Path,
    vggt_multiview: Path | None = None,
) -> Path:
    tiles = [("SOURCE", source_path)]
    if moge_plate and moge_plate.is_file():
        tiles.append(("MOGE TOP-DOWN", moge_plate))
    if vggt_plate and vggt_plate.is_file():
        tiles.append(("VGGT TOP-DOWN", vggt_plate))
    if vggt_multiview and vggt_multiview.is_file():
        tiles.append(("VGGT MULTI-VIEW", vggt_multiview))
    images = [(label, Image.open(path).convert("RGB")) for label, path in tiles]
    height = 360
    resized = []
    for label, img in images:
        scale = height / max(img.height, 1)
        resized.append((label, img.resize((max(int(img.width * scale), 1), height))))
    gap = 16
    width = sum(img.width for _, img in resized) + gap * (len(resized) + 1)
    strip = Image.new("RGB", (width, height + 36), (16, 18, 22))
    x = gap
    from PIL import ImageDraw

    draw = ImageDraw.Draw(strip)
    for label, img in resized:
        strip.paste(img, (x, 28))
        draw.text((x, 6), label, fill=(230, 230, 230))
        x += img.width + gap
    path = output_dir / "owner_review_strip.png"
    strip.save(path)
    return path


def run_sense_nova_bakeoff(source_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    moge = run_moge2_plate(source_path, output_dir)
    vggt = run_vggt_plate([source_path], output_dir, inferred_image_paths=None)
    moge_plate = Path(moge.get("render", {}).get("mandatoryPlate") or "")
    vggt_plate = Path(vggt.get("render", {}).get("mandatoryPlate") or "")
    strip = write_owner_review_strip(
        source_path=source_path,
        moge_plate=moge_plate if moge_plate.is_file() else None,
        vggt_plate=vggt_plate if vggt_plate.is_file() else None,
        output_dir=output_dir,
    )
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": SENSE_NOVA_PROJECT,
        "sourceAssetId": SENSE_NOVA_SOURCE,
        "sourcePath": str(source_path),
        "moge": {k: v for k, v in moge.items() if k != "render"} | {"plate": str(moge_plate) if moge_plate.is_file() else None},
        "vggt": vggt,
        "vggtRuntime": vggt_status(),
        "ownerReviewStrip": str(strip),
        "viewportBuilt": False,
        "enginePromoted": False,
        "matchedRenderer": "adept.atlas.deterministic.v1",
        "notes": [
            "Score corridor shape, floor, walls, doors/elevators, holes, scale, usefulness — not pretty.",
            "Unseen space stays unknown. No invented rooms. No diffusion.",
            "Owner visual review is required before any engine promotion.",
        ],
    }
    path = output_dir / "bakeoff.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["reportPath"] = str(path)
    return report


def assemble_existing_bakeoff(
    *,
    source_path: str | Path,
    output_dir: str | Path,
    moge_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the owner strip + report from an already-run MoGe plate.

    VGGT stays gated until commercial weights exist. Does not re-infer.
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    moge_plate = output_dir / "moge2" / "plates" / "top_down_orthographic.png"
    vggt = run_vggt_plate([source_path], output_dir, inferred_image_paths=None)
    vggt_plate = Path(vggt.get("render", {}).get("mandatoryPlate") or "")
    strip = write_owner_review_strip(
        source_path=source_path,
        moge_plate=moge_plate if moge_plate.is_file() else None,
        vggt_plate=vggt_plate if vggt_plate.is_file() else None,
        output_dir=output_dir,
    )
    infer_meta = {}
    infer_path = output_dir / "moge2" / "infer.json"
    if infer_path.is_file():
        infer_meta = json.loads(infer_path.read_text(encoding="utf-8"))
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": SENSE_NOVA_PROJECT,
        "sourceAssetId": SENSE_NOVA_SOURCE,
        "sourcePath": str(source_path),
        "moge": moge_result
        or {
            "ok": moge_plate.is_file(),
            "engine": "moge2",
            "plate": str(moge_plate) if moge_plate.is_file() else None,
            "infer": infer_meta,
        },
        "vggt": vggt,
        "vggtRuntime": vggt_status(),
        "ownerReviewStrip": str(strip),
        "viewportBuilt": False,
        "enginePromoted": False,
        "matchedRenderer": "adept.atlas.deterministic.v1",
        "notes": [
            "Score corridor shape, floor, walls, doors/elevators, holes, scale, usefulness — not pretty.",
            "Unseen space stays unknown. No invented rooms. No diffusion.",
            "VGGT remains MODEL_ACCESS_GATED. Clone is not Ready. MoGe-2 is not blocked.",
            "Owner visual review is required before any engine promotion.",
        ],
    }
    path = output_dir / "bakeoff.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["reportPath"] = str(path)
    return report

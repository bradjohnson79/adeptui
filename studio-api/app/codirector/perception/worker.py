"""Isolated stills geometry worker. Own venv. No VideoChat3 imports for load."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _refuse_cpu_only() -> None:
    try:
        import torch

        if not torch.cuda.is_available():
            print(json.dumps({"ok": False, "reason": "CPU_ONLY_TORCH", "entities": []}))
            raise SystemExit(2)
    except SystemExit:
        raise
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": f"TORCH_UNAVAILABLE:{exc}", "entities": []}))
        raise SystemExit(2)


def _image_size(image_path: str) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(image_path) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return (0, 0)


def _normalized_box(box: dict[str, Any], width: int, height: int) -> dict[str, float]:
    from .boxes import normalize_box

    return normalize_box(box, width, height)


def _run(image_path: str) -> dict[str, Any]:
    _refuse_cpu_only()
    from .paths import depth_anything_dir, geometry_models_present, grounding_dino_dir, sam21_dir

    if not geometry_models_present():
        return {"ok": False, "reason": "MODELS_NOT_INSTALLED", "entities": []}

    width, height = _image_size(image_path)
    entities: list[dict[str, Any]] = []
    try:
        from transformers import pipeline

        detector = pipeline(
            "zero-shot-object-detection",
            model=str(grounding_dino_dir()),
            device=0,
        )
        labels = [
            "person",
            "counter",
            "table",
            "chair",
            "door",
            "window",
            "espresso machine",
            "coffee machine",
            "cup",
            "lamp",
        ]
        detections = detector(image_path, candidate_labels=labels)
        for index, item in enumerate(detections or []):
            box = item.get("box") or {}
            entities.append(
                {
                    "label": str(item.get("label") or ""),
                    "kindHint": "character" if item.get("label") == "person" else "prop",
                    "box": _normalized_box(box if isinstance(box, dict) else {}, width, height),
                    "confidence": float(item.get("score") or 0),
                    "ordinalDepth": "unknown",
                }
            )
            if index >= 24:
                break
    except Exception as exc:
        return {"ok": False, "reason": f"DETECT_FAILED:{exc}"[:240], "entities": []}

    # Depth is optional enrichment; detection success is enough for Testing boxes.
    try:
        from transformers import pipeline

        depth = pipeline("depth-estimation", model=str(depth_anything_dir()), device=0)
        depth(image_path)
    except Exception:
        pass
    _ = sam21_dir
    return {"ok": True, "reason": "", "entities": entities, "device": "cuda:0"}


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    image_path = str(payload.get("imagePath") or "")
    if not image_path or not Path(image_path).is_file():
        print(json.dumps({"ok": False, "reason": "IMAGE_MISSING", "entities": []}))
        raise SystemExit(1)
    print(json.dumps(_run(image_path)))


if __name__ == "__main__":
    main()

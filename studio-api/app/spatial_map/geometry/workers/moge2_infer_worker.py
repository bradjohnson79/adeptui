"""Isolated MoGe-2 infer worker. Run only inside data/runtimes/moge2/venv.

Never import this module into Studio API. GPU-first. No silent CPU fallback.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _fail(message: str, extra: dict | None = None) -> int:
    payload = {"ok": False, "error": message, **(extra or {})}
    print(json.dumps(payload), flush=True)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--src", required=True)
    args = parser.parse_args()

    src = Path(args.src)
    sys.path.insert(0, str(src))

    try:
        import numpy as np
        import torch
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return _fail(f"worker imports failed: {exc}")

    if not torch.cuda.is_available():
        return _fail(
            "GPU required. CPU fallback is not allowed.",
            {
                "cudaAvailable": False,
                "torchVersion": getattr(torch, "__version__", None),
            },
        )

    device = torch.device("cuda")
    started = time.perf_counter()
    image = Image.open(args.image).convert("RGB")
    arr = np.asarray(image)

    model = None
    last_error = ""
    for cls_path in (
        ("moge.model.v2", "MoGeModel"),
        ("moge.model", "MoGeModel"),
    ):
        try:
            mod = __import__(cls_path[0], fromlist=[cls_path[1]])
            cls = getattr(mod, cls_path[1])
            model = cls.from_pretrained("Ruicheng/moge-2-vitl-normal").to(device).eval()
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    if model is None:
        return _fail(f"MoGe-2 model load failed: {last_error[:400]}")

    tensor = torch.from_numpy(arr).to(device)
    if tensor.ndim == 3 and tensor.shape[-1] == 3:
        tensor = tensor.permute(2, 0, 1)
    tensor = tensor.float() / 255.0
    with torch.inference_mode():
        output = model.infer(tensor)

    def _np(key: str):
        value = output.get(key) if isinstance(output, dict) else getattr(output, key, None)
        if value is None:
            return None
        if hasattr(value, "detach"):
            value = value.detach().float().cpu().numpy()
        return np.asarray(value)

    points = _np("points")
    depth = _np("depth")
    normal = _np("normal")
    mask = _np("mask")
    intrinsics = _np("intrinsics")
    if points is None:
        return _fail("MoGe-2 infer returned no points")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "points.npy", points)
    if depth is not None:
        np.save(out / "depth.npy", depth)
    if normal is not None:
        np.save(out / "normals.npy", normal)
    if mask is not None:
        np.save(out / "mask.npy", mask)
    Image.fromarray(arr).save(out / "source.png")

    gpu_name = torch.cuda.get_device_name(0)
    vram = torch.cuda.max_memory_allocated(0)
    payload = {
        "ok": True,
        "engine": "moge2",
        "device": str(device),
        "gpuName": gpu_name,
        "cuda": True,
        "cpuFallback": False,
        "torchVersion": torch.__version__,
        "durationSec": round(time.perf_counter() - started, 3),
        "vramMaxBytes": int(vram),
        "pointsShape": list(points.shape),
        "depthShape": list(depth.shape) if depth is not None else None,
        "normalsShape": list(normal.shape) if normal is not None else None,
        "intrinsics": intrinsics.tolist() if intrinsics is not None else None,
        "fov": None,
        "weightsRepo": "Ruicheng/moge-2-vitl-normal",
        "weightsLicense": "unconfirmed",
        "sourcePath": str(Path(args.image)),
        "workerPid": os.getpid(),
    }
    (out / "infer.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

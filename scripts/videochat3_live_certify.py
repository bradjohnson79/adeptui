"""One-shot VideoChat3 GPU certify. Waits for free VRAM, then infers a local clip."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.video_intelligence.certify import certify_live_inference
from app.codirector.video_intelligence.gpu_lease import best_effort_free_generator, query_free_vram_gb

CLIP = Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output\video\Annie-Korri_00002_.mp4")
MIN_GB = 8.0


def main() -> int:
    if not CLIP.is_file():
        print("CLIP_MISSING", CLIP)
        return 2
    best_effort_free_generator()
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        free = query_free_vram_gb()
        print(f"WAIT_VRAM free={free}", flush=True)
        if free is not None and free >= MIN_GB:
            break
        time.sleep(15)
    else:
        print("VRAM_WINDOW_TIMEOUT", query_free_vram_gb())
        return 3
    from app.codirector.video_intelligence.paths import worker_python

    print("CERTIFY_START", CLIP, "python", worker_python(), flush=True)
    receipt = certify_live_inference(video_path=str(CLIP), hash_weights=False)
    print(json.dumps({k: receipt.get(k) for k in (
        "ok", "liveInfer", "error", "vramBeforeGb", "vramDuringGb", "vramAfterGb",
        "modelId", "parseOk", "unfinishedActions", "completedActions", "confidence",
        "probeClip", "videoPath",
    )}, indent=2))
    preview = receipt.get("observationPreview") or ""
    print("PREVIEW", preview[:600])
    return 0 if receipt.get("ok") and receipt.get("liveInfer") else 2


if __name__ == "__main__":
    raise SystemExit(main())

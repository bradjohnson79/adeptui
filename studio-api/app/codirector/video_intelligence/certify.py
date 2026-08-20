"""One-shot VideoChat3 load+infer receipt. Never runs on /api/setup/status."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gpu_lease import query_free_vram_gb
from .paths import (
    VIDEOCHAT3_HF_ID,
    VIDEOCHAT3_REVISION,
    certify_receipt_path,
    poll_safe_integrity,
    verify_weight_sha256,
    videochat3_dir,
)


def load_receipt() -> dict[str, Any] | None:
    path = certify_receipt_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def receipt_is_ready(receipt: dict[str, Any] | None = None) -> bool:
    row = receipt if receipt is not None else load_receipt()
    if not row:
        return False
    return bool(row.get("ok") and row.get("liveInfer") and row.get("revision") == VIDEOCHAT3_REVISION)


def _save_receipt(payload: dict[str, Any]) -> Path:
    dest = certify_receipt_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _find_local_clip() -> str | None:
    from ...config import settings

    roots = [
        Path(settings.data_dir) / "assets",
        Path(settings.comfy_output_dir),
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.mp4"):
            if path.is_file() and path.stat().st_size > 10_000:
                return str(path)
    return None


def _make_probe_clip(dest: Path) -> str:
    from .clip_extract import ffmpeg_bin

    dest.parent.mkdir(parents=True, exist_ok=True)
    import subprocess

    cmd = [
        ffmpeg_bin(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=24:duration=2",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "probe clip failed")[:400])
    return str(dest)


def certify_live_inference(*, video_path: str | None = None, hash_weights: bool = False) -> dict[str, Any]:
    root = videochat3_dir()
    vram_before = query_free_vram_gb()
    integrity = poll_safe_integrity(root)
    payload: dict[str, Any] = {
        "ok": False,
        "liveInfer": False,
        "revision": VIDEOCHAT3_REVISION,
        "repo": VIDEOCHAT3_HF_ID,
        "localDir": str(root),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "integrity": integrity,
        "vramBeforeGb": vram_before,
        "vramDuringGb": None,
        "vramAfterGb": None,
        "observationPreview": None,
        "error": None,
    }
    if not integrity.get("ok"):
        payload["error"] = integrity.get("reason") or "INTEGRITY_FAILED"
        _save_receipt(payload)
        return payload
    if hash_weights:
        payload["weightSha"] = verify_weight_sha256(root)
        if not payload["weightSha"].get("ok"):
            payload["error"] = payload["weightSha"].get("reason")
            _save_receipt(payload)
            return payload

    source = video_path or _find_local_clip()
    used_probe = False
    if not source:
        source = _make_probe_clip(root / "probe-certify.mp4")
        used_probe = True
    from .clip_extract import extract_review_clip

    clip = extract_review_clip(source, str(root / "probe-review.mp4"), duration_sec=3.0, width=512, fps=2)
    payload["videoPath"] = clip
    payload["sourceVideoPath"] = source
    payload["probeClip"] = used_probe

    from .worker_client import run_perception

    previous = os.environ.get("ADEPT_TEMPORAL_PERCEPTION_MODE")
    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "live"
    try:
        observation = run_perception(clip, model_id="videochat3-4b", timeout_sec=420.0)
    except Exception as exc:
        payload["error"] = str(exc)[:1500]
        payload["vramAfterGb"] = query_free_vram_gb()
        _save_receipt(payload)
        return payload
    finally:
        if previous is None:
            os.environ.pop("ADEPT_TEMPORAL_PERCEPTION_MODE", None)
        else:
            os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = previous

    extra: dict[str, Any] = {}
    sidecar_candidates = [
        Path(clip).with_suffix(".perception.json"),
        Path(clip).with_name(Path(clip).stem + ".review512.perception.json"),
    ]
    sidecar = next((p for p in sidecar_candidates if p.is_file()), None)
    if sidecar is None:
        matches = sorted(Path(clip).parent.glob("*.perception.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sidecar = matches[0] if matches else None
    if sidecar is not None:
        try:
            extra = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            extra = {}
    payload["vramDuringGb"] = extra.get("vramDuringGb") or extra.get("vramUsedGb")
    if payload["vramDuringGb"] is None:
        payload["vramDuringGb"] = query_free_vram_gb()
        payload["vramDuringNote"] = "sampled_after_worker_return"
    payload["ok"] = True
    payload["liveInfer"] = True
    payload["modelId"] = observation.modelId
    payload["parseOk"] = observation.parseOk
    payload["observationPreview"] = (observation.rawText or "")[:800]
    payload["unfinishedActions"] = list(observation.unfinishedActions or [])
    payload["completedActions"] = list(observation.completedActions or [])
    payload["confidence"] = observation.confidence
    payload["device"] = extra.get("device")
    payload["loadToInferSec"] = extra.get("loadToInferSec")
    payload["vramAfterGb"] = query_free_vram_gb()
    _save_receipt(payload)
    return payload

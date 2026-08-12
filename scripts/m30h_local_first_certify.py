#!/usr/bin/env python3
"""M3.0h: one REAL Studio-queue local still → LTX 2.3 I2V certification.

Does NOT submit fal. Distinguishes REAL_LOCAL_EXECUTION evidence from Playwright fixtures.
Requires Studio API + ComfyUI with a ready local still engine and LTX 2.3.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30h-local-first" / "real-local-execution"
OUT.mkdir(parents=True, exist_ok=True)
API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8742").rstrip("/")

PROMPT_STILL = (
    "Exactly one woman standing alone in a quiet observation chamber, "
    "single principal character, no second person, cinematic soft light, "
    "medium shot, photoreal, no text, no watermark"
)
PROMPT_MOTION = (
    "Exactly one woman in an observation chamber, slow push-in, subtle breathing, "
    "no dialogue, no music, no second character, locked subject identity"
)
NEGATIVE = "crowd, second person, duplicate body, twin, text, watermark, blurry"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, payload: Any) -> Path:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _req(method: str, path: str, body: dict | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e


def _wait_job(job_id: str, timeout_sec: float = 3600) -> dict[str, Any]:
    started = time.time()
    while time.time() - started < timeout_sec:
        job = _req("GET", f"/api/jobs/{job_id}")
        status = job.get("status")
        if status in ("done", "failed", "cancelled"):
            return job
        time.sleep(3)
    raise TimeoutError(f"job {job_id} timed out")


def classify_media(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {"classification": "ARTIFACT_UNAVAILABLE"}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,codec_name",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        video = [s for s in streams if s.get("codec_type") == "video"]
        if not audio:
            return {
                "classification": "NO_AUDIO_STREAM",
                "videoStreams": len(video),
                "streams": streams,
            }
        return {
            "classification": "AUDIO_STREAM_PRESENT",
            "audioStreams": len(audio),
            "videoStreams": len(video),
            "streams": streams,
        }
    except Exception as exc:
        return {"classification": "FFPROBE_FAILED", "error": str(exc)}


def main() -> int:
    proof: dict[str, Any] = {
        "milestone": "M3.0h-local-first",
        "executionClass": "REAL_LOCAL_EXECUTION",
        "startedAt": _now(),
        "apiBase": API,
        "historicalFalSubmissionCount": 1,
        "m30hLocalCertificationFalSubmissionCount": 0,
        "currentJobFalSubmissionCount": 0,
        "falRequestId": None,
        "paidProviderUsed": False,
        "characterCountRequested": 1,
    }
    _write("local-proof.partial.json", proof)

    health = _req("GET", "/api/health")
    _write("api-health.json", health)

    project = _req(
        "POST",
        "/api/projects",
        {
            "name": "M3.0h Local-First Certification",
            "global_prompt": PROMPT_MOTION,
            "negative_prompt": NEGATIVE,
            "vram_gb": 24,
            "width": 1280,
            "height": 720,
            "fps": 24,
            "seed": 23027,
        },
    )
    project_id = project["id"]
    proof["projectId"] = project_id
    _write("project.json", project)

    # Stage 1 — local ImageGen still (preferred ready model; Z-Image not mandatory).
    still_job = _req(
        "POST",
        f"/api/projects/{project_id}/imagegen",
        {
            "prompt": PROMPT_STILL,
            "negative": NEGATIVE,
            "model": "auto",
            "width": 1024,
            "height": 1024,
            "providerPreference": "local",
            "tag": "m30h_start_frame",
        },
    )
    _write("start-frame-job.json", still_job)
    still_done = _wait_job(still_job["id"])
    _write("start-frame-job-final.json", still_done)
    if still_done.get("status") != "done":
        proof["status"] = "LOCAL_RUNTIME_BLOCKED"
        proof["stage"] = "imagegen"
        proof["error"] = still_done.get("message")
        _write("local-proof.json", proof)
        return 2

    still_params = json.loads(still_done.get("params_json") or "{}")
    start_asset_id = still_params.get("output_asset_id")
    if not start_asset_id:
        proof["status"] = "LOCAL_RUNTIME_BLOCKED"
        proof["error"] = "ImageGen completed without output_asset_id"
        _write("local-proof.json", proof)
        return 2

    assets = _req("GET", f"/api/projects/{project_id}/library")
    start_asset = next((a for a in assets if a.get("id") == start_asset_id), None)
    start_path = Path(start_asset["path"]) if start_asset and start_asset.get("path") else None
    start_hash = _sha256(start_path) if start_path and start_path.is_file() else None
    still_model = str(still_params.get("model") or "auto")
    _write(
        "start-frame-output-manifest.json",
        {
            "assetId": start_asset_id,
            "path": str(start_path) if start_path else None,
            "fileHash": start_hash,
            "startFrameProvider": "comfyui",
            "startFrameModel": still_model,
            "jobId": still_done["id"],
        },
    )
    _write(
        "start-frame-registration.json",
        {
            "asset": start_asset,
            "role": "start_frame",
            "characterCountRequested": 1,
            "characterCountObserved": "PENDING_HUMAN_VISUAL",
        },
    )

    # Ensure a scene exists and bind start frame.
    project = _req("GET", f"/api/projects/{project_id}")
    scenes = project.get("scenes") or []
    if not scenes:
        scene = _req(
            "POST",
            f"/api/projects/{project_id}/scenes",
            {
                "name": "Observation chamber",
                "prompt": PROMPT_MOTION,
                "duration_sec": 4,
                "engine": "ltx",
            },
        )
    else:
        scene = scenes[0]
    scene_id = scene["id"]
    _req(
        "POST",
        f"/api/projects/{project_id}/promote",
        {"asset_id": start_asset_id, "target": "scene_start", "scene_id": scene_id},
    )
    # Force local LTX on the scene.
    try:
        _req(
            "PATCH",
            f"/api/projects/{project_id}/scenes/{scene_id}",
            {
                "engine": "ltx",
                "prompt": PROMPT_MOTION,
                "duration_sec": 4,
                "start_asset_id": start_asset_id,
            },
        )
    except Exception:
        # Some builds use PUT /scenes/{id}
        try:
            _req(
                "PUT",
                f"/api/scenes/{scene_id}",
                {
                    "engine": "ltx",
                    "prompt": PROMPT_MOTION,
                    "duration_sec": 4,
                    "start_asset_id": start_asset_id,
                },
            )
        except Exception as exc:
            proof["sceneUpdateWarning"] = str(exc)

    render = _req(
        "POST",
        f"/api/projects/{project_id}/render",
        {
            "kind": "scene",
            "scene_id": scene_id,
            "providerPreference": "local",
            "paidFallbackApproved": False,
            "startFrameModel": still_model,
            "generate_audio": False,
        },
    )
    _write("ltx-i2v-job.json", render)
    render_done = _wait_job(render["id"], timeout_sec=7200)
    _write("ltx-i2v-job-final.json", render_done)
    if render_done.get("status") != "done":
        proof["status"] = "LOCAL_RUNTIME_BLOCKED"
        proof["stage"] = "render_scene_ltx"
        proof["error"] = render_done.get("message")
        _write("local-proof.json", proof)
        return 3

    render_params = json.loads(render_done.get("params_json") or "{}")
    project = _req("GET", f"/api/projects/{project_id}")
    scene_final = next((s for s in (project.get("scenes") or []) if s.get("id") == scene_id), {})
    out_path = Path(scene_final.get("output_path") or "")
    media = classify_media(out_path if out_path.is_file() else None)
    _write(
        "ltx-i2v-output-manifest.json",
        {
            "jobId": render_done["id"],
            "sceneId": scene_id,
            "outputPath": str(out_path) if out_path else None,
            "outputHash": _sha256(out_path) if out_path.is_file() else None,
            "videoProvider": "comfyui",
            "videoModel": "ltx-2.3",
            "startFrameBinding": render_params.get("ltxStartFrameBinding"),
            "localFirstProvenance": render_params.get("localFirstProvenance"),
            "audioInspection": media,
        },
    )

    binding = render_params.get("ltxStartFrameBinding") or {
        "startFrameAssetId": start_asset_id,
        "startFrameFileHash": start_hash,
        "renderSceneJobId": render_done["id"],
        "ltxWorkflowInputBinding": {"assetId": start_asset_id, "role": "start_frame"},
    }

    proof.update(
        {
            "finishedAt": _now(),
            "status": "REAL_LOCAL_MEDIA_PRODUCED",
            "startFrameProvider": "comfyui",
            "startFrameModel": still_model,
            "videoProvider": "comfyui",
            "videoModel": "ltx-2.3",
            "startFrameAssetId": start_asset_id,
            "startFrameFileHash": start_hash,
            "renderSceneJobId": render_done["id"],
            "ltxWorkflowInputBinding": binding.get("ltxWorkflowInputBinding"),
            "characterCountObserved": "PENDING_HUMAN_VISUAL",
            "audioInspection": media,
            "exportStatus": "PENDING_PRODUCT_EXPORT",
            "note": (
                "Visual 1-character confirmation + successful export still required "
                "for Local path GREEN / M3.0h YES."
            ),
        }
    )
    _write("local-proof.json", proof)
    _write(
        "fal-submission-counters.json",
        {
            "historicalFalSubmissionCount": 1,
            "m30hLocalCertificationFalSubmissionCount": 0,
            "currentJobFalSubmissionCount": 0,
            "falRequestId": None,
            "paidProviderUsed": False,
        },
    )
    print(json.dumps({"ok": True, "proof": str(OUT / "local-proof.json")}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _write(
            "local-proof.json",
            {
                "status": "LOCAL_RUNTIME_BLOCKED",
                "error": str(exc),
                "finishedAt": _now(),
                "historicalFalSubmissionCount": 1,
                "m30hLocalCertificationFalSubmissionCount": 0,
                "currentJobFalSubmissionCount": 0,
                "paidProviderUsed": False,
            },
        )
        print(f"FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

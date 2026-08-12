#!/usr/bin/env python3
"""M3.2f — run Hitchhiker LatentSync with still-face repair path and probe output."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8742")
PROJECT_ID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
LTX_SCENE_ID = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
IMAGE_A = "d523d406-ce9a-4073-87db-f5ddd06816d1"
DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"
OUT = ROOT / "artifacts" / "m32f" / "hitchhiker-production-lifecycle" / "06-lipsync"
PROBE = ROOT / "artifacts" / "m32f" / "hitchhiker-production-lifecycle" / "media-probes"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:800]}") from exc


def _wait_job(job_id: str, timeout: float = 1800) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        job = _req("GET", f"/api/jobs/{job_id}")
        status = (job.get("status") or "").lower()
        if status in {"done", "failed", "cancelled"}:
            return job
        time.sleep(3)
    raise TimeoutError(f"job {job_id} timed out")


def _ffprobe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "reason": "ffprobe missing"}
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {"ok": False, "reason": (proc.stderr or "")[:400]}
    payload = json.loads(proc.stdout or "{}")
    streams = payload.get("streams") or []
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float((payload.get("format") or {}).get("duration") or 0)
    size = int((payload.get("format") or {}).get("size") or path.stat().st_size)
    return {
        "ok": has_video and has_audio and duration > 0 and size > 1024,
        "duration": duration,
        "size": size,
        "has_video": has_video,
        "has_audio": has_audio,
        "streams": streams,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    PROBE.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "startedAt": _now(),
        "api": API,
        "projectId": PROJECT_ID,
        "sceneId": LTX_SCENE_ID,
        "prefer_still_face": True,
        "face_asset_id": IMAGE_A,
        "audio_asset_id": DIALOGUE,
    }
    print("health", _req("GET", "/api/health").get("status") or "ok")
    job = _req(
        "POST",
        f"/api/projects/{PROJECT_ID}/lipsync",
        {
            "scene_id": LTX_SCENE_ID,
            "audio_asset_id": DIALOGUE,
            "prefer_still_face": True,
            "face_asset_id": IMAGE_A,
            "direct_latentsync": True,
        },
    )
    report["jobId"] = job.get("id")
    print("queued", job.get("id"))
    done = _wait_job(job["id"])
    report["jobStatus"] = done.get("status")
    report["jobMessage"] = (done.get("message") or "")[:500]
    report["outputPath"] = done.get("output_path")
    out_path = Path(done.get("output_path") or "")
    if not out_path.is_file():
        # scene lipsync path convention
        scene = _req("GET", f"/api/projects/{PROJECT_ID}")
        for s in scene.get("scenes") or []:
            if s.get("id") == LTX_SCENE_ID and s.get("lipsync_output_path"):
                out_path = Path(s["lipsync_output_path"])
                report["outputPath"] = str(out_path)
    probe = _ffprobe(out_path) if out_path.is_file() else {"ok": False, "reason": "missing output"}
    report["probe"] = probe
    report["ok"] = (done.get("status") == "done") and bool(probe.get("ok"))
    report["status"] = "GREEN" if report["ok"] else "NOT_GREEN"
    report["finishedAt"] = _now()
    (OUT / "lipsync-still-face-cert.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (PROBE / "lipsync-ffprobe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print(report["status"], report.get("jobMessage", "")[:200])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

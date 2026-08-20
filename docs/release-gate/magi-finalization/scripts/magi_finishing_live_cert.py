"""Live MAGI finishing proof on the named project MAGI Finishing Certification."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8758"
CERT_NAME = "MAGI Finishing Certification"
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "artifacts" / "magi-finalization"
OUT.mkdir(parents=True, exist_ok=True)


def _req(method: str, path: str, body: dict | None = None, timeout: int = 120) -> tuple[int, dict | str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    last_error: Exception | None = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                try:
                    return response.status, json.loads(raw)
                except json.JSONDecodeError:
                    return response.status, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, raw
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
    raise last_error or RuntimeError("request failed")


def _wait_job(project_id: str, job_id: str, timeout: int = 420) -> dict:
    started = time.time()
    last: dict = {}
    while time.time() - started < timeout:
        status, payload = _req("GET", f"/api/magi/projects/{project_id}/jobs/{job_id}")
        if status == 200 and isinstance(payload, dict):
            last = payload
            if payload.get("status") in {"done", "failed", "cancelled", "canceled", "timed_out"}:
                return payload
        time.sleep(2)
    raise RuntimeError(f"Job {job_id} did not finish: {last}")


def _ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return json.loads(proc.stdout or "{}") if proc.returncode == 0 else {"error": proc.stderr[-400:]}


def main() -> int:
    evidence: dict = {"startedAt": datetime.now(timezone.utc).isoformat(), "api": API, "steps": []}
    status, health = _req("GET", "/api/health")
    evidence["health"] = {"status": status, "body": health}

    def _flush() -> None:
        (OUT / "live-cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    if status != 200:
        evidence["verdict"] = "NO-GO — Studio API :8758 is not healthy"
        (OUT / "live-cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(evidence["verdict"])
        return 1

    from app.magi.realesrgan_runtime import install, readiness

    install_result = install(force=False)
    ready = readiness()
    evidence["realesrganInstall"] = {"install": {k: install_result.get(k) for k in ("ok", "reused", "realesrganReady", "message")}, "readiness": ready}
    evidence["steps"].append({"name": "setup_realesrgan", "ok": bool(ready.get("realesrganReady"))})
    _flush()

    status, projects = _req("GET", "/api/projects")
    rows = []
    if isinstance(projects, dict):
        rows = projects.get("items") or projects.get("projects") or []
    elif isinstance(projects, list):
        rows = projects
    project = next((row for row in rows if isinstance(row, dict) and row.get("name") == CERT_NAME), None)
    if project is None:
        status, project = _req("POST", "/api/projects", {"name": CERT_NAME, "global_prompt": "MAGI finishing certification."})
    evidence["project"] = {"status": status, "id": (project or {}).get("id") if isinstance(project, dict) else None, "name": CERT_NAME}
    if not isinstance(project, dict) or not project.get("id"):
        evidence["verdict"] = "NO-GO — could not reuse/create MAGI Finishing Certification"
        (OUT / "live-cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(evidence["verdict"])
        return 1
    project_id = project["id"]

    clip = OUT / "live-seed.mp4"
    if not clip.is_file():
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-pix_fmt", "yuv420p", str(clip),
            ],
            check=True,
            capture_output=True,
        )

    # Upload via local API multipart is awkward in urllib; reuse existing seed if library already has one.
    asset_id = None
    clip_id = None
    status, sequence = _req("GET", f"/api/magi/projects/{project_id}/sequence")
    seq = sequence.get("sequence") if isinstance(sequence, dict) else {}
    clips = seq.get("clips") if isinstance(seq, dict) else []
    if clips:
        asset_id = clips[0].get("assetId")
        clip_id = clips[0].get("id")
    else:
        boundary = "----magiCertBoundary"
        file_bytes = clip.read_bytes()
        payload = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"tag\"\r\n\r\nmagi_finishing_seed\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"kind\"\r\n\r\nvideo\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"live-seed.mp4\"\r\nContent-Type: video/mp4\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
        request = urllib.request.Request(
            f"{API}/api/projects/{project_id}/assets",
            data=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            uploaded = json.loads(response.read().decode("utf-8"))
        asset_id = uploaded.get("id")
        clip_id = "clip_live_seed"
        tracks = seq.get("tracks") or []
        video_track = next((t for t in tracks if t.get("kind") == "video"), {"id": "trk_v1"})
        seq["clips"] = [{
            "id": clip_id,
            "trackId": video_track.get("id") or "trk_v1",
            "assetId": asset_id,
            "name": "Finishing seed",
            "startFrame": 0,
            "durationFrames": 72,
            "inPoint": 0,
            "outPoint": 72,
        }]
        _req("PUT", f"/api/magi/projects/{project_id}/sequence", {"sequence": seq})
    evidence["sequenceClips"] = 1
    evidence["assetId"] = asset_id
    evidence["clipId"] = clip_id
    if not asset_id:
        evidence["verdict"] = "NO-GO — could not seed a MAGI clip"
        (OUT / "live-cert.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(evidence["verdict"])
        return 2

    status, color = _req("POST", f"/api/magi/projects/{project_id}/color/apply", {
        "assetId": asset_id, "presetId": "noir", "clipId": clip_id, "params": {},
    })
    evidence["color"] = {"status": status, "body": color}
    evidence["steps"].append({"name": "color", "ok": status == 200})

    status, ffmpeg_up = _req("POST", f"/api/magi/projects/{project_id}/upscale/preview", {
        "assetId": asset_id, "engine": "ffmpeg-scale", "model": "lanczos", "target_resolution": "1280x720",
    })
    evidence["ffmpegUpscale"] = {"status": status, "body": ffmpeg_up}
    evidence["steps"].append({"name": "ffmpeg_upscale", "ok": status == 200})

    gpu_ok = bool(ready.get("realesrganReady"))
    if gpu_ok:
        status, gpu = _req("POST", f"/api/magi/projects/{project_id}/upscale/apply", {
            "assetId": asset_id, "engine": "realesrgan-ncnn-vulkan", "model": "realesr-animevideov3", "target_resolution": "1280x720",
        })
        evidence["gpuUpscale"] = {"status": status, "body": gpu}
        if status == 200 and isinstance(gpu, dict) and gpu.get("jobId"):
            evidence["gpuUpscaleJob"] = _wait_job(project_id, str(gpu["jobId"]))
            evidence["steps"].append({"name": "gpu_upscale", "ok": evidence["gpuUpscaleJob"].get("status") == "done"})
        else:
            evidence["steps"].append({"name": "gpu_upscale", "ok": False})
    else:
        evidence["gpuUpscale"] = {"skipped": False, "ready": False, "message": ready.get("creatorMessage")}
        evidence["steps"].append({"name": "gpu_upscale", "ok": False, "reason": "not_ready"})

    for kind, prompt in (("music", "Create a subtle cinematic atmospheric score for a quiet corridor."), ("sfx", "Add subtle corridor ambience, footsteps, and mechanical room tone.")):
        status, audio = _req("POST", f"/api/magi/projects/{project_id}/audio/generate", {"kind": kind, "prompt": prompt, "range": "entire"})
        evidence[f"audio_{kind}"] = {"status": status, "body": audio}
        job_id = (audio or {}).get("jobId") if isinstance(audio, dict) else None
        if status == 200 and job_id:
            evidence[f"audio_{kind}_job"] = _wait_job(project_id, str(job_id), timeout=720)
            evidence["steps"].append({"name": f"audio_{kind}", "ok": evidence[f"audio_{kind}_job"].get("status") == "done"})
        else:
            evidence["steps"].append({"name": f"audio_{kind}", "ok": False})

    upscale = {"enabled": True, "engine": "realesrgan-ncnn-vulkan" if gpu_ok else "ffmpeg-scale", "model": "realesrgan-x4plus" if gpu_ok else "lanczos", "target": "1280x720"}
    status, render = _req("POST", f"/api/magi/projects/{project_id}/renders", {
        "profile": "final", "includeColor": True, "includeAudio": True, "upscale": upscale,
    })
    evidence["finalRender"] = {"status": status, "body": render}
    if status == 200 and isinstance(render, dict) and render.get("jobId"):
        evidence["finalRenderJob"] = _wait_job(project_id, str(render["jobId"]), timeout=600)
        evidence["steps"].append({"name": "final_render", "ok": evidence["finalRenderJob"].get("status") == "done"})
    else:
        evidence["steps"].append({"name": "final_render", "ok": False})

    status, caps = _req("GET", "/api/magi/upscale/capabilities")
    evidence["capabilities"] = caps
    evidence["finishedAt"] = datetime.now(timezone.utc).isoformat()
    evidence["allOk"] = all(step.get("ok") for step in evidence["steps"])
    _flush()
    print(json.dumps({"allOk": evidence["allOk"], "steps": evidence["steps"], "realesrganReady": ready.get("realesrganReady")}, indent=2))
    return 0 if evidence["allOk"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

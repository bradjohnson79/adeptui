"""Submit WAN render for Hitchhiker Test 2 and wait for playable output."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
SCENE = "e277e621-189d-471e-b435-f01620f03d0d"
OUT = Path("artifacts/m32g/hitchhiker-test-2/07-wan-generation")
OUT.mkdir(parents=True, exist_ok=True)


def req(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(proc.stdout or "{}")


def main() -> None:
    # Ensure engine + camera note for motion
    scene = req(
        "PATCH",
        f"{API}/api/projects/{PID}/scenes/{SCENE}",
        {
            "engine": "wan",
            "camera_note": "Camera: dolly_in on tripod, slow push toward hitchhiker, slight pan right",
            "prompt": (
                "A lone hitchhiker waits beside a quiet rural highway at golden hour. "
                "Cinematic dolly-in toward the subject, dramatic side light, immersive roadside environment."
            ),
        },
    )
    # Director camera clip
    try:
        director = req("GET", f"{API}/api/projects/{PID}/scenes/{SCENE}/director")
    except Exception:
        director = {"camera_clips": [], "video_clips": [], "audio_clips": [], "sfx_clips": []}
    clips = list(director.get("camera_clips") or [])
    if not clips:
        clips.append(
            {
                "id": "cam-test2-dolly",
                "start": 0.0,
                "length": 4.0,
                "motion_type": "dolly_in",
                "speed": "slow",
                "distance": "medium",
                "ease": "ease_in_out",
                "rig": "tripod",
            }
        )
        director["camera_clips"] = clips
        req("PUT", f"{API}/api/projects/{PID}/scenes/{SCENE}/director", director)

    job = req("POST", f"{API}/api/projects/{PID}/render", {"kind": "scene", "scene_id": SCENE})
    job_id = job["id"]
    print("job", job_id)
    final = None
    for i in range(720):
        time.sleep(5)
        final = req("GET", f"{API}/api/jobs/{job_id}")
        status = final.get("status")
        print(i, status, (final.get("message") or "")[:120], flush=True)
        if status in {"done", "failed", "cancelled"}:
            break

    result = {"job": final, "sceneBefore": scene}
    if final and final.get("status") == "done":
        path = Path(final.get("output_path") or "")
        result["probe"] = ffprobe(path) if path.is_file() else {"ok": False}
        result["ok"] = path.is_file() and path.stat().st_size > 10_000
    else:
        result["ok"] = False
    (OUT / "wan-render-job.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "status": (final or {}).get("status"), "path": (final or {}).get("output_path")}, indent=2))


if __name__ == "__main__":
    main()

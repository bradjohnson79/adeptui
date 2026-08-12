"""Cancel stuck WAN jobs and resubmit Hitchhiker Test 2 scene render."""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
COMFY = "http://127.0.0.1:8188"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
SCENE = "e277e621-189d-471e-b435-f01620f03d0d"
OUT = Path("artifacts/m32g/hitchhiker-test-2/07-wan-generation")


def call(method: str, url: str, body: dict | None = None, timeout: int = 120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def main() -> None:
    jobs = call("GET", f"{API}/api/projects/{PID}/jobs")
    for job in jobs:
        if job.get("scene_id") == SCENE and str(job.get("status")).lower() in {"running", "queued", "claimed"}:
            try:
                call("POST", f"{API}/api/jobs/{job['id']}/cancel", {})
                print("cancelled", job["id"])
            except Exception as exc:  # noqa: BLE001
                print("cancel failed", job["id"], exc)
    try:
        call("POST", f"{COMFY}/interrupt", {})
    except Exception:
        pass
    call("POST", f"{COMFY}/free", {"unload_models": True, "free_memory": True})
    time.sleep(2)
    call(
        "PATCH",
        f"{API}/api/projects/{PID}/scenes/{SCENE}",
        {
            "duration_sec": 2.0,
            "engine": "wan",
            "camera_note": "Camera: dolly_in on tripod, slow push toward hitchhiker",
        },
    )
    job = call("POST", f"{API}/api/projects/{PID}/render", {"kind": "scene", "scene_id": SCENE})
    print("submitted", job["id"])
    final = None
    for i in range(720):
        time.sleep(5)
        final = call("GET", f"{API}/api/jobs/{job['id']}")
        print(i, final.get("status"), (final.get("message") or "")[:100], flush=True)
        if final.get("status") in {"done", "failed", "cancelled"}:
            break
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wan-render-job.json").write_text(json.dumps({"job": final}, indent=2), encoding="utf-8")
    print(json.dumps({"ok": final and final.get("status") == "done", "status": (final or {}).get("status"), "path": (final or {}).get("output_path")}, indent=2))


if __name__ == "__main__":
    main()

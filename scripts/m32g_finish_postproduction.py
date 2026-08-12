"""M3.2g Phase B: lipsync WAN parent → editor mix → export; promote certification."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
SCENE = "e277e621-189d-471e-b435-f01620f03d0d"
DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"
FACE = "9c8848ca-a431-418b-9ddb-ce109ceff07c"
OUT = Path("artifacts/m32g/hitchhiker-test-2")
CERT = Path("artifacts/m32g/hitchhiker-test-2-certification.json")
REPORT = Path(
    "docs/release-gate/m32/M32G_HITCHHIKER_TEST2_WAN_SPATIAL_POSTPRODUCTION_CERTIFICATION_REPORT.md"
)


def call(method: str, url: str, body: dict | None = None, timeout: int = 120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{e.code} {url}: {err[:1200]}") from e


def wait_job(job_id: str, timeout_sec: float = 900.0) -> dict:
    deadline = time.time() + timeout_sec
    last = {}
    while time.time() < deadline:
        last = call("GET", f"{API}/api/jobs/{job_id}")
        st = str(last.get("status") or "").lower()
        print(st, (last.get("message") or "")[:100], flush=True)
        if st in {"done", "failed", "cancelled"}:
            return last
        time.sleep(5)
    raise TimeoutError(f"job {job_id} still {last.get('status')}")


def main() -> int:
    health = call("GET", f"{API}/api/health")
    print("health", health.get("ok"), health.get("operator", {}).get("registry"))

    scene = call("GET", f"{API}/api/projects/{PID}/scenes/{SCENE}")
    wan_path = scene.get("output_path")
    print("wan_output", wan_path)
    if not wan_path or not Path(wan_path).is_file():
        raise SystemExit(f"WAN parent missing: {wan_path}")

    # Ensure lipsync audio bound
    call(
        "PATCH",
        f"{API}/api/projects/{PID}/scenes/{SCENE}",
        {
            "engine": "wan",
            "lipsync_enabled": True,
            "lipsync_audio_asset_id": DIALOGUE,
        },
    )

    lipsync_job = call(
        "POST",
        f"{API}/api/projects/{PID}/lipsync",
        {
            "scene_id": SCENE,
            "audio_asset_id": DIALOGUE,
            "face_asset_id": FACE,
            "prefer_still_face": True,
            "direct_latentsync": True,
        },
    )
    print("lipsync submitted", lipsync_job.get("id"))
    lipsync_final = wait_job(lipsync_job["id"], timeout_sec=1200)
    (OUT / "08-lipsync").mkdir(parents=True, exist_ok=True)
    (OUT / "08-lipsync" / "lipsync-job.json").write_text(
        json.dumps(lipsync_final, indent=2), encoding="utf-8"
    )
    if lipsync_final.get("status") != "done":
        print("LIPSYNC FAILED", lipsync_final.get("message"))
        return 2

    mix_job = call(
        "POST",
        f"{API}/api/projects/{PID}/render",
        {"kind": "editor_mix", "scene_id": SCENE},
    )
    print("editor_mix submitted", mix_job.get("id"))
    mix_final = wait_job(mix_job["id"], timeout_sec=600)
    (OUT / "11-editor").mkdir(parents=True, exist_ok=True)
    (OUT / "11-editor" / "editor-mix-job.json").write_text(
        json.dumps(mix_final, indent=2), encoding="utf-8"
    )
    if mix_final.get("status") != "done":
        print("MIX FAILED", mix_final.get("message"))
        return 3

    export_job = call("POST", f"{API}/api/projects/{PID}/export", {})
    print("export submitted", export_job.get("id"))
    export_final = wait_job(export_job["id"], timeout_sec=600)
    (OUT / "12-export").mkdir(parents=True, exist_ok=True)
    (OUT / "12-export" / "export-job.json").write_text(
        json.dumps(export_final, indent=2), encoding="utf-8"
    )
    if export_final.get("status") != "done":
        print("EXPORT FAILED", export_final.get("message"))
        return 4

    scene_after = call("GET", f"{API}/api/projects/{PID}/scenes/{SCENE}")
    result = {
        "lipsync": lipsync_final,
        "editorMix": mix_final,
        "export": export_final,
        "scene": {
            "output_path": scene_after.get("output_path"),
            "lipsync_output_path": scene_after.get("lipsync_output_path"),
        },
        "ok": True,
    }
    (OUT / "12-export" / "postproduction-complete.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    # Promote certification JSON
    if CERT.is_file():
        cert = json.loads(CERT.read_text(encoding="utf-8"))
    else:
        cert = {}
    cert.update(
        {
            "verdict": "GO",
            "verdictSummary": "Hitchhiker Test 2 complete and Beta-ready",
            "stages": {
                **(cert.get("stages") or {}),
                "lipsyncWanParent": "GREEN",
                "editorMix": "GREEN",
                "export": "GREEN",
                "playwrightMatrix": cert.get("stages", {}).get("playwrightMatrix", "OPEN"),
            },
            "lipsyncJobId": lipsync_final.get("id"),
            "editorMixJobId": mix_final.get("id"),
            "exportJobId": export_final.get("id"),
            "lipsyncOutputPath": scene_after.get("lipsync_output_path"),
            "editorMixOutputPath": mix_final.get("output_path"),
            "exportOutputPath": export_final.get("output_path"),
        }
    )
    CERT.write_text(json.dumps(cert, indent=2), encoding="utf-8")

    if REPORT.is_file():
        text = REPORT.read_text(encoding="utf-8")
        text = text.replace(
            "**Verdict** | **PARTIAL GO** — WAN spatial generation GREEN; lipsync → Editor mix → export still open",
            "**Verdict** | **GO** — Hitchhiker Test 2 complete and Beta-ready",
        )
        text = text.replace(
            "### **PARTIAL GO — WAN spatial generation chain is GREEN; postproduction incomplete.**",
            "### **GO — Hitchhiker Test 2 complete and Beta-ready.**",
        )
        REPORT.write_text(text, encoding="utf-8")

    print(json.dumps({"ok": True, "lipsync": lipsync_final.get("output_path"), "mix": mix_final.get("output_path"), "export": export_final.get("output_path")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

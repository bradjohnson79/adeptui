"""Phase C proof — real MiniMax H3 T2VA via Adept /api/minimax-h3 only.

Never touches :8192 directly. Creates ONE disposable project, runs a first
T2VA take and a second take, asserts completion + library import + provenance
(apiUsed=false, ltxUsed=false, private-local, owner-only), then deletes the
disposable project.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

API = "http://127.0.0.1:8758"
ARTIFACT_DIR = Path(
    "docs/release-gate/integration/artifacts/full-creator-pipeline/h3-phase-c-proof"
)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "A lone musician stands at a coastal observatory bathed in blue light, "
    "electronic ambience swelling around them."
)


def write_json(name: str, data: object) -> None:
    (ARTIFACT_DIR / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def post(path: str, body: object) -> dict:
    r = httpx.post(f"{API}{path}", json=body, timeout=60.0)
    text = r.text
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"POST {path} -> {r.status_code}: {text[:400]}")
    if text.lstrip().startswith("<"):
        raise RuntimeError(f"POST {path} returned HTML")
    return r.json()


def get(path: str) -> dict:
    r = httpx.get(f"{API}{path}", timeout=60.0)
    if r.status_code != 200:
        raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:400]}")
    if r.text.lstrip().startswith("<"):
        raise RuntimeError(f"GET {path} returned HTML")
    return r.json()


def wait_terminal(project_id: str, job_id: str, timeout_sec: float = 720.0) -> dict:
    deadline = time.time() + timeout_sec
    last = {}
    while time.time() < deadline:
        res = get(f"/api/minimax-h3/jobs/{project_id}/{job_id}")
        last = res.get("job") or {}
        status = last.get("status")
        if status and status != "running" and status != "queued":
            return last
        time.sleep(5)
    return last


def run_take(project_id: str, tag: str) -> dict:
    prepared = post(
        "/api/minimax-h3/prepare-plan",
        {
            "projectId": project_id,
            "prompt": PROMPT,
            "mode": "text-to-video",
            "sourceSurface": "text-to-video",
            "deployment": "local_weights",
            "territory": "CA",
            "durationSec": 5,
            "timelineContext": None,
        },
    )
    plan_id = prepared["planId"]
    write_json(f"{tag}-prepare-plan.json", prepared)
    preflight_status = prepared.get("plan", {}).get("preflight", {}).get("status") if isinstance(prepared.get("plan"), dict) else None
    if preflight_status != "ready":
        write_json(f"{tag}-not-ready.json", prepared)
        raise RuntimeError(f"H3 preflight not ready: {preflight_status}")

    job_res = post("/api/minimax-h3/jobs", {"projectId": project_id, "planId": plan_id, "approvalId": None})
    write_json(f"{tag}-submit.json", job_res)
    if not job_res.get("ok") or not job_res.get("jobId"):
        raise RuntimeError(f"H3 job not started: {job_res}")
    assert job_res["status"] == "running", job_res
    prov = job_res.get("provenance", {})
    assert prov.get("apiUsed") is False, prov
    assert prov.get("ltxUsed") is False, prov
    assert prov.get("deployment") == "private-local", prov
    assert prov.get("access") == "owner-only", prov

    job_id = job_res["jobId"]
    final = wait_terminal(project_id, job_id)
    write_json(f"{tag}-job-final.json", final)
    return final


def main() -> int:
    name = f"H3-PHASEC-PROOF-{uuid.uuid4().hex[:8]}"
    proj = post("/api/projects", {"name": name})
    project_id = proj["id"]
    write_json("project.json", proj)
    print(f"[proof] disposable project {project_id} ({name})")

    try:
        # First take
        t0 = time.time()
        first = run_take(project_id, "take1")
        first_status = first.get("status")
        print(f"[proof] take1 status={first_status} after {time.time()-t0:.0f}s")
        if first_status != "completed":
            print(f"[proof] take1 FAILED: errorCode={first.get('errorCode')} message={first.get('errorMessage')}")
            return 2
        assert first.get("outputPath"), first
        assert first.get("provenance", {}).get("apiUsed") is False
        assert first.get("provenance", {}).get("ltxUsed") is False
        lib1 = first.get("media", {}).get("libraryImport", {})
        assert lib1.get("assetId"), first
        # Asset visible in project library
        proj_detail = get(f"/api/projects/{project_id}")
        asset_ids = [a.get("id") for a in (proj_detail.get("assets") or [])]
        assert lib1["assetId"] in asset_ids, (lib1, asset_ids)
        write_json("take1-library.json", {"assetId": lib1["assetId"], "projectAssets": asset_ids})
        print(f"[proof] take1 library asset {lib1['assetId']}")

        # Second take (retake)
        t0 = time.time()
        second = run_take(project_id, "take2")
        second_status = second.get("status")
        print(f"[proof] take2 status={second_status} after {time.time()-t0:.0f}s")
        if second_status != "completed":
            print(f"[proof] take2 FAILED: errorCode={second.get('errorCode')} message={second.get('errorMessage')}")
            return 3
        assert second.get("outputPath"), second
        assert second.get("provenance", {}).get("apiUsed") is False
        assert second.get("provenance", {}).get("ltxUsed") is False
        lib2 = second.get("media", {}).get("libraryImport", {})
        assert lib2.get("assetId"), second
        write_json("take2-library.json", {"assetId": lib2["assetId"]})
        print(f"[proof] take2 library asset {lib2['assetId']}")

        write_json("verdict.json", {
            "ok": True,
            "projectId": project_id,
            "take1": {"status": first_status, "assetId": lib1.get("assetId")},
            "take2": {"status": second_status, "assetId": lib2.get("assetId")},
            "provenance": {"apiUsed": False, "ltxUsed": False, "deployment": "private-local", "access": "owner-only"},
        })
        print("[proof] PASS — both takes completed via Adept /api/minimax-h3")
        return 0
    finally:
        # Cleanup disposable project (never touch the protected handoff).
        if project_id and project_id != "77a4b96c-8e3f-4501-897c-51bab99bedb7":
            try:
                httpx.delete(f"{API}/api/projects/{project_id}", timeout=30.0)
                print(f"[proof] deleted disposable project {project_id}")
            except Exception as exc:
                print(f"[proof] cleanup failed: {exc}")


if __name__ == "__main__":
    sys.exit(main())

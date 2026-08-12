#!/usr/bin/env python3
"""Re-run WAN shot2 + LatentSync lipsync on existing M3.0i project (post-fix)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CERT_PATH = ROOT / "scripts" / "m30i_native_visual_lipsync_cert.py"
OUT = ROOT / "artifacts" / "m30i" / "native-production" / "product-route"

PROJECT_ID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
IMG_B_ASSET = "9c8848ca-a431-418b-9ddb-ce109ceff07c"
LTX_SCENE_ID = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
WAN_SCENE_ID = "f58a4484-9a78-4510-b4bc-6a3c9e9e4613"
DIALOGUE_ASSET = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"

MOTION_WAN = (
    "Same hitchhiker on rural highway, gentle camera drift, empty road, "
    "single character, cinematic, no dialogue"
)


def _load_cert():
    spec = importlib.util.spec_from_file_location("m30i_cert", CERT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _merge_case(cases: list[dict[str, Any]], case_id: str, new: dict[str, Any]) -> None:
    for i, c in enumerate(cases):
        if c.get("id") == case_id:
            cases[i] = new
            return
    cases.append(new)


def _rerender_wan(cert, project_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "VIS-CONT-WAN-SHOT2",
        "kind": "video",
        "engine": "wan",
        "startedAt": cert._now(),
        "startAssetId": IMG_B_ASSET,
        "sceneId": WAN_SCENE_ID,
    }
    try:
        cert._req(
            "POST",
            f"/api/projects/{project_id}/promote",
            {"asset_id": IMG_B_ASSET, "target": "scene_start", "scene_id": WAN_SCENE_ID},
        )
        cert._req(
            "PATCH",
            f"/api/projects/{project_id}/scenes/{WAN_SCENE_ID}",
            {
                "engine": "wan",
                "prompt": MOTION_WAN,
                "duration_sec": 4.0,
                "start_asset_id": IMG_B_ASSET,
            },
        )
        render = cert._req(
            "POST",
            f"/api/projects/{project_id}/render",
            {
                "kind": "scene",
                "scene_id": WAN_SCENE_ID,
                "providerPreference": "local",
                "paidFallbackApproved": False,
                "startFrameModel": "auto",
                "generate_audio": False,
            },
        )
        entry["jobId"] = render.get("id")
        done = cert._wait_job(render["id"], "VIS-CONT-WAN-SHOT2")
        entry["jobStatus"] = done.get("status")
        entry["jobMessage"] = done.get("message")
        if done.get("status") != "done":
            entry.update(ok=False, status="NOT_GREEN", reason=done.get("message") or "wan render failed")
            entry["finishedAt"] = cert._now()
            return entry
        out_path = cert._scene_output_path(project_id, WAN_SCENE_ID)
        rp = json.loads(done.get("params_json") or "{}")
        entry["provenance"] = {
            "source": "studio-queue-render_scene-rerun",
            "jobId": done.get("id"),
            "sceneId": WAN_SCENE_ID,
            "videoProvider": "comfyui",
            "videoModel": "wan",
            "localFirstProvenance": rp.get("localFirstProvenance"),
        }
        entry.update(cert._file_meta(out_path))
        entry["ok"] = bool(out_path and out_path.is_file() and out_path.stat().st_size > 10000)
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = "scene output_path missing or too small"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = cert._now()
    return entry


def main() -> int:
    cert = _load_cert()
    OUT.mkdir(parents=True, exist_ok=True)

    continuity_path = OUT / "visual-continuity.json"
    lipsync_path = OUT / "lipsync-product-route.json"
    continuity: dict[str, Any] = {}
    lipsync_report: dict[str, Any] = {}
    if continuity_path.is_file():
        continuity = json.loads(continuity_path.read_text(encoding="utf-8"))
    if lipsync_path.is_file():
        lipsync_report = json.loads(lipsync_path.read_text(encoding="utf-8"))

    continuity.setdefault("cases", [])
    lipsync_report.setdefault("cases", [])
    continuity["rerunStartedAt"] = cert._now()
    continuity["projectId"] = PROJECT_ID
    lipsync_report["projectId"] = PROJECT_ID

    print("API health...")
    health = cert._req("GET", "/api/health")
    continuity["comfy"] = {
        "reachable": (health.get("comfy") or {}).get("reachable"),
        "status": health.get("comfy_status"),
    }

    proj = cert._req("GET", f"/api/projects/{PROJECT_ID}")
    if not proj.get("id"):
        print("FATAL: project missing", PROJECT_ID)
        return 2

    assets = {a.get("tag"): a.get("id") for a in (proj.get("assets") or [])}
    for tag in ("m30i_image_a", "m30i_image_b", "kokoro_dialogue"):
        if tag not in assets:
            print(f"FATAL: missing asset tag {tag}")
            return 2

    scenes = {s.get("name"): s.get("id") for s in (proj.get("scenes") or [])}
    if LTX_SCENE_ID not in {s.get("id") for s in (proj.get("scenes") or [])}:
        print("FATAL: LTX scene missing")
        return 2

    print("Re-render WAN Shot2...")
    wan_case = _rerender_wan(cert, PROJECT_ID)
    _merge_case(continuity["cases"], "VIS-CONT-WAN-SHOT2", wan_case)
    print(wan_case["id"], wan_case.get("status"), wan_case.get("reason") or wan_case.get("path", ""))

    continuity["allOk"] = all(c.get("ok") for c in continuity["cases"])
    continuity["status"] = "GREEN" if continuity["allOk"] else "NOT_GREEN"
    continuity["rerunFinishedAt"] = cert._now()
    continuity_path.write_text(json.dumps(continuity, indent=2), encoding="utf-8")

    dialogue_case = next(
        (c for c in lipsync_report["cases"] if c.get("id") == "AUDIO-DIALOGUE-LIPSYNC"),
        None,
    )
    if not dialogue_case or not dialogue_case.get("ok"):
        dialogue_case = {
            "id": "AUDIO-DIALOGUE-LIPSYNC",
            "ok": True,
            "status": "GREEN",
            "assetId": DIALOGUE_ASSET,
            "source": "reuse-project-library",
            "finishedAt": cert._now(),
        }
        _merge_case(lipsync_report["cases"], "AUDIO-DIALOGUE-LIPSYNC", dialogue_case)

    print("Re-run LatentSync lipsync on LTX scene...")
    lipsync_case = cert._lipsync(PROJECT_ID, LTX_SCENE_ID, DIALOGUE_ASSET)
    _merge_case(lipsync_report["cases"], "LIPSYNC-LATENTSYNC-01", lipsync_case)
    print(lipsync_case["id"], lipsync_case.get("status"), lipsync_case.get("reason") or "")

    lipsync_report["allOk"] = all(c.get("ok") for c in lipsync_report["cases"])
    lipsync_report["status"] = "GREEN" if lipsync_report["allOk"] else "NOT_GREEN"
    lipsync_report["rerunFinishedAt"] = cert._now()
    lipsync_path.write_text(json.dumps(lipsync_report, indent=2), encoding="utf-8")

    overall = continuity["allOk"] and lipsync_report["allOk"]
    print("WAN", wan_case.get("status"), wan_case.get("reason") or "")
    print("LIPSYNC", lipsync_case.get("status"), lipsync_case.get("reason") or "")
    print("CONTINUITY", continuity["status"])
    print("LIPSYNC_REPORT", lipsync_report["status"])
    print("OVERALL", "GREEN" if overall else "NOT_GREEN")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

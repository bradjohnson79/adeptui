"""Prepare Korri Scene 1 for one disposable WAN first/last-frame Timeline generate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
SID = "1f46b621-46f9-4b7e-8273-202a49e1ca7c"
START = "b98585a0-8829-48cc-8c7b-63b9687955bb"
END = "4d48b0b0-8829-4c3a-9f3e-NEED_RESOLVE"


def main() -> int:
    global END
    with httpx.Client(timeout=30.0) as client:
        project = client.get(f"{API}/api/projects/{PID}").json()
        images = [
            {
                "id": a.get("id"),
                "tag": a.get("tag"),
                "filename": a.get("filename"),
                "kind": a.get("kind"),
            }
            for a in (project.get("assets") or [])
            if a.get("kind") == "image"
        ]
        end = None
        for a in images:
            blob = f"{a.get('tag') or ''} {a.get('filename') or ''}".lower()
            if "korri front" in blob or (a.get("filename") or "").lower() == "korri front.png":
                end = a["id"]
                break
        if not end:
            for a in images:
                blob = f"{a.get('tag') or ''} {a.get('filename') or ''}".lower()
                if "korri" in blob and "front" in blob:
                    end = a["id"]
                    break
        if not end:
            print(json.dumps({"ok": False, "error": "no Korri Front asset", "images": images[:20]}, indent=2))
            return 1
        END = end
        scene = client.get(f"{API}/api/projects/{PID}/scenes/{SID}").json()
        patch = {
            "name": scene.get("name") or "Scene 1",
            "engine": "wan",
            "prompt": scene.get("prompt") or "Korri and Anadriya walk the Venture corridor.",
            "duration_sec": 2.0,
            "start_asset_id": START,
            "middle_asset_id": None,
            "end_asset_id": END,
            "audio_asset_id": scene.get("audio_asset_id"),
            "camera_note": scene.get("camera_note") or "",
            "seed": scene.get("seed", -1),
            "aspect_ratio": scene.get("aspect_ratio") or "16:9",
        }
        updated = client.patch(f"{API}/api/projects/{PID}/scenes/{SID}", json=patch)
        updated.raise_for_status()
        master = client.get(f"{API}/api/director-timeline/projects/{PID}/scenes/{SID}/master").json()
        batches = ((master.get("master") or {}).get("batchBlocks") or [])
        if not batches:
            print(json.dumps({"ok": False, "error": "no batches", "masterKeys": list(master.keys())}, indent=2))
            return 1
        batch = batches[0]
        bid = batch["id"]
        anchors = [
            {
                "id": "anc_wan_start",
                "kind": "image",
                "assetId": START,
                "label": "Start",
                "atTime": 0.0,
                "strength": 1.0,
            },
            {
                "id": "anc_wan_end",
                "kind": "end_frame",
                "assetId": END,
                "label": "End",
                "atTime": 2.0,
                "strength": 1.0,
            },
        ]
        patched = client.patch(
            f"{API}/api/director-timeline/projects/{PID}/scenes/{SID}/batches/{bid}",
            json={
                "generatorId": "wan-local",
                "plannedDuration": 2.0,
                "sourceAnchors": anchors,
            },
        )
        patched.raise_for_status()
        out = {
            "ok": True,
            "projectId": PID,
            "sceneId": SID,
            "batchId": bid,
            "startAssetId": START,
            "endAssetId": END,
            "endTag": next((a.get("tag") or a.get("filename") for a in images if a["id"] == END), END),
            "sceneEngine": updated.json().get("engine"),
            "sceneDuration": updated.json().get("duration_sec"),
            "batchPatch": patched.json().get("ok"),
        }
        Path(__file__).resolve().parent.joinpath("evidence", "WAN_FLF_PREP.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8"
        )
        print(json.dumps(out, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

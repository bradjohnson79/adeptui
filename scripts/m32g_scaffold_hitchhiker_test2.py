"""Create Hitchhiker Test 2 WAN scene without touching the M3.2f LTX scene."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
LTX_SCENE = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
WAN_LEGACY = "f58a4484-9a78-4510-b4bc-6a3c9e9e4613"
IMAGE_B = "9c8848ca-a431-418b-9ddb-ce109ceff07c"
DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"
OUT = Path("artifacts/m32g/hitchhiker-test-2/01-project-context")
OUT.mkdir(parents=True, exist_ok=True)


def get(url: str):
    return json.load(urllib.request.urlopen(url, timeout=60))


def post(url: str, body: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def patch(url: str, body: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def main() -> None:
    project = get(f"{API}/api/projects/{PID}")
    scenes = get(f"{API}/api/projects/{PID}/scenes")
    ltx = next((s for s in scenes if s.get("id") == LTX_SCENE), None)
    legacy_wan = next((s for s in scenes if s.get("id") == WAN_LEGACY), None)
    existing = next((s for s in scenes if "Hitchhiker Test 2" in (s.get("name") or "")), None)

    if existing:
        scene = existing
        created = False
    else:
        scene = post(
            f"{API}/api/projects/{PID}/scenes",
            {
                "name": "Hitchhiker Test 2",
                "prompt": (
                    "A lone hitchhiker waits beside a quiet rural highway at golden hour. "
                    "Immersive roadside environment, deliberate camera dolly-in, cinematic side light."
                ),
                "engine": "wan",
                "start_asset_id": IMAGE_B,
                "duration_sec": 4.0,
            },
        )
        created = True
        # Ensure engine/start frame stick even if create ignored fields
        scene = patch(
            f"{API}/api/projects/{PID}/scenes/{scene['id']}",
            {
                "name": "Hitchhiker Test 2",
                "engine": "wan",
                "start_asset_id": IMAGE_B,
                "lipsync_audio_asset_id": DIALOGUE,
                "lipsync_enabled": True,
            },
        )

    ctx = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "projectId": PID,
        "projectName": project.get("name"),
        "sceneCreated": created,
        "test2SceneId": scene.get("id"),
        "test2Scene": {
            "id": scene.get("id"),
            "name": scene.get("name"),
            "index": scene.get("index"),
            "engine": scene.get("engine"),
            "start_asset_id": scene.get("start_asset_id"),
            "lipsync_audio_asset_id": scene.get("lipsync_audio_asset_id") or DIALOGUE,
            "output_path": scene.get("output_path"),
        },
        "protectedLtxScene": {
            "id": LTX_SCENE,
            "name": (ltx or {}).get("name"),
            "engine": (ltx or {}).get("engine"),
            "output_path": (ltx or {}).get("output_path"),
            "lipsync_output_path": (ltx or {}).get("lipsync_output_path"),
        },
        "legacyWanShot2": {
            "id": WAN_LEGACY,
            "name": (legacy_wan or {}).get("name"),
            "note": "Historical failed WAN shot; Test 2 is a new independent scene",
        },
        "assets": {
            "imageB": IMAGE_B,
            "dialogue": DIALOGUE,
        },
        "targets": {
            "durationSec": 4.0,
            "aspect": "16:9",
            "resolution": "1280x704",
            "engine": "wan",
            "model": "wan2.2_i2v_14B",
            "music": "ACE-Step",
            "sfx": "MMAudio",
        },
        "gaps": [
            "360 equirect registration → Spatial Map background",
            "WAN CLIP meta-tensor",
            "Editor multi-track final mix",
            "Lighting prompt auto-wire",
        ],
    }
    (OUT / "project-context.json").write_text(json.dumps(ctx, indent=2), encoding="utf-8")
    (OUT / "flow-map.md").write_text(
        "\n".join(
            [
                "# M3.2g Hitchhiker Test 2 — flow map",
                "",
                f"- projectId: `{PID}`",
                f"- test2SceneId: `{scene.get('id')}`",
                f"- protected LTX scene: `{LTX_SCENE}`",
                "",
                "## Required chain",
                "360 equirect → Spatial Map → camera/lighting → WAN 2.2 → lipsync → music → SFX → Editor mix → export",
                "",
                "## Known product gaps at start",
                "- WAN CLIP meta-tensor (M30K-WAN-01)",
                "- No equirect → Spatial Map production path",
                "- Editor tracks not muxed into final render",
                "- Lighting layer not auto-filled from Spatial Map lights",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "test2SceneId": scene.get("id"), "created": created}, indent=2))


if __name__ == "__main__":
    main()

"""M3.2g Phase 1-2: register equirect panorama + bind Spatial Map for Hitchhiker Test 2."""
from __future__ import annotations

import json
import sys
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
TEST2 = "e277e621-189d-471e-b435-f01620f03d0d"
LTX_PROTECTED = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
IMAGE_B = "9c8848ca-a431-418b-9ddb-ce109ceff07c"
IMAGE_A = "d523d406-ce9a-4073-87db-f5ddd06816d1"
ART = ROOT / "artifacts" / "m32g" / "hitchhiker-test-2"


def _req(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    if TEST2 == LTX_PROTECTED:
        raise SystemExit("Refusing to modify protected LTX scene")

    from app.db import Asset, SessionLocal
    from app.environment_assets import find_equirect_panorama, register_equirect_panorama
    from app.spatial_prompt_builder import assemble_prompt_layers, flatten_layers
    from app.spatial_scene import SpatialSceneDoc

    db = SessionLocal()
    try:
        img_b = db.get(Asset, IMAGE_B)
        img_a = db.get(Asset, IMAGE_A)
        if not img_b or not img_b.path or not Path(img_b.path).is_file():
            raise SystemExit(f"Image B missing: {IMAGE_B}")

        existing = find_equirect_panorama(db, PID, tag="hitchhiker_test2_equirect")
        if existing and existing.path and Path(existing.path).is_file():
            panorama = existing
            created = False
        else:
            sources = [Path(img_b.path)]
            if img_a and img_a.path and Path(img_a.path).is_file():
                sources = [Path(img_a.path), Path(img_b.path), Path(img_a.path)]
            panorama = register_equirect_panorama(
                db,
                project_id=PID,
                source_paths=sources,
                tag="hitchhiker_test2_equirect",
                entity_name="Hitchhiker Test 2 Highway 360",
                entity_id=TEST2,
                parent_asset_id=IMAGE_B,
                filename="hitchhiker_test2_equirect_2048x1024.png",
                extra_meta={"sceneId": TEST2, "m32g": "phase1-2"},
            )
            created = True

        meta = json.loads(panorama.prompt_meta_json or "{}")
        collage_ev = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "phase": "02-360-collage",
            "projectId": PID,
            "sceneId": TEST2,
            "protectedLtxSceneUntouched": LTX_PROTECTED,
            "assetId": panorama.id,
            "created": created,
            "kind": panorama.kind,
            "tag": panorama.tag,
            "path": panorama.path,
            "filename": panorama.filename,
            "onDisk": Path(panorama.path).is_file(),
            "dimensions": {
                "width": meta.get("width"),
                "height": meta.get("height"),
            },
            "prompt_meta": {
                "projection": meta.get("projection"),
                "kind": meta.get("kind"),
                "taxonomy": meta.get("taxonomy"),
                "library": meta.get("library"),
            },
            "parentAssetId": panorama.parent_asset_id,
            "sourceImageB": IMAGE_B,
        }
        _write(ART / "02-360-collage" / "equirect-panorama.json", collage_ev)

        char_id = str(uuid.uuid4())
        cam_id = str(uuid.uuid4())
        light_id = str(uuid.uuid4())
        state_id = str(uuid.uuid4())

        doc = {
            "version": 2,
            "width": 1000,
            "height": 700,
            "background_asset_id": panorama.id,
            "notes": "Rural highway roadside at golden hour — Hitchhiker Test 2 Spatial Map.",
            "guidance": "balanced",
            "calibration": {},
            "avatars": [
                {
                    "id": char_id,
                    "label": "Hitchhiker",
                    "initials": "HH",
                    "color": "#c45c26",
                    "shape": "circle",
                    "entity_type": "character",
                    "x": 520,
                    "y": 380,
                    "rotation": 0,
                    "scale": 1.0,
                    "height": 1.7,
                    "asset_id": IMAGE_B,
                    "spatial_prompt": "Lone hitchhiker beside quiet rural highway, same wardrobe as Image B.",
                    "continuity": "locked",
                    "visible": True,
                    "locked": False,
                    "facing": {"mode": "face_camera", "compass": "south"},
                    "relationships": [],
                    "expression": "hopeful, alert",
                    "pose": "standing with thumb out toward road",
                    "wardrobe": "travel clothes from Image B",
                },
                {
                    "id": cam_id,
                    "label": "A Cam",
                    "initials": "CA",
                    "color": "#1d4ed8",
                    "shape": "camera",
                    "entity_type": "camera",
                    "x": 280,
                    "y": 390,
                    "rotation": 15,
                    "scale": 1.0,
                    "height": 1.6,
                    "spatial_prompt": "Slow dolly-in toward hitchhiker along roadside.",
                    "visible": True,
                    "locked": False,
                    "facing": {"mode": "face_avatar", "target_avatar_id": char_id, "compass": "east"},
                    "relationships": [{"type": "looks_at", "to_id": char_id}],
                    "camera": {
                        "lens_mm": 35,
                        "height_m": 1.6,
                        "shot_size": "medium",
                        "focus_targets": [char_id],
                        "fov_deg": 45,
                        "aspect": "16:9",
                        "rig": "dolly",
                        "movement": "dolly_in",
                        "depth_of_field": "medium",
                        "sensor_preset": "",
                    },
                },
                {
                    "id": light_id,
                    "label": "Key",
                    "initials": "KY",
                    "color": "#a16207",
                    "shape": "light",
                    "entity_type": "light",
                    "x": 700,
                    "y": 220,
                    "rotation": -30,
                    "scale": 1.0,
                    "spatial_prompt": "warm golden-hour key from camera-right / sun side",
                    "visible": True,
                    "locked": False,
                    "facing": {"mode": "face_avatar", "target_avatar_id": char_id, "compass": "west"},
                    "relationships": [],
                },
            ],
            "states": [
                {
                    "id": state_id,
                    "name": "State A",
                    "avatar_overrides": {},
                    "camera_id": cam_id,
                    "lighting": "Cinematic golden-hour side light along the highway; warm key, soft cool fill from open sky.",
                    "spatial_prompt_snapshot": "",
                }
            ],
            "active_state_id": state_id,
            "prompt_layers": {},
            "points": [],
        }

        put = _req("PUT", f"{API}/api/projects/{PID}/scenes/{TEST2}/spatial", {"doc": doc})
        saved = put.get("doc") or doc
        layers = assemble_prompt_layers(SpatialSceneDoc.model_validate(saved), state_id=state_id)
        positive, negative = flatten_layers(layers)

        spatial_ev = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "phase": "03-spatial-map",
            "projectId": PID,
            "sceneId": TEST2,
            "protectedLtxSceneUntouched": LTX_PROTECTED,
            "background_asset_id": saved.get("background_asset_id"),
            "avatarCount": len(saved.get("avatars") or []),
            "avatars": [
                {
                    "id": a.get("id"),
                    "label": a.get("label"),
                    "entity_type": a.get("entity_type"),
                    "x": a.get("x"),
                    "y": a.get("y"),
                }
                for a in (saved.get("avatars") or [])
            ],
            "active_state_id": saved.get("active_state_id"),
            "notes": saved.get("notes"),
            "putOk": bool(put.get("ok")),
        }
        _write(ART / "03-spatial-map" / "spatial-doc.json", spatial_ev)

        cam_avatar = next(a for a in saved["avatars"] if a.get("entity_type") == "camera")
        camera_ev = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "phase": "04-camera",
            "projectId": PID,
            "sceneId": TEST2,
            "cameraAvatarId": cam_avatar.get("id"),
            "cameraSpec": cam_avatar.get("camera"),
            "cameraLayer": layers.camera,
            "movement": (cam_avatar.get("camera") or {}).get("movement"),
            "lens_mm": (cam_avatar.get("camera") or {}).get("lens_mm"),
            "fov_deg": (cam_avatar.get("camera") or {}).get("fov_deg"),
        }
        _write(ART / "04-camera" / "camera-spec.json", camera_ev)

        light_avatar = next(a for a in saved["avatars"] if a.get("entity_type") == "light")
        state = next(s for s in saved["states"] if s.get("id") == state_id)
        lighting_ev = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "phase": "05-lighting",
            "projectId": PID,
            "sceneId": TEST2,
            "stateLighting": state.get("lighting"),
            "lightAvatar": {
                "id": light_avatar.get("id"),
                "label": light_avatar.get("label"),
                "spatial_prompt": light_avatar.get("spatial_prompt"),
                "x": light_avatar.get("x"),
                "y": light_avatar.get("y"),
            },
            "layersLighting": layers.lighting,
            "lightingAutoPopulated": bool((layers.lighting or "").strip()),
            "positivePromptIncludesLighting": (layers.lighting or "")[:80] in positive if layers.lighting else False,
            "negative": negative[:200],
        }
        _write(ART / "05-lighting" / "lighting-layer.json", lighting_ev)

        print(
            json.dumps(
                {
                    "ok": True,
                    "assetId": panorama.id,
                    "background_asset_id": saved.get("background_asset_id"),
                    "layersLighting": layers.lighting,
                    "artifacts": [
                        str(ART / "02-360-collage" / "equirect-panorama.json"),
                        str(ART / "03-spatial-map" / "spatial-doc.json"),
                        str(ART / "04-camera" / "camera-spec.json"),
                        str(ART / "05-lighting" / "lighting-layer.json"),
                    ],
                },
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

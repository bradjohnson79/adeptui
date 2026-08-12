"""Register Hitchhiker LTX + lipsync outputs into the project library (idempotent)."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.db import Asset, Project, Scene, SessionLocal  # noqa: E402

PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
LTX_SCENE = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
IMAGE_A = "d523d406-ce9a-4073-87db-f5ddd06816d1"
DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"


def ensure_asset(db, *, path: Path, tag: str, kind: str, parent_id: str | None, meta: dict, labels: list[str]):
    existing = db.query(Asset).filter(Asset.project_id == PID, Asset.path == str(path)).first()
    if existing:
        return existing, False
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=PID,
        tag=tag,
        kind=kind,
        filename=path.name,
        path=str(path),
        comfy_name="",
        scope="project",
        parent_asset_id=parent_id,
        prompt_meta_json=json.dumps(meta),
        labels_json=json.dumps(labels),
    )
    db.add(asset)
    return asset, True


def main() -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, PID)
        scene = db.get(Scene, LTX_SCENE)
        if not project or not scene:
            raise SystemExit("Hitchhiker project/scene missing")
        created = []
        ltx = Path(scene.output_path) if scene.output_path else None
        lipsync = Path(scene.lipsync_output_path) if scene.lipsync_output_path else None
        if ltx and ltx.is_file():
            asset, is_new = ensure_asset(
                db,
                path=ltx.resolve(),
                tag=f"scene_{scene.index}_ltx",
                kind="video",
                parent_id=IMAGE_A,
                meta={"op": "render_scene", "sceneId": scene.id, "engine": "ltx"},
                labels=["video", "ltx", f"scene-{scene.index}"],
            )
            if is_new:
                created.append(asset.id)
        if lipsync and lipsync.is_file():
            asset, is_new = ensure_asset(
                db,
                path=lipsync.resolve(),
                tag=f"scene_{scene.index}_lipsync",
                kind="video",
                parent_id=IMAGE_A,
                meta={
                    "op": "lipsync",
                    "sceneId": scene.id,
                    "audioAssetId": DIALOGUE,
                    "faceAssetId": IMAGE_A,
                    "provider": "latentsync",
                },
                labels=["lipsync", "final-candidate", f"scene-{scene.index}"],
            )
            if is_new:
                created.append(asset.id)
        project.updated_at = datetime.utcnow()
        db.commit()
        print(json.dumps({"created": created, "ok": True}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()

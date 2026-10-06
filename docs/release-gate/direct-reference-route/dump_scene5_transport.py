"""Dump Scene 5 Direct Reference Transport. No GPU. Does not persist."""

from __future__ import annotations

import json
from pathlib import Path

from app.db import Scene, SessionLocal
from app.director_timeline_w46.contracts import SceneTimelineMaster
from app.director_timeline_w46.generation.direct_reference import inspect_direct_reference
from app.director_timeline_w46.migration import load_or_migrate_scene_master

PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
SCENE_ID = "a16515ce-cde8-4786-99fa-091d8bede618"
BATCH_ID = "bb_6226cbbd68b7"
OUT = Path(__file__).resolve().parent / "evidence" / "scene5_reference_transport.json"


def main() -> None:
    db = SessionLocal()
    try:
        scene = (
            db.query(Scene)
            .filter(Scene.project_id == PROJECT_ID, Scene.id == SCENE_ID)
            .one()
        )
        master, _tl, _data = load_or_migrate_scene_master(
            scene.director_json,
            scene_id=SCENE_ID,
            fallback_duration=float(scene.duration_sec or 5.0),
            fallback_prompt=scene.prompt or "",
        )
        if not isinstance(master, SceneTimelineMaster):
            master = SceneTimelineMaster.model_validate(master)
        batch = next((item for item in master.batchBlocks if item.id == BATCH_ID), None)
        if batch is None:
            raise SystemExit(f"BATCH_NOT_FOUND {BATCH_ID}")
        report = inspect_direct_reference(
            db,
            project_id=PROJECT_ID,
            scene_id=SCENE_ID,
            batch=batch,
            generator_id=batch.generatorId or "minimax-h3",
        )
        report["checkedBindingIds"] = [
            bid
            for seg in batch.promptSegments
            for bid in (seg.referenceBindingIds or [])
        ]
        report["staleBatchReferenceKinds"] = [
            ref.get("kind")
            for ref in (batch.references or [])
            if isinstance(ref, dict)
        ]
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({
            "ok": report.get("ok"),
            "tags": [row.get("canonicalTag") for row in report.get("timelineReferences") or []],
            "comfy": report.get("comfy"),
            "blocked": report.get("blocked"),
            "checkedBindingIds": report.get("checkedBindingIds"),
            "staleBatchReferenceKinds": report.get("staleBatchReferenceKinds"),
            "wrote": str(OUT),
        }, indent=2))
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()

"""LTX adapter real-duration + start-image lineage metadata tests."""

from __future__ import annotations

from uuid import uuid4

from app.db import Job, Project, Scene, SessionLocal, init_db
from app.director_timeline_w46.generation.adapters.ltx_local import _extract_gate_duration

init_db()

_PROJECT_ID = "p-ltxmeta"
_SCENE_ID = "sc-ltxmeta"


def _setup(db) -> str:
    if db.get(Project, _PROJECT_ID) is None:
        db.add(Project(id=_PROJECT_ID, name="ltx-meta"))
        db.add(Scene(id=_SCENE_ID, project_id=_PROJECT_ID, name="sc"))
        db.commit()
    job_id = str(uuid4())
    db.add(
        Job(
            id=job_id,
            project_id=_PROJECT_ID,
            scene_id=_SCENE_ID,
            kind="render_scene",
            status="done",
            output_path="C:/tmp/out.mp4",
            history_json='{"outputGate": {"durationSec": 8.041667, "width": 1280, "height": 704}}',
        )
    )
    db.commit()
    return job_id


def test_extract_gate_duration_from_history():
    db = SessionLocal()
    try:
        job_id = _setup(db)
        row = db.get(Job, job_id)
        assert _extract_gate_duration(row) == 8.041667
    finally:
        db.close()


def test_extract_gate_duration_not_done():
    db = SessionLocal()
    try:
        job_id = str(uuid4())
        db.add(
            Job(
                id=job_id,
                project_id=_PROJECT_ID,
                scene_id=_SCENE_ID,
                kind="render_scene",
                status="running",
                history_json='{"outputGate": {"durationSec": 8.0}}',
            )
        )
        db.commit()
        assert _extract_gate_duration(db.get(Job, job_id)) is None
    finally:
        db.close()


def test_extract_gate_duration_missing():
    db = SessionLocal()
    try:
        job_id = str(uuid4())
        db.add(
            Job(
                id=job_id,
                project_id=_PROJECT_ID,
                scene_id=_SCENE_ID,
                kind="render_scene",
                status="done",
                history_json="{}",
            )
        )
        db.commit()
        assert _extract_gate_duration(db.get(Job, job_id)) is None
    finally:
        db.close()

"""Prop Creator live Job.progress pin — copy-through, no invented percents."""

from __future__ import annotations

import uuid

from app.spatial_map.ers_contracts import PropCandidate, PropEntity


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Prop Progress Pin") -> str:
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def test_sync_candidates_surfaces_job_progress() -> None:
    from app.db import Job
    from app.prop_creator.service import _sync_candidates

    project_id = _create_project()
    db = _session()
    try:
        job_id = str(uuid.uuid4())
        db.add(Job(id=job_id, project_id=project_id, kind="imagegen", status="running", progress=0.4))
        db.commit()
        prop = PropEntity(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="mug",
            display_label="Mug",
            candidates=[
                PropCandidate(id="c1", prop_id="p1", index=0, job_id=job_id, status="queued"),
            ],
        )
        _sync_candidates(db, project_id, prop)
        assert prop.candidates[0].progress == 0.4
        assert prop.candidates[0].status == "generating"
    finally:
        db.close()

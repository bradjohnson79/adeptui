"""spatial_map_documents is write authority; project JSON is a projection."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.spatial_scene import SpatialSceneDoc, get_or_create_spatial, parse_spatial_doc, save_spatial_doc


def test_save_spatial_doc_projects_project_json() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Spatial Authority", description="", spatial_map_json="{}"))
    db.add(Scene(id=sid, project_id=pid, index=0, name="S", prompt="", duration_sec=5.0, director_json=""))
    db.commit()
    try:
        row = get_or_create_spatial(db, pid, sid)
        doc = SpatialSceneDoc.model_validate({"guidance": "balanced", "width": 1920, "height": 1080})
        save_spatial_doc(db, row, doc)
        db.refresh(db.get(Project, pid))
        project = db.get(Project, pid)
        assert project is not None
        projected = json.loads(project.spatial_map_json or "{}")
        assert projected.get("guidance") == "balanced"
        reloaded = parse_spatial_doc(row, "{}")
        assert reloaded.guidance == "balanced"
    finally:
        db.close()

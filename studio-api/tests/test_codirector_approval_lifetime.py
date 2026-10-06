"""Approval cards stay actionable until a real invalidation or the lifetime."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session


@pytest.fixture()
def db() -> Session:
    from app.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _project(db: Session):
    from app.db import Project

    now = datetime.utcnow()
    pid = f"apr-life-{uuid.uuid4().hex[:10]}"
    db.add(Project(id=pid, name="Approval lifetime", created_at=now, updated_at=now))
    db.commit()
    return db.get(Project, pid)


def _scene(db: Session, project_id: str):
    from app.db import Scene

    scene = Scene(
        id=str(uuid.uuid4()),
        project_id=project_id,
        index=0,
        name="Table",
        prompt="Cade at the window",
    )
    db.add(scene)
    db.commit()
    return scene


def _row(db: Session, *, project_id: str, tool_id: str, arguments: dict, versions: dict, created_at: datetime, status: str = "pending"):
    from app.codirector.tools.definitions import ToolCallPayload, ToolPreview
    from app.db import CoDirectorProposal

    payload = ToolCallPayload(
        toolId=tool_id,
        arguments=arguments,
        preview=ToolPreview(summary="Create a new scene in Timeline."),
        baseResourceVersions=versions,
    )
    row = CoDirectorProposal(
        id=str(uuid.uuid4()),
        project_id=project_id,
        proposal_type="tool_call",
        title="Create a scene",
        summary="scene",
        payload_json=json.dumps(payload.model_dump(mode="json")),
        status=status,
        created_by="test",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(row)
    db.commit()
    return row


def _listed(db: Session, project_id: str, proposal_id: str):
    from app.codirector.bible.proposals import ProposalService

    found = {item.id: item for item in ProposalService.list(db, project_id)}
    return found[proposal_id]


def test_fresh_scene_proposal_survives_a_project_clock_move(db: Session):
    from app.project_service import project_version_token

    project = _project(db)
    token = project_version_token(project)
    now = datetime.utcnow()
    row = _row(
        db,
        project_id=project.id,
        tool_id="create_scene",
        arguments={"name": "Cade at the shop", "prompt": "Cade sits by the window"},
        versions={f"project:{project.id}": token},
        created_at=now,
    )
    project.updated_at = now + timedelta(seconds=3)
    db.commit()
    for age in (timedelta(seconds=3), timedelta(seconds=30), timedelta(minutes=5)):
        stored = db.get(type(row), row.id)
        stored.created_at = datetime.utcnow() - age
        db.commit()
        listed = _listed(db, project.id, row.id)
        assert listed.status == "pending"
        assert listed.isStale is False


def test_scene_proposal_expires_only_after_the_lifetime(db: Session):
    from app.project_service import project_version_token

    project = _project(db)
    token = project_version_token(project)
    row = _row(
        db,
        project_id=project.id,
        tool_id="create_scene",
        arguments={"name": "Cade at the shop"},
        versions={f"project:{project.id}": token},
        created_at=datetime.utcnow() - timedelta(minutes=61),
    )
    listed = _listed(db, project.id, row.id)
    assert listed.isStale is True
    assert listed.status == "pending"


def test_scene_target_change_stales_immediately(db: Session):
    from app.scene_service import scene_fingerprint

    project = _project(db)
    scene = _scene(db, project.id)
    pinned = scene_fingerprint(scene)
    row = _row(
        db,
        project_id=project.id,
        tool_id="update_scene_title",
        arguments={"sceneId": scene.id, "name": "Window"},
        versions={f"scene:{scene.id}": pinned},
        created_at=datetime.utcnow(),
    )
    assert _listed(db, project.id, row.id).isStale is False
    scene.prompt = "The thermos moved."
    db.commit()
    listed = _listed(db, project.id, row.id)
    assert listed.isStale is True


def test_reject_and_complete_are_not_actionable(db: Session):
    from app.codirector.bible.proposals import ProposalService
    from app.project_service import project_version_token

    project = _project(db)
    token = project_version_token(project)
    rejected = _row(
        db,
        project_id=project.id,
        tool_id="create_scene",
        arguments={"name": "One"},
        versions={f"project:{project.id}": token},
        created_at=datetime.utcnow(),
    )
    completed = _row(
        db,
        project_id=project.id,
        tool_id="create_scene",
        arguments={"name": "Two"},
        versions={f"project:{project.id}": token},
        created_at=datetime.utcnow(),
        status="completed",
    )
    ProposalService.reject(db, project.id, rejected.id, note=None, decided_by="creator")
    rejected_out = _listed(db, project.id, rejected.id)
    completed_out = _listed(db, project.id, completed.id)
    assert rejected_out.status == "rejected"
    assert rejected_out.isStale is False
    assert completed_out.status == "completed"
    assert completed_out.isStale is False


def test_listing_twice_does_not_stale_a_fresh_proposal(db: Session):
    from app.project_service import project_version_token

    project = _project(db)
    token = project_version_token(project)
    row = _row(
        db,
        project_id=project.id,
        tool_id="create_scene",
        arguments={"name": "Replay"},
        versions={f"project:{project.id}": token},
        created_at=datetime.utcnow() - timedelta(seconds=3),
    )
    project.updated_at = datetime.utcnow()
    db.commit()
    first = _listed(db, project.id, row.id)
    second = _listed(db, project.id, row.id)
    assert first.isStale is False
    assert second.isStale is False
    assert second.status == "pending"
    assert db.get(type(row), row.id).status == "pending"

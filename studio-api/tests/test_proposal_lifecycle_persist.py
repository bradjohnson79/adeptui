"""Proposal-lifecycle persist pin.

A project clock move inside the approval lifetime does not persist status=stale.
Startup persists stale only after the lifetime, or when a real target pin moved.
"""

from __future__ import annotations

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


def _seed_project(db: Session, pid: str):
    from app.db import Project

    now = datetime.utcnow()
    db.merge(Project(id=pid, name="Lifecycle Persist", created_at=now, updated_at=now))
    db.commit()
    return db.get(Project, pid)


def _pose_payload(pid: str, token: str):
    from app.codirector.tools.definitions import ToolCallPayload, ToolPreview

    return ToolCallPayload(
        toolId="posecraft.apply_pose",
        arguments={"figureId": "fig-1", "posePresetId": "stand"},
        preview=ToolPreview(summary="Apply pose"),
        baseResourceVersions={f"project:{pid}": token},
    )


def _insert_tool_row(db: Session, *, pid: str, payload, status: str, title: str):
    import json
    from app.db import CoDirectorProposal

    now = datetime.utcnow()
    row = CoDirectorProposal(
        id=str(uuid.uuid4()),
        project_id=pid,
        bible_id=None,
        based_on_version_id=None,
        proposal_type="tool_call",
        title=title,
        summary="test leftover",
        payload_json=json.dumps(payload.model_dump(mode="json")),
        status=status,
        created_by="test",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_and_startup_persist_stale_when_project_version_token_moves(db, monkeypatch):
    """A project clock move inside the approval lifetime leaves the proposal pending.

    Startup persists stale only after the approval lifetime. No approve/cancel, no row delete.
    """
    from app.codirector.bible.proposals import ProposalService
    from app.db import CoDirectorProposal
    from app.project_service import project_version_token

    approve_calls = []
    cancel_calls = []
    monkeypatch.setattr(
        ProposalService,
        "approve",
        classmethod(lambda cls, *a, **k: approve_calls.append((a, k)) or (_ for _ in ()).throw(AssertionError("approve must not be called"))),
    )
    monkeypatch.setattr(
        ProposalService,
        "cancel",
        classmethod(lambda cls, *a, **k: cancel_calls.append((a, k)) or (_ for _ in ()).throw(AssertionError("cancel must not be called"))),
    )

    pid = f"lc-persist-{uuid.uuid4().hex[:10]}"
    project = _seed_project(db, pid)
    token0 = project_version_token(project)
    assert token0

    leftover = _insert_tool_row(
        db,
        pid=pid,
        payload=_pose_payload(pid, token0),
        status="pending",
        title="PoseCraft: apply pose leftover",
    )
    sibling = _insert_tool_row(
        db,
        pid=pid,
        payload=_pose_payload(pid, token0),
        status="completed",
        title="PoseCraft: apply pose sibling complete",
    )
    leftover_id = leftover.id
    sibling_id = sibling.id

    project.updated_at = datetime.utcnow() + timedelta(seconds=30)
    db.commit()
    token1 = project_version_token(db.get(type(project), pid))
    assert token1 != token0

    still = db.get(CoDirectorProposal, leftover_id)
    assert still is not None
    assert still.status == "pending"

    listed = ProposalService.list(db, pid)
    by_id = {row.id: row for row in listed}
    assert leftover_id in by_id
    assert sibling_id in by_id
    assert by_id[leftover_id].status == "pending"
    assert by_id[leftover_id].isStale is False
    assert by_id[sibling_id].status == "completed"
    assert by_id[sibling_id].isStale is False

    persisted = db.get(CoDirectorProposal, leftover_id)
    assert persisted is not None
    assert persisted.status == "pending"

    leftover2 = _insert_tool_row(
        db,
        pid=pid,
        payload=_pose_payload(pid, token0),
        status="pending",
        title="PoseCraft: apply pose leftover 2",
    )
    leftover2_id = leftover2.id
    untouched = ProposalService.persist_stale_non_terminal(db, project_id=pid)
    assert untouched == 0
    assert db.get(CoDirectorProposal, leftover2_id).status == "pending"

    expired = db.get(CoDirectorProposal, leftover_id)
    expired.created_at = datetime.utcnow() - timedelta(minutes=61)
    db.commit()
    n = ProposalService.persist_stale_non_terminal(db, project_id=pid)
    assert n >= 1
    assert db.get(CoDirectorProposal, leftover_id).status == "stale"
    assert db.get(CoDirectorProposal, leftover2_id).status == "pending"
    fetched = ProposalService.get(db, pid, leftover_id)
    assert fetched.status == "stale"
    assert fetched.isStale is True

    ids = {r.id for r in db.query(CoDirectorProposal).filter(CoDirectorProposal.project_id == pid).all()}
    assert ids == {leftover_id, sibling_id, leftover2_id}
    assert approve_calls == []
    assert cancel_calls == []

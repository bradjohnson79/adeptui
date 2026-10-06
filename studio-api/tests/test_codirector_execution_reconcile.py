"""Co-Director execution reconcile pin — pack is a projection of Job rows.

Fixtures only. Does not touch live Schnick, does not POST /advance or /cancel
on project 2347bf46-3762-4763-86c5-4a6032522278, does not delete job rows or
pending PNGs, and does not attach reserved output_asset_ids to Library/shots.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.execution.advance import (
    ZERO_JOB_ERROR_MESSAGE,
    advance_execution_pack,
    heal_zero_job_plan,
    reconcile_non_terminal_packs,
)
from app.codirector.execution.cancel import cancel_execution
from app.codirector.execution.contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus
from app.codirector.execution.events import bridge_job_status_change
from app.codirector.execution.pack_store import (
    get_active_execution_for_project,
    list_packs,
    load_pack,
    save_pack,
)
from app.db import Asset, Base, Job, Project


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-reconcile", name="Reconcile Fixture"))
    session.commit()
    yield session
    session.close()


def _plan(*, execution_id: str, children: list[ChildJobView], status: ExecutionStatus = ExecutionStatus.QUEUED) -> ExecutionPlan:
    return ExecutionPlan(
        execution_id=execution_id,
        capability="image.generate",
        project_id="proj-reconcile",
        status=status,
        child_jobs=children,
        surface_type="image_generation",
    )


def _child(job_id: str, status: ChildJobStatus = ChildJobStatus.QUEUED) -> ChildJobView:
    return ChildJobView(job_id=job_id, label="shot", status=status, child_index=0)


def _add_job(db, job_id: str, status: str, *, params: dict | None = None) -> Job:
    job = Job(
        id=job_id,
        project_id="proj-reconcile",
        kind="imagegen",
        status=status,
        params_json=json.dumps(params or {}),
    )
    db.add(job)
    db.commit()
    return job


# --------------------------------------------------------------------------
# A. recompute_progress — CANCELLED is terminal
# --------------------------------------------------------------------------


def test_recompute_all_completed() -> None:
    plan = _plan(
        execution_id="e-done",
        children=[_child("j1", ChildJobStatus.COMPLETED), _child("j2", ChildJobStatus.COMPLETED)],
    )
    plan.recompute_progress()
    assert plan.status == ExecutionStatus.COMPLETED
    assert plan.progress == 1.0


def test_recompute_any_failed_rest_terminal() -> None:
    plan = _plan(
        execution_id="e-fail",
        children=[
            _child("j1", ChildJobStatus.COMPLETED),
            _child("j2", ChildJobStatus.FAILED),
            _child("j3", ChildJobStatus.CANCELLED),
        ],
    )
    plan.recompute_progress()
    assert plan.status == ExecutionStatus.FAILED


def test_recompute_any_cancelled_rest_completed_or_cancelled() -> None:
    plan = _plan(
        execution_id="e-cancel",
        children=[
            _child("j1", ChildJobStatus.COMPLETED),
            _child("j2", ChildJobStatus.CANCELLED),
        ],
    )
    plan.recompute_progress()
    assert plan.status == ExecutionStatus.CANCELLED


def test_recompute_any_running() -> None:
    plan = _plan(
        execution_id="e-run",
        children=[_child("j1", ChildJobStatus.COMPLETED), _child("j2", ChildJobStatus.RUNNING)],
    )
    plan.recompute_progress()
    assert plan.status == ExecutionStatus.RUNNING


def test_recompute_any_queued() -> None:
    plan = _plan(
        execution_id="e-q",
        children=[_child("j1", ChildJobStatus.FAILED), _child("j2", ChildJobStatus.QUEUED)],
    )
    plan.recompute_progress()
    assert plan.status == ExecutionStatus.QUEUED


# --------------------------------------------------------------------------
# Advance after Job row changes
# --------------------------------------------------------------------------


def test_advance_after_job_done_parent_completed(db) -> None:
    job_id = "job-done-1"
    execution_id = str(uuid.uuid4())
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(db, job_id, "done", params={"output_asset_id": "asset-fixture-1"})

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.COMPLETED
    assert plan.status == ExecutionStatus.COMPLETED


def test_advance_done_job_missing_asset_leaves_result_asset_ids_empty(db) -> None:
    """Job done + reserved output_asset_id with no Asset row.

    Parent completes from job status. result_asset_ids / child.asset_id stay
    empty — do not stamp a Library 404.
    """
    job_id = "job-done-reserved"
    execution_id = str(uuid.uuid4())
    reserved = "asset-reserved-no-row"
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(db, job_id, "done", params={"output_asset_id": reserved})
    assert db.get(Asset, reserved) is None

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.COMPLETED
    assert plan.child_jobs[0].asset_id is None
    assert plan.status == ExecutionStatus.COMPLETED
    assert plan.result_asset_ids == []
    assert db.get(Asset, reserved) is None


def test_advance_heals_dangling_result_assets_on_terminal_pack(db) -> None:
    """Already-COMPLETED pack with a 404 result_asset_id is healed on GET/advance."""
    job_id = "job-term-ghost"
    execution_id = str(uuid.uuid4())
    ghost = "asset-ghost-404"
    child = _child(job_id, ChildJobStatus.COMPLETED)
    child.asset_id = ghost
    plan = _plan(
        execution_id=execution_id,
        children=[child],
        status=ExecutionStatus.COMPLETED,
    )
    plan.result_asset_ids = [ghost]
    plan.progress = 1.0
    save_pack(db, "proj-reconcile", plan)
    _add_job(db, job_id, "done", params={"output_asset_id": ghost})
    assert db.get(Asset, ghost) is None

    out = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert out is not None
    assert out.status == ExecutionStatus.COMPLETED
    assert out.result_asset_ids == []
    assert out.child_jobs[0].asset_id is None
    assert out.child_jobs[0].status == ChildJobStatus.COMPLETED
    reloaded = load_pack(db, "proj-reconcile", execution_id)
    assert reloaded is not None
    assert reloaded.result_asset_ids == []
    assert reloaded.child_jobs[0].asset_id is None
    assert db.get(Asset, ghost) is None


def test_reconcile_heals_terminal_dangling_result_assets(db) -> None:
    job_id = "job-recon-ghost"
    execution_id = str(uuid.uuid4())
    ghost = "asset-recon-404"
    child = _child(job_id, ChildJobStatus.COMPLETED)
    child.asset_id = ghost
    plan = _plan(
        execution_id=execution_id,
        children=[child],
        status=ExecutionStatus.COMPLETED,
    )
    plan.result_asset_ids = [ghost]
    plan.progress = 1.0
    save_pack(db, "proj-reconcile", plan)
    _add_job(db, job_id, "done", params={"output_asset_id": ghost})

    updated = reconcile_non_terminal_packs(db, "proj-reconcile", persist_artifacts=False)
    ids = {p.execution_id for p in updated}
    assert execution_id in ids
    reloaded = load_pack(db, "proj-reconcile", execution_id)
    assert reloaded is not None
    assert reloaded.status == ExecutionStatus.COMPLETED
    assert reloaded.result_asset_ids == []
    assert reloaded.child_jobs[0].asset_id is None


def test_heal_keeps_real_library_asset(db) -> None:
    job_id = "job-real-asset"
    execution_id = str(uuid.uuid4())
    real_id = "asset-real-library"
    db.add(Asset(id=real_id, project_id="proj-reconcile", filename="real.png", path="real.png"))
    db.commit()
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(db, job_id, "done", params={"output_asset_id": real_id})

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.status == ExecutionStatus.COMPLETED
    assert plan.child_jobs[0].asset_id == real_id
    assert plan.result_asset_ids == [real_id]


def test_advance_after_job_cancelled_parent_cancelled(db) -> None:
    job_id = "job-cancel-1"
    execution_id = str(uuid.uuid4())
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(db, job_id, "cancelled")

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.CANCELLED
    assert plan.status == ExecutionStatus.CANCELLED


def test_advance_after_job_404_child_failed_parent_failed(db) -> None:
    job_id = "job-missing-404"
    execution_id = str(uuid.uuid4())
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    # No Job row on purpose.

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.FAILED
    assert plan.child_jobs[0].error == "JOB_NOT_FOUND"
    assert plan.status == ExecutionStatus.FAILED


def test_advance_stale_parent_when_child_already_cancelled(db) -> None:
    """Zombie: child already CANCELLED, parent still QUEUED — advance must recompute."""
    job_id = "job-already-cancelled"
    execution_id = str(uuid.uuid4())
    save_pack(
        db,
        "proj-reconcile",
        _plan(execution_id=execution_id, children=[_child(job_id, ChildJobStatus.CANCELLED)]),
    )
    _add_job(db, job_id, "cancelled")

    plan = advance_execution_pack(db, "proj-reconcile", execution_id, persist_artifacts=False)
    assert plan is not None
    assert plan.status == ExecutionStatus.CANCELLED


# --------------------------------------------------------------------------
# Cancel when children already cancelled
# --------------------------------------------------------------------------


def test_cancel_when_children_already_cancelled_parent_cancelled(db, monkeypatch) -> None:
    job_id = "job-child-already-cancelled"
    execution_id = str(uuid.uuid4())
    save_pack(
        db,
        "proj-reconcile",
        _plan(execution_id=execution_id, children=[_child(job_id, ChildJobStatus.CANCELLED)]),
    )
    _add_job(db, job_id, "cancelled")

    def _boom(_job_id: str) -> None:
        raise AssertionError("cancel must not touch already-terminal children")

    monkeypatch.setattr("app.codirector.execution.cancel._cancel_job", _boom)

    plan = cancel_execution(db, "proj-reconcile", execution_id)
    assert plan is not None
    assert plan.status == ExecutionStatus.CANCELLED
    reloaded = load_pack(db, "proj-reconcile", execution_id)
    assert reloaded is not None
    assert reloaded.status == ExecutionStatus.CANCELLED


def test_cancel_does_not_let_recompute_undo_explicit_cancel(db, monkeypatch) -> None:
    """A FAILED sibling must not win over an explicit user cancel."""
    execution_id = str(uuid.uuid4())
    save_pack(
        db,
        "proj-reconcile",
        _plan(
            execution_id=execution_id,
            children=[
                ChildJobView(job_id="j-fail", label="a", status=ChildJobStatus.FAILED, child_index=0),
                ChildJobView(job_id="j-live", label="b", status=ChildJobStatus.QUEUED, child_index=1),
            ],
        ),
    )

    monkeypatch.setattr("app.codirector.execution.cancel._cancel_job", lambda _jid: None)

    plan = cancel_execution(db, "proj-reconcile", execution_id)
    assert plan is not None
    assert plan.status == ExecutionStatus.CANCELLED


# --------------------------------------------------------------------------
# GET active=true after reconcile omits terminal packs
# --------------------------------------------------------------------------


def test_list_packs_active_true_omits_reconciled_terminals(db) -> None:
    done_id = str(uuid.uuid4())
    cancel_id = str(uuid.uuid4())
    missing_id = str(uuid.uuid4())
    still_queued_id = str(uuid.uuid4())

    save_pack(db, "proj-reconcile", _plan(execution_id=done_id, children=[_child("job-d")]))
    save_pack(db, "proj-reconcile", _plan(execution_id=cancel_id, children=[_child("job-c")]))
    save_pack(db, "proj-reconcile", _plan(execution_id=missing_id, children=[_child("job-404")]))
    save_pack(db, "proj-reconcile", _plan(execution_id=still_queued_id, children=[_child("job-q")]))

    _add_job(db, "job-d", "done")
    _add_job(db, "job-c", "cancelled")
    _add_job(db, "job-q", "queued")
    # job-404 is absent

    active = list_packs(db, "proj-reconcile", active_only=True)
    active_ids = {p.execution_id for p in active}
    assert done_id not in active_ids
    assert cancel_id not in active_ids
    assert missing_id not in active_ids
    assert still_queued_id in active_ids

    assert load_pack(db, "proj-reconcile", done_id).status == ExecutionStatus.COMPLETED
    assert load_pack(db, "proj-reconcile", cancel_id).status == ExecutionStatus.CANCELLED
    assert load_pack(db, "proj-reconcile", missing_id).status == ExecutionStatus.FAILED


# --------------------------------------------------------------------------
# Bridge: nested creativeContext.executionId updates the pack
# --------------------------------------------------------------------------


def test_bridge_nested_creative_context_execution_id_updates_pack(db) -> None:
    job_id = "job-bridge-nested"
    execution_id = str(uuid.uuid4())
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(
        db,
        job_id,
        "done",
        params={"creativeContext": {"executionId": execution_id}},
    )

    bridge_job_status_change(db, job_id, "done", stage="complete", message="done")

    plan = load_pack(db, "proj-reconcile", execution_id)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.COMPLETED
    assert plan.status == ExecutionStatus.COMPLETED


def test_bridge_maps_cancelled(db) -> None:
    job_id = "job-bridge-cancel"
    execution_id = str(uuid.uuid4())
    save_pack(db, "proj-reconcile", _plan(execution_id=execution_id, children=[_child(job_id)]))
    _add_job(
        db,
        job_id,
        "cancelled",
        params={"creativeContext": {"executionId": execution_id}},
    )

    bridge_job_status_change(db, job_id, "cancelled", stage="cancelled", message="cancelled")

    plan = load_pack(db, "proj-reconcile", execution_id)
    assert plan is not None
    assert plan.child_jobs[0].status == ChildJobStatus.CANCELLED
    assert plan.status == ExecutionStatus.CANCELLED


# --------------------------------------------------------------------------
# E PRODUCT FAIL — preview must not become failed on hydrate/GET/reconcile
# --------------------------------------------------------------------------


def test_preview_pack_stays_preview_on_hydrate_reconcile(db) -> None:
    """Create a preview pack (no approve, no jobs). GET/reconcile/hydrate
    must leave it preview — never invent FAILED / JOB_NOT_FOUND / zero-job.
    """
    execution_id = f"preview-{uuid.uuid4().hex[:8]}"
    save_pack(
        db,
        "proj-reconcile",
        _plan(execution_id=execution_id, children=[], status=ExecutionStatus.PREVIEW),
    )

    advanced = advance_execution_pack(
        db, "proj-reconcile", execution_id, persist_artifacts=False
    )
    assert advanced is not None
    assert advanced.status == ExecutionStatus.PREVIEW
    assert advanced.child_jobs == []
    assert advanced.error not in (ZERO_JOB_ERROR_MESSAGE, "JOB_NOT_FOUND")
    assert (advanced.error or "") == ""

    healed = heal_zero_job_plan(
        db, "proj-reconcile", execution_id, reason="active_latest_heal"
    )
    assert healed is not None
    assert healed.status == ExecutionStatus.PREVIEW

    reconcile_non_terminal_packs(db, "proj-reconcile", persist_artifacts=False)
    listed = list_packs(db, "proj-reconcile", active_only=True)
    ids = {p.execution_id: p for p in listed}
    assert execution_id in ids
    assert ids[execution_id].status == ExecutionStatus.PREVIEW

    active = get_active_execution_for_project(db, "proj-reconcile")
    assert active is not None
    assert active.execution_id == execution_id
    assert active.status == ExecutionStatus.PREVIEW
    assert active.error not in (ZERO_JOB_ERROR_MESSAGE, "JOB_NOT_FOUND")

    reloaded = load_pack(db, "proj-reconcile", execution_id)
    assert reloaded is not None
    assert reloaded.status == ExecutionStatus.PREVIEW
    assert reloaded.child_jobs == []
    assert (reloaded.error or "") == ""

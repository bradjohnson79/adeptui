"""Scene Generation 0/0 loop — focused regression tests (Phase 20).

Governing invariant: no valid path may leave Scene Generation active with
zero total jobs. Zero jobs = NOT running (terminal failure or cancelled).
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

    from app.main import app, job_queue
    from app.routers import api

    monkeypatch.setattr(job_queue, "start", lambda: None)
    monkeypatch.setattr(api.job_queue, "enqueue", AsyncMock())

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    from app.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _create_project(client, name: str = "Zero Job Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _dispatch(client, project_id: str, capability: str, *, context: dict | None = None) -> dict:
    res = client.post(
        f"/api/codirector/projects/{project_id}/executions",
        json={"capability": capability, "context": context or {}},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _seed_queued_zero_job_pack(db, project_id: str, execution_id: str) -> None:
    """Directly persist a pre-fix-style QUEUED pack with zero children."""
    from app.codirector.execution.contracts import ExecutionPlan, ExecutionStatus
    from app.codirector.execution.pack_store import save_pack

    plan = ExecutionPlan(
        execution_id=execution_id,
        capability="scene.generate",
        project_id=project_id,
        status=ExecutionStatus.QUEUED,
        surface_type="scene_generation",
        child_jobs=[],
    )
    save_pack(db, project_id, plan)


# ---------------------------------------------------------------------------
# A — dispatch with zero accepted jobs must be terminal FAILED
# ---------------------------------------------------------------------------


def test_dispatch_zero_job_result_is_terminal_failed(client, db, mock_provider_env, monkeypatch) -> None:
    """A handler returning child_jobs: [] must produce a FAILED plan with a
    clear error — never QUEUED with an empty work surface (0/0 law)."""
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {
            "child_jobs": [],
            "surface_type": "scene_generation",
            "status": "failed",
            "accepted": 0,
            "rejected": 0,
            "error": "No valid scene-generation jobs were created.",
        }

    project_id = _create_project(client)
    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    plan = _dispatch(client, project_id, "scene.generate", context={"shot_requests_raw": ""})
    assert plan["status"] == "failed"
    assert plan["child_jobs"] == []
    assert "No valid scene-generation jobs" in (plan.get("error") or "")
    # The work surface must never treat this as running.
    assert plan["status"] not in ("queued", "running")


def test_dispatch_zero_job_result_without_status_is_still_terminal(client, db, mock_provider_env, monkeypatch) -> None:
    """Defensive: a handler returning empty children WITHOUT an explicit
    status must also be terminal — zero jobs is never RUNNING."""
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {"child_jobs": [], "surface_type": "scene_generation"}

    project_id = _create_project(client)
    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    plan = _dispatch(client, project_id, "scene.generate")
    assert plan["status"] == "failed"
    assert plan["error"]


def test_dispatch_partial_enqueue_reports_counts(client, db, mock_provider_env, monkeypatch) -> None:
    """Partial enqueue: accepted/rejected counts land on the plan while the
    pack stays QUEUED (children exist) — sibling failures do not kill the pack."""
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {
            "child_jobs": [
                {"job_id": "ok-1", "status": "queued", "child_index": 0},
                {"job_id": "ok-2", "status": "queued", "child_index": 1},
                {"job_id": "failed-1", "status": "failed", "child_index": 2},
            ],
            "surface_type": "scene_generation",
            "status": "queued",
            "accepted": 2,
            "rejected": 1,
            "job_ids": ["ok-1", "ok-2", "failed-1"],
        }

    project_id = _create_project(client)
    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    plan = _dispatch(client, project_id, "scene.generate")
    assert plan["status"] == "queued"
    assert len(plan["child_jobs"]) == 3
    assert plan.get("plan_data", {}).get("accepted") == 2
    assert plan.get("plan_data", {}).get("rejected") == 1


# ---------------------------------------------------------------------------
# B — scene_generate.handle zero-shots contract
# ---------------------------------------------------------------------------


def test_scene_generate_handler_empty_shots_is_terminal_contract() -> None:
    """The real handler returns status=failed + error for zero parsed shots,
    so the dispatcher can never see an ambiguous empty result."""
    from app.codirector.capabilities.handlers.scene_generate import handle

    result = handle(
        None,
        project_id="p-zero",
        execution_id="e-zero",
        shot_requests_raw="",
        ers_package_id="",
    )
    assert result["child_jobs"] == []
    assert result["status"] == "failed"
    assert result["accepted"] == 0
    assert result["rejected"] == 0
    assert "No valid scene-generation jobs" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# D — advance heals a stranded QUEUED zero-child pack (pre-fix state)
# ---------------------------------------------------------------------------


def test_advance_heals_zero_job_phantom_to_failed(client, db, mock_provider_env) -> None:
    """A QUEUED pack with zero children (stranded before the fix, or any
    empty result) must become terminal FAILED on the next advance."""
    project_id = _create_project(client)
    _seed_queued_zero_job_pack(db, project_id, "phantom-adv-1")

    res = client.post(f"/api/codirector/projects/{project_id}/executions/phantom-adv-1/advance")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "failed"
    assert body["child_jobs"] == []
    assert "No valid shots were queued" in (body.get("error") or "")


# ---------------------------------------------------------------------------
# E — cancel on a zero-job phantom terminates cleanly
# ---------------------------------------------------------------------------


def test_cancel_zero_job_phantom_terminates_cleanly(client, db, mock_provider_env) -> None:
    """Cancel on a phantom generation must reach CANCELLED immediately —
    it must not leave a queued 0/0 surface behind."""
    project_id = _create_project(client)
    _seed_queued_zero_job_pack(db, project_id, "phantom-cancel-1")

    res = client.post(f"/api/codirector/projects/{project_id}/executions/phantom-cancel-1/cancel")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "cancelled"


# ---------------------------------------------------------------------------
# active/latest — never rehydrates a phantom generation
# ---------------------------------------------------------------------------


def test_active_latest_does_not_return_zero_job_phantom(client, db, mock_provider_env) -> None:
    """Reload recovery must not surface a zero-child non-terminal pack as the
    active execution (the backend heals it to FAILED instead)."""
    project_id = _create_project(client)
    _seed_queued_zero_job_pack(db, project_id, "phantom-active-1")

    res = client.get(f"/api/codirector/projects/{project_id}/executions/active/latest")
    assert res.status_code == 200, res.text
    execution = res.json().get("execution")
    assert execution is None or execution.get("status") in ("failed", "cancelled", "completed")


# ---------------------------------------------------------------------------
# F — event lifecycle: no orphan generation_started for zero jobs
# ---------------------------------------------------------------------------




def test_dispatch_all_enqueues_failed_is_terminal(client, db, mock_provider_env, monkeypatch) -> None:
    """Runtime-unavailable path (Phase 27): when every enqueue fails, the
    children carry failed status and the pack must be terminal FAILED —
    never a running 0/0 surface."""
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {
            "child_jobs": [
                {"job_id": "failed-scene-shot-0", "status": "failed", "child_index": 0, "error": "runtime unavailable"},
                {"job_id": "failed-scene-shot-1", "status": "failed", "child_index": 1, "error": "runtime unavailable"},
            ],
            "surface_type": "scene_generation",
            "status": "failed",
            "accepted": 0,
            "rejected": 2,
        }

    project_id = _create_project(client)
    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    plan = _dispatch(client, project_id, "scene.generate")
    assert plan["status"] == "failed"
    assert len(plan["child_jobs"]) == 2
    assert plan["status"] not in ("queued", "running")


def test_scene_generate_event_lifecycle_no_orphan_start(monkeypatch) -> None:
    """The empty-shots path records scene_creator.generation_failed and never
    records generation_started — every start has a terminal counterpart."""
    events = []

    def fake_record(db, **kwargs):
        events.append(kwargs)

    # The handler imports record_production_event inside the function from
    # app.production_events — patch the canonical module.
    monkeypatch.setattr(
        "app.production_events.record_production_event",
        fake_record,
    )

    from app.codirector.capabilities.handlers.scene_generate import handle

    result = handle(
        None,
        project_id="p-evt",
        execution_id="e-evt",
        shot_requests_raw="",
        scene_id="scene-1",
    )
    assert result["status"] == "failed"
    kinds = [e.get("event_type") for e in events]
    assert "scene_creator.generation_failed" in kinds
    assert "scene_creator.generation_started" not in kinds

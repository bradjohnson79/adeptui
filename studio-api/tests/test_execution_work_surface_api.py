"""CDX-096 — direct API coverage for the Agent Work Surface execution endpoints.

Covers the Live Agent Work Surface controller (spec §19/§20/§43/§47):
- POST /codirector/projects/{project_id}/executions/{execution_id}/advance
- POST /codirector/projects/{project_id}/executions/{execution_id}/regenerate-frame
- POST /codirector/projects/{project_id}/executions/{execution_id}/cancel

Follows the mock-provider pattern of test_codirector_approval_safety.py /
test_tool_approval_bridge.py: dispatch runs with the deterministic mock
provider, and the capability handler is patched so no real GPU job is created.
The endpoints under test (advance polls REAL Job rows; cancel marks remaining
children; regenerate targets one child) are exercised end-to-end.

TESTS ONLY. No app/ source is modified here.
"""

from __future__ import annotations

import json
import uuid

import pytest


# --------------------------------------------------------------------------
# Fixtures (mirror test_codirector_approval_safety.py)
# --------------------------------------------------------------------------


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


def _create_project(client, name: str = "Work Surface Project") -> str:
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


def _approve(client, project_id: str, execution_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/executions/{execution_id}/approve")


def _advance(client, project_id: str, execution_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/executions/{execution_id}/advance")


def _cancel(client, project_id: str, execution_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/executions/{execution_id}/cancel")


def _regenerate(client, project_id: str, execution_id: str, child_index: int, **extra) -> object:
    body = {"child_index": child_index, **extra}
    return client.post(
        f"/api/codirector/projects/{project_id}/executions/{execution_id}/regenerate-frame",
        json=body,
    )


def _seed_queued_pack(client, db, monkeypatch, project_id: str, job_ids: list[str]) -> dict:
    """Dispatch storyboard.generate -> PREVIEW, approve with a patched handler
    that returns one queued child per job_id (no real GPU jobs)."""
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {
            "child_jobs": [
                {"job_id": jid, "status": "queued", "label": f"Shot {i + 1}", "child_index": i}
                for i, jid in enumerate(job_ids)
            ],
            "planned_steps": [],
            "surface_type": "storyboard_generation",
        }

    plan = _dispatch(client, project_id, "storyboard.generate", context={"count": len(job_ids)})
    assert plan["status"] == "preview"
    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    approved = _approve(client, project_id, plan["execution_id"])
    assert approved.status_code == 200, approved.text
    return approved.json()


# ==========================================================================
# advance — polls REAL Job rows (spec §20: every visible state maps to real state)
# ==========================================================================


def test_advance_reflects_real_job_state_transitions(client, db, mock_provider_env, monkeypatch) -> None:
    """POST /executions/{id}/advance reads the REAL Job row: running -> the
    child is RUNNING with real progress; done -> the child is COMPLETED with
    the output asset id (and the pack reaches COMPLETED)."""
    from app.db import Job

    project_id = _create_project(client)
    plan = _seed_queued_pack(client, db, monkeypatch, project_id, ["job-adv-1"])

    # Real Job row exists and is running.
    db.add(
        Job(
            id="job-adv-1",
            project_id=project_id,
            kind="imagegen",
            status="running",
            progress=0.4,
            stage="generating",
            message="working",
        )
    )
    db.commit()

    res = _advance(client, project_id, plan["execution_id"])
    assert res.status_code == 200, res.text
    child = res.json()["child_jobs"][0]
    assert child["status"] == "running"
    assert child["progress"] == 0.4
    assert child["stage"] == "generating"

    # Complete the real job; advance must now report COMPLETED with the asset.
    row = db.get(Job, "job-adv-1")
    row.status = "done"
    row.progress = 1.0
    row.stage = "completed"
    row.message = "done"
    row.params_json = json.dumps({"output_asset_id": "asset-adv-1"})
    db.commit()

    res2 = _advance(client, project_id, plan["execution_id"])
    assert res2.status_code == 200, res2.text
    body2 = res2.json()
    assert body2["status"] == "completed"
    assert body2["child_jobs"][0]["status"] == "completed"
    assert body2["child_jobs"][0]["asset_id"] == "asset-adv-1"
    assert "asset-adv-1" in body2["result_asset_ids"]


def test_advance_marks_missing_job_failed_honestly(client, db, mock_provider_env, monkeypatch) -> None:
    """A child whose Job row does not exist must surface as FAILED (JOB_NOT_FOUND)
    — advance never invents success (spec §20/§46)."""
    project_id = _create_project(client)
    plan = _seed_queued_pack(client, db, monkeypatch, project_id, ["job-missing-1"])
    # No Job row is created on purpose.

    res = _advance(client, project_id, plan["execution_id"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["child_jobs"][0]["status"] == "failed"
    assert body["child_jobs"][0]["error"] == "JOB_NOT_FOUND"


def test_advance_unknown_execution_returns_404(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    res = _advance(client, project_id, "execution-does-not-exist")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "EXECUTION_NOT_FOUND"


# ==========================================================================
# cancel — remaining children cancelled, completed assets kept (spec §47)
# ==========================================================================


def test_cancel_marks_remaining_children_cancelled(client, db, mock_provider_env, monkeypatch) -> None:
    """POST /executions/{id}/cancel cancels the queued children and the pack
    reaches CANCELLED; a second cancel on the terminal pack is a no-op."""
    project_id = _create_project(client)
    plan = _seed_queued_pack(client, db, monkeypatch, project_id, ["job-c1", "job-c2"])

    res = _cancel(client, project_id, plan["execution_id"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "cancelled"
    assert all(c["status"] == "cancelled" for c in body["child_jobs"])

    # Idempotent: terminal pack stays cancelled.
    res2 = _cancel(client, project_id, plan["execution_id"])
    assert res2.status_code == 200
    assert res2.json()["status"] == "cancelled"


def test_cancel_unknown_execution_returns_404(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    res = _cancel(client, project_id, "execution-does-not-exist")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "EXECUTION_NOT_FOUND"


# ==========================================================================
# regenerate-frame — targeted regen keeps siblings intact (spec §43/§21)
# ==========================================================================


def test_regenerate_frame_replaces_only_target_child(client, db, mock_provider_env, monkeypatch) -> None:
    """POST /executions/{id}/regenerate-frame submits a new job for ONE child;
    sibling frames are untouched."""
    project_id = _create_project(client)
    plan = _seed_queued_pack(client, db, monkeypatch, project_id, ["job-r1", "job-r2"])

    # Patch the regen handler module (regenerate.py imports it by path).
    import app.codirector.capabilities.handlers.storyboard_regenerate_frame as regen_mod

    def fake_regen(**kwargs):
        return {
            "child_jobs": [
                {"job_id": "job-r2-new", "status": "queued", "label": "Shot 2 (regen)", "child_index": 1}
            ]
        }

    monkeypatch.setattr(regen_mod, "handle", fake_regen)

    res = _regenerate(client, project_id, plan["execution_id"], child_index=1, user_instructions="retry framing")
    assert res.status_code == 200, res.text
    body = res.json()
    # Sibling (index 0) untouched.
    assert body["child_jobs"][0]["job_id"] == "job-r1"
    # Target (index 1) replaced with the new job and reset to queued.
    assert body["child_jobs"][1]["job_id"] == "job-r2-new"
    assert body["child_jobs"][1]["status"] == "queued"


def test_regenerate_frame_unknown_child_returns_404(client, db, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    plan = _seed_queued_pack(client, db, monkeypatch, project_id, ["job-r1"])
    res = _regenerate(client, project_id, plan["execution_id"], child_index=99)
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "EXECUTION_NOT_FOUND"

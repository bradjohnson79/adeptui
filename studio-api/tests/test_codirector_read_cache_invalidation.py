"""Read-cache invalidation on successful mutation applies (c4 follow-up repair).

The Wave 3 read cache (tools/read_cache.py) is an 8s project-keyed cache that was
never invalidated on writes, so a read issued right after a successful mutation could
serve the model pre-mutation state. execute_audited and execute_approved_proposal now
call clear_project() on success. These tests prove: success invalidates (both apply
paths), failure preserves, and a post-mutation read returns authoritative state.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.codirector.tools import read_cache


def _create_project(client) -> str:
    res = client.post("/api/projects", json={"name": "Cache Invalidation Test"})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _read(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _propose(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _approve(client, project_id: str, proposal_id: str) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve",
        json={},
    )


def _cached_scene_snapshot(project_id: str) -> dict[str, Any] | None:
    """Return the cached list_scenes snapshot for a project, regardless of argument shape."""
    prefix = f"{project_id}|list_scenes|"
    for key, (expires, value) in list(read_cache._store.items()):
        if key.startswith(prefix):
            return value
    return None


def _prime_scene_cache(client, project_id: str) -> dict[str, Any]:
    """Run a cacheable read; return the cached snapshot (must exist after the read)."""
    first = _read(client, project_id, "list_scenes")
    assert first.status_code == 200, first.text
    cached = _cached_scene_snapshot(project_id)
    assert cached is not None, "list_scenes read should populate the project read cache"
    return cached


@pytest.fixture(autouse=True)
def _clean_cache():
    yield
    # The cache is process-global; never let one test's entries leak into another.
    for key in list(read_cache._store.keys()):
        read_cache._store.pop(key, None)


def test_successful_mutation_invalidates_project_read_cache(client) -> None:
    project_id = _create_project(client)
    stale = _prime_scene_cache(client, project_id)
    stale_count = len((stale.get("data") or {}).get("scenes") or stale.get("scenes") or [])

    proposal = _propose(client, project_id, "create_scene", name="Second Scene")
    assert proposal.status_code == 200, proposal.text
    receipt = _approve(client, project_id, proposal.json()["id"])
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["status"] == "success", receipt.json()

    assert _cached_scene_snapshot(project_id) is None, (
        "a successful apply must invalidate the project's read cache"
    )

    fresh = _read(client, project_id, "list_scenes")
    assert fresh.status_code == 200, fresh.text
    data = fresh.json()["result"]["data"]
    scenes = data.get("scenes") or data.get("items") or []
    assert len(scenes) == stale_count + 1, "post-mutation read must return authoritative state"


def test_audited_write_invalidates_project_read_cache(client) -> None:
    project_id = _create_project(client)
    _prime_scene_cache(client, project_id)

    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/audited",
        json={
            "toolId": "production_plan.create_draft",
            "arguments": {"title": "Draft plan", "objective": "Cache invalidation check"},
        },
    )
    assert res.status_code == 200, res.text

    assert _cached_scene_snapshot(project_id) is None, (
        "a successful audited write must also invalidate the project's read cache"
    )


def test_failed_apply_preserves_read_cache(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "mutation_tool_execution_failure")

    project_id = _create_project(client)
    _prime_scene_cache(client, project_id)

    proposal = _propose(client, project_id, "create_scene", name="Doomed Scene")
    assert proposal.status_code == 200, proposal.text
    receipt = _approve(client, project_id, proposal.json()["id"])
    # The e2e fault hook forces the apply to raise; the receipt must report failure.
    assert receipt.status_code >= 400 or receipt.json().get("status") != "success", receipt.text

    assert _cached_scene_snapshot(project_id) is not None, (
        "a failed apply changes no state, so the read cache must be preserved"
    )

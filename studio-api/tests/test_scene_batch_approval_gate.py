"""Scene batch approval gate (CDX-043) + ERS sheetId grounding (CDX-034).

The legacy batch surface (POST /batches, regenerate-shot, send-to-timeline)
must never place unapproved images on the Timeline:

- ``POST /batches/{bid}/approve`` marks specific *completed result assets* as
  approved (validated: the id belongs to a completed job result of the batch).
- ``POST /batches/{bid}/send-to-timeline`` rejects with 409
  ``APPROVAL_REQUIRED`` naming the unapproved assets whenever any completed
  result asset lacks approval - nothing reaches the Timeline helper until the
  creator approves (generated != approved).
- ``POST /batches`` and ``regenerate-shot`` resolve the ERS reference through
  ``ers_resolver.resolve_ers_for_sheet`` when the passed id is a creator-facing
  sheetId; unresolvable references fail loudly (never silent zero grounding).
- ``scene.generate`` handler applies the same resolution.

Only repo fixtures are used - no live runtime, no service, no studio.db.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.scene_creator.ers_resolver import ErsResolveError
from app.spatial_map.ers_contracts import EnvironmentReferencePackage, SceneGenerationBatch
from app.spatial_map.ers_persistence import save_ers_package, save_scene_batch


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


# ---------------------------------------------------------------------------
# Helpers (repo fixtures only)
# ---------------------------------------------------------------------------


def _create_project(client, name: str = "Batch Approval Gate") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return str(res.json()["id"])


def _create_project_row(db, name: str = "Handler Project") -> str:
    from app.db import Project

    project_id = str(uuid.uuid4())
    db.add(Project(id=project_id, name=name))
    db.commit()
    return project_id


def _first_scene(client, project_id: str) -> str:
    scenes = client.get(f"/api/projects/{project_id}").json()["scenes"]
    assert scenes, "project should carry a default Scene 1"
    return str(scenes[0]["id"])


def _save_sheet(project_id: str, *, approved_north: str | None = None, scene_id: str | None = None):
    from app.environment_reference_sheet import orchestrator, store
    from app.environment_reference_sheet.contracts import DirectionalViewRecord

    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Batch Atrium",
        description="Glass atrium, cool daylight.",
        scene_id=scene_id,
    )
    if approved_north:
        sheet.directionalViews = [
            DirectionalViewRecord(
                direction="north",
                title="North",
                prompt="north view",
                sourceDirection="north",
                approvedAssetId=approved_north,
                status="approved",
            )
        ]
    store.save_sheet(sheet)
    return sheet


def _save_grounded_package(db, project_id: str, sheet_id: str) -> EnvironmentReferencePackage:
    """A persisted generation package bridged to the sheet via metadata.sheet_id."""
    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id="map-1",
        metadata={"sheet_id": sheet_id},
        directional_assets={"north": "asset-north", "east": None, "south": None, "west": None},
        placements=[{"characterId": "korri-1", "label": "Korri", "slotIndex": 0}],
    )
    save_ers_package(db, project_id, package)
    return package


def _seed_completed_job(db, project_id: str, job_id: str, output_asset_id: str | None = None):
    from app.db import Job

    params = {}
    if output_asset_id:
        params = {"output_asset_id": output_asset_id}
    db.add(
        Job(
            id=job_id,
            project_id=project_id,
            kind="imagegen",
            status="done",
            params_json=json.dumps(params),
        )
    )
    db.commit()


def _seed_batch(
    db,
    project_id: str,
    *,
    ers_package_id: str,
    result_asset_ids: list[str],
    shot_count: int | None = None,
    approved: list[str] | None = None,
) -> SceneGenerationBatch:
    from app.spatial_map.ers_contracts import ShotRequest

    if shot_count is None:
        shot_count = len(result_asset_ids)
    shots = [
        ShotRequest(index=i, raw_text=f"Shot {i + 1}", characters=[], prop_entities=[])
        for i in range(shot_count)
    ]
    batch = SceneGenerationBatch(
        project_id=project_id,
        ers_package_id=ers_package_id,
        shot_requests=shots,
        output_count=shot_count,
        result_asset_ids=list(result_asset_ids),
        approved_asset_ids=list(approved or []),
    )
    save_scene_batch(db, project_id, batch)
    return batch


def _fake_enqueue(captured: list[dict]):
    def _enqueue(dbs, pid, body, **kwargs):
        job_id = str(uuid.uuid4())
        captured.append({"job_id": job_id, "body": body})
        return SimpleNamespace(id=job_id)

    return _enqueue


# ---------------------------------------------------------------------------
# CDX-043 approval gate
# ---------------------------------------------------------------------------


def test_send_to_timeline_rejects_unapproved_batch(client, db, monkeypatch):
    """Completed-but-unapproved assets -> 409 APPROVAL_REQUIRED; helper untouched."""
    project_id = _create_project(client)
    scene_id = _first_scene(client, project_id)
    job_a = str(uuid.uuid4())
    job_b = str(uuid.uuid4())
    batch = _seed_batch(
        db, project_id, ers_package_id="pkg-1", result_asset_ids=[job_a, job_b]
    )
    _seed_completed_job(db, project_id, job_a)
    _seed_completed_job(db, project_id, job_b)

    sentinel = Mock()
    monkeypatch.setattr("app.scene_creator.timeline_handoff.send_scene_batch_to_timeline", sentinel)

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/send-to-timeline",
        json={"scene_id": scene_id},
    )
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "APPROVAL_REQUIRED"
    assert set(detail["unapproved_asset_ids"]) == {job_a, job_b}
    sentinel.assert_not_called()


def test_approve_then_send_only_approved_clips_reach_timeline(client, db, monkeypatch):
    """Approve a specific take (by its job output asset id) -> handoff sends only approved clips."""
    project_id = _create_project(client)
    scene_id = _first_scene(client, project_id)
    # One completed slot + one failed regen slot (never approved, never placed).
    job_a = str(uuid.uuid4())
    asset_1 = str(uuid.uuid4())
    batch = _seed_batch(
        db,
        project_id,
        ers_package_id="pkg-1",
        result_asset_ids=[job_a, "failed_regen_1"],
    )
    _seed_completed_job(db, project_id, job_a, output_asset_id=asset_1)

    captured: dict = {}

    def _fake_export(dbs, pid, scene_id_, clips, **kwargs):
        captured["clips"] = clips
        return {"ok": True, "batchBlockId": "block-1", "clips": clips}

    monkeypatch.setattr("app.scene_creator.timeline_handoff.export_to_timeline", _fake_export)

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/approve",
        json={"asset_ids": [asset_1]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["approved_asset_ids"] == [asset_1]

    res2 = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/send-to-timeline",
        json={"scene_id": scene_id},
    )
    assert res2.status_code == 200, res2.text
    clip_assets = [c["assetId"] for c in captured["clips"]]
    assert clip_assets == [job_a]


def test_approve_slot_id_and_asset_id_are_interchangeable(client, db, monkeypatch):
    project_id = _create_project(client)
    scene_id = _first_scene(client, project_id)
    job_a = str(uuid.uuid4())
    asset_1 = str(uuid.uuid4())
    batch = _seed_batch(db, project_id, ers_package_id="pkg-1", result_asset_ids=[job_a])
    _seed_completed_job(db, project_id, job_a, output_asset_id=asset_1)

    captured: dict = {}

    def _fake_export(dbs, pid, scene_id_, clips, **kwargs):
        captured["clips"] = clips
        return {"ok": True, "batchBlockId": "block-1", "clips": clips}

    monkeypatch.setattr("app.scene_creator.timeline_handoff.export_to_timeline", _fake_export)

    # Approve by the raw slot id (the job id itself).
    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/approve",
        json={"asset_ids": [job_a]},
    )
    assert res.status_code == 200, res.text

    res2 = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/send-to-timeline",
        json={"scene_id": scene_id},
    )
    assert res2.status_code == 200, res2.text
    assert [c["assetId"] for c in captured["clips"]] == [job_a]


def test_approve_rejects_unknown_or_incomplete_asset(client, db):
    project_id = _create_project(client)
    # job-a is queued, not completed -> its id is not an approvable completed result.
    batch = _seed_batch(db, project_id, ers_package_id="pkg-1", result_asset_ids=["job-a"])
    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/approve",
        json={"asset_ids": ["job-a"]},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "INVALID_ASSET"
    assert res.json()["detail"]["invalid_asset_ids"] == ["job-a"]


def test_approve_requires_asset_ids(client, db):
    project_id = _create_project(client)
    batch = _seed_batch(db, project_id, ers_package_id="pkg-1", result_asset_ids=["job-a"])
    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/approve",
        json={"asset_ids": []},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "NO_ASSETS"


# ---------------------------------------------------------------------------
# CDX-034 ERS sheetId grounding on the batch surface
# ---------------------------------------------------------------------------


def test_create_batch_with_sheet_id_resolves_package_and_grounds(client, db, monkeypatch):
    """POST /batches with the creator-facing sheetId compiles with ERS grounding."""
    project_id = _create_project(client)
    scene_id = _first_scene(client, project_id)
    sheet = _save_sheet(project_id, approved_north="asset-north", scene_id=scene_id)
    package = _save_grounded_package(db, project_id, sheet.sheetId)

    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches",
        json={
            "ers_package_id": sheet.sheetId,
            "shot_requests_raw": "Korri close-up",
            "output_count": 1,
            "character_names": ["Korri"],
        },
    )
    assert res.status_code == 200, res.text
    batch = res.json()["batch"]
    # The batch record stores the RESOLVED package id, not the sheetId.
    assert batch["ers_package_id"] == package.id
    assert len(captured) == 1
    body = captured[0]["body"]
    assert body["creativeContext"]["ersPackageId"] == package.id
    # Grounding: structured blocking from the package placements reached the prompt.
    assert "Character: Korri" in body["prompt"]


def test_create_batch_with_unresolvable_ers_fails_loudly(client, db, monkeypatch):
    """Neither package nor sheet resolves -> loud 400, zero silent grounding."""
    project_id = _create_project(client)
    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches",
        json={
            "ers_package_id": "no-such-sheet-or-package",
            "shot_requests_raw": "Korri close-up",
            "output_count": 1,
        },
    )
    assert res.status_code == 400, res.text
    assert "Environment Reference Sheet" in res.json()["detail"]
    assert captured == []


def test_regenerate_shot_with_sheet_id_compiles_with_grounding(client, db, monkeypatch):
    """Legacy batch records storing the sheetId regenerate with ERS grounding (CDX-034)."""
    project_id = _create_project(client)
    scene_id = _first_scene(client, project_id)
    sheet = _save_sheet(project_id, approved_north="asset-north", scene_id=scene_id)
    package = _save_grounded_package(db, project_id, sheet.sheetId)

    # Legacy record: ers_package_id holds the creator-facing sheetId.
    batch = _seed_batch(db, project_id, ers_package_id=sheet.sheetId, result_asset_ids=["job-0"])

    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/regenerate-shot",
        json={"shot_index": 0, "new_prompt": "Korri medium shot"},
    )
    assert res.status_code == 200, res.text
    assert len(captured) == 1
    body = captured[0]["body"]
    assert body["creativeContext"]["ersPackageId"] == package.id
    assert "Character: Korri" in body["prompt"]


def test_regenerate_shot_unresolvable_ers_fails_loudly(client, db, monkeypatch):
    project_id = _create_project(client)
    batch = _seed_batch(db, project_id, ers_package_id="missing-sheet", result_asset_ids=["job-0"])
    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    res = client.post(
        f"/api/scene-creator/projects/{project_id}/batches/{batch.id}/regenerate-shot",
        json={"shot_index": 0, "new_prompt": "Korri medium shot"},
    )
    assert res.status_code == 400, res.text
    assert "Environment Reference Sheet" in res.json()["detail"]
    assert captured == []


# ---------------------------------------------------------------------------
# CDX-034 ERS sheetId grounding on the scene.generate handler
# ---------------------------------------------------------------------------


def test_scene_generate_handler_resolves_sheet_id(monkeypatch, db):
    from app.codirector.capabilities.handlers.scene_generate import handle

    project_id = _create_project_row(db)
    sheet = _save_sheet(project_id, approved_north="asset-north")
    package = _save_grounded_package(db, project_id, sheet.sheetId)

    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    result = handle(
        db,
        project_id,
        "exec-1",
        ers_package_id=sheet.sheetId,
        shot_requests_raw="Korri close-up",
        output_count=1,
    )
    assert len(captured) == 1
    assert result["ers_package_id"] == package.id
    body = captured[0]["body"]
    assert body["creativeContext"]["ersPackageId"] == package.id
    assert "Character: Korri" in body["prompt"]


def test_scene_generate_handler_unresolvable_ers_fails_loudly(monkeypatch, db):
    from app.codirector.capabilities.handlers.scene_generate import handle

    project_id = _create_project_row(db)
    captured: list[dict] = []
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue(captured))

    with pytest.raises(ErsResolveError, match="not found"):
        handle(
            db,
            project_id,
            "exec-1",
            ers_package_id="no-such-sheet",
            shot_requests_raw="Korri close-up",
            output_count=1,
        )
    assert captured == []


def test_scene_generate_handler_empty_ers_fails_loudly(monkeypatch, db):
    from app.codirector.capabilities.handlers.scene_generate import handle

    project_id = _create_project_row(db)
    with pytest.raises(ErsResolveError, match="Select an Environment Reference Sheet"):
        handle(
            db,
            project_id,
            "exec-1",
            ers_package_id="",
            shot_requests_raw="Korri close-up",
            output_count=1,
        )

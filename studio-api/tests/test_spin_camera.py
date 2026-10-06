from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.db import Asset, Job, SessionLocal, init_db
from app.spatial_map.schemas import SpatialMapDocument
from app.spatial_map.spin_camera import (
    DIRECTIONS,
    DIRECTION_YAW,
    SPIN_CATEGORY,
    _SpinPackageManifest,
    center_status,
    compile_spin_prompt,
)


def _create_project_and_map(client, *, with_atlas: bool = True):
    res = client.post("/api/projects", json={"name": "Spin Camera Test", "global_prompt": "test"})
    assert res.status_code == 200
    project = res.json()
    project_id = project["id"]
    scene_id = project["scenes"][0]["id"]
    atlas_id = f"atlas-{uuid.uuid4()}"
    body = {"title": "Spin Map", "sceneId": scene_id}
    if with_atlas:
        body["backgroundAssetId"] = atlas_id
    res = client.post(f"/api/spatial-map/projects/{project_id}/maps", json=body)
    assert res.status_code == 200
    map_id = res.json()["document"]["id"]
    return project_id, map_id, scene_id, atlas_id


def _patch_provider_card(monkeypatch):
    def fake_card(provider_id: str):
        return {
            "providerId": provider_id,
            "apiKeyStatus": {"configured": True},
            "executableCapabilities": ["image_to_image", "image_editing"],
        }

    monkeypatch.setattr("app.spatial_map.spin_camera.provider_card", fake_card)


def _patch_schedule_enqueue(monkeypatch):
    monkeypatch.setattr("app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue", lambda job_id: None)


def _place_spin_camera(client, project_id: str, map_id: str, x: float = 0.0, z: float = 0.0):
    res = client.put(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-camera",
        json={"x": x, "z": z},
    )
    assert res.status_code == 200
    return res.json()


def _make_asset(project_id: str, atlas_id: str) -> str:
    """Create a real 1x1 PNG asset in the test data dir."""
    from app.config import settings

    init_db()
    db = SessionLocal()
    try:
        dest = Path(settings.data_dir) / "projects" / project_id / "assets"
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{atlas_id}.png"
        # Minimal PNG via Pillow if available; otherwise create a tiny placeholder file.
        try:
            from PIL import Image

            img = Image.new("RGB", (64, 64), color=(128, 128, 128))
            img.save(path)
        except Exception:
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
        asset = Asset(
            id=atlas_id,
            project_id=project_id,
            tag="atlas_shot",
            kind="image",
            filename=path.name,
            path=str(path),
        )
        db.add(asset)
        db.commit()
        return atlas_id
    finally:
        db.close()


def test_center_status_centered():
    doc = SpatialMapDocument(projectId="p", widthMeters=10.0, depthMeters=10.0)
    placement = doc.spinCamera or type("P", (), {"x": 0.0, "z": 0.0, "cameraHeight": 1.6})()
    placement.x = 0.0
    placement.z = 0.0
    result = center_status(doc, placement)
    assert result["centered"] is True
    assert result["distanceMeters"] == 0.0
    assert result["toleranceMeters"] == 0.75


def test_center_status_not_centered():
    doc = SpatialMapDocument(projectId="p", widthMeters=10.0, depthMeters=10.0)
    placement = type("P", (), {"x": 0.0, "z": 0.0, "cameraHeight": 1.6})()
    placement.x = 2.0
    placement.z = 2.0
    result = center_status(doc, placement)
    assert result["centered"] is False
    assert round(result["distanceMeters"], 2) == 2.83


def test_compile_spin_prompt_all_directions():
    doc = SpatialMapDocument(projectId="p", backgroundAssetId="atlas-1")
    placement = type("P", (), {"x": 1.0, "z": -2.0, "cameraHeight": 1.6})()
    for direction in DIRECTIONS:
        prompt = compile_spin_prompt(doc, placement, direction)
        assert direction.upper() in prompt
        assert "preserve exact environment identity" in prompt
        assert "Do not redesign the room" in prompt
        assert "Do not add people" in prompt
        assert "<Picture" not in prompt  # no MiniMax syntax in neutral template
        if direction == "center":
            assert "establishing perspective" in prompt
        else:
            assert "Direction:" in prompt


def test_put_and_get_spin_camera(client):
    project_id, map_id, _scene_id, _atlas_id = _create_project_and_map(client)
    put = _place_spin_camera(client, project_id, map_id, x=0.5, z=-0.25)
    assert put["placement"]["x"] == 0.5
    assert put["placement"]["z"] == -0.25
    assert put["centerStatus"]["centered"] is True

    res = client.get(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-camera")
    assert res.status_code == 200
    body = res.json()
    assert body["exists"] is True
    assert body["placement"]["x"] == 0.5

    res = client.delete(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-camera")
    assert res.status_code == 200
    res = client.get(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-camera")
    assert res.json()["exists"] is False


def test_create_package_missing_atlas(client):
    project_id, map_id, _scene_id, _atlas_id = _create_project_and_map(client, with_atlas=False)
    _place_spin_camera(client, project_id, map_id)
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    assert res.status_code == 400
    assert "background atlas" in res.json()["detail"].lower()


def test_create_package_unconfigured_provider(client):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    assert res.status_code == 400
    assert "not connected" in res.json()["detail"].lower()


def test_create_package_missing_confirm_paid(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": False},
    )
    assert res.status_code == 402
    detail = res.json()["detail"]
    assert "confirm" in detail.lower() and "paid" in detail.lower()


def test_create_package_success(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id, x=0.0, z=0.0)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    assert res.status_code == 200
    manifest = res.json()
    assert manifest["version"] == 1
    assert manifest["provider"] == "gpt-image-2-fal"
    assert manifest["spatialMapAssetId"] == atlas_id
    assert set(manifest["views"].keys()) == set(DIRECTIONS)
    for view in manifest["views"].values():
        assert view["status"] == "queued"
        assert view["jobId"]

    # Jobs were created in the DB.
    init_db()
    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.project_id == project_id, Job.kind == "imagegen").all()
        assert len(jobs) == 5
    finally:
        db.close()


def test_lazy_reconciliation_done_and_failed(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    manifest = res.json()
    package_id = manifest["spinPackageId"]
    job_ids = {d: manifest["views"][d]["jobId"] for d in DIRECTIONS}

    # Simulate completions in the DB.
    init_db()
    db = SessionLocal()
    try:
        for direction in DIRECTIONS:
            job = db.get(Job, job_ids[direction])
            assert job is not None
            if direction == "center":
                asset_id = f"asset-center-{uuid.uuid4()}"
                _make_asset(project_id, asset_id)
                job.status = "done"
                params = json.loads(job.params_json or "{}")
                params["output_asset_id"] = asset_id
                job.params_json = json.dumps(params)
            elif direction == "north":
                job.status = "failed"
                job.message = "hosted provider error"
            else:
                job.status = "generating"
        db.commit()
    finally:
        db.close()

    res = client.get(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages/{package_id}"
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["views"]["center"]["status"] == "done"
    assert updated["views"]["center"]["assetId"].startswith("asset-center-")
    assert updated["views"]["north"]["status"] == "failed"
    assert "hosted provider error" in updated["views"]["north"]["error"]
    assert updated["ersStale"] is True


def test_regenerate_direction_preserves_others(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    manifest = res.json()
    package_id = manifest["spinPackageId"]

    # Mark east as done with a fake asset id.
    init_db()
    db = SessionLocal()
    try:
        east_job = db.get(Job, manifest["views"]["east"]["jobId"])
        asset_id = f"asset-east-{uuid.uuid4()}"
        _make_asset(project_id, asset_id)
        east_job.status = "done"
        params = json.loads(east_job.params_json or "{}")
        params["output_asset_id"] = asset_id
        east_job.params_json = json.dumps(params)
        db.commit()
    finally:
        db.close()

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages/{package_id}/views/east/regenerate",
        json={"confirmPaidCloud": True},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["views"]["east"]["status"] == "queued"
    assert updated["ersStale"] is True
    # Other directions still reflect the original manifest (not yet reconciled in this request).
    for d in DIRECTIONS:
        if d != "east":
            assert updated["views"][d]["jobId"] == manifest["views"][d]["jobId"]


def test_version_bump(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    for expected_version in (1, 2):
        res = client.post(
            f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
            json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
        )
        assert res.status_code == 200
        assert res.json()["version"] == expected_version


def test_build_ers_missing_view_400(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    package_id = res.json()["spinPackageId"]
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages/{package_id}/build-ers"
    )
    assert res.status_code == 400
    body = res.json()
    assert "missing" in body["detail"]
    assert set(body["detail"]["missing"]) == set(DIRECTIONS)


def test_build_ers_success(client, monkeypatch):
    project_id, map_id, _scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)
    _place_spin_camera(client, project_id, map_id)
    _patch_provider_card(monkeypatch)
    _patch_schedule_enqueue(monkeypatch)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages",
        json={"provider": "gpt-image-2-fal", "confirmPaidCloud": True},
    )
    manifest = res.json()
    package_id = manifest["spinPackageId"]

    init_db()
    db = SessionLocal()
    try:
        for direction in DIRECTIONS:
            job = db.get(Job, manifest["views"][direction]["jobId"])
            asset_id = f"asset-{direction}-{uuid.uuid4()}"
            _make_asset(project_id, asset_id)
            job.status = "done"
            params = json.loads(job.params_json or "{}")
            params["output_asset_id"] = asset_id
            job.params_json = json.dumps(params)
        db.commit()
    finally:
        db.close()

    # Patch the heavy ERS composer so the test stays fast and deterministic.
    def fake_recompose(db, project_id, *, execution_id, package, sheet, spatial_document, scene_id):
        return {
            "ers_composite_asset_id": "ers-composite-1",
            "machineJsonAssetId": "machine-json-1",
        }

    monkeypatch.setattr("app.spatial_map.spin_camera.recompose_ers_package", fake_recompose)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages/{package_id}/build-ers"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ers_composite_asset_id"] == "ers-composite-1"
    assert body["package_id"] == package_id

    # Manifest is now reconciled and stale cleared.
    res = client.get(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/spin-packages/{package_id}"
    )
    assert res.json()["ersStale"] is False


def test_codirector_handler_smoke(client, monkeypatch):
    project_id, map_id, scene_id, atlas_id = _create_project_and_map(client)
    _make_asset(project_id, atlas_id)

    # Place via Co-Director proposal/approve path.
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": "spatial.place_spin_camera", "arguments": {"documentId": map_id, "x": 0.1, "z": -0.1, "sceneId": scene_id}},
    )
    assert res.status_code == 200
    proposal_id = res.json()["id"]
    res = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve", json={})
    assert res.status_code == 200

    # Read via Co-Director tool.
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": "spatial.get_spin_camera", "arguments": {"documentId": map_id}},
    )
    assert res.status_code == 200
    result = res.json()["result"]["data"]
    assert result["exists"] is True
    assert result["placement"]["x"] == 0.1

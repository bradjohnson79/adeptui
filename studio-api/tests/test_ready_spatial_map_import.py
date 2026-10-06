"""Ready Spatial Map import must never enqueue image generation."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from app.codirector.capabilities.registry import get_capability
from app.codirector.routing.atlas_intent import atlas_capability_for_message


def _floorplan_png() -> bytes:
    size = 128
    arr = np.full((size, size, 3), 210, dtype=np.uint8)
    for i in range(0, size, 16):
        arr[i : i + 2, :, :] = 40
        arr[:, i : i + 2, :] = 40
    arr[40:88, 40:88, :] = 90
    buf = BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _create_project(client, name: str = "Ready Spatial Map Import") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, project_id: str, png: bytes, tag: str = "atlas_shot") -> str:
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": (f"{tag}.png", png, "image/png")},
        data={"tag": tag, "kind": "image"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_atlas_assign_is_registered() -> None:
    cap = get_capability("atlas.assign")
    assert cap is not None
    assert cap.surface_type == "atlas_assign"


def test_assign_phrases_are_not_generate() -> None:
    assert atlas_capability_for_message("Upload this as the Spatial Map.") == "atlas.assign"
    assert atlas_capability_for_message("Use this map for the Venture.") == "atlas.assign"
    assert atlas_capability_for_message("Create an Atlas Shot from this.") == "atlas.generate"


def test_classify_assign_never_returns_generate(client) -> None:
    project_id = _create_project(client, "Classify Assign")
    asset_id = _upload(client, project_id, _floorplan_png())
    classified = client.post(
        f"/api/spatial-map/projects/{project_id}/atlas-source/classify",
        json={"assetId": asset_id, "intendedRoute": "assign"},
    )
    assert classified.status_code == 200, classified.text
    body = classified.json()
    assert body["action"] == "assign"
    assert body["action"] != "generate"
    assert body["pixelsRead"] is True


def test_ready_map_execution_does_not_queue_image_job(client) -> None:
    project_id = _create_project(client)
    asset_id = _upload(client, project_id, _floorplan_png())
    started = client.post(
        f"/api/codirector/projects/{project_id}/executions",
        json={
            "capability": "atlas.assign",
            "prompt": "Use this as the Spatial Map.",
            "attachment_asset_ids": [asset_id],
            "context": {
                "attachment_asset_ids": [asset_id],
                "attachmentAssetIds": [asset_id],
                "prompt": "Use this as the Spatial Map.",
            },
        },
    )
    assert started.status_code == 200, started.text
    plan = started.json()
    assert plan.get("capability") == "atlas.assign"
    assert plan.get("status") == "completed", plan
    assert asset_id in (plan.get("result_asset_ids") or [])
    assert plan.get("surface_type") == "atlas_assign"
    metadata = ((plan.get("child_jobs") or [{}])[0] or {}).get("metadata") or {}
    assert metadata.get("assigned_existing") is True
    assert metadata.get("auto_routed_from_assign") is False
    assert metadata.get("pixels_unchanged") is True

    maps = client.get(f"/api/spatial-map/projects/{project_id}/maps")
    assert maps.status_code == 200, maps.text
    docs = maps.json().get("documents") or []
    assert docs, maps.text
    assert docs[0]["backgroundAssetId"] == asset_id
    assert docs[0].get("geometrySource") == "supplied"


def _seed_character(project_id: str, character_id: str, name: str) -> None:
    from app.character_identity.models import CharacterProfileRow
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        existing = db.get(CharacterProfileRow, character_id)
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=name))
        db.commit()
    finally:
        db.close()


def test_codirector_references_ready_map_placements_without_generating(client) -> None:
    from app.codirector.production_state.snapshot import render_production_snapshot_block
    from app.codirector.project_grounding import grounding_reply, inspect_turn_grounding
    from app.db import SessionLocal, init_db

    project_id = _create_project(client, "Ready Map Grounding")
    asset_id = _upload(client, project_id, _floorplan_png())
    assign = client.post(
        f"/api/codirector/projects/{project_id}/executions",
        json={
            "capability": "atlas.assign",
            "prompt": "Upload this as the Spatial Map.",
            "attachment_asset_ids": [asset_id],
            "context": {"attachment_asset_ids": [asset_id], "prompt": "Upload this as the Spatial Map."},
        },
    )
    assert assign.status_code == 200, assign.text
    document_id = (assign.json().get("plan_data") or {}).get("spatial_map_id")
    if not document_id:
        maps = client.get(f"/api/spatial-map/projects/{project_id}/maps")
        document_id = (maps.json().get("documents") or [{}])[0].get("id")
    assert document_id

    _seed_character(project_id, "char-korri", "Korri")
    placed = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "char-korri", "label": "Korri", "x": 2.0, "z": 1.0},
    )
    assert placed.status_code == 200, placed.text
    crate = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Corridor crate", "x": 0.5, "z": 0.5},
    )
    assert crate.status_code == 200, crate.text
    camera = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
        json={"label": "C1 Mid Shot", "orientation": "S", "x": 2.5, "y": 1.6, "z": 1.6},
    )
    assert camera.status_code == 200, camera.text

    init_db()
    db = SessionLocal()
    try:
        inspect = inspect_turn_grounding(
            db,
            project_id,
            None,
            "Where is Korri on the Spatial Map?",
            workspace="spatial",
        )
        spatial = (inspect.get("snapshot") or {}).get("spatialMap") or {}
        assert spatial.get("hasMap") is True
        assert spatial.get("geometrySource") == "supplied"
        assert spatial.get("backgroundAssetId") == asset_id
        assert spatial.get("pixelsUnchanged") is True
        labels = {item.get("label") for item in (spatial.get("characters") or [])}
        assert "Korri" in labels
        reply = grounding_reply(inspect, "Where is Korri on the Spatial Map?")
        assert reply is not None
        assert "Korri" in reply
        assert "Corridor crate" in reply
        assert "C1 Mid Shot" in reply
        assert "not regenerated" in reply.lower() or "as-is" in reply.lower()
        assert grounding_reply(inspect, "Put Korri here.") is None
        assert grounding_reply(inspect, "Camera 1 here, facing down the corridor.") is None
        block = render_production_snapshot_block(db, project_id)
        assert "Korri" in block
        assert "Corridor crate" in block
        assert "C1 Mid Shot" in block
    finally:
        db.close()

    chat = client.post(
        "/api/codirector/chat",
        json={
            "project_id": project_id,
            "workspaceTab": "spatial",
            "mode": "chat",
            "messages": [
                {
                    "role": "user",
                    "content": "Where are Korri, the corridor crate, and Camera 1 on the Spatial Map?",
                }
            ],
        },
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert "Korri" in (body.get("reply") or "")
    assert body.get("proposal") is None
    jobs = client.get(f"/api/projects/{project_id}/jobs")
    assert jobs.status_code == 200, jobs.text
    kinds = [job.get("kind") for job in (jobs.json() or [])]
    assert "imagegen" not in kinds

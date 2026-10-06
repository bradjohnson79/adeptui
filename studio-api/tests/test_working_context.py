"""Sanitation Phase 1 — Working Context, confidence, confirmation memory."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.codirector.production_state.confidence import compile_confidence
from app.codirector.production_state.working_context import (
    WORKING_CONTEXT_SCHEMA,
    SceneSlice,
    empty_working_context,
)


def _project(client, name: str = "Working Context Cert") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Sanitation Phase 1."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_working_context_get_patch_roundtrip(client) -> None:
    project_id = _project(client)
    got = client.get(f"/api/codirector/projects/{project_id}/working-context")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["documentSchema"] == WORKING_CONTEXT_SCHEMA
    assert body["activeProjectId"] == project_id

    patched = client.patch(
        f"/api/codirector/projects/{project_id}/working-context",
        json={
            "activeSceneId": "scene-schnick",
            "scene": {"sceneId": "scene-schnick", "name": "Schnick Coffee", "approved": True},
            "performance": {"intent": "relaxed standing", "posePresetId": "neutral-relaxed"},
        },
    )
    assert patched.status_code == 200, patched.text
    again = client.get(f"/api/codirector/projects/{project_id}/working-context")
    data = again.json()
    assert data["activeSceneId"] == "scene-schnick"
    assert data["scene"]["name"] == "Schnick Coffee"
    assert data["performance"]["posePresetId"] == "neutral-relaxed"


def test_working_context_is_project_isolated(client) -> None:
    a = _project(client, "WC A")
    b = _project(client, "WC B")
    client.patch(
        f"/api/codirector/projects/{a}/working-context",
        json={"activeSceneId": "only-a"},
    )
    other = client.get(f"/api/codirector/projects/{b}/working-context").json()
    assert other["activeSceneId"] != "only-a"
    missing = client.get("/api/codirector/projects/not-a-real-project/working-context")
    assert missing.status_code == 404


def test_confidence_high_camera_only() -> None:
    ctx = empty_working_context("p1")
    ctx.activeSceneId = "s1"
    ctx.scene = SceneSlice(sceneId="s1", name="Schnick Coffee", approved=True)
    state = compile_confidence(
        ctx,
        "Give me a full close-up on Korri. High angle, 20 degrees.",
        candidate_scene_ids=["s1"],
        candidate_character_ids=["korri"],
        has_crs=True,
        has_spatial_map=True,
    )
    assert state.level == "HIGH"
    assert "camera" in state.changing
    assert "scene" in state.locked
    assert not state.asked


def test_confidence_medium_two_scenes_then_confirm(client) -> None:
    project_id = _project(client, "WC Medium")
    first = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={
            "instruction": "Give me a close-up of Korri.",
            "characterId": "korri",
            "candidateSceneIds": ["schnick", "meadow"],
            "candidateCharacterIds": ["korri"],
        },
    )
    assert first.status_code == 200, first.text
    conf = first.json()["confidence"]
    assert conf["level"] == "MEDIUM"
    assert conf["asked"] is True
    assert conf["question"]

    yes = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={"instruction": "Yes.", "characterId": "korri"},
    )
    assert yes.status_code == 200, yes.text
    bound = yes.json()["confidence"]
    assert bound["level"] == "HIGH"
    assert bound["asked"] is False
    stored = client.get(f"/api/codirector/projects/{project_id}/working-context").json()
    assert stored["confirmations"]
    assert stored["confirmations"][-1]["resolved"] is True
    assert stored["confirmations"][-1]["originalInstruction"]


def test_apply_instruction_keeps_active_scene_for_camera_followup(client) -> None:
    project_id = _project(client, "WC Followup")
    client.patch(
        f"/api/codirector/projects/{project_id}/working-context",
        json={
            "activeSceneId": "schnick",
            "scene": {"sceneId": "schnick", "name": "Schnick Coffee", "approved": True},
        },
    )
    res = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={"instruction": "Give me a close-up of Korri. High angle, 20 degrees."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["confidence"]["level"] == "HIGH"
    assert res.json()["confidence"]["asked"] is False


def test_confidence_low_without_scene() -> None:
    ctx = empty_working_context("p1")
    state = compile_confidence(ctx, "Make a shot.", has_crs=False, has_spatial_map=False)
    assert state.level == "LOW"
    assert state.asked is True


def test_approval_persists(client) -> None:
    project_id = _project(client, "WC Approve")
    res = client.post(
        f"/api/codirector/projects/{project_id}/working-context/approvals",
        json={"what": "image", "assetId": "asset-1", "characterId": "korri"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["scene"]["approved"] is True
    assert body["approvals"][-1]["what"] == "image"


def test_diagnostics_are_not_empty(client) -> None:
    project_id = _project(client, "WC Diag")
    res = client.get(f"/api/codirector/projects/{project_id}/working-context/diagnostics")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["activeProjectId"] == project_id
    assert data["confidence"] == "LOW"
    assert "resolvedFigureIds" in data
    assert "poseWorldStatePacketIds" in data


def test_patch_cannot_forge_confidence_or_approvals(client) -> None:
    project_id = _project(client, "WC Forge")
    forged = client.patch(
        f"/api/codirector/projects/{project_id}/working-context",
        json={
            "confidence": {"level": "HIGH", "reasons": ["forged"], "asked": False},
            "approvals": [{"what": "image", "source": "forged"}],
            "confirmations": [{"originalInstruction": "forged", "resolved": True}],
            "activeSceneId": "allowed",
        },
    )
    assert forged.status_code == 200, forged.text
    body = forged.json()
    assert body["activeSceneId"] == "allowed"
    assert body["confidence"]["level"] != "HIGH" or "forged" not in (body["confidence"].get("reasons") or [])
    assert not any(a.get("source") == "forged" for a in (body.get("approvals") or []))
    assert not any(
        c.get("originalInstruction") == "forged" for c in (body.get("confirmations") or [])
    )


def test_confirmation_survives_reassemble_like_api_restart(client) -> None:
    """Persisted confirmations must come back from the column, not chat history."""
    project_id = _project(client, "WC Restart")
    first = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={
            "instruction": "Give me a close-up of Korri.",
            "candidateSceneIds": ["schnick", "meadow"],
            "candidateCharacterIds": ["korri"],
        },
    )
    assert first.status_code == 200, first.text
    client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={"instruction": "Yes."},
    )
    client.post(
        f"/api/codirector/projects/{project_id}/working-context/approvals",
        json={"what": "image", "assetId": "asset-restart", "characterId": "korri"},
    )
    again = client.get(f"/api/codirector/projects/{project_id}/working-context").json()
    assert again["confirmations"][-1]["resolved"] is True
    assert again["confirmations"][-1]["originalInstruction"]
    assert again["approvals"][-1]["what"] == "image"
    assert again["approvals"][-1]["assetId"] == "asset-restart"


def test_concurrent_posecraft_proposals_do_not_hang(client) -> None:
    """Root-cause sanitation: local PoseCraft proposes must not wait on GPU snapshots."""
    project_id = _project(client, "WC Concurrent")
    scene = {
        "schemaVersion": 1,
        "currentScene": {
            "schemaVersion": 1,
            "revision": 1,
            "updatedAt": "",
            "name": "Load",
            "notes": "",
            "stage": {"gridSize": 12, "showAxes": True, "showPrimitives": True},
            "camera": {
                "lensMm": 35, "aspect": "16:9", "guides": ["safe"],
                "alpha": -1.57, "beta": 1.12, "radius": 7.5,
                "target": {"x": 0, "y": 1.2, "z": 0},
            },
            "figures": [
                {
                    "id": "fig-a", "name": "A", "archetypeId": "adult-female",
                    "colorId": "teal", "position": {"x": 0, "z": 0}, "rotationY": 0,
                    "scale": 1.0, "pose": {},
                }
            ],
            "primitives": [],
            "selectedId": "fig-a",
            "creatorModified": False,
        },
    }
    put = client.put(f"/api/posecraft/projects/{project_id}/scene", json=scene)
    assert put.status_code == 200, put.text

    def propose(_i: int):
        return client.post(
            f"/api/codirector/projects/{project_id}/tools/proposals",
            json={
                "toolId": "posecraft.apply_pose",
                "arguments": {"figureId": "fig-a", "posePresetId": "action-strike"},
            },
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(propose, i) for i in range(8)]
        results = [f.result(timeout=8) for f in as_completed(futures, timeout=10)]
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()["id"] for r in results}) == 8


def test_working_context_reassembles_from_column_without_api_bounce(client) -> None:
    """API restart recovery: a new Session + assemble() reads the column.

    Does not bounce live :8758. Proves confirmation memory is not chat history.
    """
    from app.codirector.production_state.working_context_service import assemble, load_persisted
    from app.db import Project, SessionLocal

    project_id = _project(client, "WC Reassemble")
    first = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={
            "instruction": "Give me a close-up of Korri.",
            "candidateSceneIds": ["schnick", "meadow"],
            "candidateCharacterIds": ["korri"],
        },
    )
    assert first.status_code == 200, first.text
    yes = client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={"instruction": "Yes."},
    )
    assert yes.status_code == 200, yes.text
    client.post(
        f"/api/codirector/projects/{project_id}/working-context/approvals",
        json={"what": "image", "assetId": "asset-reassemble", "characterId": "korri"},
    )

    db = SessionLocal()
    try:
        row = db.get(Project, project_id)
        assert row is not None
        raw = row.working_context_json or ""
        assert "close-up" in raw
        assert "resolved" in raw
        persisted = load_persisted(db, project_id)
        assert persisted.confirmations[-1].resolved is True
        assert persisted.confirmations[-1].originalInstruction
        assert persisted.approvals[-1].assetId == "asset-reassemble"
        reassembled = assemble(db, project_id)
        assert reassembled.activeProjectId == project_id
        assert reassembled.confirmations[-1].resolved is True
        assert reassembled.approvals[-1].what == "image"
    finally:
        db.close()

    got = client.get(f"/api/codirector/projects/{project_id}/working-context").json()
    assert got["confirmations"][-1]["resolved"] is True
    assert got["confirmations"][-1]["originalInstruction"]
    assert got["approvals"][-1]["assetId"] == "asset-reassemble"


def test_working_context_reload_keeps_high_confirmation(client) -> None:
    """Reload analog: GET after confirmation must not re-ask."""
    project_id = _project(client, "WC Reload")
    client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={
            "instruction": "Give me a close-up of Korri.",
            "candidateSceneIds": ["schnick", "meadow"],
            "candidateCharacterIds": ["korri"],
        },
    )
    client.post(
        f"/api/codirector/projects/{project_id}/working-context/compile-confidence",
        json={"instruction": "Yes."},
    )
    first = client.get(f"/api/codirector/projects/{project_id}/working-context").json()
    second = client.get(f"/api/codirector/projects/{project_id}/working-context").json()
    assert first["confirmations"][-1]["resolved"] is True
    assert second["confirmations"][-1]["resolved"] is True
    assert second["confirmations"][-1]["originalInstruction"] == first["confirmations"][-1]["originalInstruction"]
    assert second["confidence"]["asked"] is False


def test_posecraft_slice_reads_selected_snapshot_image_asset(client) -> None:
    """PoseCraft Slice must expose the SELECTED Snapshot's Library PNG.

    Regression: the slice previously read a non-existent ``snapshotAssetId``
    key, so Co-Director handoffs always carried an empty asset. The snapshot
    contract stores the PNG as ``imageAssetId`` on ``doc.snapshots`` keyed by
    ``selectedSnapshotId``.
    """
    from app.codirector.production_state.posecraft_slice import build_posecraft_slice
    from app.db import SessionLocal

    project_id = _project(client, "PoseCraft Slice Asset")
    document = {
        "schemaVersion": 1,
        "currentScene": {
            "schemaVersion": 1,
            "revision": 3,
            "updatedAt": "",
            "name": "Rooftop Standoff",
            "figures": [
                {
                    "id": "fig-1", "name": "Hero", "archetypeId": "adult-male",
                    "colorId": "teal", "position": {"x": 0.0, "z": 0.0}, "rotationY": 0,
                    "scale": 1.0, "pose": {},
                }
            ],
            "primitives": [],
            "camera": {"lensMm": 50, "aspect": "16:9", "guides": [], "alpha": 0, "beta": 1, "radius": 8, "target": {"x": 0, "y": 1, "z": 0}},
        },
        "savedVersions": [],
        "snapshots": [
            {
                "snapshotId": "snap-old", "projectId": project_id, "sceneId": "s1",
                "sceneRevision": 1, "name": "Old", "imageAssetId": "asset-old",
                "camera": {"lensMm": 35, "aspect": "16:9", "guides": [], "alpha": 0, "beta": 1, "radius": 7, "target": {"x": 0, "y": 1, "z": 0}},
                "figures": [], "primitives": [], "customFigures": [],
                "semanticSummary": "", "createdAt": "", "updatedAt": "",
            },
            {
                "snapshotId": "snap-selected", "projectId": project_id, "sceneId": "s1",
                "sceneRevision": 3, "name": "Hero close-up", "imageAssetId": "asset-selected",
                "camera": {"lensMm": 50, "aspect": "16:9", "guides": [], "alpha": 0, "beta": 1, "radius": 8, "target": {"x": 0, "y": 1, "z": 0}},
                "figures": [], "primitives": [], "customFigures": [],
                "semanticSummary": "Hero on the rooftop", "createdAt": "", "updatedAt": "",
            },
        ],
        "selectedSnapshotId": "snap-selected",
    }
    res = client.put(f"/api/posecraft/projects/{project_id}/scene", json=document)
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        slice_ = build_posecraft_slice(db, project_id)
    finally:
        db.close()

    assert slice_.snapshotAssetId == "asset-selected"
    assert slice_.figures[0].snapshotAssetId == "asset-selected"
    assert slice_.revision == 3


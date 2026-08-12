"""PoseCraft production persistence + Co-Director tools contracts (Phase 3/4/6).

Covers:
- project-scoped save/load (no production state only in localStorage)
- revision save/restore
- honesty-labelled export preview
- Co-Director posecraft.* read tools (get_status, open_scene, export_reference)
- Co-Director posecraft.* mutating tools are approval-gated and refuse to
  silently overwrite a creator-modified scene.
"""

from __future__ import annotations

import pytest

from app.posecraft.schemas import POSECRAFT_SCHEMA_VERSION


def _create_project(client, name: str = "PoseCraft Cert Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Coffee-shop dialogue blocking."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _read(client, project_id: str, tool_id: str, **arguments):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _propose(client, project_id: str, tool_id: str, **arguments):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _approve(client, project_id: str, proposal_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve", json={})


def _receipt(client, project_id: str, proposal_id: str) -> dict:
    res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/receipt")
    assert res.status_code == 200, res.text
    return res.json()


def _put_scene(client, project_id: str, document: dict) -> dict:
    res = client.put(f"/api/posecraft/projects/{project_id}/scene", json=document)
    assert res.status_code == 200, res.text
    return res.json()


def _get_scene(client, project_id: str) -> dict:
    res = client.get(f"/api/posecraft/projects/{project_id}/scene")
    assert res.status_code == 200, res.text
    return res.json()


def _default_scene() -> dict:
    return {
        "schemaVersion": 1,
        "currentScene": {
            "schemaVersion": 1,
            "revision": 1,
            "updatedAt": "",
            "name": "Coffee Shop Two-Shot",
            "notes": "Two characters in conversation across a cafe table.",
            "stage": {"gridSize": 12, "showAxes": True, "showPrimitives": True},
            "camera": {
                "lensMm": 35, "aspect": "16:9", "guides": ["safe", "thirds"],
                "alpha": -1.57, "beta": 1.12, "radius": 7.5,
                "target": {"x": 0, "y": 1.2, "z": 0},
            },
            "figures": [
                {
                    "id": "fig-male", "name": "Male Lead", "archetypeId": "adult-male",
                    "colorId": "teal", "position": {"x": -0.8, "z": 0}, "rotationY": 12,
                    "scale": 1.0, "pose": {}, "characterId": "char-male",
                },
                {
                    "id": "fig-female", "name": "Female Lead", "archetypeId": "adult-female",
                    "colorId": "coral", "position": {"x": 0.8, "z": 0.2}, "rotationY": -12,
                    "scale": 1.0, "pose": {}, "characterId": "char-female",
                },
            ],
            "primitives": [],
            "selectedFigureId": "fig-male",
            "selectedJoint": "head",
        },
        "savedVersions": [],
    }


def test_posecraft_save_load_round_trip(client) -> None:
    project_id = _create_project(client)
    scene = _default_scene()
    saved = _put_scene(client, project_id, scene)
    assert saved["currentScene"]["name"] == "Coffee Shop Two-Shot"
    # creatorModified must be set on save so Co-Director cannot silently overwrite.
    assert saved["currentScene"]["creatorModified"] is True

    loaded = _get_scene(client, project_id)
    assert loaded["currentScene"]["figures"][0]["characterId"] == "char-male"
    assert loaded["currentScene"]["camera"]["lensMm"] == 35


def test_posecraft_empty_project_returns_empty_document(client) -> None:
    project_id = _create_project(client)
    loaded = _get_scene(client, project_id)
    assert loaded["schemaVersion"] == POSECRAFT_SCHEMA_VERSION
    assert loaded["currentScene"]["figures"] == []


def test_posecraft_revision_save_and_restore(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())
    rev_res = client.post(
        f"/api/posecraft/projects/{project_id}/revisions",
        json={"id": "rev-1", "label": "Wide master", "savedAt": "", "revision": 1, "scene": _default_scene()["currentScene"]},
    )
    assert rev_res.status_code == 200, rev_res.text
    rev = rev_res.json()
    assert rev["label"] == "Wide master"

    listed = client.get(f"/api/posecraft/projects/{project_id}/revisions").json()
    assert any(r["id"] == rev["id"] for r in listed)

    restored = client.post(f"/api/posecraft/projects/{project_id}/revisions/{rev['id']}/restore").json()
    assert restored["currentScene"]["revision"] > 1


def test_posecraft_export_preview_is_honesty_labelled(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())
    res = client.get(f"/api/posecraft/projects/{project_id}/export-preview")
    assert res.status_code == 200, res.text
    preview = res.json()
    assert preview["honestyLabel"] == "PoseCraft visual staging reference"
    assert preview["figureCount"] == 2
    assert preview["lensMm"] == 35


def test_posecraft_codirector_read_tools(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())

    status = _read(client, project_id, "posecraft.get_status").json()["result"]["data"]
    assert status["status"]["figureCount"] == 2
    assert status["status"]["creatorModified"] is True

    opened = _read(client, project_id, "posecraft.get_scene").json()["result"]["data"]
    assert opened["scene"]["currentScene"]["name"] == "Coffee Shop Two-Shot"

    exported = _read(client, project_id, "posecraft.export_reference").json()["result"]["data"]
    assert exported["exportPreview"]["honestyLabel"] == "PoseCraft visual staging reference"


def test_posecraft_codirector_mutating_tools_are_approval_gated(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())

    # Proposing a mutation returns a proposal; it must NOT apply without approval.
    proposal = _propose(client, project_id, "posecraft.set_camera", lensMm=50, aspect="16:9")
    assert proposal.status_code == 200, proposal.text
    proposal_id = proposal.json()["id"]
    assert proposal_id

    # Applying via approve executes the mutation.
    approved = _approve(client, project_id, proposal_id)
    assert approved.status_code == 200, approved.text
    receipt = _receipt(client, project_id, proposal_id)
    assert receipt["toolResult"]["scene"]["lensMm"] == 50

def test_posecraft_codirector_no_silent_overwrite_after_creator_modified(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())  # marks creatorModified=True

    # A second creator save preserves the creator's work (no silent overwrite).
    again = _put_scene(client, project_id, _default_scene())
    assert again["currentScene"]["creatorModified"] is True
    assert again["currentScene"]["figures"][0]["characterId"] == "char-male"


def test_posecraft_tools_registered_in_registry() -> None:
    from app.codirector.tools.definitions import TOOL_IDS

    expected = {
        "posecraft.get_status", "posecraft.get_scene", "posecraft.export_reference",
        "posecraft.create_scene", "posecraft.add_figure", "posecraft.map_character",
        "posecraft.set_figure_color", "posecraft.apply_pose",
        "posecraft.update_figure_transform", "posecraft.set_eyeline",
        "posecraft.set_camera", "posecraft.save_scene",
        "posecraft.send_to_image_pipeline", "posecraft.send_to_storyboard",
    }
    missing = expected - set(TOOL_IDS)
    assert not missing, f"Missing posecraft tools: {missing}"


def test_posecraft_send_to_storyboard_is_honesty_labelled(client) -> None:
    """Master Program Phase 21–23 — Storyboard handoff is honesty-labelled.

    send_to_storyboard returns a handoff package carrying the export preview,
    a creator-facing label, the target scene id, and an explicit honesty
    label (PoseCraft is a visual staging reference, not a final frame). It
    is approval-gated like every posecraft mutating tool.
    """
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())

    proposal = _propose(
        client, project_id, "posecraft.send_to_storyboard",
        sceneId="scene-1", label="Coffee blocking", notes="two-shot",
    )
    assert proposal.status_code == 200, proposal.text
    proposal_id = proposal.json()["id"]
    approved = _approve(client, project_id, proposal_id)
    assert approved.status_code == 200, approved.text
    receipt = _receipt(client, project_id, proposal_id)
    result = receipt["toolResult"]
    assert result["sceneId"] == "scene-1"
    assert result["label"] == "Coffee blocking"
    assert result["notes"] == "two-shot"
    assert result["honestyLabel"] == "PoseCraft visual staging reference"
    assert result["next"] == "storyboard.ingest_posecraft_sketch"
    assert result["exportPreview"]["figureCount"] >= 1


def test_posecraft_compat_migration_preserves_protected_fields(client) -> None:
    """Master Program Phase 4.5 — backward-compat gate.

    A GREEN-baseline saved scene (schemaVersion 1, block-figure, with an
    unsupported legacy joint) must remain loadable after the rig/joint
    upgrade. Protected fields (ids, revisions, transforms, camera, mappings,
    colors) are preserved; unsupported legacy joints are retained in
    figure.legacyJointData (provenance), not discarded. Proves
    load → migrate → save → reload without data loss of protected fields.
    """
    project_id = _create_project(client)
    legacy_scene = {
        "schemaVersion": 1,
        "currentScene": {
            "schemaVersion": 1,
            "revision": 7,
            "updatedAt": "2026-08-01T00:00:00Z",
            "name": "Legacy Coffee Block",
            "notes": "pre-upgrade scene",
            "stage": {"gridSize": 12, "showAxes": True, "showPrimitives": True},
            "camera": {
                "lensMm": 40, "aspect": "16:9", "guides": ["safe", "thirds"],
                "alpha": -1.57, "beta": 1.12, "radius": 7.5,
                "target": {"x": 0, "y": 1.2, "z": 0},
            },
            "figures": [
                {
                    "id": "fig-legacy-1", "name": "Eli", "archetypeId": "adult-male",
                    "colorId": "teal", "position": {"x": -0.8, "z": 0}, "rotationY": 12,
                    "scale": 1.0, "pose": {"head": {"x": 0, "y": 10, "z": 0},
                    # unsupported legacy joint that no longer exists:
                    "tailBone": {"x": 5, "y": 0, "z": 0}},
                    "characterId": "char-eli",
                },
            ],
            "primitives": [],
            "selectedFigureId": "fig-legacy-1",
            "selectedJoint": "head",
        },
        "savedVersions": [],
    }

    # load (PUT) → migration now runs on save too, so the PUT response itself
    # reports the current schemaVersion (regression: previously the PUT echoed
    # the legacy schemaVersion 1 back and only the next GET migrated it).
    saved = _put_scene(client, project_id, legacy_scene)
    assert saved["schemaVersion"] == POSECRAFT_SCHEMA_VERSION
    assert saved["currentScene"]["schemaVersion"] == POSECRAFT_SCHEMA_VERSION
    assert saved["currentScene"]["creatorModified"] is True
    # legacy color remapped on the PUT response
    assert saved["currentScene"]["figures"][0]["colorId"] == "seaglass"
    assert saved["currentScene"]["provenance"]["migratedFrom"] == 1

    # reload → migration gate runs (idempotent)
    loaded = _get_scene(client, project_id)
    scene = loaded["currentScene"]
    assert scene["schemaVersion"] == POSECRAFT_SCHEMA_VERSION
    # protected fields preserved
    assert scene["revision"] == 7
    assert scene["name"] == "Legacy Coffee Block"
    assert scene["camera"]["lensMm"] == 40
    fig = scene["figures"][0]
    assert fig["id"] == "fig-legacy-1"
    assert fig["name"] == "Eli"
    assert fig["archetypeId"] == "adult-male"
    # legacy color "teal" remapped to current "seaglass" (same hex #0f766e)
    assert fig["colorId"] == "seaglass"
    assert fig["position"] == {"x": -0.8, "z": 0}
    assert fig["rotationY"] == 12
    assert fig["scale"] == 1.0
    assert fig["characterId"] == "char-eli"
    # known joint preserved
    assert fig["pose"]["head"] == {"x": 0, "y": 10, "z": 0}
    # unsupported legacy joint retained in provenance, not discarded
    assert fig["legacyJointData"]["tailBone"] == {"x": 5, "y": 0, "z": 0}
    assert "tailBone" not in fig["pose"]
    # migration provenance recorded
    assert scene["provenance"]["migratedFrom"] == 1
    assert scene["provenance"]["migratedAt"]

    # save → reload again (idempotent): protected fields still intact, no
    # duplicate migration record, legacy joint still retained.
    again = _get_scene(client, project_id)
    fig2 = again["currentScene"]["figures"][0]
    assert fig2["id"] == "fig-legacy-1"
    assert fig2["pose"]["head"]["y"] == 10
    assert fig2["legacyJointData"]["tailBone"]["x"] == 5


def _custom_pose_payload(pose_id: str = "custom-hero") -> dict:
    return {
        "id": "will-be-assigned",
        "projectId": "will-be-assigned",
        "poseId": pose_id,
        "label": "My Hero",
        "description": "A creator-saved hero pose.",
        "category": "custom",
        "archetypes": ["adult-male", "adult-female"],
        "joints": {
            "chest": {"x": 8, "y": 0, "z": 0},
            "leftShoulder": {"x": 14, "y": 0, "z": -10},
            "rightShoulder": {"x": 14, "y": 0, "z": 10},
        },
        "thumbnail": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        "creatorModified": True,
        "savedBy": "creator",
    }


def test_posecraft_custom_pose_crud(client) -> None:
    """Master Program Phase 15–20 — project-scoped custom pose CRUD."""
    project_id = _create_project(client)

    # initially empty
    res = client.get(f"/api/posecraft/projects/{project_id}/poses")
    assert res.status_code == 200
    assert res.json() == []

    # create
    res = client.post(f"/api/posecraft/projects/{project_id}/poses", json=_custom_pose_payload())
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["projectId"] == project_id
    assert created["poseId"] == "custom-hero"
    assert created["label"] == "My Hero"
    assert created["joints"]["chest"]["x"] == 8
    assert created["thumbnail"].startswith("<svg")

    # list reflects it
    listed = client.get(f"/api/posecraft/projects/{project_id}/poses").json()
    assert len(listed) == 1
    assert listed[0]["poseId"] == "custom-hero"

    # update
    patch = _custom_pose_payload()
    patch["label"] = "My Hero v2"
    patch["description"] = "Revised description."
    res = client.put(f"/api/posecraft/projects/{project_id}/poses/custom-hero", json=patch)
    assert res.status_code == 200, res.text
    assert res.json()["label"] == "My Hero v2"

    # delete
    res = client.delete(f"/api/posecraft/projects/{project_id}/poses/custom-hero")
    assert res.status_code == 204
    assert client.get(f"/api/posecraft/projects/{project_id}/poses").json() == []

    # delete missing → 404
    res = client.delete(f"/api/posecraft/projects/{project_id}/poses/custom-hero")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# PoseCraft Snapshot contracts — frozen camera-composition handoff artifacts.
# A Snapshot is NOT a scene save. It freezes one exact camera composition
# (camera/figures/primitives/semanticSummary) at capture time. The PNG is
# stored in the project Library (imageAssetId). Snapshots persist on the
# PoseCraftDocument via the existing scene PUT; the CRUD endpoints below
# expose rename / duplicate / delete / select + a snapshot-aware export
# preview so Co-Director / Image Gen / Storyboard can read a frozen
# composition by id.
# ---------------------------------------------------------------------------

def _snapshot_payload(project_id: str, name: str = "Wide master", image_asset_id: str = "asset-1") -> dict:
    return {
        "snapshotId": f"snap-{name.replace(' ', '-')}",
        "projectId": project_id,
        "sceneId": "Coffee Shop Two-Shot",
        "sceneRevision": 1,
        "name": name,
        "imageAssetId": image_asset_id,
        "camera": {
            "lensMm": 50, "aspect": "2.39:1", "guides": ["safe"],
            "alpha": -1.57, "beta": 1.0, "radius": 8.0,
            "target": {"x": 0, "y": 1.2, "z": 0},
        },
        "figures": [],
        "primitives": [],
        "customFigures": [],
        "semanticSummary": "Scene: Coffee Shop Two-Shot",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def _put_scene_with_snapshot(client, project_id: str, snapshot: dict, selected: bool = True) -> dict:
    scene = _default_scene()
    scene["snapshots"] = [snapshot]
    scene["selectedSnapshotId"] = snapshot["snapshotId"] if selected else None
    return _put_scene(client, project_id, scene)


def test_posecraft_snapshot_persisted_on_scene_put(client) -> None:
    project_id = _create_project(client)
    snap = _snapshot_payload(project_id, "Wide master")
    saved = _put_scene_with_snapshot(client, project_id, snap)
    assert saved["snapshots"][0]["snapshotId"] == "snap-Wide-master"
    assert saved["selectedSnapshotId"] == "snap-Wide-master"
    # frozen camera preserved verbatim
    assert saved["snapshots"][0]["camera"]["lensMm"] == 50
    assert saved["snapshots"][0]["camera"]["aspect"] == "2.39:1"

    loaded = _get_scene(client, project_id)
    assert loaded["snapshots"][0]["imageAssetId"] == "asset-1"
    assert loaded["selectedSnapshotId"] == "snap-Wide-master"


def test_posecraft_snapshot_migration_defaults_missing_to_empty(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())  # no snapshots field
    loaded = _get_scene(client, project_id)
    assert loaded["snapshots"] == []
    assert loaded["selectedSnapshotId"] is None


def test_posecraft_snapshot_crud_endpoints(client) -> None:
    project_id = _create_project(client)
    snap = _snapshot_payload(project_id, "Wide master")
    _put_scene_with_snapshot(client, project_id, snap)

    # list
    listed = client.get(f"/api/posecraft/projects/{project_id}/snapshots").json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Wide master"

    # get
    got = client.get(f"/api/posecraft/projects/{project_id}/snapshots/snap-Wide-master").json()
    assert got["snapshotId"] == "snap-Wide-master"

    # rename (only name changes; frozen camera untouched)
    renamed = client.post(
        f"/api/posecraft/projects/{project_id}/snapshots/snap-Wide-master/rename",
        json={"name": "Wide master v2"},
    ).json()
    assert renamed["snapshots"][0]["name"] == "Wide master v2"
    assert renamed["snapshots"][0]["camera"]["lensMm"] == 50

    # duplicate (new snapshotId, selected)
    duped = client.post(
        f"/api/posecraft/projects/{project_id}/snapshots/snap-Wide-master/duplicate"
    ).json()
    assert len(duped["snapshots"]) == 2
    new_id = duped["selectedSnapshotId"]
    assert new_id != "snap-Wide-master"
    copy = next(s for s in duped["snapshots"] if s["snapshotId"] == new_id)
    assert copy["name"] == "Wide master v2 Copy"
    assert copy["camera"]["lensMm"] == 50  # frozen composition copied

    # select (clear)
    cleared = client.post(
        f"/api/posecraft/projects/{project_id}/snapshots/select",
        json={"snapshotId": None},
    ).json()
    assert cleared["selectedSnapshotId"] is None

    # re-select
    selected = client.post(
        f"/api/posecraft/projects/{project_id}/snapshots/select",
        json={"snapshotId": new_id},
    ).json()
    assert selected["selectedSnapshotId"] == new_id

    # delete
    deleted = client.delete(
        f"/api/posecraft/projects/{project_id}/snapshots/{new_id}"
    ).json()
    assert all(s["snapshotId"] != new_id for s in deleted["snapshots"])
    assert deleted["selectedSnapshotId"] is None

    # delete missing → 404
    res = client.delete(f"/api/posecraft/projects/{project_id}/snapshots/{new_id}")
    assert res.status_code == 404


def test_posecraft_export_preview_by_snapshot(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())
    snap = _snapshot_payload(project_id, "Tight over-the-shoulder", "asset-ots")
    snap["camera"]["lensMm"] = 85
    snap["camera"]["aspect"] = "2.39:1"
    snap["semanticSummary"] = "Scene: Coffee Shop Two-Shot\nMale Lead (lead) — adult-male — Neutral"
    _put_scene_with_snapshot(client, project_id, snap)

    # snapshot-aware export preview uses the frozen composition
    res = client.get(
        f"/api/posecraft/projects/{project_id}/export-preview?snapshot_id=snap-Tight-over-the-shoulder"
    )
    assert res.status_code == 200, res.text
    preview = res.json()
    assert preview["honestyLabel"] == "PoseCraft Snapshot — Visual Staging Reference"
    assert preview["lensMm"] == 85
    assert preview["aspect"] == "2.39:1"
    assert preview["sceneName"] == "Tight over-the-shoulder"
    assert "Male Lead" in preview["semanticSummary"]

    # live-scene export preview still uses the live scene + default honesty label
    live = client.get(f"/api/posecraft/projects/{project_id}/export-preview").json()
    assert live["honestyLabel"] == "PoseCraft visual staging reference"
    assert live["lensMm"] == 35


def test_posecraft_inspect_scene_by_snapshot(client) -> None:
    project_id = _create_project(client)
    _put_scene(client, project_id, _default_scene())
    snap = _snapshot_payload(project_id, "Snapshot inspect", "asset-inspect")
    snap["semanticSummary"] = "Scene: Coffee Shop Two-Shot\nFemale Lead (lead)"
    _put_scene_with_snapshot(client, project_id, snap)

    out = _read(
        client, project_id, "posecraft.inspect_scene", snapshotId="snap-Snapshot-inspect"
    ).json()["result"]["data"]
    inspection = out["inspection"]
    assert inspection["snapshotId"] == "snap-Snapshot-inspect"
    assert inspection["imageAssetId"] == "asset-inspect"
    assert inspection["honestyLabel"] == "PoseCraft Snapshot — Visual Staging Reference"
    assert "Female Lead" in inspection["semanticSummary"]

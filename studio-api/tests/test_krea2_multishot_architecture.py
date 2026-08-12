"""Krea 2 Phase D — Multi-Shot Image Planning architecture tests (no GPU, no queue).

Covers the provider-agnostic plan -> ordered shots -> candidate history data
model, HTTP API, persistence, and project isolation:

- plan creation under a scene, listing, reload persistence
- stable shot UUIDs, ordering, full-set reorder, no arbitrary shot cap
- simulated candidates (fake asset ids — never any generation), approve/reject
  semantics, append-only candidate history
- shot delete keeps siblings; plan delete cascades shots + candidates
- cross-project access is always 404; project deletion sweeps all three tables
- provider-agnostic plans (e.g. provider_id="flux") need no registry entries
"""

from __future__ import annotations

import uuid

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project(client, name: str) -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _first_scene_id(client, project_id: str) -> str:
    res = client.get(f"/api/projects/{project_id}/scenes")
    assert res.status_code == 200, res.text
    scenes = res.json()
    assert scenes, "project creation seeds a default scene"
    return scenes[0]["id"]


def _create_plan(client, project_id: str, scene_id: str, **overrides) -> dict:
    body = {"name": "Scene Decomposition", "providerId": "comfyui", "modelId": "krea2-turbo-local"}
    body.update(overrides)
    res = client.post(f"/api/projects/{project_id}/scenes/{scene_id}/multi-shot-plans", json=body)
    assert res.status_code == 200, res.text
    return res.json()["plan"]


def _get_plan(client, project_id: str, plan_id: str) -> dict:
    res = client.get(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}")
    assert res.status_code == 200, res.text
    return res.json()["plan"]


def _add_shot(client, project_id: str, plan_id: str, **overrides) -> dict:
    body = {"title": "Shot", "prompt": "a quiet shot"}
    body.update(overrides)
    res = client.post(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/shots", json=body)
    assert res.status_code == 200, res.text
    return res.json()["shot"]


def _add_candidate(client, project_id: str, plan_id: str, shot_id: str, **overrides) -> dict:
    body = {"provider": "comfyui", "model": "krea2-turbo-local", "seed": 1234, "assetId": f"asset-{uuid.uuid4().hex[:8]}"}
    body.update(overrides)
    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}/candidates",
        json=body,
    )
    assert res.status_code == 200, res.text
    return res.json()["candidate"]


def _db_counts(project_id: str) -> tuple[int, int, int]:
    from app.db import SessionLocal
    from app.image_pipeline.multi_shot.models import MultiShotCandidateRow, MultiShotPlanRow, MultiShotRow

    session = SessionLocal()
    try:
        plans = session.query(MultiShotPlanRow).filter(MultiShotPlanRow.project_id == project_id).count()
        shots = session.query(MultiShotRow).filter(MultiShotRow.project_id == project_id).count()
        candidates = session.query(MultiShotCandidateRow).filter(MultiShotCandidateRow.project_id == project_id).count()
        return plans, shots, candidates
    finally:
        session.close()


def _assert_uuid(value: str) -> None:
    parsed = uuid.UUID(str(value))
    assert str(parsed) == str(value).lower()


# ---------------------------------------------------------------------------
# Plan lifecycle
# ---------------------------------------------------------------------------


def test_create_plan_persists_and_reloads(client) -> None:
    project_id = _create_project(client, "MultiShot Plan Basics")
    scene_id = _first_scene_id(client, project_id)

    plan = _create_plan(
        client,
        project_id,
        scene_id,
        sharedVisualContext="Overcast coastal town, muted teal palette.",
        sharedReferences=[
            {"role": "style", "assetId": "asset-style-1", "label": "Teal grade"},
            {"role": "character", "assetId": "asset-char-1", "label": "Korri"},
            {"role": "moodboard", "assetId": "asset-mood-1"},
        ],
        aspectRatio="2.39:1",
        resolutionLabel="2K",
    )
    _assert_uuid(plan["planId"])
    assert plan["projectId"] == project_id
    assert plan["sceneId"] == scene_id
    assert plan["providerId"] == "comfyui"
    assert plan["modelId"] == "krea2-turbo-local"
    assert plan["status"] == "draft"
    assert plan["shotCount"] == 0
    assert plan["createdAt"] and plan["updatedAt"]

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert reloaded["sharedVisualContext"].startswith("Overcast coastal town")
    assert len(reloaded["sharedReferences"]) == 3
    # Role-grouped convenience views derive from the single polymorphic list.
    assert [r["label"] for r in reloaded["sharedStyleReferences"]] == ["Teal grade"]
    assert [r["label"] for r in reloaded["sharedCharacterReferences"]] == ["Korri"]
    assert len(reloaded["sharedMoodboardReferences"]) == 1
    assert reloaded["sharedEnvironmentReferences"] == []
    assert reloaded["aspectRatio"] == "2.39:1"
    assert reloaded["resolutionLabel"] == "2K"


def test_list_plans_is_scene_scoped(client) -> None:
    project_id = _create_project(client, "MultiShot List")
    scene_id = _first_scene_id(client, project_id)
    other_scene = client.post(f"/api/projects/{project_id}/scenes", json={"name": "Scene 2"}).json()

    plan_a = _create_plan(client, project_id, scene_id, name="Plan A")
    plan_b = _create_plan(client, project_id, scene_id, name="Plan B")
    _create_plan(client, project_id, other_scene["id"], name="Other Scene Plan")

    res = client.get(f"/api/projects/{project_id}/scenes/{scene_id}/multi-shot-plans")
    assert res.status_code == 200, res.text
    names = {p["name"] for p in res.json()["plans"]}
    assert names == {"Plan A", "Plan B"}
    assert plan_a["planId"] != plan_b["planId"]


def test_update_plan_fields(client) -> None:
    project_id = _create_project(client, "MultiShot Plan Update")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)

    res = client.patch(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}",
        json={
            "name": "Renamed Plan",
            "status": "active",
            "sharedVisualContext": "Night interiors, practical lamps.",
            "sharedReferences": [{"role": "environment", "assetId": "asset-env-9"}],
        },
    )
    assert res.status_code == 200, res.text
    updated = res.json()["plan"]
    assert updated["name"] == "Renamed Plan"
    assert updated["status"] == "active"

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert reloaded["sharedVisualContext"] == "Night interiors, practical lamps."
    assert len(reloaded["sharedEnvironmentReferences"]) == 1
    # Untouched fields survive the patch.
    assert reloaded["providerId"] == "comfyui"
    assert reloaded["modelId"] == "krea2-turbo-local"


def test_plan_accepts_snake_case_payload(client) -> None:
    """DB-style snake_case payloads parse identically to camelCase ones."""
    project_id = _create_project(client, "MultiShot Snake Case")
    scene_id = _first_scene_id(client, project_id)
    res = client.post(
        f"/api/projects/{project_id}/scenes/{scene_id}/multi-shot-plans",
        json={"name": "Snake", "provider_id": "comfyui", "model_id": "zimage-local", "aspect_ratio": "16:9"},
    )
    assert res.status_code == 200, res.text
    plan = res.json()["plan"]
    assert plan["providerId"] == "comfyui"
    assert plan["modelId"] == "zimage-local"
    assert plan["aspectRatio"] == "16:9"


# ---------------------------------------------------------------------------
# Shots: ordering, stability, reorder, caps
# ---------------------------------------------------------------------------


def test_five_shots_have_stable_uuids_and_order(client) -> None:
    project_id = _create_project(client, "MultiShot Five Shots")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)

    created = [
        _add_shot(client, project_id, plan["planId"], title=f"Shot {i}", prompt=f"prompt {i}", framing="wide", cameraAngle="low")
        for i in range(5)
    ]
    ids = [shot["shotId"] for shot in created]
    assert len(set(ids)) == 5
    for shot_id in ids:
        _assert_uuid(shot_id)
    assert [shot["order"] for shot in created] == [0, 1, 2, 3, 4]

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert reloaded["shotCount"] == 5
    assert [shot["shotId"] for shot in reloaded["shots"]] == ids
    assert [shot["order"] for shot in reloaded["shots"]] == [0, 1, 2, 3, 4]
    assert reloaded["shots"][2]["framing"] == "wide"
    assert reloaded["shots"][2]["cameraAngle"] == "low"
    assert reloaded["shots"][0]["status"] == "pending"
    assert reloaded["shots"][0]["seedStrategy"] == "sequence"


def test_reorder_shots_persists_after_reload(client) -> None:
    project_id = _create_project(client, "MultiShot Reorder")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shots = [_add_shot(client, project_id, plan["planId"], title=f"S{i}") for i in range(5)]
    ids = [s["shotId"] for s in shots]

    new_order = [ids[3], ids[1], ids[4], ids[0], ids[2]]
    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/reorder",
        json={"shotIds": new_order},
    )
    assert res.status_code == 200, res.text
    assert [s["shotId"] for s in res.json()["plan"]["shots"]] == new_order
    assert [s["order"] for s in res.json()["plan"]["shots"]] == [0, 1, 2, 3, 4]

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert [shot["shotId"] for shot in reloaded["shots"]] == new_order
    assert [shot["order"] for shot in reloaded["shots"]] == [0, 1, 2, 3, 4]


def test_reorder_rejects_partial_or_foreign_sets(client) -> None:
    project_id = _create_project(client, "MultiShot Reorder Guards")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shots = [_add_shot(client, project_id, plan["planId"], title=f"S{i}") for i in range(3)]
    ids = [s["shotId"] for s in shots]

    missing = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/reorder",
        json={"shotIds": [ids[0], ids[1]]},
    )
    assert missing.status_code == 400

    foreign = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/reorder",
        json={"shotIds": [ids[0], ids[1], str(uuid.uuid4())]},
    )
    assert foreign.status_code == 400

    duplicate = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/reorder",
        json={"shotIds": [ids[0], ids[0], ids[1]]},
    )
    assert duplicate.status_code == 400

    # Failed reorders never disturb the stored order.
    reloaded = _get_plan(client, project_id, plan["planId"])
    assert [shot["shotId"] for shot in reloaded["shots"]] == ids


def test_twenty_five_shots_no_arbitrary_cap(client) -> None:
    project_id = _create_project(client, "MultiShot Capacity")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)

    ids = []
    for i in range(25):
        shot = _add_shot(client, project_id, plan["planId"], title=f"Beat {i:02d}")
        ids.append(shot["shotId"])
    assert len(set(ids)) == 25
    for shot_id in ids:
        _assert_uuid(shot_id)

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert reloaded["shotCount"] == 25
    assert [shot["shotId"] for shot in reloaded["shots"]] == ids
    assert [shot["order"] for shot in reloaded["shots"]] == list(range(25))


def test_update_shot_fields(client) -> None:
    project_id = _create_project(client, "MultiShot Shot Update")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"], title="Original")

    res = client.patch(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}",
        json={
            "title": "Dolly-in on Korri",
            "imagePrompt": "close-up, rain on the window",
            "videoPrompt": "slow dolly, 4 seconds",
            "durationHint": 4.5,
            "framing": "close-up",
            "cameraAngle": "eye-level",
            "subjectIds": ["char-korri"],
            "referenceIds": ["asset-ref-1", "asset-ref-2"],
            "seedStrategy": "fixed",
        },
    )
    assert res.status_code == 200, res.text
    updated = res.json()["shot"]
    assert updated["title"] == "Dolly-in on Korri"
    assert updated["seedStrategy"] == "fixed"

    reloaded = _get_plan(client, project_id, plan["planId"])["shots"][0]
    assert reloaded["imagePrompt"] == "close-up, rain on the window"
    assert reloaded["videoPrompt"] == "slow dolly, 4 seconds"
    assert reloaded["durationHint"] == 4.5
    assert reloaded["subjectIds"] == ["char-korri"]
    assert reloaded["referenceIds"] == ["asset-ref-1", "asset-ref-2"]
    assert reloaded["framing"] == "close-up"


# ---------------------------------------------------------------------------
# Candidates: record, approve, reject, history
# ---------------------------------------------------------------------------


def test_candidate_approve_persists_asset_and_candidate_ids(client) -> None:
    project_id = _create_project(client, "MultiShot Approval")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])

    candidate = _add_candidate(
        client,
        project_id,
        plan["planId"],
        shot["shotId"],
        prompt="final prompt text",
        settings={"steps": 8, "cfg": 0.0, "mu": 1.15},
        references=[{"role": "character", "assetId": "asset-char-1"}],
        loras=[{"name": "korri-identity", "strength": 0.8}],
    )
    _assert_uuid(candidate["candidateId"])
    assert candidate["status"] == "pending"
    assert candidate["settings"]["mu"] == 1.15

    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/approve",
        json={"candidateId": candidate["candidateId"]},
    )
    assert res.status_code == 200, res.text
    approved = res.json()["shot"]
    assert approved["status"] == "approved"
    assert approved["approvedCandidateId"] == candidate["candidateId"]
    assert approved["approvedAssetId"] == candidate["assetId"]

    reloaded = _get_plan(client, project_id, plan["planId"])["shots"][0]
    assert reloaded["approvedCandidateId"] == candidate["candidateId"]
    assert reloaded["approvedAssetId"] == candidate["assetId"]
    statuses = {c["candidateId"]: c["status"] for c in reloaded["candidates"]}
    assert statuses[candidate["candidateId"]] == "approved"


def test_approve_demotes_previous_candidate(client) -> None:
    project_id = _create_project(client, "MultiShot Reapprove")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])
    first = _add_candidate(client, project_id, plan["planId"], shot["shotId"])
    second = _add_candidate(client, project_id, plan["planId"], shot["shotId"])

    for candidate in (first, second):
        res = client.post(
            f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/approve",
            json={"candidateId": candidate["candidateId"]},
        )
        assert res.status_code == 200, res.text

    reloaded = _get_plan(client, project_id, plan["planId"])["shots"][0]
    assert reloaded["approvedCandidateId"] == second["candidateId"]
    statuses = {c["candidateId"]: c["status"] for c in reloaded["candidates"]}
    assert statuses[first["candidateId"]] == "pending"
    assert statuses[second["candidateId"]] == "approved"


def test_rejected_candidate_stays_in_history(client) -> None:
    project_id = _create_project(client, "MultiShot Reject History")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])
    keep = _add_candidate(client, project_id, plan["planId"], shot["shotId"])
    drop = _add_candidate(client, project_id, plan["planId"], shot["shotId"])

    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/reject",
        json={"candidateId": drop["candidateId"]},
    )
    assert res.status_code == 200, res.text

    reloaded = _get_plan(client, project_id, plan["planId"])["shots"][0]
    assert len(reloaded["candidates"]) == 2  # rejection never deletes history
    statuses = {c["candidateId"]: c["status"] for c in reloaded["candidates"]}
    assert statuses[keep["candidateId"]] == "pending"
    assert statuses[drop["candidateId"]] == "rejected"


def test_rejecting_approved_candidate_clears_shot_approval(client) -> None:
    project_id = _create_project(client, "MultiShot Reject Approved")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])
    candidate = _add_candidate(client, project_id, plan["planId"], shot["shotId"])

    client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/approve",
        json={"candidateId": candidate["candidateId"]},
    )
    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/reject",
        json={"candidateId": candidate["candidateId"]},
    )
    assert res.status_code == 200, res.text
    shot_after = res.json()["shot"]
    assert shot_after["approvedCandidateId"] is None
    assert shot_after["approvedAssetId"] is None
    assert shot_after["status"] == "candidate_review"
    assert shot_after["candidates"][0]["status"] == "rejected"


def test_unknown_candidate_action_returns_404(client) -> None:
    project_id = _create_project(client, "MultiShot Unknown Candidate")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])

    for action in ("approve", "reject"):
        res = client.post(
            f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/{action}",
            json={"candidateId": str(uuid.uuid4())},
        )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Deletion semantics
# ---------------------------------------------------------------------------


def test_delete_shot_keeps_siblings(client) -> None:
    project_id = _create_project(client, "MultiShot Delete Shot")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shots = [_add_shot(client, project_id, plan["planId"], title=f"S{i}") for i in range(3)]
    doomed = shots[1]
    _add_candidate(client, project_id, plan["planId"], doomed["shotId"])

    res = client.delete(f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{doomed['shotId']}")
    assert res.status_code == 200, res.text

    reloaded = _get_plan(client, project_id, plan["planId"])
    remaining_ids = [shot["shotId"] for shot in reloaded["shots"]]
    assert remaining_ids == [shots[0]["shotId"], shots[2]["shotId"]]
    assert reloaded["shotCount"] == 2

    gone = client.get(f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}")
    assert gone.status_code == 200
    # The deleted shot's candidates went with it.
    assert _db_counts(project_id) == (1, 2, 0)


def test_delete_plan_cascades_shots_and_candidates(client) -> None:
    project_id = _create_project(client, "MultiShot Delete Plan")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    for i in range(3):
        shot = _add_shot(client, project_id, plan["planId"], title=f"S{i}")
        _add_candidate(client, project_id, plan["planId"], shot["shotId"])
    assert _db_counts(project_id) == (1, 3, 3)

    res = client.delete(f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}")
    assert res.status_code == 200, res.text

    gone = client.get(f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}")
    assert gone.status_code == 404
    assert _db_counts(project_id) == (0, 0, 0)


def test_project_deletion_sweeps_multi_shot_tables(client) -> None:
    project_id = _create_project(client, "MultiShot Project Delete")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id)
    shot = _add_shot(client, project_id, plan["planId"])
    candidate = _add_candidate(client, project_id, plan["planId"], shot["shotId"])
    client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{shot['shotId']}/approve",
        json={"candidateId": candidate["candidateId"]},
    )
    assert _db_counts(project_id) == (1, 1, 1)

    res = client.delete(f"/api/projects/{project_id}")
    assert res.status_code == 200, res.text
    assert _db_counts(project_id) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Project isolation
# ---------------------------------------------------------------------------


def test_cross_project_access_always_404(client) -> None:
    project_a = _create_project(client, "MultiShot Isolation A")
    project_b = _create_project(client, "MultiShot Isolation B")
    scene_a = _first_scene_id(client, project_a)
    scene_b = _first_scene_id(client, project_b)
    plan_a = _create_plan(client, project_a, scene_a, name="A Plan")
    shot_a = _add_shot(client, project_a, plan_a["planId"], title="A Shot")
    candidate_a = _add_candidate(client, project_a, plan_a["planId"], shot_a["shotId"])

    base_b = f"/api/projects/{project_b}/multi-shot-plans/{plan_a['planId']}"
    assert client.get(base_b).status_code == 404
    assert client.patch(base_b, json={"name": "hijack"}).status_code == 404
    assert client.delete(base_b).status_code == 404
    assert client.post(f"{base_b}/shots", json={"title": "hijack"}).status_code == 404
    assert client.post(f"{base_b}/shots/reorder", json={"shotIds": [shot_a["shotId"]]}).status_code == 404
    assert client.patch(f"{base_b}/shots/{shot_a['shotId']}", json={"title": "hijack"}).status_code == 404
    assert client.delete(f"{base_b}/shots/{shot_a['shotId']}").status_code == 404
    assert client.post(f"{base_b}/shots/{shot_a['shotId']}/candidates", json={"assetId": "x"}).status_code == 404
    assert client.post(f"{base_b}/shots/{shot_a['shotId']}/approve", json={"candidateId": candidate_a["candidateId"]}).status_code == 404
    assert client.post(f"{base_b}/shots/{shot_a['shotId']}/reject", json={"candidateId": candidate_a["candidateId"]}).status_code == 404
    # Scene-scoped creation under a foreign scene is rejected too.
    assert client.post(f"/api/projects/{project_b}/scenes/{scene_a}/multi-shot-plans", json={"name": "hijack"}).status_code == 404
    assert client.get(f"/api/projects/{project_b}/scenes/{scene_a}/multi-shot-plans").status_code == 404

    # Project A's data is untouched and still reachable through its own project.
    reloaded = _get_plan(client, project_a, plan_a["planId"])
    assert reloaded["name"] == "A Plan"
    assert [s["title"] for s in reloaded["shots"]] == ["A Shot"]
    assert _db_counts(project_a) == (1, 1, 1)
    assert _db_counts(project_b) == (0, 0, 0)

    # Sanity: project B can run its own full lifecycle.
    plan_b = _create_plan(client, project_b, scene_b, name="B Plan")
    shot_b = _add_shot(client, project_b, plan_b["planId"], title="B Shot")
    assert shot_b["shotId"] != shot_a["shotId"]


def test_missing_project_and_plan_return_404(client) -> None:
    project_id = _create_project(client, "MultiShot Missing")
    scene_id = _first_scene_id(client, project_id)
    ghost = str(uuid.uuid4())

    assert client.get(f"/api/projects/{ghost}/multi-shot-plans/{ghost}").status_code == 404
    assert client.get(f"/api/projects/{project_id}/multi-shot-plans/{ghost}").status_code == 404
    assert client.post(f"/api/projects/{project_id}/scenes/{ghost}/multi-shot-plans", json={"name": "x"}).status_code == 404
    plan = _create_plan(client, project_id, scene_id)
    assert client.patch(f"/api/projects/{project_id}/multi-shot-plans/{plan['planId']}/shots/{ghost}", json={"title": "x"}).status_code == 404


# ---------------------------------------------------------------------------
# Provider-agnostic design
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider_id", "model_id"),
    [
        ("flux", "flux-dev-local"),
        ("comfyui", "krea2-turbo-local"),
        ("google_imagen", "imagen-4"),
        ("some-future-provider", "arbitrary-model-name"),
    ],
)
def test_plan_is_provider_agnostic(client, provider_id: str, model_id: str) -> None:
    """Any provider/model string pair is storable — no Krea hardcoding, no registry gate."""
    project_id = _create_project(client, f"MultiShot Provider {provider_id}")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id, providerId=provider_id, modelId=model_id)
    assert plan["providerId"] == provider_id
    assert plan["modelId"] == model_id

    shot = _add_shot(client, project_id, plan["planId"], title="Provider shot")
    candidate = _add_candidate(client, project_id, plan["planId"], shot["shotId"], provider=provider_id, model=model_id)
    assert candidate["provider"] == provider_id
    assert candidate["model"] == model_id

    reloaded = _get_plan(client, project_id, plan["planId"])
    assert reloaded["providerId"] == provider_id
    assert reloaded["modelId"] == model_id


def test_candidate_defaults_inherit_plan_provider_context(client) -> None:
    project_id = _create_project(client, "MultiShot Candidate Defaults")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id, providerId="flux", modelId="flux-dev-local")
    shot = _add_shot(client, project_id, plan["planId"], imagePrompt="establishing wide of the harbor")

    # No provider/model/prompt supplied — the candidate inherits plan + shot context.
    candidate = _add_candidate(client, project_id, plan["planId"], shot["shotId"], provider=None, model=None, prompt=None)
    assert candidate["provider"] == "flux"
    assert candidate["model"] == "flux-dev-local"
    assert candidate["prompt"] == "establishing wide of the harbor"

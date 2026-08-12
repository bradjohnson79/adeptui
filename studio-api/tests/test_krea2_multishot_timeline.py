"""Krea 2 Phase D/E — Multi-Shot to Timeline handoff + ERS recommendation (no GPU).

Covers the backend wiring that turns approved Multi-Shot images into W46 Timeline
batch blocks with stable lineage, plus the ERS advisory surfaced for Krea 2
Multi-Shot plans.
"""

from __future__ import annotations

import uuid

import pytest

from app.environment_reference_sheet.orchestrator import create_sheet
from app.environment_reference_sheet.store import save_sheet


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


def _add_shot(client, project_id: str, plan_id: str, **overrides) -> dict:
    body = {"title": "Shot", "prompt": "a quiet shot", "videoPrompt": "camera holds"}
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


def _approve(client, project_id: str, plan_id: str, shot_id: str, candidate_id: str) -> dict:
    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}/approve",
        json={"candidateId": candidate_id},
    )
    assert res.status_code == 200, res.text
    return res.json()["shot"]


def _master(client, project_id: str, scene_id: str) -> dict:
    res = client.get(f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/master")
    assert res.status_code == 200, res.text
    return res.json()["master"]


def _create_ers(project_id: str, scene_id: str) -> str:
    sheet = create_sheet(project_id=project_id, scene_id=scene_id, name="Test Location", description="A dim corridor")
    save_sheet(sheet)
    return sheet.sheetId


# ---------------------------------------------------------------------------
# Send-to-Timeline
# ---------------------------------------------------------------------------


def test_send_to_timeline_creates_batches_with_lineage(client) -> None:
    project_id = _create_project(client, "MultiShot Timeline Handoff")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id, name="Handoff Plan")
    plan_id = plan["planId"]

    shot_a = _add_shot(client, project_id, plan_id, title="Barnes enters", videoPrompt="Barnes walks in")
    shot_b = _add_shot(client, project_id, plan_id, title="Barnes sees Kyung", videoPrompt="Barnes glances over")
    # Unapproved shot should be ignored.
    _add_shot(client, project_id, plan_id, title="Unapproved", videoPrompt="Not approved")

    cand_a = _add_candidate(client, project_id, plan_id, shot_a["shotId"])
    cand_b = _add_candidate(client, project_id, plan_id, shot_b["shotId"])
    _approve(client, project_id, plan_id, shot_a["shotId"], cand_a["candidateId"])
    _approve(client, project_id, plan_id, shot_b["shotId"], cand_b["candidateId"])

    res = client.post(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/send-to-timeline", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert len(body["created"]) == 2
    assert body["skipped"] == []
    for item in body["created"]:
        assert item["batchBlockId"]
        assert item["approvedAssetId"]

    # Shot rows now record the linked batch block id.
    plan_reload = client.get(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}").json()["plan"]
    linked_shots = {s["shotId"]: s for s in plan_reload["shots"]}
    for item in body["created"]:
        assert linked_shots[item["shotId"]]["timelineBatchBlockId"] == item["batchBlockId"]
        assert linked_shots[item["shotId"]]["status"] == "sent_to_timeline"

    # Timeline master has matching batches with visual clips and prompt segments.
    master = _master(client, project_id, scene_id)
    batch_map = {b["id"]: b for b in master["batchBlocks"]}
    for item in body["created"]:
        assert item["batchBlockId"] in batch_map, "created batch must exist in Timeline master"
        batch = batch_map[item["batchBlockId"]]
        assert batch["label"] in ("Barnes enters", "Barnes sees Kyung")
        assert len(batch["visualClips"]) == 1
        assert batch["visualClips"][0]["assetId"] == item["approvedAssetId"]
        assert batch["visualClips"][0]["role"] == "start"
        assert len(batch["promptSegments"]) == 1
        assert batch["promptSegments"][0]["text"] == item["prompt"]
        assert batch["promptSegments"][0]["length"] == pytest.approx(5.0)


def test_send_to_timeline_uses_custom_duration_and_generator(client) -> None:
    project_id = _create_project(client, "MultiShot Timeline Custom Config")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id, name="Custom Config")
    plan_id = plan["planId"]

    shot = _add_shot(client, project_id, plan_id, title="Long shot", videoPrompt="Slow pan", durationHint=8.5)
    cand = _add_candidate(client, project_id, plan_id, shot["shotId"])
    _approve(client, project_id, plan_id, shot["shotId"], cand["candidateId"])

    res = client.post(
        f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/send-to-timeline",
        json={"generatorId": "ltx-local", "defaultDuration": 3.0},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 1

    master = _master(client, project_id, scene_id)
    batch = next(b for b in master["batchBlocks"] if b["id"] == body["created"][0]["batchBlockId"])
    assert batch["generatorId"] == "ltx-local"
    assert batch["promptSegments"][0]["length"] == pytest.approx(8.5)
    assert batch["duration"]["plannedDuration"] == pytest.approx(8.5)


def test_send_to_timeline_is_idempotent_with_only_missing(client) -> None:
    project_id = _create_project(client, "MultiShot Timeline Idempotent")
    scene_id = _first_scene_id(client, project_id)
    plan = _create_plan(client, project_id, scene_id, name="Idempotent")
    plan_id = plan["planId"]

    shot = _add_shot(client, project_id, plan_id, title="One shot", videoPrompt="Hold")
    cand = _add_candidate(client, project_id, plan_id, shot["shotId"])
    _approve(client, project_id, plan_id, shot["shotId"], cand["candidateId"])

    res1 = client.post(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/send-to-timeline", json={})
    assert res1.status_code == 200, res.text
    first_batch_id = res1.json()["created"][0]["batchBlockId"]

    res2 = client.post(f"/api/projects/{project_id}/multi-shot-plans/{plan_id}/send-to-timeline", json={})
    assert res2.status_code == 200, res2.text
    body = res2.json()
    assert body["count"] == 0
    assert body["skipped"] == [shot["shotId"]]
    assert len(body["created"]) == 0

    master = _master(client, project_id, scene_id)
    assert any(b["id"] == first_batch_id for b in master["batchBlocks"])


def test_send_to_timeline_rejects_cross_project_plan(client) -> None:
    project_a = _create_project(client, "Project A Handoff")
    scene_a = _first_scene_id(client, project_a)
    plan_a = _create_plan(client, project_a, scene_a, name="Plan A")

    project_b = _create_project(client, "Project B Handoff")

    res = client.post(
        f"/api/projects/{project_b}/multi-shot-plans/{plan_a['planId']}/send-to-timeline", json={}
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# ERS recommendation
# ---------------------------------------------------------------------------


def test_ers_recommendation_recommends_when_no_sheet(client) -> None:
    project_id = _create_project(client, "MultiShot ERS Empty")
    scene_id = _first_scene_id(client, project_id)

    res = client.get(f"/api/projects/{project_id}/scenes/{scene_id}/multi-shot-ers-recommendation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ersAvailable"] is False
    assert body["sheetCount"] == 0
    assert body["recommended"] is True
    assert body["missingReason"] == "no_ers_sheet"
    assert body["sheetIds"] == []


def test_ers_recommendation_available_when_sheet_exists(client) -> None:
    project_id = _create_project(client, "MultiShot ERS Present")
    scene_id = _first_scene_id(client, project_id)
    sheet_id = _create_ers(project_id, scene_id)

    res = client.get(f"/api/projects/{project_id}/scenes/{scene_id}/multi-shot-ers-recommendation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ersAvailable"] is True
    assert body["sheetCount"] == 1
    assert body["recommended"] is False
    assert body["missingReason"] is None
    assert body["sheetIds"] == [sheet_id]


def test_ers_recommendation_is_project_scoped(client) -> None:
    project_a = _create_project(client, "ERS Project A")
    scene_a = _first_scene_id(client, project_a)
    _create_ers(project_a, scene_a)

    project_b = _create_project(client, "ERS Project B")
    scene_b = _first_scene_id(client, project_b)

    res = client.get(f"/api/projects/{project_b}/scenes/{scene_b}/multi-shot-ers-recommendation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ersAvailable"] is False
    assert body["recommended"] is True

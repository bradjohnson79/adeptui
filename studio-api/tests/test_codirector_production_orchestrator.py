"""Co-Director Full Production Orchestrator - integration tests (mission Part 61).

Covers: production state snapshot shape/bounds, production event recording,
production memory + reference resolution (C1-A, ordinals, ambiguity),
execution authority (direct vs proposals, allowlist), and prompt-segment
provenance (userDirection / productionPrompt / dialogue).
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture()
def project_with_scene(client):
    """Create a fresh disposable project + scene via the API."""
    res = client.post("/api/projects", json={"name": "Orchestrator Test " + uuid.uuid4().hex[:8]})
    assert res.status_code == 200, res.text
    project = res.json()
    pid = project["id"]
    scenes = project.get("scenes") or []
    if not scenes:
        r2 = client.post(f"/api/projects/{pid}/scenes", json={"name": "Scene 1", "prompt": ""})
        assert r2.status_code in (200, 201), r2.text
        scenes = r2.json().get("scenes") or [r2.json()]
    scene_id = scenes[0]["id"] if isinstance(scenes[0], dict) else scenes[0]
    yield pid, scene_id


@pytest.fixture()
def db_session():
    from app.db import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


# ----------------------------------------------------------------------
# 1. Production state snapshot
# ----------------------------------------------------------------------


def test_snapshot_shape_and_bounds(project_with_scene, db_session):
    from app.codirector.production_state.snapshot import build_production_snapshot

    pid, scene_id = project_with_scene
    snap = build_production_snapshot(db_session, pid, scene_id)
    assert set(snap.keys()) == {"project", "scene", "spatialMap", "ers", "candidates", "timeline", "jobs", "events"}
    assert snap["project"]["id"] == pid
    assert snap["scene"]["id"] == scene_id
    assert snap["spatialMap"]["hasMap"] is False
    # a fresh scene migrates a timeline master with a default batch block
    assert snap["timeline"]["hasTimeline"] is True
    assert isinstance(snap["timeline"]["batchCount"], int)
    assert isinstance(snap["candidates"], list)
    assert isinstance(snap["jobs"], dict)
    assert isinstance(snap["events"], list)


def test_snapshot_reflects_timeline_batch(project_with_scene, db_session):
    from app.codirector.production_state.snapshot import build_production_snapshot
    from app.director_timeline_w46.service import add_batch

    pid, scene_id = project_with_scene
    result = add_batch(db_session, pid, scene_id, label="Cert Batch")
    assert result["ok"]
    snap = build_production_snapshot(db_session, pid, scene_id)
    tl = snap["timeline"]
    assert tl["hasTimeline"] is True
    assert any(b["label"] == "Cert Batch" for b in tl["batches"])


# ----------------------------------------------------------------------
# 2. Production events
# ----------------------------------------------------------------------


def test_event_recording_and_listing(project_with_scene, db_session):
    from app.production_events import (
        ACTOR_CODIRECTOR,
        list_production_events,
        record_production_event,
        recent_production_events_block,
    )

    pid, scene_id = project_with_scene
    eid = record_production_event(
        db_session,
        project_id=pid,
        scene_id=scene_id,
        event_type="timeline.clip_added",
        actor=ACTOR_CODIRECTOR,
        actor_detail="tool:timeline.build_shot",
        subject_kind="image_clip",
        subject_id="img_test",
        summary="Shot Test added at 0.0s for 5.0s",
        payload={"clipId": "img_test", "start": 0.0, "length": 5.0},
    )
    assert eid
    rows = list_production_events(db_session, pid, limit=10)
    assert len(rows) >= 1
    assert rows[0]["eventType"] == "timeline.clip_added"
    assert rows[0]["actor"] == "codirector"
    assert rows[0]["sceneId"] == scene_id
    assert rows[0]["payload"]["length"] == 5.0
    block = recent_production_events_block(db_session, pid, limit=5)
    assert "Shot Test added at 0.0s for 5.0s" in block


def test_timeline_service_emits_batch_event(project_with_scene, db_session):
    from app.director_timeline_w46.service import add_batch
    from app.production_events import list_production_events

    pid, scene_id = project_with_scene
    add_batch(db_session, pid, scene_id, label="Event Batch")
    rows = list_production_events(db_session, pid, limit=10)
    assert any(r["eventType"] == "timeline.batch_created" and "Event Batch" in r["summary"] for r in rows)


# ----------------------------------------------------------------------
# 3. Production memory + reference resolution
# ----------------------------------------------------------------------


def test_reference_resolution_candidate_tags(project_with_scene, db_session):
    from app.db import Asset
    from app.codirector.production_state.memory import resolve_reference

    pid, scene_id = project_with_scene
    ids = {}
    for tag, key in [("scene_creator_mini_1_C1_A", "c1a"), ("scene_creator_mini_1_C1_B", "c1b"), ("scene_creator_mini_1_C2_A", "c2a")]:
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=pid,
            tag=tag,
            kind="image",
            filename=key + ".png",
            path="C:\\tmp\\" + key + ".png",
            scope="project",
        )
        db_session.add(asset)
        ids[key] = asset.id
    db_session.commit()

    r = resolve_reference(db_session, pid, "C1-A", scene_id=scene_id)
    assert r["matched"] and r["matched"][0]["assetId"] == ids["c1a"]
    r2 = resolve_reference(db_session, pid, "the first C2 shot", scene_id=scene_id)
    assert r2["matched"][0]["assetId"] == ids["c2a"]
    r3 = resolve_reference(db_session, pid, "C1-B", scene_id=scene_id)
    assert r3["matched"][0]["assetId"] == ids["c1b"]
    r4 = resolve_reference(db_session, pid, "shot frame 2", scene_id=scene_id)
    assert r4["matched"] and not r4["ambiguous"]


def test_reference_resolution_ambiguity(project_with_scene, db_session):
    from app.db import Asset
    from app.codirector.production_state.memory import resolve_reference

    pid, scene_id = project_with_scene
    for i in range(2):
        db_session.add(Asset(
            id=str(uuid.uuid4()),
            project_id=pid,
            tag="scene_creator_mini_" + str(i) + "_C1_A",
            kind="image",
            filename="dup" + str(i) + ".png",
            path="C:\\tmp\\dup" + str(i) + ".png",
            scope="project",
        ))
    db_session.commit()
    r = resolve_reference(db_session, pid, "C1-A", scene_id=scene_id)
    assert len(r["matched"]) == 2
    assert r["ambiguous"] is True


def test_production_memory_block(project_with_scene, db_session):
    from app.codirector.production_state.memory import build_production_memory, production_memory_block

    pid, scene_id = project_with_scene
    memory = build_production_memory(db_session, pid, scene_id)
    assert set(memory.keys()) == {"events", "toolActions", "snapshot"}
    block = production_memory_block(db_session, pid, scene_id)
    assert isinstance(block, str)


# ----------------------------------------------------------------------
# 4. Execution authority
# ----------------------------------------------------------------------


def test_execution_authority_default_and_roundtrip(project_with_scene, db_session):
    from app.codirector.execution_authority import (
        AUTHORITY_DIRECT,
        AUTHORITY_PROPOSALS,
        get_execution_authority,
        set_execution_authority,
    )

    pid, _ = project_with_scene
    assert get_execution_authority(db_session, pid) == AUTHORITY_PROPOSALS
    assert set_execution_authority(db_session, pid, AUTHORITY_DIRECT) == AUTHORITY_DIRECT
    assert get_execution_authority(db_session, pid) == AUTHORITY_DIRECT
    set_execution_authority(db_session, pid, AUTHORITY_PROPOSALS)


def test_execution_authority_should_auto_approve(project_with_scene, db_session):
    from app.codirector.execution_authority import (
        AUTHORITY_DIRECT,
        ROUTINE_TOOLS,
        get_execution_authority,
        set_execution_authority,
        should_auto_approve,
    )

    pid, _ = project_with_scene
    assert "timeline.propose_add_image_clip" in ROUTINE_TOOLS
    assert "timeline.propose_generate_scene" not in ROUTINE_TOOLS
    assert "timeline.remove_item" not in ROUTINE_TOOLS
    assert not should_auto_approve(db_session, pid, "timeline.propose_add_image_clip", "req-1")
    set_execution_authority(db_session, pid, AUTHORITY_DIRECT)
    assert should_auto_approve(db_session, pid, "timeline.propose_add_image_clip", "req-1")
    assert not should_auto_approve(db_session, pid, "timeline.propose_add_image_clip", None)
    assert not should_auto_approve(db_session, pid, "timeline.propose_generate_scene", "req-1")
    set_execution_authority(db_session, pid, "proposals")


def test_execution_authority_direct_endpoint(client, project_with_scene):
    pid, scene_id = project_with_scene
    r = client.put(f"/api/codirector/projects/{pid}/execution-authority", json={"executionAuthority": "direct"})
    assert r.status_code == 200, r.text
    assert r.json()["executionAuthority"] == "direct"
    g = client.get(f"/api/codirector/projects/{pid}/execution-authority")
    assert g.status_code == 200
    body = g.json()
    assert body["executionAuthority"] == "direct"
    assert "timeline.build_shot" in body["routineTools"]
    r2 = client.put(f"/api/codirector/projects/{pid}/execution-authority", json={"executionAuthority": "banana"})
    assert r2.status_code == 400


def test_direct_authority_auto_approves_routine_tool(client, project_with_scene):
    """propose() with direct authority + request_id auto-executes a routine tool."""
    pid, scene_id = project_with_scene
    client.put(f"/api/codirector/projects/{pid}/execution-authority", json={"executionAuthority": "direct"})
    res = client.post(
        f"/api/codirector/projects/{pid}/tools/proposals",
        json={
            "toolId": "timeline.propose_add_batch",
            "arguments": {"sceneId": scene_id, "label": "Auto Batch"},
            "sceneId": scene_id,
            "requestId": "auto-test-" + uuid.uuid4().hex[:8],
            "createdBy": "assistant",
        },
    )
    assert res.status_code == 200, res.text
    from app.db import SessionLocal
    from app.db import CoDirectorProposal
    s = SessionLocal()
    try:
        row = s.get(CoDirectorProposal, res.json()["id"])
        assert row is not None
        assert row.status == "completed", row.status
    finally:
        s.close()
    from app.director_timeline_w46.service import load_timeline_bundle
    s2 = SessionLocal()
    try:
        bundle = load_timeline_bundle(s2, pid, scene_id)
        assert bundle["ok"]
        labels = [b.label for b in bundle["master"].batchBlocks]
        assert "Auto Batch" in labels
    finally:
        s2.close()


def test_proposals_mode_keeps_pending(client, project_with_scene):
    """Default authority: proposals stay pending for user approval."""
    pid, scene_id = project_with_scene
    res = client.post(
        f"/api/codirector/projects/{pid}/tools/proposals",
        json={
            "toolId": "timeline.propose_add_batch",
            "arguments": {"sceneId": scene_id, "label": "Pending Batch"},
            "sceneId": scene_id,
            "requestId": "pending-test-" + uuid.uuid4().hex[:8],
            "createdBy": "assistant",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "pending"


# ----------------------------------------------------------------------
# 5. Prompt segment provenance (mission Parts 13-16, 19-20)
# ----------------------------------------------------------------------


def test_prompt_segment_provenance_fields(project_with_scene, db_session):
    from app.director_timeline_w46.contracts import TimelinePromptSegment
    from app.director_timeline import PromptSegment

    legacy = PromptSegment(
        id="ps_1",
        text="compiled",
        user_direction="Korri makes a gross face then fake smiles.",
        production_prompt="Refined production language...",
        dialogue="I am not drinking that.",
    )
    assert legacy.user_direction == "Korri makes a gross face then fake smiles."
    assert legacy.dialogue == "I am not drinking that."
    w46 = TimelinePromptSegment(
        id="ps_2",
        text="compiled",
        userDirection="original",
        productionPrompt="refined",
        dialogue="exact line",
    )
    assert w46.userDirection == "original"
    assert w46.productionPrompt == "refined"
    assert w46.dialogue == "exact line"


def test_build_shot_tool_writes_provenance(client, project_with_scene, db_session):
    """timeline.build_shot apply persists provenance and clips."""
    from app.db import Asset
    from app.codirector.tools.definitions import ToolContext
    from app.director_timeline_w46.service import load_timeline_bundle

    pid, scene_id = project_with_scene
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="scene_creator_mini_1_C1_A",
        kind="image",
        filename="shot.png",
        path="C:\\tmp\\shot.png",
        scope="project",
    )
    db_session.add(asset)
    db_session.commit()
    asset_id = asset.id

    from app.codirector.tools import registry as tool_registry

    ctx = ToolContext(
        db=db_session,
        project_id=pid,
        scene_id=scene_id,
        request_id="tool-test",
        capabilities={},
    )
    handler = tool_registry.mutation_handler("timeline.build_shot")
    preview = handler.preview(ctx, {"sceneId": scene_id, "assetId": asset_id, "length": 5.0, "label": "Shot 1"})
    assert preview.summary
    result = handler.apply(ctx, {
        "sceneId": scene_id,
        "assetId": asset_id,
        "length": 5.0,
        "label": "Shot 1",
        "userDirection": "Korri makes a gross face.",
        "productionPrompt": "Korri recoils with disgust.",
        "dialogue": "No way.",
        "addPromptSegment": True,
    })
    assert result["ok"]
    assert result["start"] == 0.0
    assert result["duration"] == 5.0
    assert result["clipId"]
    assert result["segmentId"]
    bundle = load_timeline_bundle(db_session, pid, scene_id)
    legacy = bundle["directorTimeline"]
    assert len(legacy.image_clips) == 1
    assert legacy.image_clips[0].asset_id == asset_id
    seg = legacy.prompt_segments[0]
    assert seg.user_direction == "Korri makes a gross face."
    assert seg.production_prompt == "Korri recoils with disgust."
    assert seg.dialogue == "No way."


def test_build_shot_sequential_placement_no_drift(project_with_scene, db_session):
    from app.db import Asset
    from app.codirector.tools import registry as tool_registry
    from app.codirector.tools.definitions import ToolContext
    from app.director_timeline_w46.service import load_timeline_bundle

    pid, scene_id = project_with_scene
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="scene_creator_mini_1_C1_A",
        kind="image",
        filename="s.png",
        path="C:\\tmp\\s.png",
        scope="project",
    )
    db_session.add(asset)
    db_session.commit()
    ctx = ToolContext(db=db_session, project_id=pid, scene_id=scene_id, request_id="seq", capabilities={})
    handler = tool_registry.mutation_handler("timeline.build_shot")
    expected_start = None
    for i, length in enumerate([5.0, 5.0, 4.0]):
        r = handler.apply(ctx, {"sceneId": scene_id, "assetId": asset.id, "length": length, "label": "Shot " + str(i + 1)})
        assert r["ok"]
        assert r["duration"] == length
        if i > 0:
            assert abs(r["start"] - expected_start) < 1e-6, r["start"]
        expected_start = round(r["start"] + r["duration"], 6)
    bundle = load_timeline_bundle(db_session, pid, scene_id)
    clips = bundle["directorTimeline"].image_clips
    assert [c.start for c in clips] == [0.0, 5.0, 10.0]
    assert [c.length for c in clips] == [5.0, 5.0, 4.0]

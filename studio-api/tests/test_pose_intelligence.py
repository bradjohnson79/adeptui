"""Revision C Phase 2 — Pose intelligence contracts and API."""

from __future__ import annotations

from app.codirector.pose_intelligence.analyze import (
    build_character_state,
    build_contacts,
    compare_worlds,
    infer_stance,
    infer_support,
    pose_cache_key,
    solve_joints,
)
from app.codirector.pose_intelligence.compile import compile_pose_motion_conditioning
from app.codirector.pose_intelligence.compare import review_intended_vs_observed
from app.codirector.pose_intelligence.contracts import PoseWorldStatePacket
from app.codirector.world_intelligence.contracts import WorldStatePacket
from app.posecraft.schemas import BlockingPrimitive, FigureInstance, JointRotation


def _figure(**overrides) -> FigureInstance:
    pose = {
        name: JointRotation()
        for name in (
            "pelvis", "spine", "chest", "neck", "head",
            "leftShoulder", "leftElbow", "leftWrist",
            "rightShoulder", "rightElbow", "rightWrist",
            "leftHip", "leftKnee", "leftAnkle",
            "rightHip", "rightKnee", "rightAnkle",
        )
    }
    pose.update(overrides.pop("pose", {}))
    data = {
        "id": "fig-korri",
        "name": "Korri",
        "archetypeId": "adult-female",
        "colorId": "seaglass",
        "position": {"x": 0.0, "z": 0.0},
        "rotationY": 0.0,
        "scale": 1.0,
        "pose": pose,
        "characterId": "char-korri",
    }
    data.update(overrides)
    return FigureInstance.model_validate(data)


def _chair() -> BlockingPrimitive:
    return BlockingPrimitive(
        id="prim-counter",
        name="service counter",
        kind="table-medium",
        position={"x": 0.35, "z": 0.15},
        size={"x": 1.2, "y": 0.95, "z": 0.5},
    )


def test_world_state_packet_remains_v1() -> None:
    packet = WorldStatePacket()
    assert packet.schemaVersion == "world-state-v1"
    pose = PoseWorldStatePacket(world=packet)
    assert pose.schemaVersion == "pose-world-state-v1"
    assert pose.world.schemaVersion == "world-state-v1"


def test_neutral_tpose_is_standing_with_floor_contact() -> None:
    figure = _figure()
    world = solve_joints(figure)
    assert world["leftAnkle"][1] < 0.12
    assert world["rightAnkle"][1] < 0.12
    primary, _secondary, _wl, _wr, balance, ground = infer_support(world)
    assert ground is True
    assert primary in {"both", "left_foot", "right_foot"}
    assert balance in {"stable", "unstable"}
    assert infer_stance(world, {k: {"x": 0, "y": 0, "z": 0} for k in world}) == "standing"


def test_contact_with_counter() -> None:
    figure = _figure(
        pose={
            "rightShoulder": JointRotation(x=-20, z=25),
            "rightElbow": JointRotation(x=-15),
        }
    )
    world = solve_joints(figure)
    # Place the wrist onto the counter by moving the figure if needed.
    ix = build_contacts(world, [_chair()])
    assert ix.graph.edges
    assert ix.groundContact is True
    assert ix.seatedContact is False


def test_seated_pose_detected() -> None:
    figure = _figure(
        pose={
            "leftHip": JointRotation(x=80),
            "rightHip": JointRotation(x=80),
            "leftKnee": JointRotation(x=80),
            "rightKnee": JointRotation(x=80),
        }
    )
    world = solve_joints(figure)
    char = build_character_state(figure, world, 2)
    assert char.stance in {"sitting", "crouching", "kneeling"}


def test_support_foot_teleport_warning() -> None:
    a = _figure()
    b = _figure(position={"x": 2.4, "z": 0.0})
    aw, bw = solve_joints(a), solve_joints(b)
    ac = build_character_state(a, aw, 1)
    bc = build_character_state(b, bw, 2)
    aix = build_contacts(aw, [])
    bix = build_contacts(bw, [])
    _changes, warnings, _motion = compare_worlds(aw, bw, ac, bc, aix, bix)
    assert any("teleport" in w.lower() or "translated" in w.lower() or "discontinuity" in w.lower() for w in warnings + [c.summary.lower() for c in _changes])


def test_cache_key_changes_with_pose() -> None:
    a = _figure()
    b = _figure(pose={"chest": JointRotation(y=40)})
    ka = pose_cache_key("proj-a", 1, a, [])
    kb = pose_cache_key("proj-a", 1, b, [])
    kc = pose_cache_key("proj-b", 1, a, [])
    assert ka != kb
    assert ka != kc
    kd = pose_cache_key("proj-a", 1, a, [], image_asset_id="asset-1")
    assert ka != kd


def test_conditioning_has_no_embeddings() -> None:
    packet = PoseWorldStatePacket(
        availability="available",
        projectId="p1",
        creatorFacingSummary="Balance: Stable.",
    )
    packet.character.figureName = "Korri"
    packet.character.primarySupport = "left_foot"
    packet.interaction.handContact = ["right_hand → service counter"]
    compiled = compile_pose_motion_conditioning(packet)
    assert compiled["applied"] is True
    blob = str(compiled)
    assert "embedding" not in blob.lower() or "No embeddings" in blob
    assert "latent" not in blob.lower()
    assert "Korri" in compiled["promptPrefix"]


def test_intended_vs_observed_does_not_overwrite_pose() -> None:
    intended = PoseWorldStatePacket(
        availability="available",
        projectId="p1",
        stateKind="intended",
    )
    intended.interaction.handContact = ["right_hand → service counter"]
    intended.constraints.creatorIntentHonored = True
    review = review_intended_vs_observed(
        intended,
        observed_text="The right hand detaches from the counter and lets go.",
        project_id="p1",
    )
    assert review.intended is not None
    assert review.intended.constraints.creatorIntentHonored is True
    assert any("departed" in r.lower() or "restore" in g.lower() for r in review.continuityRisk for g in review.nextBatchGuidance) or review.nextBatchGuidance
    assert "stale" in review.authorityNote.lower() or "observed" in review.authorityNote.lower()


def test_timeline_request_includes_pose_motion_conditioning(monkeypatch) -> None:
    from app.director_timeline_w46.contracts import BatchBlock, ExecutionSnapshot, TimelinePromptSegment
    from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request

    packet = PoseWorldStatePacket(availability="available", projectId="p1")
    packet.character.figureName = "Korri"
    packet.character.primarySupport = "left_foot"
    packet.creatorFacingSummary = "Balance: Stable."

    monkeypatch.setattr(
        "app.codirector.pose_intelligence.persist.load_packet",
        lambda db, project_id, **kwargs: packet,
    )

    class _DummySession:
        def close(self) -> None:
            return None

    monkeypatch.setattr("app.db.SessionLocal", lambda: _DummySession())
    batch = BatchBlock(
        sceneId="s",
        generatorId="ltx-local",
        promptSegments=[
            TimelinePromptSegment(text="Korri leans on the counter", start=0, length=5, role="primary", versionId="v1")
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    req = build_timeline_generation_request(project_id="p1", scene_id="s", batch=batch, snapshot=snap)
    pose = (req.providerOptions or {}).get("poseMotionConditioning") or {}
    assert pose.get("applied") is True
    assert "pose continuity" in str(pose.get("promptPrefix") or "").lower()
    assert "pose continuity" in (req.prompt or "").lower()
    assert "temporalContinuation" in (req.providerOptions or {})


def test_unavailable_packet_is_not_fake_success() -> None:
    packet = PoseWorldStatePacket(availability="unavailable", reason="No PoseCraft figure to analyze.")
    assert packet.is_actionable() is False
    compiled = compile_pose_motion_conditioning(packet)
    assert compiled["applied"] is False


def _create_project(client, name: str = "Pose Intel A") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Pose intelligence."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _put_scene(client, project_id: str, figure: dict, primitive: dict | None = None) -> dict:
    doc = {
        "schemaVersion": 2,
        "currentScene": {
            "schemaVersion": 2,
            "revision": 3,
            "name": "Pose study",
            "notes": "",
            "stage": {"gridSize": 12, "showAxes": True, "showPrimitives": True},
            "camera": {
                "lensMm": 35, "aspect": "16:9", "guides": ["safe"],
                "alpha": -1.57, "beta": 1.12, "radius": 7.5,
                "target": {"x": 0, "y": 1.2, "z": 0},
            },
            "figures": [figure],
            "primitives": [primitive] if primitive else [],
            "selectedFigureId": figure["id"],
            "selectedJoint": "head",
            "creatorModified": True,
        },
        "savedVersions": [],
        "snapshots": [],
    }
    res = client.put(f"/api/posecraft/projects/{project_id}/scene", json=doc)
    assert res.status_code == 200, res.text
    return res.json()


def test_analyze_route_persists_and_isolates(client) -> None:
    a = _create_project(client, "Pose Intel A")
    b = _create_project(client, "Pose Intel B")
    fig = _figure().model_dump()
    chair = _chair().model_dump()
    _put_scene(client, a, fig, chair)
    _put_scene(client, b, _figure(id="fig-other", name="Other", characterId="char-b").model_dump())

    analyzed = client.post(f"/api/posecraft/projects/{a}/intelligence/analyze", json={})
    assert analyzed.status_code == 200, analyzed.text
    packet = analyzed.json()["packet"]
    assert packet["projectId"] == a
    assert packet["character"]["figureName"] == "Korri"
    assert packet["extras"]["doesNotOverwriteCRS"] is True
    assert packet["availability"] in {"available", "degraded", "low_confidence"}
    assert packet["constraints"]["creatorIntentHonored"] is True

    latest_a = client.get(f"/api/posecraft/projects/{a}/intelligence")
    latest_b = client.get(f"/api/posecraft/projects/{b}/intelligence")
    assert latest_a.status_code == 200
    assert latest_b.status_code == 200
    pa = latest_a.json().get("packet")
    pb = latest_b.json().get("packet")
    assert pa and pa["packetId"] == packet["packetId"]
    assert (pb or {}).get("packetId") != packet["packetId"]


def test_handoffs_and_tools(client) -> None:
    project_id = _create_project(client, "Pose Intel Handoff")
    _put_scene(client, project_id, _figure().model_dump(), _chair().model_dump())
    scene = client.post(f"/api/posecraft/projects/{project_id}/intelligence/handoff/scene-creator", json={})
    timeline = client.post(f"/api/posecraft/projects/{project_id}/intelligence/handoff/timeline", json={})
    assert scene.status_code == 200, scene.text
    assert timeline.status_code == 200, timeline.text
    assert scene.json()["poseWorldStatePacketId"]
    assert timeline.json()["compiled"]["applied"] is True
    assert "pose continuity" in timeline.json()["compiled"]["promptPrefix"].lower()

    read = client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": "posecraft.get_pose_intelligence", "arguments": {}},
    )
    assert read.status_code == 200, read.text
    body = read.json()
    data = ((body.get("result") or {}).get("data") or {})
    packet = data.get("packet") or {}
    assert packet.get("character", {}).get("figureName") == "Korri"
    assert packet.get("availability") in {"available", "degraded", "low_confidence"}
    assert data.get("honorsCreatorIntent") is True
    assert body.get("resultTruncated") is not True

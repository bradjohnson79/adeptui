"""ContinuityBridge + Auto-Extend contract tests (no Playwright)."""

from __future__ import annotations

from app.director_timeline_w46.continuity import (
    bridge_blocks_submit,
    compile_retake_memory,
    continue_without_continuity,
    default_policy_for_locality,
    effective_tail_duration,
    generator_locality,
    new_bridge,
    paid_continuity_forbidden,
    set_continuity_policy,
    should_prepare_bridge,
    supersede_outgoing_bridges,
)
from app.director_timeline_w46.contracts import (
    CURRENT_CONTINUITY_CONTEXT_VERSION,
    ApprovedClip,
    BatchBlock,
    CandidateVersion,
    ContinuityBridge,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request


def test_effective_tail_clamps_to_generated_duration():
    assert effective_tail_duration(5.0, 3.2) == 3.2
    assert effective_tail_duration(5.0, 5.0) == 5.0
    assert effective_tail_duration(5.0, 15.0) == 5.0
    assert effective_tail_duration(0.0, 15.0) == 0.0
    assert effective_tail_duration(5.0, None) == 5.0


def test_local_policy_locked_on_five_seconds():
    policy = default_policy_for_locality("local")
    assert policy.autoContinuity is True
    assert policy.configuredTailDuration == 5.0
    assert policy.continuityAwareRetake is True


def test_api_policy_defaults_off():
    policy = default_policy_for_locality("api")
    assert policy.autoContinuity is False
    assert policy.configuredTailDuration == 0.0
    assert paid_continuity_forbidden(policy, "seedance-api") is True
    assert should_prepare_bridge(policy, "seedance-api") is False


def test_bridge_context_version_and_roundtrip():
    bridge = new_bridge(
        scene_id="s1",
        source_batch_id="b1",
        target_batch_id="b2",
        source_take_id="take_a",
        configured_tail=5.0,
        actual_generated_duration=15.0,
    )
    assert bridge.contextVersion == CURRENT_CONTINUITY_CONTEXT_VERSION
    assert bridge.effectiveTailDuration == 5.0
    assert bridge.status == "Waiting"
    assert bridge.continuityStrategy == "none"
    master = SceneTimelineMaster(batchBlocks=[BatchBlock(sceneId="s1")], continuityBridges=[bridge])
    dumped = master.model_dump()
    restored = SceneTimelineMaster.model_validate(dumped)
    assert restored.continuityBridges[0].bridgeId == bridge.bridgeId
    assert restored.continuityBridges[0].contextVersion == 1


def test_candidate_keeps_structured_retake_memory():
    cand = CandidateVersion(
        executionSnapshotId="snap_1",
        sequenceMemory={"characters": ["Korri"]},
        incomingContinuity={"bridgeId": "cbr_1"},
        originalTakeIntent={"prompt": "walk past the cruiser"},
        takeState={"tail": "cruiser foreground"},
        userCorrection={"delta": "pass behind the cruiser, not in front"},
    )
    data = cand.model_dump()
    assert data["sequenceMemory"]["characters"] == ["Korri"]
    assert data["userCorrection"]["delta"].startswith("pass behind")
    assert "incomingContinuity" in data
    assert "originalTakeIntent" in data
    assert "takeState" in data


def test_generator_locality():
    assert generator_locality("minimax-h3-local") == "local"
    assert generator_locality("ltx-local") == "local"
    assert generator_locality("seedance-api") == "api"
    assert generator_locality("kling-fal") == "api"
    assert generator_locality("fal_seedance") == "api"


def test_api_policy_accepts_off_3_5_and_rejects_other():
    master = SceneTimelineMaster(
        sceneGeneratorId="seedance-api",
        batchBlocks=[BatchBlock(sceneId="s", generatorId="seedance-api")],
    )
    p0 = set_continuity_policy(master, generator_id="seedance-api", configured_tail=0)
    assert p0.autoContinuity is False
    p3 = set_continuity_policy(master, generator_id="seedance-api", configured_tail=3)
    assert p3.autoContinuity is True and p3.configuredTailDuration == 3.0
    p5 = set_continuity_policy(master, generator_id="seedance-api", configured_tail=5)
    assert p5.configuredTailDuration == 5.0
    try:
        set_continuity_policy(master, generator_id="seedance-api", configured_tail=4)
        raise AssertionError("4s window must be rejected")
    except ValueError:
        pass
    local = SceneTimelineMaster(batchBlocks=[BatchBlock(sceneId="s", generatorId="minimax-h3-local")])
    locked = set_continuity_policy(local, generator_id="minimax-h3-local", configured_tail=0)
    assert locked.autoContinuity is True
    assert locked.configuredTailDuration == 5.0


def test_minimax_t2v_continuity_is_prompt_context_not_i2v():
    batch = BatchBlock(sceneId="s", generatorId="minimax-h3-t2v-local")
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
    bridge = ContinuityBridge(
        targetBatchId=batch.id,
        lastFrameAssetId="frame-1",
        status="Ready",
        continuityStrategy="none",
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=snap,
        incoming_bridge=bridge,
    )
    assert req.generationMode == "text_to_video"
    assert req.startImageAssetId is None
    assert req.continuityStrategy == "prompt_context"
    assert req.lastFrameAssetId == "frame-1"


def test_ltx_last_frame_is_i2v_not_native_tail():
    batch = BatchBlock(
        sceneId="s",
        generatorId="ltx-local",
        promptSegments=[
            TimelinePromptSegment(text="continue the walk", start=0, length=5, role="primary", versionId="v1")
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    bridge = ContinuityBridge(targetBatchId=batch.id, lastFrameAssetId="frame-ltx", status="Ready")
    req = build_timeline_generation_request(
        project_id="p", scene_id="s", batch=batch, snapshot=snap, incoming_bridge=bridge
    )
    assert req.generationMode == "image_to_video"
    assert req.startImageAssetId == "frame-ltx"
    assert req.continuityStrategy == "last_frame_i2v"
    assert req.continuityStrategy != "native_tail"


def test_new_angle_start_image_wins_over_last_frame():
    batch = BatchBlock(
        sceneId="s",
        generatorId="ltx-local",
        promptSegments=[TimelinePromptSegment(text="new angle", start=0, length=5, role="primary", versionId="v1")],
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="angle-img", label="Start")],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    bridge = ContinuityBridge(targetBatchId=batch.id, lastFrameAssetId="frame-ltx", status="Ready")
    req = build_timeline_generation_request(
        project_id="p", scene_id="s", batch=batch, snapshot=snap, incoming_bridge=bridge
    )
    assert req.startImageAssetId == "angle-img"
    assert req.continuityStrategy == "prompt_context"


def test_bridge_blocks_submit_until_ready_or_failed():
    b1 = BatchBlock(id="b1", sceneId="s", order=0)
    b2 = BatchBlock(id="b2", sceneId="s", order=1)
    waiting = ContinuityBridge(sourceBatchId="b1", targetBatchId="b2", status="Waiting")
    master = SceneTimelineMaster(
        batchBlocks=[b1, b2],
        continuityBridges=[waiting],
        continuityPolicy=default_policy_for_locality("local"),
    )
    assert bridge_blocks_submit(master, "b2") is waiting
    waiting.status = "Ready"
    assert bridge_blocks_submit(master, "b2") is None
    waiting.status = "Failed"
    assert bridge_blocks_submit(master, "b2") is waiting
    master.continuityPolicy.autoContinuity = False
    assert bridge_blocks_submit(master, "b2") is None


def test_supersede_marks_downstream_stale():
    b1 = BatchBlock(id="b1", sceneId="s", order=0, activeTakeId="take_a")
    b2 = BatchBlock(id="b2", sceneId="s", order=1, approvedClip=ApprovedClip(assetId="a2", executionSnapshotId="s2"))
    bridge = ContinuityBridge(sourceBatchId="b1", targetBatchId="b2", sourceTakeId="take_a", status="Applied")
    master = SceneTimelineMaster(batchBlocks=[b1, b2], continuityBridges=[bridge])
    supersede_outgoing_bridges(master, "b1", now="2026-08-14T00:00:00Z")
    assert bridge.status == "Superseded"
    assert b2.downstreamStale is True
    assert b2.staleFromTakeId == "take_a"


def test_continue_without_continuity_supersedes_failed_bridge():
    b2 = BatchBlock(id="b2", sceneId="s", order=1)
    bridge = ContinuityBridge(sourceBatchId="b1", targetBatchId="b2", status="Failed")
    master = SceneTimelineMaster(batchBlocks=[b2], continuityBridges=[bridge])
    continue_without_continuity(master, "b2")
    assert bridge.status == "Superseded"
    assert bridge.error == "CREATOR_CONTINUE_WITHOUT"


def test_compile_retake_memory_keeps_five_sections():
    batch = BatchBlock(
        sceneId="s",
        id="b1",
        approvedClip=ApprovedClip(assetId="old", executionSnapshotId="snap0"),
        candidateVersions=[
            CandidateVersion(
                executionSnapshotId="snap0",
                approved=True,
                originalTakeIntent={"prompt": "walk past"},
                takeState={"tail": "cruiser"},
                sequenceMemory={"batchOrder": 0},
            )
        ],
    )
    incoming = ContinuityBridge(
        bridgeId="cbr_x", lastFrameAssetId="fr", status="Ready", continuityStrategy="prompt_context"
    )
    memory = compile_retake_memory(
        master=SceneTimelineMaster(batchBlocks=[batch]),
        batch=batch,
        user_correction={"delta": "walk behind"},
        incoming=incoming,
    )
    assert set(memory) >= {
        "sequenceMemory",
        "incomingContinuity",
        "originalTakeIntent",
        "takeState",
        "userCorrection",
    }
    assert memory["userCorrection"]["delta"] == "walk behind"
    assert memory["incomingContinuity"]["bridgeId"] == "cbr_x"
    assert memory["originalTakeIntent"]["prompt"] == "walk past"


def test_minimax_t2v_refuses_to_claim_native_extend():
    adapter = MiniMaxH3LocalAdapter()
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="image_to_video",
        prompt="x",
        startImageAssetId="img",
        continuityStrategy="last_frame_i2v",
    )
    result = adapter.validate(req)
    assert result.ok is False

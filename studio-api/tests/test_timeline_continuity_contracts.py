"""ContinuityBridge + Auto-Extend contract tests (no Playwright)."""

from __future__ import annotations

from app.director_timeline_w46.continuity import (
    bridge_blocks_submit,
    bridge_extract_stale,
    bridge_source_stale,
    compile_retake_memory,
    continue_without_continuity,
    default_policy_for_locality,
    effective_tail_duration,
    generator_locality,
    last_frame_extract_seconds,
    new_bridge,
    paid_continuity_forbidden,
    prepare_outgoing_bridge,
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
    DurationState,
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
    assert generator_locality("ltx-2.5-distilled") == "local"
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
    assert req.generationMode == "reference"
    assert req.startImageAssetId is None
    assert req.continuityStrategy == "prompt_context"
    assert req.lastFrameAssetId == "frame-1"
    slots = (req.providerOptions.get("r2v") or {}).get("slots") or []
    assert any(slot.get("assetId") == "frame-1" and slot.get("role") == "prior_frame" for slot in slots)


def test_ltx_last_frame_is_i2v_not_native_tail():
    batch = BatchBlock(
        sceneId="s",
        generatorId="ltx-2.5-distilled",
        promptSegments=[
            TimelinePromptSegment(text="continue the walk", start=0, length=5, role="primary", versionId="v1")
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled")
    bridge = ContinuityBridge(targetBatchId=batch.id, lastFrameAssetId="frame-ltx", status="Ready")
    req = build_timeline_generation_request(
        project_id="p", scene_id="s", batch=batch, snapshot=snap, incoming_bridge=bridge
    )
    assert req.generationMode == "reference"
    assert req.startImageAssetId == "frame-ltx"
    assert req.continuityStrategy == "last_frame_i2v"
    assert req.continuityStrategy != "native_tail"


def test_new_angle_start_image_wins_over_last_frame():
    batch = BatchBlock(
        sceneId="s",
        generatorId="ltx-2.5-distilled",
        promptSegments=[TimelinePromptSegment(text="new angle", start=0, length=5, role="primary", versionId="v1")],
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="angle-img", label="Start")],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled")
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


def test_shot_last_frame_is_latent_end_not_five_seconds(monkeypatch):
    from app.media_clip import ltx_latent_frame_count, shot_last_frame_seconds
    import app.director_timeline_w46.continuity as continuity_mod

    assert ltx_latent_frame_count(5.0, 24.0) == 120
    assert abs(shot_last_frame_seconds(5.0, 24.0) - (119 / 24.0)) < 0.001
    monkeypatch.setattr(continuity_mod, "probe_video_duration", lambda path: 9.7)
    source = BatchBlock(sceneId="s", duration=DurationState(plannedDuration=5.0))
    assert last_frame_extract_seconds(source, "overlong.mp4") == shot_last_frame_seconds(5.0)
    monkeypatch.setattr(continuity_mod, "probe_video_duration", lambda path: 4.71)
    assert last_frame_extract_seconds(source, "trimmed.mp4") is None


def test_bridge_extract_stale_when_eof_used_on_overlong_file():
    source = BatchBlock(
        sceneId="s",
        duration=DurationState(plannedDuration=5.0),
        approvedClip=ApprovedClip(assetId="take_c", executionSnapshotId="snap"),
    )
    old = ContinuityBridge(sourceBatchId="b1", targetBatchId="b2", status="Ready")
    assert bridge_extract_stale(old, source, None) is False
    old.continuityState = {"sourceMediaDuration": 9.7}
    assert bridge_extract_stale(old, source, None) is True
    old.continuityState = {"sourceMediaDuration": 9.7, "extractedAtSeconds": 4.667}
    assert bridge_extract_stale(old, source, None) is False
    old.continuityState = {"sourceMediaDuration": 4.7}
    assert bridge_extract_stale(old, source, None) is False


def test_bridge_source_stale_on_new_approved_asset():
    source = BatchBlock(
        sceneId="s",
        approvedClip=ApprovedClip(assetId="new_asset", executionSnapshotId="snap"),
        activeTakeId="take_c",
    )
    bridge = ContinuityBridge(
        sourceTakeId="take_a",
        continuityState={"sourceAssetId": "old_asset"},
    )
    assert bridge_source_stale(bridge, source) is True
    source.activeTakeId = "take_a"
    source.approvedClip.assetId = "old_asset"
    assert bridge_source_stale(bridge, source) is False


def test_prepare_outgoing_rebuilds_when_extract_stale(monkeypatch):
    import app.director_timeline_w46.continuity as continuity_mod

    b1 = BatchBlock(
        id="b1",
        order=0,
        sceneId="s",
        generatorId="ltx-2.5-distilled",
        approvedClip=ApprovedClip(assetId="take_c", executionSnapshotId="snap"),
        duration=DurationState(plannedDuration=5.0, generatedDuration=9.7),
        activeTakeId="take_c",
    )
    b2 = BatchBlock(id="b2", order=1, sceneId="s", generatorId="ltx-2.5-distilled")
    stale = ContinuityBridge(
        sourceBatchId="b1",
        targetBatchId="b2",
        sourceTakeId="take_c",
        status="Ready",
        lastFrameAssetId="sheet_frame",
        continuityState={"sourceAssetId": "take_c", "sourceMediaDuration": 9.7},
    )
    master = SceneTimelineMaster(
        batchBlocks=[b1, b2],
        continuityBridges=[stale],
        continuityPolicy=default_policy_for_locality("local"),
    )

    def fake_analyze(db, project_id, master_in, bridge):
        bridge.status = "Ready"
        bridge.lastFrameAssetId = "shot_frame"
        return bridge

    monkeypatch.setattr(continuity_mod, "analyze_bridge", fake_analyze)
    monkeypatch.setattr(continuity_mod, "_approved_video_path", lambda db, source: None)
    monkeypatch.setattr(continuity_mod, "_run_temporal_review", lambda *a, **k: None)

    out = prepare_outgoing_bridge(None, "p", "s", master, "b1")
    assert stale.status == "Superseded"
    assert out is not None
    assert out.bridgeId != stale.bridgeId
    assert out.lastFrameAssetId == "shot_frame"


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


def test_extract_last_frame_skips_appended_sheet_tail(tmp_path):
    import shutil
    import subprocess

    import numpy as np
    import pytest
    from PIL import Image

    from app.director_timeline_w46.continuity import extract_last_frame_png
    from app.media_clip import trim_video_to_seconds

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")

    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    Image.new("RGB", (64, 36), (200, 20, 20)).save(red)
    Image.new("RGB", (64, 36), (20, 20, 200)).save(blue)
    shot = tmp_path / "shot.mp4"
    sheet = tmp_path / "sheet.mp4"
    concat = tmp_path / "concat.mp4"

    def still(src, dest, frames: int) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(src),
                "-frames:v",
                str(frames),
                "-r",
                "24",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )

    still(red, shot, 113)
    still(blue, sheet, 121)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(shot),
            "-i",
            str(sheet),
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            str(concat),
        ],
        check=True,
        capture_output=True,
    )
    dest = tmp_path / "last.png"
    extract_last_frame_png(str(concat), str(dest), at_frame=112)
    pix = np.asarray(Image.open(dest).convert("RGB"))
    assert pix[..., 0].mean() > 120
    assert pix[..., 2].mean() < 80
    assert trim_video_to_seconds(concat, 113 / 24.0) is True
    tail = tmp_path / "after_trim.png"
    extract_last_frame_png(str(concat), str(tail))
    trimmed = np.asarray(Image.open(tail).convert("RGB"))
    assert trimmed[..., 0].mean() > 120


def test_strip_leading_reference_removes_sheet_head(tmp_path):
    import shutil
    import subprocess

    import numpy as np
    import pytest
    from PIL import Image

    from app.media_clip import strip_leading_reference_frames

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")

    sheet_png = tmp_path / "sheet.png"
    shot_png = tmp_path / "shot.png"
    Image.new("RGB", (64, 36), (20, 20, 200)).save(sheet_png)
    Image.new("RGB", (64, 36), (200, 20, 20)).save(shot_png)
    sheet_mp4 = tmp_path / "sheet.mp4"
    shot_mp4 = tmp_path / "shot.mp4"
    concat = tmp_path / "concat.mp4"

    def still(src, dest, frames: int) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(src),
                "-frames:v",
                str(frames),
                "-r",
                "24",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )

    still(sheet_png, sheet_mp4, 16)
    still(shot_png, shot_mp4, 48)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(sheet_mp4),
            "-i",
            str(shot_mp4),
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            str(concat),
        ],
        check=True,
        capture_output=True,
    )
    assert strip_leading_reference_frames(concat, sheet_png) is True
    head = tmp_path / "head.png"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(concat), "-frames:v", "1", str(head)],
        check=True,
        capture_output=True,
    )
    pix = np.asarray(Image.open(head).convert("RGB"))
    assert pix[..., 0].mean() > 120

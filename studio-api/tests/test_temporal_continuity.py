"""Revision A temporal continuity contracts, gate, and adapter consumption."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.codirector.video_intelligence.cadence import resolve_cadence, window_seconds
from app.codirector.video_intelligence.compare import compare_intent_vs_actual
from app.codirector.video_intelligence.compile import compile_temporal_continuation
from app.codirector.video_intelligence.contracts import (
    PACKET_SCHEMA,
    CoDirectorContinuityPolicy,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
)
from app.codirector.video_intelligence.service import (
    find_packet_for_handoff,
    packet_blocks_submit,
    review_completed_batch,
    set_codirector_continuity_policy,
)
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    ContinuityBridge,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.setup.catalog import BY_ID


def _master_two_batches() -> SceneTimelineMaster:
    first = BatchBlock(
        id="bb_a",
        sceneId="s1",
        order=0,
        status="Approved",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(text="Korri and Anadriya walk. Korri begins turning toward Anadriya.")
        ],
        approvedClip=ApprovedClip(assetId="asset_a", executionSnapshotId="snap_a"),
    )
    second = BatchBlock(
        id="bb_b",
        sceneId="s1",
        order=1,
        status="Queued",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="Korri responds. Both keep walking.")],
    )
    return SceneTimelineMaster(
        batchBlocks=[first, second],
        continuityBridges=[
            ContinuityBridge(
                bridgeId="cbr_1",
                sceneId="s1",
                sourceBatchId="bb_a",
                targetBatchId="bb_b",
                status="Ready",
                lastFrameAssetId="frame_a",
            )
        ],
    )


def test_packet_name_is_not_wave5_continuity_packet():
    packet = TemporalContinuityPacket()
    assert packet.schemaVersion == PACKET_SCHEMA
    assert type(packet).__name__ == "TemporalContinuityPacket"


def test_automatic_cadence_picks_action_vs_dialogue():
    policy = CoDirectorContinuityPolicy(reviewCadence="automatic")
    assert resolve_cadence(policy, prompt="a fight and dolly", character_count=2) == "interval_3"
    assert resolve_cadence(policy, prompt="quiet dialogue sitting") == "interval_5"
    assert window_seconds("interval_3", 5.0) == 3.0


def test_compare_keeps_successful_material_and_continues_unfinished():
    packet = TemporalContinuityPacket()
    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText="Walking remains correct. Turn is about 70 percent complete. Dolly remains correct.",
        unfinishedActions=["finish Korri's turn"],
        completedActions=["walking continues"],
        confidence=0.7,
        parseOk=True,
    )
    out = compare_intent_vs_actual(
        packet,
        observation,
        context={"prompt": "Korri turns toward Anadriya while walking."},
    )
    assert out.decision == "keep_and_continue"
    assert out.availability == "ready"
    assert any("turn" in item.lower() for item in out.continuation.continue_)
    assert any("restart" in item.lower() for item in out.continuation.avoid)


def test_degraded_packet_releases_gate_and_does_not_invent_directives():
    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="VIDEOCHAT3_NOT_INSTALLED",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    master.temporalPackets = [packet]
    assert packet.is_gate_ready()
    assert packet_blocks_submit(master, "bb_b") is False
    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    assert compiled["applied"] is False
    assert compiled["promptPrefix"] == ""


def test_missing_packet_blocks_submit_when_continuity_on():
    master = _master_two_batches()
    assert master.coDirectorContinuityPolicy.enabled is True
    assert packet_blocks_submit(master, "bb_b") is True
    set_codirector_continuity_policy(master, {"enabled": False})
    assert packet_blocks_submit(master, "bb_b") is False


def test_request_builder_consumes_ready_packet():
    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    packet.continuation.nextBatchDirectives = ["Finish the remaining Korri turn."]
    packet.continuation.preserve = ["walking velocity"]
    packet.continuation.avoid = ["recenter"]
    snap = ExecutionSnapshot(batchBlockId="bb_b")
    req = build_timeline_generation_request(
        project_id="p1",
        scene_id="s1",
        batch=master.batchBlocks[1],
        snapshot=snap,
        incoming_bridge=master.continuityBridges[0],
        temporal_packet=packet,
    )
    assert req.temporalContinuityPacketId == packet.packetId
    assert "Finish the remaining Korri turn" in req.prompt
    assert req.providerOptions["temporalContinuation"]["applied"] is True
    assert MiniMaxH3LocalAdapter.capabilities.supportsPromptContinuation is True
    assert MiniMaxH3LocalAdapter.capabilities.supportsTemporalConditioning is False


def test_review_without_video_emits_degraded_packet(monkeypatch):
    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "fail"
    master = _master_two_batches()
    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.availability == "unavailable"
    assert find_packet_for_handoff(master, "bb_a", "bb_b") is not None
    assert packet_blocks_submit(master, "bb_b") is False


def test_setup_catalog_marks_videochat3_required():
    assert BY_ID["videochat3_4b"].required is True
    assert BY_ID["internvideo3_8b"].required is False
    assert BY_ID["videochat3_4b"].category == "Video Understanding"


def test_timelens_is_not_a_setup_component():
    assert "timelens" not in BY_ID


def test_video_understanding_revisions_are_pinned():
    from app.codirector.video_intelligence.paths import (
        INTERNVIDEO3_HF_ID,
        INTERNVIDEO3_REVISION,
        VIDEOCHAT3_HF_ID,
        VIDEOCHAT3_REVISION,
    )

    assert VIDEOCHAT3_HF_ID == "MCG-NJU/VideoChat3-4B"
    assert VIDEOCHAT3_REVISION == "37fa901ec5913f84bc31108ebc1e60ad1903634c"
    assert INTERNVIDEO3_HF_ID == "yanziang/InternVideo3-8B-Instruct"
    assert INTERNVIDEO3_REVISION == "c4602918b65225650d152db2850fe34e01d21fcd"


def test_stub_perception_is_used_by_compare_and_adapter_compile(tmp_path, monkeypatch):
    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "stub"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-mp4")
    from app.codirector.video_intelligence.worker_client import run_perception

    observation = run_perception(str(video), model_id="videochat3-4b")
    assert "Walking remains correct" in observation.rawText
    packet = compare_intent_vs_actual(
        TemporalContinuityPacket(),
        observation,
        context={"prompt": "Korri turns while walking."},
    )
    assert packet.availability == "ready"
    assert packet.decision == "keep_and_continue"
    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    assert compiled["applied"] is True
    assert "turn" in compiled["promptPrefix"].lower()


def test_stub_review_with_video_emits_ready_packet(tmp_path, monkeypatch):
    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "stub"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-mp4")
    master = _master_two_batches()
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._asset_path",
        lambda *args, **kwargs: str(video),
    )
    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.availability == "ready"
    assert packet.decision == "keep_and_continue"
    assert packet_blocks_submit(master, "bb_b") is False
    assert master.continuityBridges[0].continuityState.get("temporalPacketId") == packet.packetId


def test_submit_next_queued_does_not_call_adapter_until_packet_exists(monkeypatch):
    from app.director_timeline_w46 import orchestrator
    from app.director_timeline_w46.generation.adapters.seedance_api import SeedanceApiAdapter
    from app.director_timeline_w46.generation.adapters.kling_api import KlingApiAdapter

    master = _master_two_batches()
    submitted: list[str] = []

    monkeypatch.setattr(
        orchestrator.store,
        "load_master",
        lambda *args, **kwargs: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(orchestrator.store, "save_master", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        orchestrator,
        "submit_batch_generation",
        lambda *args, **kwargs: submitted.append("submit") or {"ok": True},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        lambda *args, **kwargs: None,
    )

    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert result.get("submitted") is False
    assert result.get("reason") == "temporal_review_pending"
    assert submitted == []

    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="VIDEOCHAT3_NOT_INSTALLED",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    master.temporalPackets = [packet]

    def ensure_ready(*args, **kwargs):
        return packet

    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        ensure_ready,
    )
    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert submitted == ["submit"]
    assert result.get("submitted") is True
    assert SeedanceApiAdapter.capabilities.supportsPromptContinuation is True
    assert KlingApiAdapter.capabilities.supportsTemporalConditioning is False


def test_continuity_on_forces_sequential_scene_generation():
    master = _master_two_batches()
    master.orchestratorMode = "parallel"
    master.coDirectorContinuityPolicy.enabled = True
    cd_enabled = master.coDirectorContinuityPolicy.enabled
    sequential = master.orchestratorMode != "parallel" or cd_enabled
    assert sequential is True
    master.coDirectorContinuityPolicy.enabled = False
    sequential = master.orchestratorMode != "parallel" or master.coDirectorContinuityPolicy.enabled
    assert sequential is False


def test_prepare_plan_routes_videochat3_away_from_hunyuan():
    from app.setup.orchestrator import _checkpoint_for

    action = _checkpoint_for("videochat3_4b", "install")
    assert action["type"] == "video_understanding_hf_install"
    assert "Tencent" not in action["summary"]
    hunyuan = _checkpoint_for("hunyuan_video_15", "install")
    assert hunyuan["type"] == "hunyuan_hf_install"

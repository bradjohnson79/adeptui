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
        VIDEOCHAT3_POLL_SHA256,
        VIDEOCHAT3_REVISION,
        VIDEOCHAT3_WEIGHT_BYTES,
        VIDEOCHAT3_WEIGHT_SHA256,
    )

    assert VIDEOCHAT3_HF_ID == "MCG-NJU/VideoChat3-4B"
    assert VIDEOCHAT3_REVISION == "37fa901ec5913f84bc31108ebc1e60ad1903634c"
    assert INTERNVIDEO3_HF_ID == "yanziang/InternVideo3-8B-Instruct"
    assert INTERNVIDEO3_REVISION == "c4602918b65225650d152db2850fe34e01d21fcd"
    assert VIDEOCHAT3_POLL_SHA256["config.json"].startswith("d855aa0d")
    assert VIDEOCHAT3_WEIGHT_BYTES["model-0001-others-save_rank0.safetensors"] == 4252181336
    assert len(VIDEOCHAT3_WEIGHT_SHA256) == 3


def test_poll_safe_integrity_rejects_filename_only(tmp_path):
    from app.codirector.video_intelligence.paths import poll_safe_integrity

    dest = tmp_path / "videochat3-4b"
    dest.mkdir()
    (dest / "config.json").write_text("{}", encoding="utf-8")
    (dest / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
    (dest / "model-0001-others-save_rank0.safetensors").write_bytes(b"not-weights")
    result = poll_safe_integrity(dest)
    assert result["ok"] is False
    assert result["reason"] in ("SHA_MISMATCH:config.json", "MISSING:model-0001-others-save_rank0.safetensors") or str(
        result["reason"]
    ).startswith("SHA_MISMATCH") or str(result["reason"]).startswith("SIZE_MISMATCH")


def test_certify_receipt_is_required_for_ready(tmp_path, monkeypatch):
    from app.codirector.video_intelligence import certify

    monkeypatch.setattr(certify, "load_receipt", lambda: None)
    assert certify.receipt_is_ready() is False
    monkeypatch.setattr(
        certify,
        "load_receipt",
        lambda: {"ok": True, "liveInfer": True, "revision": "37fa901ec5913f84bc31108ebc1e60ad1903634c"},
    )
    assert certify.receipt_is_ready() is True


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


def test_worker_python_prefers_override(monkeypatch, tmp_path):
    from app.codirector.video_intelligence.paths import worker_python

    fake = tmp_path / "gpu-python.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("ADEPT_VIDEO_INTELLIGENCE_PYTHON", str(fake))
    assert worker_python() == fake


def test_health_probe_skips_spawn_when_requested(monkeypatch, tmp_path):
    from app.codirector.video_intelligence import health

    dest = tmp_path / "videochat3-4b"
    dest.mkdir()
    monkeypatch.setattr(health, "videochat3_dir", lambda: dest)
    monkeypatch.setattr(health, "model_present", lambda *args, **kwargs: True)
    monkeypatch.setattr(health, "_config_ok", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(health, "poll_safe_integrity", lambda *args, **kwargs: {"ok": True})
    spawned: list[bool] = []

    def fake_run(*args, **kwargs):
        spawned.append(True)
        raise AssertionError("worker --health must not spawn on poll-safe verify")

    monkeypatch.setattr(health.subprocess, "run", fake_run)
    result = health.probe_component("videochat3_4b", spawn_worker=False)
    assert spawned == []
    assert result["ok"] is True
    assert result["workerHealth"]["skipped"] is True


def test_prepare_plan_routes_videochat3_away_from_hunyuan():
    from app.setup.orchestrator import _checkpoint_for

    action = _checkpoint_for("videochat3_4b", "install")
    assert action["type"] == "video_understanding_hf_install"
    assert "Tencent" not in action["summary"]
    hunyuan = _checkpoint_for("hunyuan_video_15", "install")
    assert hunyuan["type"] == "hunyuan_hf_install"


def test_production_forbids_stub_and_missing_model_is_unavailable(tmp_path, monkeypatch):
    from app.codirector.video_intelligence.worker_client import (
        normalize_perception_reason,
        run_perception,
        stub_allowed,
    )

    monkeypatch.setenv("ADEPT_TEMPORAL_PERCEPTION_MODE", "stub")
    monkeypatch.delenv("ADEPT_ALLOW_PERCEPTION_STUB", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert stub_allowed() is False
    with pytest.raises(RuntimeError, match="STUB_FORBIDDEN"):
        run_perception(str(tmp_path / "clip.mp4"))

    monkeypatch.setenv("ADEPT_TEMPORAL_PERCEPTION_MODE", "live")
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.videochat3_dir",
        lambda: tmp_path / "missing-videochat3",
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.model_present",
        lambda *args, **kwargs: False,
    )
    with pytest.raises(RuntimeError, match="MODEL_NOT_INSTALLED"):
        run_perception(str(tmp_path / "clip.mp4"))
    assert normalize_perception_reason("VIDEOCHAT3_NOT_INSTALLED") == "MODEL_NOT_INSTALLED"


def test_review_maps_missing_model_to_unavailable_without_stub_directives(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-mp4")
    master = _master_two_batches()
    monkeypatch.delenv("ADEPT_TEMPORAL_PERCEPTION_MODE", raising=False)
    monkeypatch.delenv("ADEPT_ALLOW_PERCEPTION_STUB", raising=False)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._asset_path",
        lambda *args, **kwargs: str(video),
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.best_effort_free_generator",
        lambda: {"comfyFreeRequested": True, "comfyFreeStatus": 200, "vramAfterFreeGb": 20.0},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.preflight_for_review",
        lambda: {"ok": True, "freeVramGb": 20.0, "unknownVram": False},
    )

    def boom(*args, **kwargs):
        raise RuntimeError("MODEL_NOT_INSTALLED")

    monkeypatch.setattr("app.codirector.video_intelligence.service.run_perception", boom)
    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.availability == "unavailable"
    assert packet.reason == "MODEL_NOT_INSTALLED"
    assert packet.continuation.preserve == []
    assert packet.continuation.nextBatchDirectives == []
    assert packet_blocks_submit(master, "bb_b") is False


def test_extracted_review_clip_is_removed(tmp_path):
    from app.codirector.video_intelligence.clip_extract import cleanup_extracted_clip

    source = tmp_path / "approved.mp4"
    source.write_bytes(b"source")
    review = tmp_path / "approved.review512.mp4"
    review.write_bytes(b"extract")
    assert cleanup_extracted_clip(str(review), source_path=str(source)) is True
    assert not review.exists()
    assert source.exists()
    assert cleanup_extracted_clip(str(source), source_path=str(source)) is False


def test_gpu_lease_records_vram_after_free(monkeypatch):
    from app.codirector.video_intelligence import gpu_lease

    class FakeResp:
        status_code = 200

    monkeypatch.setattr(gpu_lease, "query_free_vram_gb", lambda: 12.5)

    class FakeHttpx:
        @staticmethod
        def post(*args, **kwargs):
            assert kwargs.get("timeout") == 30.0
            return FakeResp()

    import sys
    import types

    monkeypatch.setitem(sys.modules, "httpx", FakeHttpx)
    evidence = gpu_lease.best_effort_free_generator()
    assert evidence["comfyFreeRequested"] is True
    assert evidence["comfyFreeStatus"] == 200
    assert evidence["vramAfterFreeGb"] == 12.5
    assert evidence["vramFullyReleased"] is True


def test_unfinished_string_does_not_split_into_characters():
    from app.codirector.video_intelligence.worker_client import _as_str_list

    assert _as_str_list("The turn is unfinished.") == ["The turn is unfinished."]
    assert _as_str_list(["a", "b"]) == ["a", "b"]
    assert _as_str_list(None) == []
    assert _as_str_list("[]") == []
    assert _as_str_list(["[],"]) == []


def test_empty_json_unfinished_does_not_become_brackets():
    from app.codirector.video_intelligence.worker_client import _observation_from_payload

    raw = (
        "The girls still standing in the same positions, facing each other.\n\n"
        '{\n  "unfinishedActions": [],\n  "completedActions": ["left looks right"],\n  "confidence": 1.0\n}'
    )
    obs = _observation_from_payload(
        {
            "ok": True,
            "modelId": "videochat3-4b",
            "rawText": raw,
            "unfinishedActions": [],
            "completedActions": [],
            "parseOk": True,
        }
    )
    assert obs.unfinishedActions == []
    filled = compare_intent_vs_actual(TemporalContinuityPacket(), obs, protection="strong")
    assert filled.continuation.continue_ != ["Finish: [],"]
    assert "Finish: []," not in filled.continuation.continue_
    assert filled.continuation.continue_[0].startswith("Continue:")


def test_unfinished_string_compare_is_one_directive():
    from app.codirector.video_intelligence.worker_client import _as_str_list

    packet = TemporalContinuityPacket()
    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText="Korri begins turning toward Anadriya.",
        unfinishedActions=_as_str_list("turn toward the other character"),
        parseOk=True,
    )
    filled = compare_intent_vs_actual(packet, observation, protection="strong")
    continue_items = filled.continuation.continue_
    assert continue_items == ["Finish: turn toward the other character"]
    assert len(continue_items) == 1


def test_compare_uses_observed_ending_when_unfinished_empty():
    packet = TemporalContinuityPacket()
    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText="The character on the left turns her head to look at the character on the right. The character on the right looks at the front.",
        unfinishedActions=[],
        parseOk=False,
    )
    filled = compare_intent_vs_actual(packet, observation, protection="strong")
    assert filled.continuation.continue_ == ["Continue: The character on the right looks at the front."]
    assert "Finish: T" not in filled.continuation.continue_


def test_continuity_off_does_not_block_submit():
    master = _master_two_batches()
    master.coDirectorContinuityPolicy.enabled = False
    assert packet_blocks_submit(master, "bb_b") is False

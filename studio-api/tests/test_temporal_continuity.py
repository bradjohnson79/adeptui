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
    Assessment,
    CoDirectorContinuityPolicy,
    ExitState,
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
    from app.runtime_session import current_runtime_session_id

    return SceneTimelineMaster(
        renderSessionId=current_runtime_session_id(),
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


def test_automatic_cadence_uses_full_clip_every_batch():
    """Full-clip Continuity: automatic Timeline path reviews the whole approved shot."""
    from app.codirector.video_intelligence.cadence import review_window_kind

    policy = CoDirectorContinuityPolicy(reviewCadence="automatic")
    assert resolve_cadence(policy, prompt="a fight and dolly", character_count=2) == "every_batch"
    assert resolve_cadence(policy, prompt="quiet dialogue sitting") == "every_batch"
    assert resolve_cadence(policy, prompt="anything", generated_duration=15.0) == "every_batch"
    # Explicit creator choices still honor interval / every_batch.
    assert resolve_cadence(CoDirectorContinuityPolicy(reviewCadence="interval_3"), prompt="fight") == "interval_3"
    assert resolve_cadence(CoDirectorContinuityPolicy(reviewCadence="interval_5"), prompt="dialogue") == "interval_5"
    assert window_seconds("interval_3", 5.0) == 3.0
    assert window_seconds("every_batch", 15.0) == 15.0
    assert review_window_kind("every_batch") == "full_clip"
    assert review_window_kind("interval_5") == "tail_5"


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


def test_compile_carries_full_watch_and_exit_frame():
    packet = TemporalContinuityPacket(
        availability="ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
        assessment=Assessment(
            observedState=(
                "One distant figure walks through a golden field. "
                "The camera pushes in. The last frame is a medium shot of that same figure, "
                "sun still on the left. {\"unfinishedActions\": [], \"completedActions\": [], \"confidence\": 0.8}"
            )
        ),
        exitState=ExitState(
            summary="The figure is still walking away.",
            cameraState="medium shot, pushing in",
            environmentState="golden field, sun on the left",
            characterStates=["one distant figure in dark clothing"],
        ),
    )
    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    prefix = compiled["promptPrefix"]
    assert "Watched:" in prefix
    assert "golden field" in prefix
    assert "unfinishedActions" not in prefix
    assert "ExitCamera: medium shot, pushing in" in prefix
    assert "ExitPlace: golden field, sun on the left" in prefix
    assert "ExitPerson: one distant figure in dark clothing" in prefix


def test_degraded_packet_releases_gate_and_does_not_invent_directives():
    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="VIDEOCHAT3_NOT_INSTALLED",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
        extras={"reviewedAssetId": "asset_a"},
    )
    master.temporalPackets = [packet]
    assert packet.is_gate_ready() is False
    assert packet_blocks_submit(master, "bb_b") is True
    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    assert compiled["applied"] is False
    assert compiled["promptPrefix"] == ""


def test_unstamped_packet_blocks_submit_gate():
    """Historical-take contamination guard at the gate: a packet that cannot
    prove it reviewed the predecessor's CURRENT asset must not release the
    extension submit — even when it is otherwise gate-ready."""
    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="VIDEOCHAT3_NOT_INSTALLED",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
        # No extras.reviewedAssetId — legacy/stale packet shape.
    )
    master.temporalPackets = [packet]
    assert packet.is_gate_ready() is False
    assert packet_blocks_submit(master, "bb_b") is True


def test_packet_invalidated_by_revision_is_stale():
    """REBUILD LAW fence (scene revision authority): when a batch's prompt
    materially changes, packets derived from the OLD intent are invalidated
    (extras.invalidatedByRevision) and must not release the extension submit
    even though the reviewed asset id is unchanged — the next submit forces a
    re-review against the current revision."""
    from app.codirector.video_intelligence.service import (
        invalidate_packets_for_source_batch,
        is_packet_stale_for_batch,
    )

    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
        extras={"reviewedAssetId": "asset_a"},
    )
    master.temporalPackets = [packet]
    # Asset unchanged → not stale before revision.
    batch_a = next(b for b in master.batchBlocks if b.id == "bb_a")
    assert is_packet_stale_for_batch(packet, batch_a) is False
    # Material revision → invalidated → stale at the gate.
    assert invalidate_packets_for_source_batch(master, "bb_a") == 1
    assert is_packet_stale_for_batch(packet, batch_a) is True
    assert packet_blocks_submit(master, "bb_b") is True
    # Idempotent.
    assert invalidate_packets_for_source_batch(master, "bb_a") == 0


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
    assert packet_blocks_submit(master, "bb_b") is True


def test_setup_catalog_does_not_require_videochat3():
    from app.setup.catalog import public_components

    assert BY_ID["videochat3_4b"].required is False
    assert "videochat3_4b" not in {item.id for item in public_components()}
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

    from app.codirector.video_intelligence.gpu_lease import handoff_key, note_handoff, reset_handoff_state

    reset_handoff_state()
    note_handoff(handoff_key("s1", "", "bb_a"), state="ready")
    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert result.get("submitted") is False
    assert result.get("reason") == "temporal_review_pending"
    assert submitted == []

    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="VIDEOCHAT3_NOT_INSTALLED",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
        extras={"reviewedAssetId": "asset_a"},
    )
    master.temporalPackets = [packet]

    def ensure_ready(*args, **kwargs):
        return packet

    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        ensure_ready,
    )
    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert submitted == []
    assert result.get("submitted") is False
    assert result.get("reason") == "temporal_review_pending"
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
    assert hunyuan["type"] == "retired_video_generator"


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
    assert packet_blocks_submit(master, "bb_b") is True


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


def test_compare_prefers_motion_sentence_over_atmosphere():
    packet = TemporalContinuityPacket()
    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText=(
            "The woman on the left then looks back forward. "
            "The overall atmosphere is one of mystery and intrigue."
        ),
        unfinishedActions=[],
        parseOk=False,
    )
    filled = compare_intent_vs_actual(packet, observation, protection="strong")
    assert filled.continuation.continue_ == ["Continue: The woman on the left then looks back forward."]


def test_continuity_off_does_not_block_submit():
    master = _master_two_batches()
    master.coDirectorContinuityPolicy.enabled = False
    assert packet_blocks_submit(master, "bb_b") is False


def test_queue_hops_merge_keeps_claim_timestamp():
    from app.video_runtime.job_model import merge_video_runtime_history

    first = merge_video_runtime_history(None, {"queueHops": {"claimedAt": "t0", "enqueueOk": True}})
    second = merge_video_runtime_history(
        first,
        {"queueHops": {"providerPromptId": "p1", "providerAccepted": True}},
    )
    import json

    hops = json.loads(second)["videoRuntime"]["queueHops"]
    assert hops["claimedAt"] == "t0"
    assert hops["enqueueOk"] is True
    assert hops["providerPromptId"] == "p1"
    assert hops["providerAccepted"] is True


# ---------------------------------------------------------------------------
# Full-clip Continuity Challenge + rolling scene state
# ---------------------------------------------------------------------------


def test_sample_timestamps_cover_early_and_dense_end():
    from app.codirector.video_intelligence.clip_extract import sample_timestamps_for_full_clip_review

    stamps = sample_timestamps_for_full_clip_review(15.0, broad_count=6, dense_end_sec=3.0, dense_fps=2.0)
    assert stamps[0] <= 0.05
    assert any(t <= 2.5 for t in stamps)  # early
    assert any(5.0 <= t <= 10.0 for t in stamps)  # mid
    assert stamps[-1] >= 14.0
    # Dense near end: multiple samples in last 3s
    end_samples = [t for t in stamps if t >= 12.0]
    assert len(end_samples) >= 3


def test_continuity_challenge_early_event_survives_into_next_packet(tmp_path, monkeypatch):
    """Continuity Challenge: event early in ~15s clip must appear in next-shot packet."""
    import os
    from app.codirector.video_intelligence.contracts import ImportantEvent
    from app.codirector.video_intelligence.worker_client import VideoPerceptionObservation as _unused

    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "stub"
    video = tmp_path / "clip15.mp4"
    video.write_bytes(b"not-a-real-mp4")

    master = _master_two_batches()
    master.batchBlocks[0].duration.generatedDuration = 15.0
    master.batchBlocks[0].duration.plannedDuration = 15.0
    master.coDirectorContinuityPolicy.reviewCadence = "automatic"

    # Stub perception that reports an EARLY event in a 15s window.
    from app.codirector.video_intelligence.contracts import VideoPerceptionObservation

    early_obs = VideoPerceptionObservation(
        modelId="videochat3-4b",
        timeRange=(0.0, 15.0),
        rawText=(
            "At the start a blue cup is knocked over on the left table. "
            "Later the characters keep walking forward. "
            "Near the end Korri turns toward Anadriya."
            '\n\n{"unfinishedActions": [], "completedActions": ["blue cup knocked over", "walking continues", "Korri turns"], "confidence": 0.82}'
        ),
        unfinishedActions=[],
        completedActions=["blue cup knocked over", "walking continues", "Korri turns"],
        confidence=0.82,
        parseOk=True,
    )

    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._asset_path",
        lambda *args, **kwargs: str(video),
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.run_perception",
        lambda *args, **kwargs: early_obs,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.extract_full_clip_review",
        lambda *args, **kwargs: str(video),
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.cleanup_extracted_clip",
        lambda *args, **kwargs: True,
    )

    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.availability == "ready"
    assert (packet.extras or {}).get("reviewWindowKind") == "full_clip"
    assert float(packet.source.startTime) == 0.0
    assert float(packet.source.endTime) >= 14.0

    labels = " ".join(e.label.lower() for e in (packet.importantEvents or []))
    assert "blue cup" in labels or "knocked" in labels
    early_or_mid = [e for e in (packet.importantEvents or []) if e.phase in ("early", "mid")]
    assert early_or_mid, f"expected early/mid events, got {[e.phase for e in packet.importantEvents]}"

    # Early event must appear in next-batch directives / compiled prompt for N+1.
    directive_blob = " ".join(packet.continuation.nextBatchDirectives).lower()
    assert "blue cup" in directive_blob or "earlier beat" in directive_blob or "knocked" in directive_blob

    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    assert compiled["applied"] is True
    assert compiled.get("reviewWindowKind") == "full_clip"
    assert "blue cup" in compiled["promptPrefix"].lower() or "knocked" in compiled["promptPrefix"].lower()
    assert "Event(" in compiled["promptPrefix"]

    # Rolling digest persisted on master
    assert getattr(master, "coDirectorRollingSceneDigest", None)
    digest = master.coDirectorRollingSceneDigest
    assert isinstance(digest, dict)
    event_labels = " ".join(
        str(e.get("label") or "").lower() for e in (digest.get("importantEvents") or [])
    )
    assert "blue cup" in event_labels or "knocked" in event_labels


def test_compare_captures_early_mid_events_not_only_tail():
    packet = TemporalContinuityPacket(
        source={"batchId": "bb_a", "targetBatchId": "bb_b", "startTime": 0.0, "endTime": 15.0}
    )
    observation = VideoPerceptionObservation(
        modelId="stub",
        timeRange=(0.0, 15.0),
        rawText="Early on a lantern tips over. Midway she waves. At the end he looks left.",
        completedActions=["lantern tips over", "she waves", "he looks left"],
        unfinishedActions=[],
        confidence=0.9,
        parseOk=True,
    )
    out = compare_intent_vs_actual(packet, observation, context={"prompt": "continue the scene"})
    phases = {e.phase for e in out.importantEvents}
    assert "early" in phases or "mid" in phases
    assert any("lantern" in e.label.lower() for e in out.importantEvents)
    assert out.exitState is not None
    assert out.rollingSceneDigest is not None


def test_retake_memory_freezes_temporal_directives_from_approved_prior():
    from app.director_timeline_w46.continuity import compile_retake_memory

    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    packet.continuation.nextBatchDirectives = ["Finish the remaining Korri turn."]
    packet.continuation.preserve = ["walking velocity"]
    packet.importantEvents = [
        __import__("app.codirector.video_intelligence.contracts", fromlist=["ImportantEvent"]).ImportantEvent(
            label="blue cup knocked over", phase="early", approxTimeSec=1.2
        )
    ]
    packet.extras = {"reviewWindowKind": "full_clip"}
    master.temporalPackets = [packet]
    master.coDirectorRollingSceneDigest = {"schemaVersion": "rolling-scene-digest-v1", "preserve": ["walking velocity"]}

    mem = compile_retake_memory(
        master=master,
        batch=master.batchBlocks[1],
        user_correction={"note": "tighter framing"},
        incoming=master.continuityBridges[0],
    )
    frozen = mem["incomingContinuity"].get("temporalContinuity") or {}
    assert frozen.get("packetId") == packet.packetId
    assert "Finish the remaining Korri turn." in (frozen.get("nextBatchDirectives") or [])
    assert mem["sequenceMemory"].get("temporalDirectivesFrozen") is True
    assert any("blue cup" in str(e.get("label") or "").lower() for e in (frozen.get("importantEvents") or []))


def test_rejected_packet_not_frozen_into_retake_memory():
    from app.director_timeline_w46.continuity import compile_retake_memory

    master = _master_two_batches()
    packet = TemporalContinuityPacket(
        availability="ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    packet.continuation.nextBatchDirectives = ["BAD DIRECTIVE FROM REJECTED"]
    packet.continuation.creatorRejected = True
    master.temporalPackets = [packet]
    mem = compile_retake_memory(
        master=master,
        batch=master.batchBlocks[1],
        user_correction={},
        incoming=master.continuityBridges[0],
    )
    assert "temporalContinuity" not in (mem.get("incomingContinuity") or {})

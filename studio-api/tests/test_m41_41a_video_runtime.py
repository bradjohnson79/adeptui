"""M41 4.1A — Video Runtime unit tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.video_runtime.compatibility_registry import (
    catalog_as_dict,
    get_entry,
    missing_nodes,
    validate_inputs,
)
from app.video_runtime.failures import classify_exception, failure_payload
from app.video_runtime.job_model import (
    FailureClass,
    NormalizedStage,
    ProviderKindVideo,
    VideoJobContract,
    apply_contract_to_job_params,
    concurrency_for_workflow,
)
from app.video_runtime.output_gate import validate_video_output
from app.video_runtime.vram_safety import VramSafetyState, estimate_vram


def test_compatibility_catalog_loads_production_and_deferred():
    entries = catalog_as_dict()
    keys = {e["workflowKey"] for e in entries}
    assert "wan.first_last_frame" in keys
    assert "ltx.simple_i2v" in keys
    assert "video.upscale" in keys
    assert "video.motion_transfer" in keys
    wan = get_entry("wan.first_last_frame")
    assert wan is not None
    assert wan.min_vram_gb >= 20
    assert "middle_frame" in wan.unsupported_inputs
    # M41 4.1B honesty: not production_ready until CERTIFIED with live evidence
    assert wan.capability_state in {
        "production_ready",
        "pending_certification",
        "blocked",
    }
    assert get_entry("video.upscale").capability_state == "deferred"


def test_wan_middle_frame_rejected_by_registry():
    wan = get_entry("wan.first_last_frame")
    assert wan is not None
    bad = validate_inputs(wan, ["first_frame", "middle_frame", "prompt"])
    assert "middle_frame" in bad


def test_missing_nodes_alias_latentsync():
    entry = get_entry("lipsync.latentsync")
    assert entry is not None
    # Only D_LatentSyncNode present satisfies the sampler alias group, and
    # VHS_LoadAudio satisfies the [LoadAudio, VHS_LoadAudio] alias group.
    miss = missing_nodes(entry, {"D_LatentSyncNode", "PreviewAny", "VHS_VideoCombine", "VHS_LoadAudio"})
    assert miss == []
    # Without any audio-loader alias member, LoadAudio is correctly reported missing.
    miss_no_audio = missing_nodes(entry, {"D_LatentSyncNode", "PreviewAny", "VHS_VideoCombine"})
    assert miss_no_audio == ["LoadAudio"]


def test_vram_estimate_states():
    with patch("app.video_runtime.vram_safety._free_vram_gb", return_value=30.0):
        est = estimate_vram("wan.first_last_frame", width=1280, height=720, frames=81)
        assert est.state == VramSafetyState.SAFE
    with patch("app.video_runtime.vram_safety._free_vram_gb", return_value=8.0):
        est = estimate_vram("wan.first_last_frame", width=1920, height=1080, frames=241)
        assert est.state in {
            VramSafetyState.INSUFFICIENT,
            VramSafetyState.HIGH_RISK,
            VramSafetyState.TIGHT,
        }
        assert est.recommendations
        assert est.safe_config.get("tiledVae") is True


def test_job_contract_roundtrip():
    c = VideoJobContract(
        mode="image_to_video",
        workflow_key="ltx.simple_i2v",
        provider_kind=ProviderKindVideo.LOCAL,
        engine="ltx",
        width=1280,
        height=720,
        frames=81,
        stage=NormalizedStage.SAMPLING,
    )
    raw = apply_contract_to_job_params({}, c)
    params = json.loads(raw)
    assert params["videoRuntime"]["workflow_key"] == "ltx.simple_i2v"
    assert concurrency_for_workflow("fal.seedance", ProviderKindVideo.EXTERNAL_API).value == "cloud"


def test_failure_classification():
    assert classify_exception(RuntimeError("CUDA out of memory")) == FailureClass.VRAM_EXHAUSTED
    assert classify_exception(TimeoutError("timed out")) == FailureClass.PROVIDER_TIMEOUT
    payload = failure_payload(
        FailureClass.USER_CANCELLATION,
        message="Cancelled",
        compute_consumed=True,
    )
    assert payload["retrySafe"] is False
    assert payload["computeConsumed"] is True


def test_output_gate_missing_file(tmp_path: Path):
    result = validate_video_output(tmp_path / "missing.mp4")
    assert result.passed is False
    assert result.status == "output_missing"


def test_output_gate_nonzero_file(tmp_path: Path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"not-a-real-mp4-but-nonzero" * 20)
    result = validate_video_output(p, asset_registered=True)
    # Without ffprobe, extension-based soft checks may pass with warning
    assert "FILE_EXISTS" in result.checks
    assert result.checks["NONZERO_SIZE"] is True


def test_comfy_halt_prompt_confirms_stopped():
    from app.comfy_client import ComfyClient

    client = ComfyClient(base_url="http://127.0.0.1:8188")
    client.interrupt = AsyncMock()
    client.delete_queue_prompt = AsyncMock(return_value={"ok": True})
    client.free_memory = AsyncMock(return_value={"ok": True})
    client.prompt_queue_presence = AsyncMock(
        return_value={"reachable": True, "running": False, "pending": False, "active": False}
    )
    result = asyncio.run(client.halt_prompt("prompt-abc"))
    assert client.interrupt.await_count >= 1
    client.delete_queue_prompt.assert_awaited_once_with("prompt-abc")
    client.free_memory.assert_awaited()
    assert result["interrupt"] is True
    assert result["confirmedStopped"] is True
    assert result["vramFullyReleased"] is False


def test_comfy_halt_prompt_not_confirmed():
    from app.comfy_client import ComfyClient

    client = ComfyClient(base_url="http://127.0.0.1:8188")
    client.interrupt = AsyncMock()
    client.delete_queue_prompt = AsyncMock(return_value={"ok": True})
    client.free_memory = AsyncMock(return_value={"ok": True})
    client.prompt_queue_presence = AsyncMock(
        return_value={"reachable": True, "running": True, "pending": False, "active": True}
    )
    result = asyncio.run(client.halt_prompt("prompt-abc", confirm_timeout_sec=0.5))
    assert result["confirmedStopped"] is False
    assert result["errorCode"] == "COMFY_CANCEL_NOT_CONFIRMED"


def test_wait_for_prompt_observes_cancel():
    from app.comfy_client import ComfyClient, JobCancelledError

    client = ComfyClient(base_url="http://127.0.0.1:8188")
    client.get_history = AsyncMock(return_value={})
    client.get_queue = AsyncMock(return_value={"queue_running": [], "queue_pending": []})
    client.interrupt = AsyncMock()
    client.delete_queue_prompt = AsyncMock(return_value={"ok": True})

    def cancel_check() -> bool:
        return True

    with pytest.raises(JobCancelledError):
        asyncio.run(client.wait_for_prompt("p1", timeout_sec=5, cancel_check=cancel_check))
    client.interrupt.assert_awaited()


def test_preflight_deferred_blocked():
    from app.video_runtime.preflight import run_preflight

    with patch(
        "app.comfy_health.comfy_health",
        new=AsyncMock(return_value={"reachable": True, "devices": []}),
    ), patch("app.comfy_client.comfy.get_object_info", new=AsyncMock(return_value={})):
        result = asyncio.run(run_preflight("video.upscale"))
    assert result["status"] == "blocked"
    assert result.get("capabilityState") == "deferred" or result["statusLabel"] == "Deferred"


def test_diagnostics_shape():
    from app.video_runtime.diagnostics import build_diagnostics

    with patch(
        "app.comfy_health.comfy_health",
        new=AsyncMock(
            return_value={
                "reachable": True,
                "version": "test",
                "status": "ready",
                "message": "ok",
                "nodeTypeCount": 10,
                "devices": [],
                "missingModelComponentIds": [],
            }
        ),
    ), patch("app.comfy_client.comfy.get_object_info", new=AsyncMock(return_value={"KSampler": {}})), patch(
        "app.comfy_client.comfy.get_queue",
        new=AsyncMock(return_value={"queue_running": [], "queue_pending": []}),
    ), patch("app.vram_profiles.query_gpu_stats", return_value={"ok": False, "gpus": []}), patch(
        "app.comfy_health.model_component_states",
        return_value=[
            {"componentId": "wan_models", "present": True},
            {"componentId": "ltx_checkpoint", "present": True},
            {"componentId": "zimage_models", "present": False},
            {"componentId": "ltx23_ic_lora_ingredients", "present": False},
        ],
    ):
        payload = asyncio.run(build_diagnostics(None))
    assert payload["comfyui"]["connected"] is True
    assert "modelInventory" in payload
    assert "wave6MediaExecutionUnlocked" in payload

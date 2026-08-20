"""Runtime-prove Revision A submit gate: packet before N+1, degraded still unblocks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.video_intelligence.compile import compile_temporal_continuation
from app.codirector.video_intelligence.contracts import TemporalContinuityPacket
from app.codirector.video_intelligence.service import (
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
from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request


def _master() -> SceneTimelineMaster:
    first = BatchBlock(
        id="bb_a",
        sceneId="s1",
        order=0,
        status="Approved",
        generatorId="ltx-2.5-distilled",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                text="Anadriya and Korri walk a long corridor. Camera dollies with them. Korri begins turning toward Anadriya."
            )
        ],
        approvedClip=ApprovedClip(assetId="asset_a", executionSnapshotId="snap_a"),
    )
    second = BatchBlock(
        id="bb_b",
        sceneId="s1",
        order=1,
        status="Ready",
        generatorId="ltx-2.5-distilled",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="Continue the walk. Finish Korri's turn.")],
    )
    return SceneTimelineMaster(
        sceneId="s1",
        batchBlocks=[first, second],
        continuityBridges=[
            ContinuityBridge(
                id="bridge_ab",
                fromBatchId="bb_a",
                toBatchId="bb_b",
                lastFrameAssetId="frame_a",
                continuityState={"intact": True},
            )
        ],
    )


def main() -> int:
    failures: list[str] = []

    missing = _master()
    if not packet_blocks_submit(missing, "bb_b"):
        failures.append("Missing packet did not block N+1")
    set_codirector_continuity_policy(missing, {"enabled": False})
    if packet_blocks_submit(missing, "bb_b"):
        failures.append("Continuity OFF still blocked submit")

    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "fail"
    forced = _master()
    packet = review_completed_batch(None, "p1", "s1", forced, forced.batchBlocks[0], target_batch_id="bb_b")
    if packet.availability != "unavailable":
        failures.append(f"Forced fail availability={packet.availability}")
    if packet_blocks_submit(forced, "bb_b"):
        failures.append("Forced-fail packet blocked N+1")
    compiled_fail = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    if compiled_fail.get("applied"):
        failures.append("Degraded compile invented a continuation")

    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "stub"
    stub = _master()
    dummy = ROOT / ".runtime" / "_temporal_runtime_stub.mp4"
    dummy.parent.mkdir(parents=True, exist_ok=True)
    if not dummy.is_file():
        dummy.write_bytes(b"not-a-real-mp4")
    from unittest.mock import patch

    with patch(
        "app.codirector.video_intelligence.service._asset_path",
        return_value=str(dummy),
    ):
        ready = review_completed_batch(None, "p1", "s1", stub, stub.batchBlocks[0], target_batch_id="bb_b")
    if ready.availability != "ready":
        failures.append(f"Stub review availability={ready.availability}")
    if packet_blocks_submit(stub, "bb_b"):
        failures.append("Ready packet still blocked N+1")
    req = build_timeline_generation_request(
        project_id="p1",
        scene_id="s1",
        batch=stub.batchBlocks[1],
        snapshot=ExecutionSnapshot(batchBlockId="bb_b"),
        incoming_bridge=stub.continuityBridges[0],
        temporal_packet=ready,
    )
    if req.temporalContinuityPacketId != ready.packetId:
        failures.append("Request missing temporalContinuityPacketId")
    if not (req.providerOptions or {}).get("temporalContinuation", {}).get("applied"):
        failures.append("Adapter compile did not apply temporalContinuation")
    if MiniMaxH3LocalAdapter.capabilities.supportsTemporalConditioning:
        failures.append("MiniMax claimed fake temporal conditioning")
    ltx_caps = LtxLocalAdapter.capabilities
    if getattr(ltx_caps, "supportsTemporalConditioning", False):
        failures.append("LTX claimed fake temporal conditioning")
    if not getattr(ltx_caps, "supportsImageToVideo", False):
        failures.append("LTX I2V capability missing")
    if not getattr(stub.continuityBridges[0], "lastFrameAssetId", None):
        failures.append("Last-frame bridge dropped")

    print("gate_missing_blocks", True)
    print("gate_off_unblocks", True)
    print("forced_unavailable", packet.availability, packet.reason)
    print("stub_ready", ready.availability, ready.decision)
    print("request_packet", req.temporalContinuityPacketId)
    print("prompt_has_continuation", "turn" in (req.prompt or "").lower())
    print("last_frame_bridge", stub.continuityBridges[0].lastFrameAssetId)
    if failures:
        print("FAILURES", failures)
        return 2
    print("RUNTIME_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

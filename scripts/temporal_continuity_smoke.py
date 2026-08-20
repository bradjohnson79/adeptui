"""Smoke: discovery, packet serialize, cadence, compile, Setup catalog, hardware profile."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1] / "studio-api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.codirector.video_intelligence.cadence import resolve_cadence
from app.codirector.video_intelligence.compile import compile_temporal_continuation
from app.codirector.video_intelligence.contracts import CoDirectorContinuityPolicy, TemporalContinuityPacket
from app.codirector.video_intelligence.hardware_profile import hardware_profile
from app.codirector.video_intelligence.paths import VIDEOCHAT3_MARKERS, model_present, videochat3_dir
from app.codirector.video_intelligence.worker_client import _as_str_list
from app.setup.catalog import BY_ID
from app.video_runtime.workflow_resolver import (
    is_ltx_25_generator,
    local_video_identity,
    resolve_from_scene_params,
)


def main() -> int:
    report = {
        "videochat3CatalogRequired": BY_ID["videochat3_4b"].required,
        "internvideo3CatalogRequired": BY_ID["internvideo3_8b"].required,
        "videochat3Installed": model_present(videochat3_dir(), VIDEOCHAT3_MARKERS),
        "hardware": hardware_profile(),
        "cadence": resolve_cadence(CoDirectorContinuityPolicy(), prompt="walk and turn"),
    }
    packet = TemporalContinuityPacket(availability="unavailable", reason="SMOKE")
    blob = packet.model_dump()
    restored = TemporalContinuityPacket.model_validate(blob)
    report["packetRoundtrip"] = restored.packetId == packet.packetId
    compiled = compile_temporal_continuation(packet, supports_prompt_continuation=True)
    report["degradedDoesNotInvent"] = compiled["applied"] is False
    report["unfinishedActionsNormalized"] = _as_str_list("turn toward the other character") == [
        "turn toward the other character"
    ]
    report["ltx25Routing"] = is_ltx_25_generator("ltx-2.5-distilled") and (
        resolve_from_scene_params(
            engine="ltx",
            start_asset_id="start",
            intent="scene_render",
            generator_id="ltx-2.5-distilled",
        ).leaf_workflow_key
        == "ltx_25.i2v"
    )
    ident = local_video_identity(
        requested_model="ltx-2.5-distilled",
        leaf_workflow_key="ltx_25.i2v",
        ltx_23_checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        ltx_25_checkpoint="ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    )
    report["ltxProvenanceNotMinimax"] = "minimax" not in ident["videoModel"].lower()
    report["requestedResolved"] = ident
    print(json.dumps(report, indent=2))
    if not report["videochat3CatalogRequired"]:
        return 2
    if not report["packetRoundtrip"] or not report["degradedDoesNotInvent"]:
        return 3
    if not report["unfinishedActionsNormalized"] or not report["ltx25Routing"] or not report["ltxProvenanceNotMinimax"]:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())

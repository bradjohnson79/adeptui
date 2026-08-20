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
from app.setup.catalog import BY_ID


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
    print(json.dumps(report, indent=2))
    if not report["videochat3CatalogRequired"]:
        return 2
    if not report["packetRoundtrip"] or not report["degradedDoesNotInvent"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

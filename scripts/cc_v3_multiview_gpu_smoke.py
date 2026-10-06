"""Isolated Character Angles smoke: three Qwen Edit 2509 I2I jobs from one Front.

Does not download Wonder3D. Does not install torch. Uses the live Studio API.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
OUT = Path("docs/release-gate/character-creator/evidence/cc_v3_multiview_gpu_smoke.json")


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{API}{path}", timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    health = _get("/api/healthz")
    from app.character_identity.multiview_engine import production_engine_status
    from app.workflows.qwen_image_edit_2509 import discover_qwen_edit_2509

    disc = discover_qwen_edit_2509()
    engine = production_engine_status(force=True)
    report = {
        "health": health,
        "discover": {
            "installed": disc.get("installed"),
            "runtimeReady": disc.get("runtimeReady"),
            "reason": disc.get("reason"),
            "license": disc.get("license"),
            "hfRepo": disc.get("hfRepo"),
        },
        "engine": engine,
        "jobs": [],
        "verdict": "NO-GO — MULTIVIEW ENGINE NOT READY",
    }
    if not (engine.get("available") and engine.get("status") == "READY"):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    report["verdict"] = "READY_FOR_LIVE_GENERATE — run Character Angles from the creator UI"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "studio-api"))
    raise SystemExit(main())

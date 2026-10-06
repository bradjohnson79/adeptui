"""Character Creator single CRS smoke — one slot, Qwen default, GPT selectable."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.character_identity.visual_sheet import _build_candidate_routing_plan, _coerce_single_crs_sources
from app.codirector.routing.unified_intent import classify_intent
from app.codirector.tools.handlers.character_creator import _crs_generator_sources


def main() -> int:
    qwen = _coerce_single_crs_sources(None)
    gpt = _crs_generator_sources({"generator": "gpt-image-2"})
    parallel = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id=None,
        visual_style="cinematic_anime",
        generator_sources={
            "local": [
                {"family": "qwen2512", "enabled": True, "batchCount": 2},
                {"family": "illustrious", "enabled": True, "batchCount": 2},
            ]
        },
    )
    crs = classify_intent("Create Korri's CRS.", {})
    multi = classify_intent("Create a multi-view image of Korri.", {})
    report = {
        "qwen_default": qwen["local"][0]["family"],
        "gpt_model": gpt["api"][0]["modelId"],
        "slots": len(parallel),
        "crs_capability": crs.capability,
        "multi_capability": multi.capability,
    }
    print(json.dumps(report, indent=2))
    ok = (
        qwen["local"][0]["family"] == "qwen2512"
        and gpt["api"][0]["modelId"] == "gpt-image-2"
        and len(parallel) == 1
        and crs.capability == "character.generate_visual_sheet"
        and multi.capability == "image.generate"
    )
    print("PASS — CHARACTER CREATOR SINGLE CRS SMOKE" if ok else "FAIL — single CRS smoke")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

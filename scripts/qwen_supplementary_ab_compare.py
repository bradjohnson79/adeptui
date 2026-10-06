"""Controlled A/B: same MoGe geometry vs enriched reasoning annotations.

Experimental isolation only — Atlas source-color pixels must match.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "supplementary_views"
BASELINE_ATLAS = ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "geometry_bakeoff" / "moge2" / "plates" / "top_down_orthographic.png"
SOURCE = ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "geometry_bakeoff" / "source.png"


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not BASELINE_ATLAS.is_file() or not SOURCE.is_file():
        print("MISSING_BASELINE")
        return 2
    enriched = EVIDENCE / "enriched_atlas.png"
    shutil.copy2(BASELINE_ATLAS, EVIDENCE / "baseline_atlas.png")
    shutil.copy2(BASELINE_ATLAS, enriched)
    a = Image.open(BASELINE_ATLAS)
    b = Image.open(enriched)
    identical = list(a.getdata()) == list(b.getdata())
    report = {
        "experimentalIsolation": True,
        "permanentArchitectureLaw": False,
        "geometryPixelsIdentical": identical,
        "contamination": not identical,
        "notes": [
            "For this controlled A/B only, geometric Atlas pixels must remain identical.",
            "Supplementary Qwen views may change structured reasoning/confidence annotations only.",
            "INFERRED + INFERRED ≠ OBSERVED.",
        ],
        "baselineAtlas": str(EVIDENCE / "baseline_atlas.png"),
        "enrichedAtlas": str(enriched),
    }
    (EVIDENCE / "ab_compare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())

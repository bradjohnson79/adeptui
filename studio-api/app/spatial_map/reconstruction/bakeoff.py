"""Atlas bake-off scoring — topology, source identity, top-down, readability.

Certification evidence, not creator chrome.
"""

from __future__ import annotations

from typing import Any

from ...codirector.routing.atlas_classify import classify_pixels
from ...codirector.vision.atlas_gate import evaluate_atlas_candidate_pixels


def score_atlas_candidate(
    *,
    candidate_path: str,
    source_path: str = "",
    guide_path: str = "",
    slot_order: str = "",
) -> dict[str, Any]:
    from PIL import Image
    import numpy as np

    gate = evaluate_atlas_candidate_pixels(
        candidate_path=candidate_path,
        source_path=source_path,
        guide_path=guide_path,
    )
    cand = Image.open(candidate_path).convert("RGB")
    arr = np.asarray(cand)
    kind, conf = classify_pixels(arr, int(arr.shape[1]), int(arr.shape[0]))
    top_down = 1.0 if kind == "atlas" else 0.15 if kind == "uncertain" else 0.0
    topology = 0.85 if gate.get("ok") else 0.2
    identity = 0.85 if gate.get("failCode") not in {"FAIL_SOURCE_IDENTITY", "FAIL_UNRELATED_SCENE"} else 0.15
    if gate.get("failCode") == "FAIL_TOPOLOGY":
        topology = 0.1
    if gate.get("failCode") == "FAIL_TOP_DOWN":
        top_down = 0.1
    # Readability: both-axis structure without becoming a grid overlay on a photo.
    gy = np.abs(np.diff(arr.mean(axis=2), axis=0)).mean()
    gx = np.abs(np.diff(arr.mean(axis=2), axis=1)).mean()
    readability = float(min(1.0, (gx + gy) / 40.0))
    if "grid" in str(gate.get("reason") or "").lower():
        readability = min(readability, 0.2)
        topology = min(topology, 0.15)
    scores = {
        "topology": round(topology, 3),
        "sourceIdentity": round(identity, 3),
        "topDown": round(top_down, 3),
        "readability": round(readability, 3),
    }
    both_quality = scores["topology"] >= 0.6 and scores["sourceIdentity"] >= 0.6
    return {
        "slotOrder": slot_order,
        "scores": scores,
        "bothQualityBar": both_quality,
        "gate": gate,
        "classifyKind": kind,
        "classifyConfidence": conf,
    }


def pick_winning_slot_order(results: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in results if r.get("bothQualityBar")]
    pool = eligible or results
    def _total(row: dict[str, Any]) -> float:
        s = row.get("scores") or {}
        return float(s.get("topology") or 0) + float(s.get("sourceIdentity") or 0)

    winner = max(pool, key=_total) if pool else {}
    return {
        "winner": winner.get("slotOrder") or "",
        "locked": bool(winner.get("bothQualityBar")),
        "results": results,
    }

"""Per-view and set consistency gates, including information gain."""

from __future__ import annotations

from typing import Any

from PIL import Image
import numpy as np

from .contracts import GateVerdict, SpatialReferenceRecord


def _load_rgb(path: str) -> np.ndarray | None:
    try:
        return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    except Exception:
        return None


def _mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    h = min(a.shape[0], b.shape[0], 256)
    w = min(a.shape[1], b.shape[1], 256)
    if h < 8 or w < 8:
        return 0.0
    aa = a[:h, :w]
    bb = b[:h, :w]
    if aa.shape != bb.shape:
        return 0.0
    return float(np.mean(np.abs(aa - bb)))


def evaluate_view_gate(
    *,
    master_path: str,
    candidate_path: str,
    camera_role: str,
    slot: str = "A",
    prior_inferred_path: str | None = None,
    invented_room: bool = False,
    contradicts_master: bool = False,
    severe_corruption: bool = False,
    requested_transform_occurred: bool | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    master = _load_rgb(master_path)
    cand = _load_rgb(candidate_path)
    if master is None or cand is None:
        return {
            "verdict": "FAIL",
            "reasons": ["The generated view could not be opened for validation."],
            "informationGain": False,
        }
    gray = cand.mean(axis=2)
    if severe_corruption or float(np.std(cand)) < 4.0:
        return {
            "verdict": "FAIL",
            "reasons": ["The generated view is severely corrupted or blank."],
            "informationGain": False,
        }
    if invented_room:
        return {
            "verdict": "FAIL",
            "reasons": ["The generated view invented major room structure. The observed master wins."],
            "informationGain": False,
        }
    if contradicts_master:
        return {
            "verdict": "FAIL",
            "reasons": ["The generated view contradicts the observed master. Qwen loses."],
            "informationGain": False,
        }
    delta = _mean_abs_diff(master, cand)
    similar_to_master = delta < 8.0
    if requested_transform_occurred is False or similar_to_master:
        return {
            "verdict": "FAIL_NO_INFORMATION_GAIN",
            "reasons": [
                "A supplementary view is useful only if it exposes spatial information that was "
                "obscured or ambiguous in the observed master. This output restyles or slightly "
                "shifts the source without a meaningful new camera relationship."
            ],
            "informationGain": False,
            "pixelDelta": delta,
        }
    hist, _ = np.histogram(gray, bins=16, range=(0.0, 255.0))
    peak_frac = float(hist.max() / max(int(hist.sum()), 1))
    if float(np.std(gray)) < 8.0 or peak_frac > 0.82:
        return {
            "verdict": "FAIL",
            "reasons": ["The generated view is a near-solid color with no usable spatial structure."],
            "informationGain": False,
            "pixelDelta": delta,
        }
    if slot == "B" and prior_inferred_path:
        prior = _load_rgb(prior_inferred_path)
        if prior is not None and _mean_abs_diff(prior, cand) < 8.0:
            return {
                "verdict": "FAIL_NO_INFORMATION_GAIN",
                "reasons": [
                    "View B must target remaining uncertainty after Master + accepted View A. "
                    "This output repeats View A instead of exposing a new spatial relationship."
                ],
                "informationGain": False,
            }
    if delta < 18.0:
        reasons.append("Camera change is modest; treat as low-confidence support only.")
        verdict: GateVerdict = "PASS_WITH_LOW_CONFIDENCE"
    else:
        verdict = "PASS"
        reasons.append(f"Requested camera {camera_role} produced a distinct viewpoint.")
    reasons.append("Same-environment identity assumed pending creator review.")
    return {
        "verdict": verdict,
        "reasons": reasons,
        "informationGain": True,
        "pixelDelta": delta,
    }


def evaluate_set_gate(
    *,
    master: SpatialReferenceRecord,
    view_a: SpatialReferenceRecord | None,
    view_b: SpatialReferenceRecord | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if master.evidenceClass != "OBSERVED":
        return {"verdict": "FAIL", "reasons": ["The master is not observed spatial truth."], "forward": False}
    accepted = [
        item
        for item in (view_a, view_b)
        if item
        and item.approvedForSpatialReasoning
        and item.evidenceClass == "INFERRED"
        and item.status == "READY"
    ]
    if not accepted:
        return {"verdict": "FAIL", "reasons": ["No inferred view is accepted for spatial reasoning."], "forward": False}
    if any(item.gateVerdict in {"FAIL", "FAIL_NO_INFORMATION_GAIN"} for item in accepted):
        return {"verdict": "FAIL", "reasons": ["A failed inferred view cannot be forwarded."], "forward": False}
    if any(item.evidenceClass == "OBSERVED" for item in (view_a, view_b) if item):
        return {"verdict": "FAIL", "reasons": ["An inferred view was illegally marked OBSERVED."], "forward": False}
    reasons.append("Inferred views remain support only. They do not become observed photographs.")
    return {"verdict": "PASS", "reasons": reasons, "forward": True}

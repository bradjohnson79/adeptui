"""Confidence summary. INFERRED + INFERRED ≠ OBSERVED."""

from __future__ import annotations

from .contracts import ConfidenceSummary, SpatialReferenceRecord


def summarize_confidence(
    *,
    master: SpatialReferenceRecord,
    view_a: SpatialReferenceRecord | None = None,
    view_b: SpatialReferenceRecord | None = None,
    scene_description: str = "",
    unknown_notes: list[str] | None = None,
) -> ConfidenceSummary:
    observed = [
        "Facts visible in the owner-provided master remain the highest-authority spatial truth.",
    ]
    if (scene_description or "").strip():
        observed.append(f"Master location description: {scene_description.strip()}")
    inferred: list[str] = []
    conflicted: list[str] = []
    for item in (view_a, view_b):
        if not item or item.evidenceClass != "INFERRED":
            continue
        if item.gateVerdict in {"FAIL", "FAIL_NO_INFORMATION_GAIN"} or item.status == "REJECTED":
            conflicted.append(
                f"View {item.slot} is not spatial-reasoning evidence ({item.gateVerdict or item.status})."
            )
            continue
        if item.approvedForSpatialReasoning:
            inferred.append(
                f"View {item.slot} ({item.cameraRole or 'unspecified'}) is INFERRED_SUPPORTED only. "
                "It supports the master; it is not an observed photograph."
            )
    notes = [
        "INFERRED + INFERRED ≠ OBSERVED. Two Qwen views agreeing with each other are not independent evidence. "
        "Both descend from the same observed master and may reproduce the same hallucination.",
        "Confidence may move from UNKNOWN to INFERRED_SUPPORTED, never to OBSERVED solely from generated views.",
    ]
    unknown = list(unknown_notes or ["Space still unseen from the observed master remains UNKNOWN."])
    if view_a and view_b and view_a.approvedForSpatialReasoning and view_b.approvedForSpatialReasoning:
        notes.append(
            "Agreement between View A and View B does not upgrade any fact to OBSERVED."
        )
    return ConfidenceSummary(
        observed=observed,
        inferredSupported=inferred,
        conflicted=conflicted,
        unknown=unknown,
        notes=notes,
    )


def promote_inferred_agreement_to_observed(_facts: list[str]) -> None:
    raise ValueError("INFERRED + INFERRED ≠ OBSERVED. Generated views cannot create observed facts.")

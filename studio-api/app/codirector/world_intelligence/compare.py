"""World-state comparison logic for Co-Director.

Translates raw embedding similarity into structured Co-Director advisories.
"""

from __future__ import annotations

from typing import Any, Optional

from .contracts import (
    ComparisonType,
    ConfidenceLevel,
    SceneStateSummary,
    StateComparison,
    WorldStatePacket,
    WorldStateRecommendation,
    WorldStateSource,
)


def compute_recommendation(
    similarity: float,
    anomaly_score: float,
    confidence: ConfidenceLevel,
    comparison_type: ComparisonType = "image_pair",
    intentional_change: bool = False,
) -> WorldStateRecommendation:
    """Translate raw scores into a structured Co-Director recommendation.

    Thresholds are calibrated heuristics, not absolutes.
    These should be tuned based on benchmark results.
    """
    if confidence == "insufficient_reference":
        return WorldStateRecommendation(
            consistent=False,
            caution=["Insufficient world references for confident comparison."],
        )

    if intentional_change:
        return WorldStateRecommendation(
            consistent=True,
            caution=["Intended change detected — world revision accepted."],
        )

    rec = WorldStateRecommendation()

    # High similarity = world preserved
    if similarity >= 0.85:
        rec.consistent = True
    elif similarity >= 0.70:
        rec.consistent = True
        rec.caution.append("Minor world-state drift detected.")
    elif similarity >= 0.50:
        rec.consistent = False
        rec.review_.append(
            "The scene environment differs notably from the approved reference."
        )
    else:
        rec.consistent = False
        rec.review_.append(
            "Major world-state change detected — the scene may no longer "
            "belong to the established visual world."
        )

    # Anomaly overlay
    if anomaly_score > 0.5:
        rec.review_.append(
            "Unexpected visual anomaly detected in scene structure."
        )

    return rec


def build_world_state_packet(
    source_asset_id: str,
    reference_asset_ids: list[str],
    similarity: Optional[float],
    anomaly_score: Optional[float],
    model_id: str,
    model_revision: str,
    comparison_type: ComparisonType = "image_pair",
    confidence: ConfidenceLevel = "uncertain",
    intentional_change: bool = False,
    latency_ms: Optional[float] = None,
    vram_gb: Optional[float] = None,
    reason: str = "",
) -> WorldStatePacket:
    """Build a complete WorldStatePacket from comparison results."""
    if confidence == "insufficient_reference":
        return WorldStatePacket(
            availability="insufficient_reference",
            reason=reason or "Insufficient reference imagery for world-state comparison.",
            source=WorldStateSource(
                assetId=source_asset_id,
                sourceType=comparison_type,
                modelId=model_id,
                modelRevision=model_revision,
            ),
            latencyMs=latency_ms,
            vramUsedGb=vram_gb,
        )

    if similarity is None:
        return WorldStatePacket(
            availability="unavailable",
            reason=reason or "World-state comparison could not produce a similarity score.",
            source=WorldStateSource(
                assetId=source_asset_id,
                sourceType=comparison_type,
                modelId=model_id,
                modelRevision=model_revision,
            ),
            latencyMs=latency_ms,
            vramUsedGb=vram_gb,
        )

    rec = compute_recommendation(
        similarity=similarity,
        anomaly_score=anomaly_score or 0.0,
        confidence=confidence,
        comparison_type=comparison_type,
        intentional_change=intentional_change,
    )

    comparisons = []
    for ref_id in reference_asset_ids:
        comparisons.append(
            StateComparison(
                referenceAssetId=ref_id,
                observedAssetId=source_asset_id,
                similarity=similarity,
                anomalyScore=anomaly_score,
                confidence=confidence,
            )
        )

    return WorldStatePacket(
        availability="available",
        source=WorldStateSource(
            assetId=source_asset_id,
            sourceType=comparison_type,
            modelId=model_id,
            modelRevision=model_revision,
        ),
        sceneState=SceneStateSummary(
            similarityToReference=similarity,
            anomalyScore=anomaly_score,
            confidence=confidence,
        ),
        comparisons=comparisons,
        recommendation=rec,
        latencyMs=latency_ms,
        vramUsedGb=vram_gb,
    )

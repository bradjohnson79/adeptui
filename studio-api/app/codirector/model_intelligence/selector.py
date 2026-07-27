"""Explainable model suitability scoring and recommendation."""

from __future__ import annotations

from typing import Any, Optional

from .loader import discover_packs
from .registry import BINDINGS
from .schemas import (
    AudioChannelPolicy,
    ModelRecommendation,
    NormalizedGenerationIntent,
    PackStatus,
    ProductionReadiness,
)

# Versioned weighting — configurable & testable
SCORING_VERSION = "m30e-scoring-v1"
DEFAULT_WEIGHTS: dict[str, float] = {
    "capabilityFit": 1.4,
    "audioFit": 1.3,
    "motionFit": 1.0,
    "cameraFit": 0.8,
    "referenceFit": 1.0,
    "productionReadiness": 1.5,
    "providerHealth": 1.0,
    "hardwareFit": 0.7,
    "costFit": 0.6,
    "speedFit": 0.5,
    "historicalSuccess": 0.4,
    "promptReliability": 0.8,
    "continuityFit": 0.7,
    "qualityFit": 0.8,
}


def _cap(pack: dict[str, Any], key: str) -> str:
    caps = pack.get("capabilities") or {}
    return str(caps.get(key) or caps.get("modes", {}).get(key) or "UNKNOWN").upper()


def score_model(
    model_id: str,
    intent: NormalizedGenerationIntent,
    *,
    provider_health: Optional[dict[str, float]] = None,
    weights: Optional[dict[str, float]] = None,
) -> tuple[dict[str, float], list[str], list[str]]:
    packs = discover_packs()
    pack = packs.get(model_id)
    binding = BINDINGS.get(model_id)
    reasons: list[str] = []
    risks: list[str] = []
    scores: dict[str, float] = {k: 0.0 for k in DEFAULT_WEIGHTS}

    if not pack or not binding:
        risks.append("No knowledge pack or binding")
        return scores, reasons, risks

    manifest = pack["manifest"]
    if manifest.status == PackStatus.QUARANTINED:
        risks.append("Pack quarantined / product approval required")
        return scores, reasons, risks

    # capabilityFit
    mode_key = intent.mode.replace("-", "_")
    support = _cap(pack, mode_key)
    if support in ("SUPPORTED", "TRUE", "PARTIAL", "EXPERIMENTAL"):
        scores["capabilityFit"] = 1.0 if support in ("SUPPORTED", "TRUE") else 0.55
        reasons.append(f"{model_id} supports {intent.mode} ({support})")
    else:
        scores["capabilityFit"] = 0.0
        risks.append(f"{model_id} does not support {intent.mode}")

    # media
    if intent.mediaType not in (manifest.media or []):
        scores["capabilityFit"] *= 0.2
        risks.append(f"Media type {intent.mediaType} not in pack media list")

    # audioFit
    audio = intent.audioIntent
    ab = pack.get("audio_behavior") or {}
    native = bool(ab.get("supportsNativeAudio"))
    if audio.music == AudioChannelPolicy.PROHIBITED:
        if native and ab.get("generateAudioParam"):
            scores["audioFit"] = 0.95
            reasons.append("Native generate_audio can be disabled")
        elif not native:
            scores["audioFit"] = 0.85
            reasons.append("No native soundtrack — external audio pipeline fits no-music intent")
        else:
            scores["audioFit"] = 0.4
            risks.append("Music prohibition hard to enforce on this model")
    elif audio.music == AudioChannelPolicy.REQUIRED:
        scores["audioFit"] = 0.9 if native else 0.25
        if not native:
            risks.append("Cannot generate native music on this model")
    else:
        scores["audioFit"] = 0.7

    # referenceFit
    if intent.hasSourceImage or intent.referenceCount:
        ref = _cap(pack, "reference_images")
        scores["referenceFit"] = 1.0 if ref in ("SUPPORTED", "PARTIAL", "TRUE") else 0.3
    else:
        scores["referenceFit"] = 0.6

    # productionReadiness
    ready_map = {
        ProductionReadiness.PRODUCTION: 1.0,
        ProductionReadiness.EXPERIMENTAL: 0.45,
        ProductionReadiness.NOT_PRODUCTION_READY: 0.25,
        ProductionReadiness.CONFIGURATION_REQUIRED: 0.35,
        ProductionReadiness.PRODUCT_APPROVAL_REQUIRED: 0.0,
        ProductionReadiness.UNAVAILABLE: 0.0,
    }
    scores["productionReadiness"] = ready_map.get(manifest.runtimeStatus, 0.3)
    if manifest.runtimeStatus != ProductionReadiness.PRODUCTION:
        risks.append(f"Runtime readiness: {manifest.runtimeStatus.value}")

    # providerHealth
    ph = (provider_health or {}).get(binding.providerId, 0.7)
    scores["providerHealth"] = float(ph)

    # defaults for remaining dimensions
    scores["motionFit"] = 0.8 if intent.mediaType == "video" else 0.5
    scores["cameraFit"] = 0.7
    scores["hardwareFit"] = 0.8 if binding.providerId == "comfy.local" else 0.9
    scores["costFit"] = 0.9 if binding.providerId == "comfy.local" else 0.55
    scores["speedFit"] = 0.6
    scores["historicalSuccess"] = float((manifest.confidence or {}).get("overall") or 0.5)
    scores["promptReliability"] = float((manifest.confidence or {}).get("overall") or 0.5)
    scores["continuityFit"] = 0.7
    scores["qualityFit"] = 0.7

    w = weights or DEFAULT_WEIGHTS
    return scores, reasons, risks


def weighted_total(scores: dict[str, float], weights: Optional[dict[str, float]] = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    num = sum(scores.get(k, 0.0) * w.get(k, 0.0) for k in w)
    den = sum(w.values()) or 1.0
    return round(num / den, 4)


def recommend(
    intent: NormalizedGenerationIntent,
    *,
    provider_health: Optional[dict[str, float]] = None,
    candidate_model_ids: Optional[list[str]] = None,
) -> ModelRecommendation:
    candidates = candidate_model_ids or [
        mid
        for mid, b in BINDINGS.items()
        if b.capabilityIds  # skip approval placeholders without capabilities
    ]
    ranked: list[tuple[str, float, dict[str, float], list[str], list[str]]] = []
    for mid in candidates:
        scores, reasons, risks = score_model(mid, intent, provider_health=provider_health)
        total = weighted_total(scores)
        ranked.append((mid, total, scores, reasons, risks))
    ranked.sort(key=lambda row: row[1], reverse=True)

    if intent.forceModelId:
        forced = intent.forceModelId
        forced_row = next((r for r in ranked if r[0] == forced), None)
        if forced_row is None:
            scores, reasons, risks = score_model(forced, intent, provider_health=provider_health)
            total = weighted_total(scores)
        else:
            forced, total, scores, reasons, risks = forced_row
        alts = [
            {"modelId": m, "score": s, "reasons": rs[:3]}
            for m, s, _, rs, _ in ranked
            if m != forced
        ][:3]
        return ModelRecommendation(
            recommendedModel=forced,
            alternatives=alts,
            reasons=reasons + [f"User forced model {forced}"],
            risks=risks,
            confidence=min(total, 0.7),
            requiresApproval=bool(risks),
            scores=scores,
            explanation=(
                f"Keeping user-selected {forced} (score {total:.2f}). "
                + (" ".join(risks[:2]) if risks else "Risks acceptable.")
            ),
        )

    if not ranked:
        return ModelRecommendation(
            recommendedModel="",
            reasons=[],
            risks=["No candidates"],
            confidence=0.0,
            explanation="No generation models available",
        )

    best_id, best_score, best_scores, reasons, risks = ranked[0]
    alts = [
        {"modelId": m, "score": s, "reasons": rs[:3]}
        for m, s, _, rs, _ in ranked[1:4]
    ]
    return ModelRecommendation(
        recommendedModel=best_id,
        alternatives=alts,
        reasons=reasons,
        risks=risks,
        confidence=best_score,
        requiresApproval=best_score < 0.45 or any("approval" in r.lower() for r in risks),
        scores=best_scores,
        explanation=(
            f"Recommended {best_id} (score {best_score:.2f}, {SCORING_VERSION}). "
            + "; ".join(reasons[:3])
        ),
    )

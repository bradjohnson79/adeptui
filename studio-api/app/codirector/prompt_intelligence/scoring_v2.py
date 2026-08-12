"""Prompt Quality Analyzer V2 — three separate axes (no single certainty number)."""

from __future__ import annotations

from typing import Any, Optional

from .benchmark_models import AnalyzerV2Axes, PromptStrategyRecommendation
from .intent import analyze_intent
from .models import GenerationDomain, PromptQualityReport
from .profiles import PromptProfile, resolve_profile
from .recommendation import resolve_strategy_recommendation
from .scoring import analyze_quality


def analyze_v2(
    prompt: str,
    *,
    domain: GenerationDomain = "video",
    provider_id: Optional[str] = None,
    model_revision: str = "default",
    category: str = "general",
    strategy_mode: str = "recommend",
    modules_enabled_zh: bool = False,
    project_prefs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    profile = resolve_profile(
        provider_id=provider_id,
        model_version=model_revision,
        domain=domain,
    )
    intent = analyze_intent(prompt or "", domain=domain)
    quality: PromptQualityReport = analyze_quality(
        prompt or "",
        intent,
        domain=domain,
        profile=profile,
        modules_enabled_zh=modules_enabled_zh,
    )
    provider_compat = _provider_compatibility(profile, domain)
    recommendation = resolve_strategy_recommendation(
        domain=domain,
        category=category,
        provider_id=provider_id,
        model_revision=model_revision,
        strategy_mode=strategy_mode,  # type: ignore[arg-type]
        project_prefs=project_prefs,
    )
    strategy_conf = _confidence_to_score(recommendation)
    axes = AnalyzerV2Axes(
        promptQuality=int(quality.overall),
        providerCompatibility=provider_compat,
        recommendedStrategyConfidence=strategy_conf,
        notes=[
            "Axes are independent — do not average into a single certainty score.",
            f"strategyMode={strategy_mode}",
            recommendation.reason,
        ],
    )
    return {
        "ok": True,
        "axes": axes.model_dump(mode="json"),
        "promptQualityReport": quality.model_dump(mode="json"),
        "strategyRecommendation": recommendation.model_dump(mode="json"),
        "profileId": profile.profileId,
        "profileVersion": profile.profileVersion,
    }


def _provider_compatibility(profile: PromptProfile, domain: GenerationDomain) -> int:
    score = 70
    if profile.generationDomain == domain:
        score += 10
    # bilingualCertified false is expected — does not reduce English compatibility
    if profile.negativePromptSupport:
        score += 5
    if profile.maxPromptLength:
        score += 5
    return max(0, min(100, score))


def _confidence_to_score(rec: PromptStrategyRecommendation) -> int:
    base = {"low": 25, "medium": 60, "high": 85}.get(rec.confidence, 25)
    if rec.status.startswith("certified_"):
        base = min(100, base + 10)
    if rec.status in ("not_tested", "insufficient_evidence"):
        base = min(base, 30)
    if rec.sampleCount >= 3:
        base = min(100, base + 5)
    return base

"""Adaptive strategy recommendation for Prompt Intelligence V2."""

from __future__ import annotations

from typing import Any, Optional

from .benchmark_models import PromptStrategyRecommendation, StrategyMode
from .benchmark_store import list_evidence, load_evidence, load_overlay
from .profiles import resolve_profile

DEFAULT_STRATEGY = "refined-english"


def resolve_strategy_recommendation(
    *,
    domain: str,
    category: str = "general",
    provider_id: Optional[str] = None,
    model_revision: str = "default",
    strategy_mode: StrategyMode = "manual",
    manual_override: Optional[str] = None,
    min_confidence: str = "medium",
    project_prefs: Optional[dict[str, Any]] = None,
) -> PromptStrategyRecommendation:
    prefs = project_prefs or {}
    mode: StrategyMode = prefs.get("strategyMode") or strategy_mode  # type: ignore[assignment]
    min_conf = str(prefs.get("minConfidence") or min_confidence)

    if manual_override:
        return PromptStrategyRecommendation(
            strategy=manual_override,  # type: ignore[arg-type]
            status="experimental",
            confidence="high",
            reason="Manual override",
            category=category,
            domain=domain,
            providerId=provider_id or "",
            modelRevision=model_revision,
            appliedAutomatically=False,
        )

    if mode == "manual":
        return PromptStrategyRecommendation(
            strategy=DEFAULT_STRATEGY,  # type: ignore[arg-type]
            status="not_tested",
            confidence="low",
            reason="strategyMode=manual — no auto recommendation applied",
            category=category,
            domain=domain,
            providerId=provider_id or "",
            modelRevision=model_revision,
            appliedAutomatically=False,
        )

    evidence = None
    if provider_id:
        evidence = load_evidence(provider_id, model_revision, domain, category)

    if evidence and not evidence.stale and evidence.recommendedStrategy:
        conf_ok = _confidence_meets(evidence.confidence, min_conf)
        certified = evidence.status.startswith("certified_") or evidence.status == "english_preferred"
        if mode == "recommend":
            return PromptStrategyRecommendation(
                strategy=evidence.recommendedStrategy,
                status=evidence.status,
                confidence=evidence.confidence,
                sampleCount=evidence.sampleCount,
                reason=f"Category evidence ({evidence.status})",
                evidenceVersion=evidence.evidenceVersion,
                category=category,
                domain=domain,
                providerId=provider_id or "",
                modelRevision=model_revision,
                appliedAutomatically=False,
            )
        if mode == "automatic_certified":
            if certified and conf_ok and evidence.status not in (
                "experimental",
                "not_tested",
                "insufficient_evidence",
                "benchmarking",
            ):
                return PromptStrategyRecommendation(
                    strategy=evidence.recommendedStrategy,
                    status=evidence.status,
                    confidence=evidence.confidence,
                    sampleCount=evidence.sampleCount,
                    reason="automatic_certified exact scope match",
                    evidenceVersion=evidence.evidenceVersion,
                    category=category,
                    domain=domain,
                    providerId=provider_id or "",
                    modelRevision=model_revision,
                    appliedAutomatically=True,
                )
            return PromptStrategyRecommendation(
                strategy=DEFAULT_STRATEGY,  # type: ignore[arg-type]
                status=evidence.status if evidence else "not_tested",
                confidence="low",
                sampleCount=evidence.sampleCount if evidence else 0,
                reason="automatic_certified refused — uncertified or low confidence; using refined-english",
                evidenceVersion=evidence.evidenceVersion if evidence else "",
                category=category,
                domain=domain,
                providerId=provider_id or "",
                modelRevision=model_revision,
                appliedAutomatically=False,
            )

    # Overlay fallback
    if provider_id:
        profile = resolve_profile(provider_id=provider_id, model_version=model_revision, domain=domain)  # type: ignore[arg-type]
        overlay = load_overlay(profile.profileId, profile.profileVersion)
        if overlay:
            for raw in overlay.get("recommendations") or []:
                if (
                    raw.get("domain") == domain
                    and raw.get("category") == category
                    and raw.get("providerId") == provider_id
                    and raw.get("modelRevision") == model_revision
                ):
                    rec = PromptStrategyRecommendation.model_validate(raw)
                    rec.appliedAutomatically = mode == "automatic_certified" and str(rec.status).startswith("certified_")
                    if mode == "automatic_certified" and not rec.appliedAutomatically:
                        continue
                    rec.reason = rec.reason or "evidence overlay"
                    return rec

    return PromptStrategyRecommendation(
        strategy=DEFAULT_STRATEGY,  # type: ignore[arg-type]
        status="not_tested",
        confidence="low",
        reason="No category evidence — profile/default refined-english",
        category=category,
        domain=domain,
        providerId=provider_id or "",
        modelRevision=model_revision,
        appliedAutomatically=False,
    )


def _confidence_meets(actual: str, required: str) -> bool:
    order = {"low": 0, "medium": 1, "high": 2}
    return order.get(actual, 0) >= order.get(required, 1)


def list_recommendations_for_provider(provider_id: str, model_revision: str = "default") -> list[dict[str, Any]]:
    return [
        e.model_dump(mode="json")
        for e in list_evidence()
        if e.providerId == provider_id and e.modelRevision == model_revision
    ]

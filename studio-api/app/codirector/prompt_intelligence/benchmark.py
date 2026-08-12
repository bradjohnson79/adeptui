"""Benchmark harness scaffold — does not auto-certify bilingual prompting."""

from __future__ import annotations

from typing import Any

from .models import ModulesEnabled, PromptIntelligenceRequest
from .pipeline import enhance
from .profiles import list_profiles


def run_offline_matrix(
    prompt: str,
    *,
    provider_id: str,
    domain: str = "video",
) -> dict[str, Any]:
    """Compare original / EN-only / EN+subtle ZH / EN+balanced ZH without generating media."""
    variants = [
        ("original", ModulesEnabled(productionRefinement=False, cinematicRefinement=False, motionRefinement=False, audioRefinement=False, characterContinuity=False, providerOptimization=False, languageModules=["en"]), "balanced"),
        ("refined_en", ModulesEnabled(languageModules=["en"]), "balanced"),
        ("refined_en_zh_subtle", ModulesEnabled(languageModules=["en", "zh"]), "subtle"),
        ("refined_en_zh_balanced", ModulesEnabled(languageModules=["en", "zh"]), "balanced"),
    ]
    rows: list[dict[str, Any]] = []
    for name, mods, balance in variants:
        result = enhance(
            PromptIntelligenceRequest(
                creatorPrompt=prompt,
                domain=domain,  # type: ignore[arg-type]
                providerId=provider_id,
                modulesEnabled=mods,
                languageBalance=balance,  # type: ignore[arg-type]
            )
        )
        rows.append(
            {
                "variant": name,
                "ok": result.ok,
                "finalProviderPrompt": result.record.finalProviderPrompt,
                "chineseEnhancement": result.record.languageEnhancements.get("zh", ""),
                "overallQuality": (result.record.qualityReport.overall if result.record.qualityReport else None),
                "profileId": result.record.promptProfileId,
                "profileVersion": result.record.promptProfileVersion,
            }
        )
    return {
        "prompt": prompt,
        "providerId": provider_id,
        "domain": domain,
        "variants": rows,
        "note": "Offline prompt matrix only — bilingualCertified requires recorded generation evidence.",
        "profilesAvailable": [p.profileKey for p in list_profiles()],
    }

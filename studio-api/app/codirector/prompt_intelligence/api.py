"""Prompt Intelligence HTTP API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .language.registry import list_language_modules
from .models import GenerationDomain, LanguageBalance, ModulesEnabled, PromptIntelligenceRequest
from .pipeline import analyze_only, enhance
from .profiles import list_profiles, recommendation_banner, resolve_profile
from .recommendation import resolve_strategy_recommendation
from .scoring_v2 import analyze_v2

router = APIRouter(prefix="/prompt-intelligence", tags=["prompt-intelligence"])


class EnhanceBody(BaseModel):
    creatorPrompt: str = ""
    prompt: Optional[str] = None  # alias
    domain: GenerationDomain = "video"
    providerId: Optional[str] = None
    modelId: Optional[str] = None
    modelVersion: Optional[str] = None
    engineId: Optional[str] = None
    negativePrompt: Optional[str] = None
    modulesEnabled: ModulesEnabled = Field(default_factory=ModulesEnabled)
    languageBalance: LanguageBalance = "balanced"
    lockedTerms: list[str] = Field(default_factory=list)
    continuityHints: list[str] = Field(default_factory=list)
    characterNames: list[str] = Field(default_factory=list)
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    manuallyOverridden: bool = False
    existingFinalPrompt: Optional[str] = None
    category: str = "general"
    strategyMode: str = "recommend"
    projectPrefs: Optional[dict[str, Any]] = None


class AnalyzeBody(EnhanceBody):
    pass


class ValidateBody(BaseModel):
    finalProviderPrompt: str
    creatorPrompt: str = ""
    maxPromptLength: Optional[int] = None


def _to_request(body: EnhanceBody) -> PromptIntelligenceRequest:
    creator = (body.creatorPrompt or body.prompt or "").strip()
    return PromptIntelligenceRequest(
        creatorPrompt=creator,
        domain=body.domain,
        providerId=body.providerId,
        modelId=body.modelId,
        modelVersion=body.modelVersion,
        engineId=body.engineId,
        negativePrompt=body.negativePrompt,
        modulesEnabled=body.modulesEnabled,
        languageBalance=body.languageBalance,
        lockedTerms=body.lockedTerms,
        continuityHints=body.continuityHints,
        characterNames=body.characterNames,
        projectId=body.projectId,
        sceneId=body.sceneId,
        manuallyOverridden=body.manuallyOverridden,
        existingFinalPrompt=body.existingFinalPrompt,
    )


@router.post("/enhance")
def enhance_prompt(body: EnhanceBody) -> dict[str, Any]:
    result = enhance(_to_request(body))
    profile = resolve_profile(
        provider_id=body.providerId,
        model_id=body.modelId,
        model_version=body.modelVersion,
        engine_id=body.engineId,
        domain=body.domain,
    )
    payload = result.model_dump(mode="json")
    payload["profileRecommendation"] = result.profileRecommendation or recommendation_banner(profile)
    # UI aliases
    record = payload.get("record") or {}
    record["originalPrompt"] = record.get("creatorPrompt", "")
    record["chineseEnhancement"] = (record.get("languageEnhancements") or {}).get("zh", "")
    payload["record"] = record
    # V2 adaptive recommendation (non-breaking additive field)
    rec = resolve_strategy_recommendation(
        domain=body.domain,
        category=body.category,
        provider_id=body.providerId,
        model_revision=body.modelVersion or "default",
        strategy_mode=body.strategyMode,  # type: ignore[arg-type]
        project_prefs=body.projectPrefs,
    )
    payload["strategyRecommendation"] = rec.model_dump(mode="json")
    axes = analyze_v2(
        body.creatorPrompt or body.prompt or "",
        domain=body.domain,
        provider_id=body.providerId,
        model_revision=body.modelVersion or "default",
        category=body.category,
        strategy_mode=body.strategyMode,
        project_prefs=body.projectPrefs,
        modules_enabled_zh="zh" in (body.modulesEnabled.languageModules or []),
    )
    payload["analyzerV2"] = axes.get("axes")
    return payload


@router.post("/analyze")
def analyze_prompt(body: AnalyzeBody) -> dict[str, Any]:
    base = analyze_only(_to_request(body))
    axes = analyze_v2(
        body.creatorPrompt or body.prompt or "",
        domain=body.domain,
        provider_id=body.providerId,
        model_revision=body.modelVersion or "default",
        category=body.category,
        strategy_mode=body.strategyMode,
        project_prefs=body.projectPrefs,
    )
    base["strategyRecommendation"] = axes.get("strategyRecommendation")
    base["analyzerV2"] = axes.get("axes")
    return base


@router.get("/profiles")
def get_profiles(
    providerId: Optional[str] = None,
    modelId: Optional[str] = None,
    engineId: Optional[str] = None,
    domain: GenerationDomain = "video",
) -> dict[str, Any]:
    resolved = resolve_profile(
        provider_id=providerId,
        model_id=modelId,
        engine_id=engineId,
        domain=domain,
    )
    return {
        "resolved": resolved.model_dump(mode="json"),
        "recommendation": recommendation_banner(resolved),
        "profiles": [p.model_dump(mode="json") for p in list_profiles()],
        "languageModules": list_language_modules(),
    }


@router.post("/validate")
def validate_prompt(body: ValidateBody) -> dict[str, Any]:
    final = (body.finalProviderPrompt or "").strip()
    creator = (body.creatorPrompt or "").strip()
    errors: list[str] = []
    if not final:
        errors.append("FINAL_PROMPT_EMPTY")
    if body.maxPromptLength and len(final) > body.maxPromptLength:
        errors.append("PROMPT_TOO_LONG")
    return {
        "ok": not errors,
        "errors": errors,
        "length": len(final),
        "creatorUnchanged": True,  # creator is never mutated by validate
        "creatorPrompt": creator,
    }

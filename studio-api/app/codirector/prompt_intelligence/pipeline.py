"""Prompt Intelligence pipeline orchestrator."""

from __future__ import annotations

from typing import Any, Optional

from . import compose
from . import terminology
from .errors import (
    MANUAL_OVERRIDE_CONFLICT,
    PROMPT_ENHANCEMENT_FAILED,
    PromptIntelligenceError,
    english_only_fallback,
)
from .intent import analyze_intent
from .language.registry import get_language_module
from .models import (
    ENHANCEMENT_ENGINE_VERSION,
    ModulesEnabled,
    PromptIntelligenceRecord,
    PromptIntelligenceRequest,
    PromptIntelligenceResult,
    source_prompt_hash,
    utc_now_iso,
)
from .modules import audio as audio_mod
from .modules import cinematic as cinematic_mod
from .modules import continuity as continuity_mod
from .modules import motion as motion_mod
from .modules import production as production_mod
from .modules import provider_opt as provider_mod
from .profiles import recommendation_banner, resolve_profile
from .scoring import analyze_quality


def enhance(request: PromptIntelligenceRequest) -> PromptIntelligenceResult:
    creator = (request.creatorPrompt or "").strip()
    if request.manuallyOverridden and request.existingFinalPrompt:
        # Honor override — do not silently regenerate over it
        profile = resolve_profile(
            provider_id=request.providerId,
            model_id=request.modelId,
            model_version=request.modelVersion,
            engine_id=request.engineId,
            domain=request.domain,
        )
        record = PromptIntelligenceRecord(
            creatorPrompt=creator,
            refinedEnglishPrompt=creator,
            languageEnhancements={},
            finalProviderPrompt=request.existingFinalPrompt,
            negativePrompt=request.negativePrompt,
            modulesEnabled=request.modulesEnabled,
            languageBalance=request.languageBalance,
            promptProfileId=profile.profileId,
            promptProfileVersion=profile.profileVersion,
            enhancementEngineVersion=ENHANCEMENT_ENGINE_VERSION,
            manuallyOverridden=True,
            sourcePromptHash=source_prompt_hash(creator),
            generatedAt=utc_now_iso(),
        )
        return PromptIntelligenceResult(
            ok=True,
            record=record,
            profileRecommendation=recommendation_banner(profile),
            error={
                "code": MANUAL_OVERRIDE_CONFLICT,
                "message": "Manual override is active; regenerated layers were not applied to the final prompt.",
                "recommendedAction": "return_to_generated_mode",
            },
        )

    try:
        return PromptIntelligenceResult(ok=True, record=_run(request), profileRecommendation=None)
    except PromptIntelligenceError as exc:
        fb = english_only_fallback(creator, code=exc.code, message=exc.message, details=exc.details)
        profile = resolve_profile(
            provider_id=request.providerId,
            model_id=request.modelId,
            model_version=request.modelVersion,
            engine_id=request.engineId,
            domain=request.domain,
        )
        fallback = fb["fallback"]
        record = PromptIntelligenceRecord(
            creatorPrompt=fallback["creatorPrompt"],
            refinedEnglishPrompt=fallback["refinedEnglishPrompt"],
            languageEnhancements={},
            finalProviderPrompt=fallback["finalProviderPrompt"],
            negativePrompt=request.negativePrompt,
            modulesEnabled=request.modulesEnabled,
            languageBalance=request.languageBalance,
            promptProfileId=profile.profileId,
            promptProfileVersion=profile.profileVersion,
            enhancementEngineVersion=ENHANCEMENT_ENGINE_VERSION,
            sourcePromptHash=source_prompt_hash(creator),
            generatedAt=utc_now_iso(),
            usedEnglishOnlyFallback=True,
        )
        return PromptIntelligenceResult(ok=False, record=record, error=fb["error"], profileRecommendation=recommendation_banner(profile))
    except Exception as exc:  # noqa: BLE001 — pipeline must never wipe a valid prompt
        fb = english_only_fallback(
            creator,
            code=PROMPT_ENHANCEMENT_FAILED,
            message=str(exc) or "Prompt enhancement failed.",
        )
        profile = resolve_profile(
            provider_id=request.providerId,
            model_id=request.modelId,
            engine_id=request.engineId,
            domain=request.domain,
        )
        fallback = fb["fallback"]
        record = PromptIntelligenceRecord(
            creatorPrompt=fallback["creatorPrompt"],
            refinedEnglishPrompt=fallback["refinedEnglishPrompt"],
            finalProviderPrompt=fallback["finalProviderPrompt"],
            negativePrompt=request.negativePrompt,
            modulesEnabled=request.modulesEnabled,
            languageBalance=request.languageBalance,
            promptProfileId=profile.profileId,
            promptProfileVersion=profile.profileVersion,
            enhancementEngineVersion=ENHANCEMENT_ENGINE_VERSION,
            sourcePromptHash=source_prompt_hash(creator),
            generatedAt=utc_now_iso(),
            usedEnglishOnlyFallback=True,
        )
        return PromptIntelligenceResult(ok=False, record=record, error=fb["error"])


def _run(request: PromptIntelligenceRequest) -> PromptIntelligenceRecord:
    creator = (request.creatorPrompt or "").strip()
    profile = resolve_profile(
        provider_id=request.providerId,
        model_id=request.modelId,
        model_version=request.modelVersion,
        engine_id=request.engineId,
        domain=request.domain,
    )
    mods = request.modulesEnabled or ModulesEnabled()

    locked = terminology.collect_locked_terms(
        creator,
        explicit=request.lockedTerms,
        character_names=request.characterNames,
    )
    protected, mapping = terminology.protect(creator, locked)

    intent = analyze_intent(
        protected,
        domain=request.domain,
        continuity_hints=request.continuityHints,
        negative_prompt=request.negativePrompt,
    )

    refinement_layers: dict[str, str] = {}
    english_bits: list[str] = []

    working = protected
    if mods.productionRefinement and "production" in (profile.enabledRefinementModules or ["production"]):
        layer = production_mod.refine(working, intent, request.domain)
        refinement_layers["production"] = layer
        working = layer or working

    if mods.cinematicRefinement and "cinematic" in (profile.enabledRefinementModules or []):
        layer = cinematic_mod.refine(working, intent, request.domain)
        if layer:
            refinement_layers["cinematic"] = layer
            english_bits.append(layer)

    if mods.motionRefinement and "motion" in (profile.enabledRefinementModules or []):
        layer = motion_mod.refine(working, intent, request.domain)
        if layer:
            refinement_layers["motion"] = layer
            english_bits.append(layer)

    if mods.audioRefinement and "audio" in (profile.enabledRefinementModules or []):
        layer = audio_mod.refine(working, intent, request.domain)
        if layer:
            refinement_layers["audio"] = layer
            english_bits.append(layer)

    if mods.characterContinuity and "continuity" in (profile.enabledRefinementModules or []):
        layer = continuity_mod.refine(working, intent, request.domain, request.continuityHints)
        if layer:
            refinement_layers["continuity"] = layer
            english_bits.append(layer)

    if mods.providerOptimization and "provider" in (profile.enabledRefinementModules or []):
        layer = provider_mod.refine(working, profile, request.domain)
        if layer:
            refinement_layers["provider"] = layer
            english_bits.append(layer)

    refined_english = compose.merge_english(working, english_bits)
    refined_english = terminology.restore(refined_english, mapping)

    language_enhancements: dict[str, str] = {}
    enabled_langs = [x.lower() for x in (mods.languageModules or ["en"])]
    # Never silently add zh from profile recommendation
    for lang_id in enabled_langs:
        if lang_id == "en":
            continue
        module = get_language_module(lang_id)
        if not module or getattr(module, "status", "") != "active":
            continue
        clause = module.enhance(intent, domain=request.domain, balance=request.languageBalance)
        if clause:
            language_enhancements[lang_id] = clause

    zh_on = "zh" in enabled_langs and bool(language_enhancements.get("zh"))
    quality = analyze_quality(
        creator,
        intent,
        domain=request.domain,
        profile=profile,
        modules_enabled_zh=zh_on,
    )

    final = compose.compose_final(refined_english, language_enhancements, profile=profile)

    # Negatives stay separate — never fold into Chinese layer
    return PromptIntelligenceRecord(
        creatorPrompt=creator,
        refinedEnglishPrompt=refined_english,
        languageEnhancements=language_enhancements,
        finalProviderPrompt=final,
        negativePrompt=request.negativePrompt,
        refinementLayers=refinement_layers,
        modulesEnabled=mods,
        languageBalance=request.languageBalance,
        promptProfileId=profile.profileId,
        promptProfileVersion=profile.profileVersion,
        enhancementEngineVersion=ENHANCEMENT_ENGINE_VERSION,
        qualityReport=quality,
        manuallyOverridden=False,
        sourcePromptHash=source_prompt_hash(creator),
        generatedAt=utc_now_iso(),
        intentSummary=intent.summary(),
    )


def analyze_only(request: PromptIntelligenceRequest) -> dict[str, Any]:
    profile = resolve_profile(
        provider_id=request.providerId,
        model_id=request.modelId,
        model_version=request.modelVersion,
        engine_id=request.engineId,
        domain=request.domain,
    )
    intent = analyze_intent(
        request.creatorPrompt,
        domain=request.domain,
        continuity_hints=request.continuityHints,
        negative_prompt=request.negativePrompt,
    )
    zh_on = "zh" in [x.lower() for x in (request.modulesEnabled.languageModules or [])]
    report = analyze_quality(
        request.creatorPrompt,
        intent,
        domain=request.domain,
        profile=profile,
        modules_enabled_zh=zh_on,
    )
    return {
        "ok": True,
        "qualityReport": report.model_dump(),
        "intentSummary": intent.summary(),
        "profile": {
            "profileId": profile.profileId,
            "profileVersion": profile.profileVersion,
            "providerId": profile.providerId,
            "modelId": profile.modelId,
            "certificationStatus": profile.certificationStatus,
            "bilingualCertified": profile.bilingualCertified,
            "recommendedLanguageModules": profile.recommendedLanguageModules,
            "recommendedBalance": profile.recommendedBalance,
        },
        "profileRecommendation": recommendation_banner(profile),
    }


def apply_record_to_payload(record: PromptIntelligenceRecord) -> dict[str, Any]:
    """Shape persisted on jobs / snapshots / scene director_json."""
    return {
        "promptIntelligence": record.model_dump(mode="json"),
        "prompt": record.finalProviderPrompt,
        "originalPrompt": record.creatorPrompt,
        "negativePrompt": record.negativePrompt,
    }

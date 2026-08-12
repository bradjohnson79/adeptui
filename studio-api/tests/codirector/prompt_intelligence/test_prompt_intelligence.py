"""Unit tests for Co-Director Prompt Intelligence."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codirector.prompt_intelligence.models import ModulesEnabled, PromptIntelligenceRequest
from app.codirector.prompt_intelligence.pipeline import analyze_only, enhance
from app.codirector.prompt_intelligence.profiles import resolve_profile
from app.codirector.prompt_intelligence.terminology import collect_locked_terms, protect, restore
from app.codirector.prompt_intelligence.language.registry import list_language_modules


def test_resolve_hunyuan_profile():
    profile = resolve_profile(engine_id="hunyuan15", domain="video")
    assert profile.profileId == "hunyuan-video-1.5"
    assert profile.bilingualCertified is False
    assert "zh" in profile.recommendedLanguageModules


def test_resolve_ltx_english_only():
    profile = resolve_profile(engine_id="ltx", domain="video")
    assert profile.profileId == "ltx-video"
    assert profile.defaultStrategy == "english-only"


def test_locked_term_protection():
    prompt = 'Korri looks at the horizon. "Stay with me." Use @korri_ref and style_lora_v1'
    terms = collect_locked_terms(prompt, character_names=["Korri"])
    protected, mapping = protect(prompt, terms)
    assert "Korri" not in protected or "⟦LOCK_" in protected
    restored = restore(protected, mapping)
    assert "Korri" in restored
    assert "@korri_ref" in restored or "korri_ref" in restored


def test_enhance_preserves_original_and_adds_chinese():
    creator = "Korri stands on a cliff at sunset, wide shot, soft light"
    result = enhance(
        PromptIntelligenceRequest(
            creatorPrompt=creator,
            domain="video",
            engineId="hunyuan15",
            characterNames=["Korri"],
            modulesEnabled=ModulesEnabled(languageModules=["en", "zh"]),
            languageBalance="balanced",
        )
    )
    assert result.ok
    assert result.record.creatorPrompt == creator
    assert "Korri" in result.record.refinedEnglishPrompt
    assert result.record.languageEnhancements.get("zh")
    assert result.record.finalProviderPrompt
    assert creator in result.record.finalProviderPrompt or "Korri" in result.record.finalProviderPrompt
    assert result.record.qualityReport is not None
    assert result.record.qualityReport.overall > 0


def test_chinese_off_by_default():
    result = enhance(
        PromptIntelligenceRequest(
            creatorPrompt="A quiet forest path at dawn",
            domain="video",
            engineId="hunyuan15",
        )
    )
    assert result.ok
    assert not result.record.languageEnhancements.get("zh")


def test_manual_override_not_replaced():
    result = enhance(
        PromptIntelligenceRequest(
            creatorPrompt="original",
            domain="video",
            engineId="ltx",
            manuallyOverridden=True,
            existingFinalPrompt="MANUAL FINAL",
        )
    )
    assert result.record.finalProviderPrompt == "MANUAL FINAL"
    assert result.record.manuallyOverridden is True


def test_negative_prompt_stays_separate():
    result = enhance(
        PromptIntelligenceRequest(
            creatorPrompt="A dancer in soft light",
            domain="video",
            engineId="ltx",
            negativePrompt="camera shake, extra fingers",
            modulesEnabled=ModulesEnabled(languageModules=["en", "zh"]),
        )
    )
    assert result.record.negativePrompt == "camera shake, extra fingers"
    zh = result.record.languageEnhancements.get("zh") or ""
    assert "camera shake" not in zh


def test_analyze_scores():
    out = analyze_only(
        PromptIntelligenceRequest(
            creatorPrompt="wide shot of a hero walking through rain, cinematic lighting",
            domain="video",
            engineId="wan",
        )
    )
    assert out["ok"]
    assert out["qualityReport"]["overall"] >= 50
    assert "cameraLanguage" in out["qualityReport"]["dimensions"]


def test_future_language_modules_registered():
    mods = {m["languageId"]: m["status"] for m in list_language_modules()}
    assert mods["en"] == "active"
    assert mods["zh"] == "active"
    assert mods["ja"] == "future"
    assert mods["ko"] == "future"
    assert mods["fr"] == "future"


def test_image_and_audio_domains():
    img = enhance(
        PromptIntelligenceRequest(
            creatorPrompt="Portrait of Korri, soft rim light",
            domain="image",
            providerId="comfyui",
            characterNames=["Korri"],
        )
    )
    audio = enhance(
        PromptIntelligenceRequest(
            creatorPrompt="Warm cinematic score with gentle rise",
            domain="music",
            providerId="audio-studio",
        )
    )
    assert img.ok and "Korri" in img.record.finalProviderPrompt
    assert audio.ok and audio.record.finalProviderPrompt

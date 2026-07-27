"""M3.0F multilingual platform — LF scenarios and language intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.codirector.language_intelligence import audio_phrases, glossary, intent, registry, translate
from app.codirector.language_intelligence.bible_localization import merge_localization, wrap_localized_field
from app.codirector.language_intelligence.dialogue import add_variant, make_dialogue, mark_constructed_language
from app.codirector.model_intelligence.compiler import compile_intent, normalize_audio_from_text
from app.codirector.model_intelligence.schemas import (
    AudioChannelPolicy,
    NormalizedGenerationIntent,
)


def test_locale_registry_twelve_active():
    assert len(registry.LOCALE_REGISTRY) == 12
    assert registry.is_supported_locale("zh-Hans")
    assert registry.get_locale("pt")["dateLocale"] == "pt-BR"
    assert registry.get_locale("ar")["direction"] == "rtl"
    assert registry.get_locale("ur")["direction"] == "rtl"
    assert registry.resolve_locale("pt-BR") == "pt"


def test_lf11_spanish_audio_exclusion():
    audio = audio_phrases.normalize_audio_from_multilingual_text("Sin música de fondo.")
    assert audio.music == AudioChannelPolicy.PROHIBITED


@pytest.mark.parametrize(
    "phrase",
    [
        "No background music.",
        "Pas de musique de fond.",
        "Sin música de fondo.",
        "背景音楽なし。",
        "不要背景音乐。",
        "sem música de fundo",
        "بدون موسيقى خلفية",
        "tanpa musik latar",
    ],
)
def test_multilingual_music_prohibited(phrase: str):
    audio = normalize_audio_from_text(phrase)
    assert audio.music == AudioChannelPolicy.PROHIBITED


def test_intent_preserves_original_and_protected_terms():
    result = intent.normalize_creative_intent(
        "Anadriya holds the Life Vital in Handari speech.",
        source_language="ja",
        protected_terms=["Life Vital", "Handari", "Anadriya"],
    )
    assert result.sourceLanguage == "ja"
    assert "Life Vital" in result.originalText
    assert "Life Vital" in result.protectedTerms or "Life Vital" in result.normalizedIntent["subjects"]


def test_locked_translation_not_replaced():
    out = translate.translate_text(
        "Hello",
        source_language="en",
        target_language="fr",
        locked=True,
    )
    assert out["state"] == "LOCKED"
    assert out["translatedText"] == "Hello"


def test_bible_localization_never_overwrites_canon():
    field = wrap_localized_field(
        field_id="character.anadriya.description",
        canonical_language="en",
        canonical_text="Canonical EN",
    )
    field = merge_localization(field, locale="fr", text="FR draft", status="draft")
    field = merge_localization(field, locale="fr", text="FR locked", status="locked")
    field = merge_localization(field, locale="fr", text="should not replace", status="draft")
    assert field["canonicalText"] == "Canonical EN"
    assert field["localizedText"]["fr"] == "FR locked"


def test_dialogue_variants_same_id():
    dlg = make_dialogue(
        scene_id="scene_12",
        speaker_id="character_01",
        original_language="en",
        original_text="Let's go.",
    )
    dlg = add_variant(dlg, locale="fr", text="Allons-y.", status="approved")
    dlg = mark_constructed_language(dlg, enabled=True)
    assert dlg["dialogueId"]
    assert dlg["localizedVariants"]["fr"]["text"] == "Allons-y."
    assert dlg["constructedLanguage"] is True


def test_mil_compile_records_language_provenance():
    intent_obj = NormalizedGenerationIntent(
        userPrompt="Cinematic I2V. Sin música de fondo.",
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={"sourceLanguage": "es", "promptLanguagePolicy": "auto"},
    )
    result = compile_intent(intent_obj, model_id="fal_seedance")
    assert result.parameters.get("generate_audio") is False
    assert result.originalRequest
    assert result.sourceLanguage == "es"
    assert result.promptLanguage


def test_platform_protected_terms():
    assert "Co-Director" in glossary.PLATFORM_PROTECTED_TERMS
    assert "Production Bible" in glossary.PLATFORM_PROTECTED_TERMS


def test_frontend_locale_packs_exist():
    root = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "i18n" / "locales"
    critical = ["common", "navigation", "codirector", "errors", "settings", "jobs"]
    for locale in registry.SUPPORTED:
        for ns in critical:
            path = root / locale / f"{ns}.json"
            assert path.is_file(), f"missing {path}"
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data, f"empty {path}"


def test_language_pack_no_script_injection():
    root = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "i18n" / "locales"
    for path in root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text.lower()
        assert "javascript:" not in text.lower()


def test_language_intelligence_api_locales(client):
    res = client.get("/api/codirector/language-intelligence/locales")
    assert res.status_code == 200
    body = res.json()
    assert len(body["locales"]) == 12


def test_language_intelligence_normalize_audio_api(client):
    res = client.post(
        "/api/codirector/language-intelligence/normalize-audio",
        json={"text": "Pas de musique de fond."},
    )
    assert res.status_code == 200
    assert res.json()["music"] == "prohibited"

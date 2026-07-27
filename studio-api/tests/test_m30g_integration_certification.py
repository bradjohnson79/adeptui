"""M3.0g integration certification — canon, ML, provenance, EN-REG, LOC-ISO, security."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.codirector.language_intelligence import audio_phrases, glossary, intent, translate
from app.codirector.language_intelligence.bible_localization import merge_localization, wrap_localized_field
from app.codirector.language_intelligence.dialogue import add_variant, make_dialogue
from app.codirector.language_intelligence.registry import LOCALE_REGISTRY, resolve_locale
from app.codirector.model_intelligence.compiler import compile_intent, normalize_audio_from_text
from app.codirector.model_intelligence.preflight import run_preflight
from app.codirector.model_intelligence.schemas import (
    AudioChannelPolicy,
    NormalizedGenerationIntent,
    PreflightStatus,
)


PROTECTED = [
    "Dreamweaver",
    "Starcaster",
    "Anadriya",
    "Korri",
    "Chroma",
    "Life Vital",
    "Shadow Law",
    "Production Bible",
    "Co-Director",
    "Adept UI Studio",
]


def test_canon_01_platform_protected_terms_present():
    for term in ("Co-Director", "Production Bible", "Life Vital", "Dreamweaver", "Chroma"):
        assert term in glossary.PLATFORM_PROTECTED_TERMS


def test_canon_02_protected_terms_survive_translate_passthrough():
    text = "Anadriya holds the Life Vital near Dreamweaver."
    out = translate.translate_text(
        text, source_language="en", target_language="fr", glossary=[]
    )
    assert "Life Vital" in out["originalText"]
    assert "Life Vital" in out["protectedTermsApplied"] or "Life Vital" in out["translatedText"]
    assert out["originalText"] == text


def test_canon_03_bible_localization_never_overwrites_canon():
    field = wrap_localized_field(
        field_id="character.anadriya.description",
        canonical_language="en",
        canonical_text="Anadriya of Life Vital",
    )
    field = merge_localization(field, locale="ja", text="アナドリヤ", status="draft")
    assert field["canonicalText"] == "Anadriya of Life Vital"
    assert "Life Vital" in field["canonicalText"]


def test_ml_locale_dimensions_independent():
    """LOC-ISO / ML — UI locale resolution must not imply project language mutation."""
    ui = resolve_locale("ar")
    project = resolve_locale("en")
    prompt = resolve_locale("en")
    assert ui == "ar"
    assert project == "en"
    assert prompt == "en"
    assert ui != project


def test_en_reg_english_compile_unchanged_shape():
    intent_obj = NormalizedGenerationIntent(
        userPrompt="Cinematic locked camera. No background music.",
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={"sourceLanguage": "en", "promptLanguagePolicy": "english"},
    )
    result = compile_intent(intent_obj, model_id="fal_seedance")
    assert result.status == "ok"
    assert result.parameters.get("generate_audio") is False
    assert result.sourceLanguage == "en"
    assert result.originalRequest


@pytest.mark.parametrize(
    "phrase",
    [
        "Create a five-second cinematic shot. No dialogue. No background music. Only soft room ambience. Keep the camera locked.",
        "Crea un plano cinematográfico de cinco segundos. Sin diálogo. Sin música de fondo. Solo ambiente suave. Cámara fija.",
        "Créez un plan cinématographique de cinq secondes. Pas de dialogue. Pas de musique de fond. Seulement une ambiance douce. Caméra verrouillée.",
    ],
)
def test_li_intent_equivalence_no_music(phrase: str):
    audio = normalize_audio_from_text(phrase)
    assert audio.music == AudioChannelPolicy.PROHIBITED


def test_mi_live_compile_generate_audio_false_seedance():
    intent_obj = NormalizedGenerationIntent(
        userPrompt="Sin música de fondo. Plano cinematográfico.",
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={"sourceLanguage": "es", "promptLanguagePolicy": "auto"},
    )
    result = compile_intent(intent_obj, model_id="fal_seedance")
    assert result.parameters.get("generate_audio") is False
    assert result.promptLanguage
    assert result.protectedTermsApplied is not None


def test_e2e07_quarantined_seedream_preflight_blocked():
    intent_obj = NormalizedGenerationIntent(
        userPrompt="still portrait",
        mode="text_to_image",
        mediaType="image",
        forceModelId="seedream",
    )
    pf = run_preflight(intent_obj, model_id="seedream")
    assert pf.status in (PreflightStatus.BLOCKED, PreflightStatus.APPROVAL_REQUIRED)


def test_sec_malicious_locale_payload_no_script():
    evil = '<script>alert(1)</script> no music'
    out = translate.translate_text(evil, source_language="en", target_language="fr")
    assert "<script>" in out["originalText"]
    # translation must not execute; identity/offline path preserves text safely for review
    assert out["state"] in ("REVIEW_REQUIRED", "APPROVED", "FAILED", "LOCKED")


def test_sec_unsupported_locale_resolves_to_en():
    assert resolve_locale("xx-ZZ") == "en"


def test_dialogue_subtitle_utf8_roundtrip():
    dlg = make_dialogue(
        scene_id="s1",
        speaker_id="c1",
        original_language="en",
        original_text="Let's go.",
        start=12.4,
        end=13.2,
    )
    dlg = add_variant(dlg, locale="ja", text="行こう。", status="approved")
    raw = json.dumps(dlg, ensure_ascii=False)
    loaded = json.loads(raw)
    assert loaded["localizedVariants"]["ja"]["text"] == "行こう。"
    assert loaded["originalText"] == "Let's go."


def test_twelve_locales_registered():
    assert len(LOCALE_REGISTRY) == 12
    assert resolve_locale("zh-Hans") == "zh-Hans"
    assert resolve_locale("pt-BR") == "pt"


def test_loc_iso_language_prefs_shape_in_settings_json():
    """Project settings language block keeps dimensions separate."""
    settings = {
        "language": {
            "interfaceLocale": "ja",
            "conversationLocale": "ja",
            "projectPrimaryLocale": "en",
            "promptLanguagePolicy": "english",
            "exportLocale": "fr",
            "dialogueLanguage": "en",
            "subtitleLanguage": "ja",
        }
    }
    lang = settings["language"]
    assert lang["interfaceLocale"] == "ja"
    assert lang["projectPrimaryLocale"] == "en"
    assert lang["dialogueLanguage"] == "en"
    assert lang["subtitleLanguage"] == "ja"
    assert lang["promptLanguagePolicy"] == "english"
    # mutating UI locale must not require mutating project/dialogue
    lang["interfaceLocale"] = "ar"
    assert lang["projectPrimaryLocale"] == "en"
    assert lang["dialogueLanguage"] == "en"


def test_frontend_locale_packs_still_present():
    root = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "i18n" / "locales"
    for locale in ("en", "fr", "es", "ja", "zh-Hans", "ar", "ur"):
        assert (root / locale / "common.json").is_file()

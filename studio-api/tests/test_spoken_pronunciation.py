"""Platform spoken respelling for Qwen3-TTS / Kokoro / IndexTTS2."""

from __future__ import annotations

from app.character_identity.spoken_pronunciation import (
    PLATFORM_SPOKEN_PRONUNCIATIONS,
    apply_spoken_pronunciations,
    merge_spoken_pronunciations,
)
from app.voice_performance.compiler import apply_pronunciations
from app.voice_performance.schemas import PerformanceSegmentOut


def test_platform_table_has_anadriya_hyphen_respell_only():
    table = dict(PLATFORM_SPOKEN_PRONUNCIATIONS)
    assert table["Anadriya"] == "Anna-Dree-Ya"
    assert "Adept" not in table
    assert "Add-ept" not in table.values()
    assert "Anna-Dree-Yah" not in table.values()


def test_apply_anadriya_hyphen_syllables():
    assert apply_spoken_pronunciations("Stay close, Anadriya.") == "Stay close, Anna-Dree-Ya."


def test_apply_leaves_adept_unrespelled():
    assert apply_spoken_pronunciations("Where is the Adept?") == "Where is the Adept?"


def test_apply_combined_possessive_and_adept():
    assert apply_spoken_pronunciations("Anadriya's Adept") == "Anna-Dree-Ya's Adept"


def test_apply_skips_when_phonetic_equals_word():
    spoken = apply_spoken_pronunciations(
        "Where is the Adept?",
        [("Adept", "Adept"), ("Anadriya", "Anna-Dree-Ya")],
    )
    assert spoken == "Where is the Adept?"


def test_voice_override_wins_over_platform():
    merged = merge_spoken_pronunciations(
        [{"word": "Anadriya", "phonetic": "AH-nah-DREE-yah"}]
    )
    assert ("Anadriya", "AH-nah-DREE-yah") in merged
    spoken = apply_spoken_pronunciations("Stay close, Anadriya.", merged)
    assert spoken == "Stay close, AH-nah-DREE-yah."
    assert "Anna-Dree-Ya" not in spoken


def test_voice_can_add_adept_respell():
    merged = merge_spoken_pronunciations([{"word": "Adept", "phonetic": "Add-ept"}])
    assert apply_spoken_pronunciations("Where is the Adept?", merged) == "Where is the Add-ept?"


def test_compiler_applies_spoken_respell_without_warning_anadriya():
    segments = [
        PerformanceSegmentOut(
            id="s1",
            orderIndex=1,
            segmentType="speech",
            text="Stay close, Anadriya. Where is the Adept?",
        )
    ]
    out, issues = apply_pronunciations(segments, voice=None)
    assert out[0].text == "Stay close, Anna-Dree-Ya. Where is the Adept?"
    assert not any(i.code == "UNRESOLVED_PRONUNCIATION" and "Anadriya" in i.message for i in issues)


def test_compiler_voice_override_wins():
    segments = [
        PerformanceSegmentOut(
            id="s1",
            orderIndex=1,
            segmentType="speech",
            text="Anadriya's Adept",
        )
    ]
    voice = {
        "pronunciations": [
            {"word": "Anadriya", "phonetic": "AH-nah-DREE-yah", "status": "approved"}
        ]
    }
    out, _issues = apply_pronunciations(segments, voice=voice)
    assert out[0].text == "AH-nah-DREE-yah's Adept"
    assert out[0].pronunciationOverrides[0]["word"] == "Anadriya"
    assert out[0].pronunciationOverrides[0]["phonetic"] == "AH-nah-DREE-yah"

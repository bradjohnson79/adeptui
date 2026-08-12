"""Tests for M42 Qwen-2512 visual style intelligence."""

from __future__ import annotations

import json

import pytest

from app.style_intelligence import REQUIRED_STYLE_KEYS, get_profile, list_profiles, registry_as_dict


def test_registry_contains_all_required_style_keys():
    assert tuple(profile.key for profile in list_profiles()) == REQUIRED_STYLE_KEYS


def test_every_profile_has_all_required_content():
    for profile in list_profiles():
        assert profile.displayName
        assert profile.identityPreservationRules
        assert profile.renderingLanguage
        assert profile.anatomyLanguage
        assert profile.faceLanguage
        assert profile.materialLanguage
        assert profile.lightingLanguage
        assert profile.colorLanguage
        assert profile.cameraLanguage
        assert profile.negativeConstraints
        assert profile.qwen2512PromptRules


def test_identity_preservation_explicitly_locks_core_traits():
    required_phrases = (
        "eye color",
        "hair",
        "ears",
        "body",
        "wardrobe",
        "circuit",
        "personality",
    )
    for profile in list_profiles():
        combined = " ".join(profile.identityPreservationRules).lower()
        for phrase in required_phrases:
            assert phrase in combined, f"{profile.key} missing lock for {phrase}"


@pytest.mark.parametrize(
    ("style_key", "expected_fragments"),
    [
        (
            "anime",
            ("same character, anime rendering only", "no chibi conversion", "anime stylization"),
        ),
        (
            "realistic_anime",
            ("anime-rooted identity with realistic shading", "no full photoreal conversion"),
        ),
        (
            "live_action",
            ("faithful live-action adaptation", "no actor recasting drift", "practical-production equivalents"),
        ),
        (
            "stop_motion",
            ("stop-motion puppet interpretation only", "miniature", "generic puppet"),
        ),
        (
            "claymation",
            ("claymation cues like fingerprints", "generic blob-like clay figure", "squash-and-stretch"),
        ),
    ],
)
def test_detailed_locks_exist_for_high_risk_style_transfers(
    style_key: str,
    expected_fragments: tuple[str, ...],
):
    profile = get_profile(style_key)
    combined = " ".join(
        (
            *profile.identityPreservationRules,
            *profile.negativeConstraints,
            *profile.qwen2512PromptRules,
        )
    ).lower()
    for fragment in expected_fragments:
        assert fragment in combined


def test_registry_as_dict_is_json_serializable():
    dumped = json.dumps(registry_as_dict(), ensure_ascii=True)
    assert '"key": "anime"' in dumped
    assert '"key": "documentary_realism"' in dumped


def test_unknown_style_raises_helpful_error():
    with pytest.raises(KeyError) as excinfo:
        get_profile("unknown_style")
    assert "Unknown visual style" in str(excinfo.value)

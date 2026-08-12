from __future__ import annotations

from app.codirector.foundation.domains.guidance import domain_guidance
from app.codirector.foundation.domains.registry import clear_profile_cache, list_profiles, resolve_profiles


def test_list_profiles_loads_expected_catalog() -> None:
    clear_profile_cache()
    profiles = list_profiles()
    ids = {profile.profileId for profile in profiles}

    assert len(profiles) == 16
    assert "feature_film" in ids
    assert "documentary" in ids
    assert "educational_explainer" in ids
    assert "custom" in ids


def test_resolve_profiles_supports_aliases_and_combinations() -> None:
    clear_profile_cache()
    profiles = resolve_profiles("documentary", traits=["educational"])
    ids = [profile.profileId for profile in profiles]

    assert ids[0] == "documentary"
    assert "educational_explainer" in ids


def test_resolve_profiles_accepts_series_web_series_alias() -> None:
    clear_profile_cache()
    profiles = resolve_profiles("web_series")

    assert [profile.profileId for profile in profiles] == ["series_web_series"]


def test_resolve_profiles_falls_back_to_custom() -> None:
    clear_profile_cache()
    profiles = resolve_profiles("unknown_format")

    assert [profile.profileId for profile in profiles] == ["custom"]


def test_domain_guidance_is_deterministic_and_creator_safe() -> None:
    clear_profile_cache()
    profiles = resolve_profiles("documentary", traits=["educational"])

    first = domain_guidance(profiles, "approval review")
    second = domain_guidance(profiles, "approval review")

    assert first == second
    assert "Documentary + Educational Explainer" in first
    assert "knowledgepackids" not in first.lower()
    assert "factual review" in first.lower()
    assert "json" not in first.lower()


def test_domain_guidance_changes_focus_by_topic() -> None:
    clear_profile_cache()
    profiles = resolve_profiles("feature_film")

    story = domain_guidance(profiles, "story pacing")
    delivery = domain_guidance(profiles, "export handoff")

    assert story != delivery
    assert "quality checks" in story.lower()
    assert "deliverables" in delivery.lower()

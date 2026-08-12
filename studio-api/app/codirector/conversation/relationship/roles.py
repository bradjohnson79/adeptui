"""Role emphasis weights — change priority, never strip capability."""

from __future__ import annotations

from .schemas import CoDirectorRelationshipProfile, PrimaryRole


def role_emphasis(profile: CoDirectorRelationshipProfile) -> dict[str, float]:
    """Return expression/context weights in 0–1 range."""

    base = {
        "encouragement": 0.5,
        "story": 0.5,
        "production": 0.5,
        "vision": 0.5,
        "research": 0.4,
        "operations": 0.4,
        "warmth_boost": 0.5,
    }
    role = profile.primary_role
    if role == PrimaryRole.CREATIVE_SUPPORTER:
        base.update(encouragement=0.85, warmth_boost=0.75, production=0.35)
    elif role == PrimaryRole.PRODUCER:
        base.update(production=0.85, operations=0.7, story=0.4)
    elif role == PrimaryRole.STORY_PARTNER:
        base.update(story=0.9, vision=0.55, production=0.35)
    elif role == PrimaryRole.CREATIVE_DIRECTOR:
        base.update(vision=0.9, story=0.6, production=0.4)
    elif role == PrimaryRole.RESEARCH_PARTNER:
        base.update(research=0.9, story=0.5, production=0.35)
    elif role == PrimaryRole.MARKETING_PITCH_PARTNER:
        base.update(vision=0.75, research=0.55, production=0.45, encouragement=0.55)
    elif role == PrimaryRole.PRODUCTION_OPERATOR:
        base.update(operations=0.9, production=0.85, warmth_boost=0.4)
    # BALANCED / CUSTOM keep defaults
    if profile.feedback_style == "CANDID":
        base["encouragement"] = max(0.2, base["encouragement"] - 0.2)
    elif profile.feedback_style == "GENTLE":
        base["encouragement"] = min(1.0, base["encouragement"] + 0.15)
        base["warmth_boost"] = min(1.0, base["warmth_boost"] + 0.1)
    return base


def role_guidance_text(profile: CoDirectorRelationshipProfile) -> str:
    w = role_emphasis(profile)
    return (
        f"Role emphasis (capability unchanged): {profile.primary_role.value}. "
        f"Weights: story={w['story']:.2f}, production={w['production']:.2f}, "
        f"vision={w['vision']:.2f}, research={w['research']:.2f}, "
        f"operations={w['operations']:.2f}, encouragement={w['encouragement']:.2f}."
    )

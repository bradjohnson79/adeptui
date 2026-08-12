"""Compact first-conversation relationship onboarding helpers."""

from __future__ import annotations

import re

from .schemas import CoDirectorRelationshipProfile, PrimaryRole

_NAME_ME = re.compile(
    r"\b(?:call me|my name is|i(?:'|’)m)\s+([A-Z][\w'’\-]{1,40})\b",
    re.I,
)
_CALL_YOU = re.compile(
    r"\b(?:call you|your name (?:is|should be)|i(?:'|’)ll call you)\s+([A-Z][\w'’\-]{1,40})\b",
    re.I,
)
_SKIP = re.compile(r"\b(skip|later|just start|get started|no onboarding)\b", re.I)
_ROLE_MAP = {
    "creative supporter": PrimaryRole.CREATIVE_SUPPORTER,
    "supporter": PrimaryRole.CREATIVE_SUPPORTER,
    "producer": PrimaryRole.PRODUCER,
    "story partner": PrimaryRole.STORY_PARTNER,
    "story": PrimaryRole.STORY_PARTNER,
    "creative director": PrimaryRole.CREATIVE_DIRECTOR,
    "research": PrimaryRole.RESEARCH_PARTNER,
    "research partner": PrimaryRole.RESEARCH_PARTNER,
    "production operator": PrimaryRole.PRODUCTION_OPERATOR,
    "operator": PrimaryRole.PRODUCTION_OPERATOR,
    "balanced": PrimaryRole.BALANCED,
}


def needs_onboarding(profile: CoDirectorRelationshipProfile) -> bool:
    if profile.onboarding_completed or profile.onboarding_skipped:
        return False
    return True


def apply_onboarding_message(
    profile: CoDirectorRelationshipProfile,
    user_message: str,
) -> tuple[CoDirectorRelationshipProfile, bool]:
    """Mutate profile from a compact onboarding turn. Returns (profile, completed_now)."""

    text = user_message or ""
    if _SKIP.search(text):
        profile.onboarding_skipped = True
        profile.onboarding_completed = True
        if not profile.primary_role:
            profile.primary_role = PrimaryRole.BALANCED
        return profile, True

    m = _NAME_ME.search(text)
    if m:
        profile.user_preferred_name = m.group(1).strip()
    m2 = _CALL_YOU.search(text)
    if m2:
        profile.assistant_preferred_name = m2.group(1).strip()

    lowered = text.lower()
    for key, role in _ROLE_MAP.items():
        if key in lowered:
            profile.primary_role = role
            break

    if "wait until i ask" in lowered:
        profile.initiative_level = "RESPONSIVE"
    elif "actively prepare" in lowered or "high initiative" in lowered:
        profile.initiative_level = "HIGH_INITIATIVE"
    elif "suggest when useful" in lowered:
        profile.initiative_level = "PROACTIVE"

    if "very candid" in lowered or "candid" in lowered:
        profile.feedback_style = "CANDID"
    elif "gentle" in lowered:
        profile.feedback_style = "GENTLE"

    if "only document when asked" in lowered:
        profile.documentation_mode = "MANUAL_ONLY"
    elif "propose" in lowered and "approval" in lowered:
        profile.documentation_mode = "PROPOSE_FOR_APPROVAL"
    elif "capture confirmed" in lowered or "automatically" in lowered:
        profile.documentation_mode = "AUTO_CONFIRMED"

    if "offline" in lowered:
        profile.research_permission = "OFFLINE"
    elif "active research" in lowered:
        profile.research_permission = "ACTIVE"
    elif "search when" in lowered or "when useful" in lowered:
        profile.research_permission = "WHEN_USEFUL"

    completed = bool(profile.user_preferred_name) and (
        bool(profile.assistant_preferred_name) or profile.primary_role != PrimaryRole.BALANCED
    )
    # Completing names + any explicit role/pref finishes compact onboarding.
    if profile.user_preferred_name and profile.assistant_preferred_name:
        profile.onboarding_completed = True
        completed = True
    elif completed and profile.user_preferred_name:
        profile.onboarding_completed = True
    return profile, profile.onboarding_completed


def onboarding_prompt_block(profile: CoDirectorRelationshipProfile) -> str:
    if not needs_onboarding(profile):
        user = profile.user_preferred_name or "friend"
        assistant = profile.assistant_preferred_name or "Co-Director"
        ownership = getattr(profile, "default_ownership", None) or "CO_CREATE"
        return (
            f"Relationship established. Address the creator as \"{user}\" when natural. "
            f"Your name is {assistant}. "
            f"Primary role emphasis: {profile.primary_role.value}. "
            f"Assistance depth / ownership default: {ownership}.\n"
            "When the creator has just submitted working preferences (names, role, hands-on level):\n"
            f"- Explicitly acknowledge: you are {assistant}; you will call them {user}.\n"
            "- Acknowledge the chosen role and how hands-on they want you to be.\n"
            "- Thank them warmly for sharing preferences.\n"
            "- Invite them to start telling you about the project in natural conversation.\n"
            "- Be interactive and encouraging — do not reply with a single terse line or go silent."
        )
    return (
        "First-conversation relationship onboarding (compact, not a wizard):\n"
        "- Warmly greet the creator.\n"
        "- Ask what they would like to call you, and what you should call them.\n"
        "- Ask how they want you to work with them most of the time "
        "(Creative Supporter, Producer, Story Partner, Creative Director, "
        "Research Partner, Production Operator, Balanced, or custom).\n"
        "- Offer Skip / start working immediately with balanced defaults.\n"
        "- Do not present a long form."
    )

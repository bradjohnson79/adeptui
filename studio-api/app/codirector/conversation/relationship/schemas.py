"""Relationship onboarding and creator creative profile schemas."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PrimaryRole(str, Enum):
    CREATIVE_SUPPORTER = "CREATIVE_SUPPORTER"
    PRODUCER = "PRODUCER"
    STORY_PARTNER = "STORY_PARTNER"
    CREATIVE_DIRECTOR = "CREATIVE_DIRECTOR"
    RESEARCH_PARTNER = "RESEARCH_PARTNER"
    MARKETING_PITCH_PARTNER = "MARKETING_PITCH_PARTNER"
    PRODUCTION_OPERATOR = "PRODUCTION_OPERATOR"
    BALANCED = "BALANCED"
    CUSTOM = "CUSTOM"


CollaborationOwnershipLiteral = Literal[
    "USER_LEADS",
    "CO_CREATE",
    "CODIRECTOR_LEADS",
    "CODIRECTOR_EXECUTES",
    "ASK_EACH_TIME",
]


class CoDirectorRelationshipProfile(BaseModel):
    assistant_preferred_name: str = "Co-Director"
    user_preferred_name: str = ""
    pronunciation_or_title: str = ""
    primary_role: PrimaryRole = PrimaryRole.BALANCED
    secondary_roles: list[str] = Field(default_factory=list)
    initiative_level: Literal["RESPONSIVE", "PROACTIVE", "HIGH_INITIATIVE"] = "PROACTIVE"
    feedback_style: Literal["GENTLE", "BALANCED", "CANDID"] = "BALANCED"
    narration_mode: Literal["LISTEN_FIRST", "FOCUSED_QUESTIONS", "ACTIVE_DISCOVERY"] = "LISTEN_FIRST"
    documentation_mode: Literal["AUTO_CONFIRMED", "PROPOSE_FOR_APPROVAL", "MANUAL_ONLY"] = "AUTO_CONFIRMED"
    research_permission: Literal["ASK_FIRST", "WHEN_USEFUL", "ACTIVE", "OFFLINE"] = "ASK_FIRST"
    default_ownership: CollaborationOwnershipLiteral = "CO_CREATE"
    relationship_scope: Literal["GLOBAL", "PROJECT"] = "PROJECT"
    onboarding_completed: bool = False
    onboarding_skipped: bool = False
    updated_at: str = ""


class CreatorCreativeProfile(BaseModel):
    preferred_name: str = ""
    creative_disciplines: list[str] = Field(default_factory=list)
    recurring_themes: list[str] = Field(default_factory=list)
    artistic_priorities: list[str] = Field(default_factory=list)
    preferred_working_style: list[str] = Field(default_factory=list)
    preferred_feedback_style: str = ""
    inspiration_sources: list[str] = Field(default_factory=list)
    production_comfort_areas: list[str] = Field(default_factory=list)
    production_challenge_areas: list[str] = Field(default_factory=list)
    creator_confirmed: bool = False
    source_ids: list[str] = Field(default_factory=list)


def balanced_defaults() -> CoDirectorRelationshipProfile:
    return CoDirectorRelationshipProfile(
        primary_role=PrimaryRole.BALANCED,
        initiative_level="PROACTIVE",
        feedback_style="BALANCED",
        narration_mode="LISTEN_FIRST",
        documentation_mode="AUTO_CONFIRMED",
        research_permission="ASK_FIRST",
        default_ownership="CO_CREATE",
        onboarding_skipped=True,
        onboarding_completed=True,
    )

"""Seed-policy contracts for exploration, refinement, and continuity."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class SeedPolicy(str, Enum):
    EXPLORE = "explore"
    REFINE = "refine"
    PRODUCTION_CONTINUITY = "production_continuity"


class SeedPolicyContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: SeedPolicy
    display_name: str
    intent: str
    seed_behavior: str
    reference_requirement: str
    when_to_use: list[str]


SEED_POLICIES: dict[SeedPolicy, SeedPolicyContract] = {
    SeedPolicy.EXPLORE: SeedPolicyContract(
        policy=SeedPolicy.EXPLORE,
        display_name="Explore",
        intent="Discover promising directions before identity is locked.",
        seed_behavior="Rotate seeds freely across broad prompt or composition exploration.",
        reference_requirement="Optional; use loose identity anchors if available.",
        when_to_use=[
            "Early ideation",
            "Style look-dev",
            "Broad composition search",
        ],
    ),
    SeedPolicy.REFINE: SeedPolicyContract(
        policy=SeedPolicy.REFINE,
        display_name="Refine",
        intent="Adjust a promising result without losing its useful structure.",
        seed_behavior="Start from a known-good seed and perturb only when drift is acceptable.",
        reference_requirement="Recommended; preserve approved identity anchors while tuning.",
        when_to_use=[
            "Correcting specific drift",
            "Improving a near-hit",
            "Tightening pose or framing",
        ],
    ),
    SeedPolicy.PRODUCTION_CONTINUITY: SeedPolicyContract(
        policy=SeedPolicy.PRODUCTION_CONTINUITY,
        display_name="Production Continuity",
        intent="Preserve an approved look across deliverables and later generations.",
        seed_behavior="Lock the anchor seed unless a reviewed correction loop explicitly changes it.",
        reference_requirement="Required; use approved anchor references tied to the same project.",
        when_to_use=[
            "Approved character sheets",
            "Continuity-critical scene coverage",
            "Asset-library ready outputs",
        ],
    ),
}


def choose_seed_policy(*, has_approved_anchor: bool, exploration_mode: bool = False) -> SeedPolicyContract:
    if exploration_mode:
        return SEED_POLICIES[SeedPolicy.EXPLORE]
    if has_approved_anchor:
        return SEED_POLICIES[SeedPolicy.PRODUCTION_CONTINUITY]
    return SEED_POLICIES[SeedPolicy.REFINE]

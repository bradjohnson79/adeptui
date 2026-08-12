"""Creative Companion & Advisory Intelligence (additive to Conversation Core)."""

from .advisory import build_advisory_plan, transition_advisory_state
from .block import assess_creative_block
from .context import assemble_companion_context, assembler_mode_for
from .deviation import assess_story_deviation
from .lens import update_creative_lens
from .persistence import load_companion_bundle, save_companion_bundle
from .principles import extract_emerging_principles, merge_principles, profile_from_principles
from .problem_source import classify_problem_source, foundational_rewrite_likely_premature
from .return_points import maybe_capture_return_point, merge_return_points
from .schemas import (
    AdvisoryDecisionState,
    CompanionProjectBundle,
    CreativeAdvisoryPlan,
    CreativeSupportAssessment,
    CreativeWorkingState,
    CompanionNeed,
)
from .strengths import merge_strengths, propose_strength_from_principles
from .support import assess_creative_support

IDENTITY_POLICY_VERSION = "codirector-companion-identity-v1"

__all__ = [
    "IDENTITY_POLICY_VERSION",
    "AdvisoryDecisionState",
    "CompanionProjectBundle",
    "CreativeAdvisoryPlan",
    "CreativeSupportAssessment",
    "CreativeWorkingState",
    "CompanionNeed",
    "assess_creative_support",
    "assess_creative_block",
    "assess_story_deviation",
    "build_advisory_plan",
    "transition_advisory_state",
    "assemble_companion_context",
    "assembler_mode_for",
    "load_companion_bundle",
    "save_companion_bundle",
    "extract_emerging_principles",
    "merge_principles",
    "profile_from_principles",
    "classify_problem_source",
    "foundational_rewrite_likely_premature",
    "maybe_capture_return_point",
    "merge_return_points",
    "merge_strengths",
    "propose_strength_from_principles",
    "update_creative_lens",
]

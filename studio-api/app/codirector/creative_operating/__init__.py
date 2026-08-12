"""Co-Director Creative Operating Intelligence."""

from .composition import COACHING_DOCTRINE, creative_operating_prompt_block, soft_next_step_invitations
from .contracts import (
    INITIATIVE_LABELS,
    INITIATIVE_TIPS,
    CoDirectorCreativeDecision,
    CreativeCuriosityThread,
    CreativeOpening,
    CreativeOperatingBundle,
    ForwardDevelopmentSuggestion,
    ProfessionalDisagreement,
)
from .decision_loop import run_creative_decision_loop
from .persistence import load_bundle, save_bundle
from .service import (
    answer_curiosity_thread,
    apply_identity_correction,
    dismiss_forward_suggestion,
    get_creative_operating,
    process_creative_operating_turn,
    set_initiative_level,
)

__all__ = [
    "COACHING_DOCTRINE",
    "INITIATIVE_LABELS",
    "INITIATIVE_TIPS",
    "CoDirectorCreativeDecision",
    "CreativeCuriosityThread",
    "CreativeOpening",
    "CreativeOperatingBundle",
    "ForwardDevelopmentSuggestion",
    "ProfessionalDisagreement",
    "answer_curiosity_thread",
    "apply_identity_correction",
    "creative_operating_prompt_block",
    "dismiss_forward_suggestion",
    "get_creative_operating",
    "load_bundle",
    "process_creative_operating_turn",
    "run_creative_decision_loop",
    "save_bundle",
    "set_initiative_level",
    "soft_next_step_invitations",
]

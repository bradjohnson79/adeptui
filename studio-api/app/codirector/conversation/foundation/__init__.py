"""Foundational AI intelligence layer for Conversation Core (Part A)."""

from .schemas import (
    CoDirectorInferenceTrace,
    CoDirectorMode,
    CoDirectorPersonality,
    ConversationState,
    DialoguePlan,
    IntentAnalysis,
    IntentType,
    InteractionPosture,
    ResponseGroundingCheck,
)
from .intent import analyze_intent
from .dialogue_policy import build_dialogue_plan
from .grounding import evaluate_grounding, reply_violates_dialogue_plan
from .context_assembler import assemble_listening_context
from .personality import default_personality
from .response_generation import (
    build_generation_messages,
    deterministic_listening_fallback,
    SYSTEM_PROMPT_VERSION,
)

__all__ = [
    "CoDirectorInferenceTrace",
    "CoDirectorMode",
    "CoDirectorPersonality",
    "ConversationState",
    "DialoguePlan",
    "IntentAnalysis",
    "IntentType",
    "InteractionPosture",
    "ResponseGroundingCheck",
    "analyze_intent",
    "build_dialogue_plan",
    "evaluate_grounding",
    "reply_violates_dialogue_plan",
    "assemble_listening_context",
    "default_personality",
    "build_generation_messages",
    "deterministic_listening_fallback",
    "SYSTEM_PROMPT_VERSION",
]

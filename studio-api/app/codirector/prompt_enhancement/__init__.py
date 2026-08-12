"""Compatibility alias for Prompt Intelligence (legacy plan name)."""

from ..prompt_intelligence import (
    PromptIntelligenceRecord,
    PromptIntelligenceRequest,
    PromptIntelligenceResult,
    analyze_only,
    enhance,
    list_profiles,
    resolve_profile,
)

__all__ = [
    "PromptIntelligenceRecord",
    "PromptIntelligenceRequest",
    "PromptIntelligenceResult",
    "analyze_only",
    "enhance",
    "list_profiles",
    "resolve_profile",
]

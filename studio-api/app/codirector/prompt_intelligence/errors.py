"""Typed Prompt Intelligence error codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


PROMPT_ENHANCEMENT_FAILED = "PROMPT_ENHANCEMENT_FAILED"
PROVIDER_PROFILE_MISSING = "PROVIDER_PROFILE_MISSING"
UNSUPPORTED_LANGUAGE_STRATEGY = "UNSUPPORTED_LANGUAGE_STRATEGY"
PROMPT_TOO_LONG = "PROMPT_TOO_LONG"
LOCKED_TERM_CORRUPTED = "LOCKED_TERM_CORRUPTED"
FINAL_PROMPT_EMPTY = "FINAL_PROMPT_EMPTY"
MANUAL_OVERRIDE_CONFLICT = "MANUAL_OVERRIDE_CONFLICT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
CERTIFICATION_REFUSED = "CERTIFICATION_REFUSED"
EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
ROLLBACK_UNAVAILABLE = "ROLLBACK_UNAVAILABLE"
SUITE_NOT_FOUND = "SUITE_NOT_FOUND"
SUITE_RUN_NOT_FOUND = "SUITE_RUN_NOT_FOUND"
REVIEW_NOT_FOUND = "REVIEW_NOT_FOUND"
FEEDBACK_OPT_IN_REQUIRED = "FEEDBACK_OPT_IN_REQUIRED"


@dataclass
class PromptIntelligenceError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    recommended_action: str = "fallback_english_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
            "recommendedAction": self.recommended_action,
        }


def english_only_fallback(
    creator_prompt: str,
    *,
    code: str = PROMPT_ENHANCEMENT_FAILED,
    message: str = "Prompt enhancement failed; using original English prompt.",
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    text = (creator_prompt or "").strip()
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "recoverable": True,
            "recommendedAction": "fallback_english_only",
        },
        "fallback": {
            "creatorPrompt": text,
            "refinedEnglishPrompt": text,
            "languageEnhancements": {},
            "finalProviderPrompt": text,
            "usedEnglishOnlyFallback": True,
        },
    }

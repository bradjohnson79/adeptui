"""Collaboration mode inference and normalization."""

from __future__ import annotations

from typing import Any, cast, get_args

from app.codirector.foundation.contracts import CollaborationMode

_MODES = set(get_args(CollaborationMode))


def normalize_collaboration_mode(value: Any, fallback: CollaborationMode = "explore") -> CollaborationMode:
    """Normalize arbitrary input into the frozen collaboration mode vocabulary."""

    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "brainstorm": "explore",
            "ideate": "explore",
            "feedback": "critique",
            "revision": "refine",
            "decision": "decide",
            "qa": "review",
            "teach_me": "teach",
            "make": "execute",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in _MODES:
            return cast(CollaborationMode, normalized)
    return fallback


def infer_mode(user_message: str, intent: Any = None) -> CollaborationMode:
    """Infer the best collaboration mode from a creator request."""

    text = " ".join([str(user_message or ""), str(getattr(intent, "primaryIntent", "") or "")]).lower()
    if any(token in text for token in ("compare", "versus", "vs", "option a", "option b")):
        return "compare"
    if any(token in text for token in ("critique", "feedback", "what is weak", "what is wrong")):
        return "critique"
    if any(token in text for token in ("decide", "choose", "pick one", "final call")):
        return "decide"
    if any(token in text for token in ("review", "check", "audit", "continuity")):
        return "review"
    if any(token in text for token in ("refine", "polish", "tighten", "revise")):
        return "refine"
    if any(token in text for token in ("teach", "explain", "why", "learn")):
        return "teach"
    if any(token in text for token in ("do it", "execute", "make", "generate", "build")):
        return "execute"
    return "explore"


__all__ = ["infer_mode", "normalize_collaboration_mode"]

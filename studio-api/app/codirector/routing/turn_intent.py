"""Turn-intent gate: production vs platform Q&A.

Internal Adept knowledge may guide routing. It must never become the
creator-facing answer on a scene-production, revision, or Retry turn.
"""

from __future__ import annotations

import re
from typing import Literal

TurnKind = Literal[
    "timeline_prepare",
    "scene_revision",
    "production_retry",
    "platform_question",
    "other",
]

PRODUCTION_KINDS = frozenset({"timeline_prepare", "scene_revision", "production_retry"})

_RETRY_RE = re.compile(
    r"\b(?:retry(?:\s+that)?|try\s+again|prepare\s+again|reprocess|"
    r"do\s+that\s+again(?!\s+but\s+with))\b",
    re.I,
)
_RETRY_ONLY_RE = re.compile(
    r"^\s*(?:retry(?:\s+that)?|try\s+again|prepare\s+again|reprocess|"
    r"do\s+that\s+again)\s*[.!]?\s*$",
    re.I,
)

_SCENE_REVISION_RE = re.compile(
    r"(?:"
    r"\b(?:change|update|adjust|tweak|revise|edit|fix)\b.+\bscene\b"
    r"|"
    r"\bmake\s+this\s+(?:one\s+)?(?:\d+(?:\.\d+)?\s*-?\s*second\s+)?scene\b"
    r"|"
    r"\b(?:one|a|this)\s+\d+(?:\.\d+)?\s*-?\s*second\s+(?:continuous\s+)?scene\b"
    r"|"
    r"\bscene\s+so\b"
    r"|"
    r"\b(?:no|without)\s+(?:background\s+)?soldiers\b"
    r")",
    re.I,
)

_QUOTED_RE = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")
_SPEAKER_LINE_RE = re.compile(
    r"(?:^|\n)\s*[A-Z][A-Za-z0-9'’ .-]{0,40}:\s*[\"“].+?[\"”]",
    re.S,
)

_PLATFORM_QUESTION_RE = re.compile(
    r"(?is)"
    r"^\s*(what|what's|whats|which|who|how|is|can|does|do)\b"
    r"|[?]"
    r"|\bvs\.?\b|\bversus\b"
    r"|\bcompared to\b"
)


def strip_quoted_dialogue(text: str) -> str:
    """Remove quoted dialogue so '?' inside a line is not a platform question."""
    cleaned = _QUOTED_RE.sub(" ", text or "")
    cleaned = _SPEAKER_LINE_RE.sub(" ", cleaned)
    return cleaned


def is_production_turn(kind: str) -> bool:
    return kind in PRODUCTION_KINDS


def is_production_retry(message: str) -> bool:
    return bool(_RETRY_RE.search(message or ""))


def classify_turn_intent(
    message: str,
    *,
    workspace: str | None = None,
    has_active_production: bool = False,
) -> TurnKind:
    text = (message or "").strip()
    if not text:
        return "other"

    if has_active_production and (_RETRY_ONLY_RE.search(text) or _RETRY_RE.search(text)):
        return "production_retry"

    from .generation_authority import (
        classify_generation_authority,
        is_timeline_scene_prepare_request,
    )

    authority = classify_generation_authority(text, workspace=workspace)
    if authority is not None and str(getattr(authority, "owner", "") or "") == "timeline":
        return "timeline_prepare"
    if is_timeline_scene_prepare_request(text):
        return "timeline_prepare"

    if _SCENE_REVISION_RE.search(text):
        return "scene_revision"

    if has_active_production:
        try:
            from ..production.intent_parser import is_follow_up_edit

            if is_follow_up_edit(text):
                return "scene_revision"
        except Exception:
            pass

    residual = strip_quoted_dialogue(text)
    if _PLATFORM_QUESTION_RE.search(residual) and not _SCENE_REVISION_RE.search(residual):
        return "platform_question"
    return "other"


def has_active_scene_production(db, project_id: str) -> bool:
    if not project_id:
        return False
    try:
        from ..production.orchestrator import load_active_production

        active = load_active_production(db, project_id)
        return bool(active.get("shotId"))
    except Exception:
        return False

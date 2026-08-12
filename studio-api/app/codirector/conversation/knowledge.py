"""Knowledge application rules for project conversation memory."""

from __future__ import annotations

import re

from .schemas import ProjectIntelligenceSnapshot, WikiCandidate

_QUESTION_RE = re.compile(r"^(what|why|how|when|where|who|which|should|could|would|can|do|does|did|is|are)\b")
_COMMAND_RE = re.compile(
    r"^(please\s+)?(create|make|build|generate|open|go to|navigate|show|start|run|save|approve|delete|rename|update|set)\b"
)
_SPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").strip().lower())


def _is_question(text: str) -> bool:
    cleaned = _clean(text)
    if cleaned.endswith("?"):
        return True
    # Imperatives like "Do not define..." are corrections/rejections, not questions.
    if re.match(r"^do\s+not\b", cleaned) or re.match(r"^don't\b", cleaned):
        return False
    return bool(_QUESTION_RE.match(cleaned))


def _is_residue(text: str) -> bool:
    cleaned = _clean(text)
    if not cleaned:
        return True
    if _is_question(cleaned):
        return True
    if _COMMAND_RE.match(cleaned) and len(cleaned) < 80:
        return True
    return False


def _match_entry(entries: list[WikiCandidate], text: str) -> WikiCandidate | None:
    normalized = _clean(text)
    for entry in entries:
        existing = _clean(entry.text)
        if not existing:
            continue
        if normalized == existing or normalized in existing or existing in normalized:
            return entry
    return None


def apply_wiki_candidates(
    snapshot: ProjectIntelligenceSnapshot,
    candidates: list[WikiCandidate],
    user_message: str,
) -> ProjectIntelligenceSnapshot:
    """Apply conversation wiki candidates with simple supersede and reject lifecycles.

    Phase CK — Wiki user-authority law:
    Only candidates with state="confirmed" or "rejected" are persisted.
    State="proposed" from generic conversation is NEVER persisted — it was meant
    for the Knowledge Card review flow, not as canonical Wiki data.
    Generic conversation (onboarding, questions, suggestions) must not become
    Wiki truth. Only explicit user save/approve/correction actions can.
    """

    updated = snapshot.model_copy(deep=True)
    if _is_question(user_message):
        return updated

    for candidate in candidates:
        if _is_question(candidate.text) or not candidate.text.strip():
            continue
        # Phase CK — only persist confirmed/rejected, skip proposed from conversation
        if candidate.state not in ("confirmed", "rejected"):
            continue

        matched = _match_entry(updated.knowledgeEntries, candidate.text)

        if candidate.state == "rejected":
            if matched and matched.state in {"proposed", "approved", "reference-only"}:
                matched.state = "rejected"
            continue

        if candidate.supersedes_id:
            for entry in updated.knowledgeEntries:
                if entry.id == candidate.supersedes_id:
                    entry.state = "superseded"
                    break
        elif candidate.state == "confirmed" and matched and matched.id != candidate.id:
            matched.state = "superseded"

        if _is_residue(candidate.text):
            continue

        if matched and matched.state == candidate.state and _clean(matched.text) == _clean(candidate.text):
            continue

        if matched and candidate.state == "confirmed":
            matched.state = "superseded"

        updated.knowledgeEntries.append(candidate.model_copy(deep=True))

    return updated

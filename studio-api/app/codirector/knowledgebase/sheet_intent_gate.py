"""Explicit ERS/CRS/PRS sheet-knowledge intent gate.

Sheet curriculum (ers-law, ers-spec, character-identity) may enter Co-Director
chat retrieve ONLY when the user names a formal sheet product, or the call
already has a *_reference_sheet purpose.

Ordinary background / timeline / visual-reference creative intent must NOT
activate sheet curriculum. Negated sheet refusals ("Do NOT make an ERS") must
NOT activate either. Generation paths that set purpose remain unaffected.
"""

from __future__ import annotations

import re

# Formal sheet lecture docs surfaced by chat retrieve.
SHEET_FORMAL_CURRICULUM_IDS: frozenset[str] = frozenset(
    {
        "ers-law",
        "ers-spec",
        "character-identity",
    }
)

_SHEET_PURPOSES: frozenset[str] = frozenset(
    {
        "environment_reference_sheet",
        "character_reference_sheet",
        "prop_reference_sheet",
    }
)

_SHEET_PRODUCT = (
    r"ers|crs|prs|"
    r"environment\s+reference\s+sheet|"
    r"environment\s+sheet|"
    r"production\s+ers|"
    r"character\s+reference\s+sheet|"
    r"character\s+sheet|"
    r"prop\s+reference\s+sheet|"
    r"prop\s+sheet|"
    r"reference\s+sheet"
)

# Formal sheet product language (ERS/CRS/PRS or long-form equivalents).
_SHEET_PRODUCT_RE = re.compile(rf"(?ix)\b(?:{_SHEET_PRODUCT})\b")

# Negated sheet refusals — strip these spans before deciding.
# Requires a refusal cue + sheet action (or no/without + sheet product).
_NEGATED_SHEET_RE = re.compile(
    rf"(?ix)"
    rf"(?:"
    rf"\b(?:do\s*n['\u2019]?t|dont|do\s+not|never|avoid|skip|refuse)\b"
    rf"\s+(?:make|create|generate|build|compile|validate|run|start|use)\s+"
    rf"(?:an?\s+|the\s+|any\s+)?"
    rf"(?:{_SHEET_PRODUCT})\b"
    rf"|"
    rf"\b(?:no|without|not)\s+(?:making\s+|creating\s+|generating\s+)?"
    rf"(?:an?\s+|the\s+|any\s+)?"
    rf"(?:{_SHEET_PRODUCT})\b"
    rf")"
)


def is_explicit_sheet_knowledge_intent(
    message: str | None,
    *,
    purpose: str | None = None,
) -> bool:
    """True only for affirmative sheet create/validate/ask — or sheet purpose."""
    purpose_l = str(purpose or "").strip().lower()
    if purpose_l in _SHEET_PURPOSES or purpose_l.endswith("_reference_sheet"):
        return True

    text = str(message or "").strip()
    if not text:
        return False

    # Drop negated refusals, then require a remaining affirmative sheet mention.
    residual = _NEGATED_SHEET_RE.sub(" ", text)
    return bool(_SHEET_PRODUCT_RE.search(residual))


def allow_sheet_curriculum_doc(
    doc_id: str,
    message: str | None,
    *,
    purpose: str | None = None,
) -> bool:
    """Whether a formal sheet curriculum doc may be retrieved for this turn."""
    if doc_id not in SHEET_FORMAL_CURRICULUM_IDS:
        return True
    return is_explicit_sheet_knowledge_intent(message, purpose=purpose)
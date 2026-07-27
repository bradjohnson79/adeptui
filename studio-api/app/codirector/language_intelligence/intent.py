"""Semantic creative-intent normalization (preserve original text)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .registry import resolve_locale


class NormalizedCreativeIntent(BaseModel):
    sourceLanguage: str = "en"
    originalText: str = ""
    normalizedIntent: dict[str, Any] = Field(default_factory=dict)
    protectedTerms: list[str] = Field(default_factory=list)
    translationNotes: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


def normalize_creative_intent(
    text: str,
    *,
    source_language: Optional[str] = None,
    protected_terms: Optional[list[str]] = None,
    must_include: Optional[list[str]] = None,
    must_avoid: Optional[list[str]] = None,
) -> NormalizedCreativeIntent:
    src = resolve_locale(source_language)
    original = text or ""
    subjects: list[str] = []
    for term in protected_terms or []:
        if term and term in original:
            subjects.append(term)

    return NormalizedCreativeIntent(
        sourceLanguage=src,
        originalText=original,
        normalizedIntent={
            "subjects": subjects,
            "action": {},
            "environment": {},
            "cinematography": {},
            "performance": {},
            "audioIntent": {},
            "mustInclude": list(must_include or []),
            "mustAvoid": list(must_avoid or []),
            "summary": original.strip()[:2000],
        },
        protectedTerms=list(protected_terms or []),
        translationNotes=[],
        ambiguities=[],
    )

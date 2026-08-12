"""Response evidence scoring — tone alone is never enough."""

from __future__ import annotations

import re

from .schemas import ResponseEvidence, ResponseEvidenceSlot

_INTRIGUE = re.compile(
    r"\b(stands out|compelling|distinctive|especially|what (?:immediately )?matters|"
    r"creative potential|emotional (?:center|engine|hook)|cinematic)\b",
    re.I,
)
_REFLECT = re.compile(
    r"\b(you(?:'|’)re describing|that tension|thematic|theme|feeling|intimacy|"
    r"consequence|reflect|i(?:'|’)m hearing|holds|tracking)\b",
    re.I,
)
_WIKI = re.compile(
    r"\b(document(?:ing|ed)?|captured|wiki|added|noted|recording|living brief|"
    r"\d+\s+(?:confirmed|character|timeline|fact))\b",
    re.I,
)
_QUESTION = re.compile(r"\?")
_PROJECT_Q = re.compile(
    r"\b(when you(?:'|’)re ready|curious about|want to understand|how does|"
    r"what happens|who is|where does)\b",
    re.I,
)
_RESEARCH = re.compile(
    r"\b(compar(?:e|able|ison)|research|similar works|references?|film history|"
    r"anti-?reference|look into)\b",
    re.I,
)


def score_response_evidence(reply: str, *, wiki_summary: str = "", discovery_question: str = "") -> ResponseEvidence:
    text = reply or ""
    hits: list[ResponseEvidenceSlot] = []
    notes: list[str] = []

    if _INTRIGUE.search(text):
        hits.append(ResponseEvidenceSlot.INTRIGUE)
    else:
        notes.append("missing_intrigue")

    if _REFLECT.search(text):
        hits.append(ResponseEvidenceSlot.REFLECTION)
    else:
        notes.append("missing_reflection")

    if _WIKI.search(text) or (wiki_summary and len(wiki_summary) >= 8):
        hits.append(ResponseEvidenceSlot.WIKI_SUMMARY)
    else:
        notes.append("missing_wiki_summary")

    if discovery_question or (_QUESTION.search(text) and _PROJECT_Q.search(text)):
        hits.append(ResponseEvidenceSlot.DISCOVERY_QUESTION)
    else:
        notes.append("missing_discovery_question")

    if _RESEARCH.search(text):
        hits.append(ResponseEvidenceSlot.RESEARCH_OPPORTUNITY)
    else:
        notes.append("missing_research_opportunity")

    # Deduplicate while preserving order
    seen: set[ResponseEvidenceSlot] = set()
    ordered: list[ResponseEvidenceSlot] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            ordered.append(h)

    count = len(ordered)
    return ResponseEvidence(
        slots_hit=ordered,
        count=count,
        required_minimum=2,
        ok=count >= 2,
        notes=notes,
    )

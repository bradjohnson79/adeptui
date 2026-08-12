"""Facts vs interpretations vs possibilities — canon safety."""

from __future__ import annotations

import re

from .contracts import KnowledgeKind, StructuredKnowledge


def classify_knowledge_kind(statement: str, *, creator_asserted: bool = False) -> KnowledgeKind:
    lower = (statement or "").lower()
    if creator_asserted and not re.search(r"\b(maybe|might|could|perhaps|possibly|what if)\b", lower):
        return "CONFIRMED_FACT"
    if re.search(r"\b(maybe|might|could|perhaps|possibility|what if|exploratory)\b", lower):
        return "POSSIBILITY"
    if re.search(r"\b(seems|suggests|implies|appears|reading|interpretation)\b", lower):
        return "INTERPRETATION"
    if creator_asserted:
        return "CONFIRMED_FACT"
    return "INTERPRETATION"


def build_knowledge(
    statement: str,
    *,
    creator_asserted: bool = False,
    evidence: str | None = None,
    source_id: str | None = None,
) -> StructuredKnowledge:
    kind = classify_knowledge_kind(statement, creator_asserted=creator_asserted)
    canon = {
        "CONFIRMED_FACT": "CONFIRMED",
        "INTERPRETATION": "INFERRED",
        "POSSIBILITY": "EXPLORATORY",
    }[kind]
    return StructuredKnowledge(
        statement=statement.strip()[:400],
        kind=kind,  # type: ignore[arg-type]
        evidence=evidence,
        canonState=canon,  # type: ignore[arg-type]
        confidence=0.85 if kind == "CONFIRMED_FACT" else (0.55 if kind == "INTERPRETATION" else 0.35),
        sourceIds=[source_id] if source_id else [],
    )


def assert_not_promoted_to_canon(items: list[StructuredKnowledge]) -> list[StructuredKnowledge]:
    """Ensure speculative items never carry CONFIRMED/LOCKED without approval path."""
    out: list[StructuredKnowledge] = []
    for item in items:
        if item.kind in {"INTERPRETATION", "POSSIBILITY"} and item.canonState in {"CONFIRMED", "LOCKED"}:
            item = item.model_copy(
                update={"canonState": "INFERRED" if item.kind == "INTERPRETATION" else "EXPLORATORY"}
            )
        out.append(item)
    return out


def separation_prompt_block(items: list[StructuredKnowledge]) -> str:
    if not items:
        return ""
    confirmed = [i.statement for i in items if i.kind == "CONFIRMED_FACT"][:2]
    interpretations = [i.statement for i in items if i.kind == "INTERPRETATION"][:2]
    possibilities = [i.statement for i in items if i.kind == "POSSIBILITY"][:2]
    lines = ["Knowledge separation (do not promote speculative to canon):"]
    if confirmed:
        lines.append("- Confirmed: " + "; ".join(confirmed))
    if interpretations:
        lines.append("- Interpretation: " + "; ".join(interpretations))
    if possibilities:
        lines.append("- Possibility: " + "; ".join(possibilities))
    return "\n".join(lines)

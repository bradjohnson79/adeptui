"""Creative intrigue assessment — specific, evidence-based, non-flattering."""

from __future__ import annotations

import re

from .schemas import CreativeIntrigueAssessment, IntrigueLevel

_GENERIC_BAN = re.compile(
    r"\b(amazing|groundbreaking|genius|brilliant|revolutionary|best ever)\b",
    re.I,
)


def assess_intrigue(user_message: str) -> CreativeIntrigueAssessment:
    text = (user_message or "").strip()
    if len(text) < 40:
        return CreativeIntrigueAssessment(confidence=0.2, intrigue_level=IntrigueLevel.EMERGING)

    spans: list[str] = []
    distinctive: list[str] = []
    emotional: list[str] = []
    cinematic: list[str] = []
    thematic: list[str] = []
    questions: list[str] = []

    # Sentence-like clauses as evidence candidates
    clauses = [c.strip() for c in re.split(r"[.!?\n]+", text) if len(c.strip()) >= 24]
    for clause in clauses[:6]:
        spans.append(clause[:160])
        lowered = clause.lower()
        if any(k in lowered for k in ("feel", "heart", "love", "fear", "grief", "hope", "memory", "emotion")):
            emotional.append(clause[:140])
        if any(k in lowered for k in ("light", "camera", "shot", "scene", "harbor", "night", "visual", "image")):
            cinematic.append(clause[:140])
        if any(k in lowered for k in ("theme", "about", "means", "identity", "truth", "consequence")):
            thematic.append(clause[:140])
        if any(k in lowered for k in ("unusual", "strange", "never", "secret", "two versions", "entity", "myth", "lantern")):
            distinctive.append(clause[:140])

    if not distinctive and clauses:
        distinctive.append(clauses[0][:140])
    if not emotional and clauses:
        # Prefer later emotional-ish clause or fallback first
        emotional.append(clauses[min(1, len(clauses) - 1)][:140])

    if distinctive:
        questions.append(f"What makes “{distinctive[0][:60]}…” carry the emotional center?")
    if cinematic:
        questions.append("Which visual rule should stay consistent as the story grows?")

    level = IntrigueLevel.EMERGING
    score = 0.35 + 0.08 * min(len(spans), 5)
    if len(distinctive) + len(emotional) >= 3:
        level = IntrigueLevel.STRONG
        score = min(0.85, score + 0.2)
    if len(text) > 400 and len(distinctive) >= 2 and emotional:
        level = IntrigueLevel.EXCEPTIONAL
        score = min(0.92, score + 0.1)

    return CreativeIntrigueAssessment(
        distinctive_elements=distinctive[:4],
        emotional_hooks=emotional[:4],
        cinematic_hooks=cinematic[:4],
        thematic_potential=thematic[:4],
        audience_promise=[],
        originality_signals=distinctive[:2],
        unanswered_creative_questions=questions[:3],
        intrigue_level=level,
        evidence_spans=spans[:6],
        confidence=round(score, 2),
    )


def intrigue_guidance(assessment: CreativeIntrigueAssessment) -> str:
    if not assessment.evidence_spans:
        return "Intrigue: listen for distinctive, cinematic, and emotional hooks; avoid generic praise."
    hook = assessment.distinctive_elements[0] if assessment.distinctive_elements else assessment.evidence_spans[0]
    why = assessment.emotional_hooks[0] if assessment.emotional_hooks else "it creates a clear human stake"
    return (
        "Intrigue guidance (expression only):\n"
        f"- Lead with a specific compelling element grounded in user material, e.g. focus on: {hook[:120]}\n"
        f"- Explain why it matters creatively (grounded): {why[:120]}\n"
        f"- Intrigue level: {assessment.intrigue_level.value}; confidence={assessment.confidence:.2f}\n"
        "- Never use unsupported genius/groundbreaking praise.\n"
        f"- Banned tone check patterns: {_GENERIC_BAN.pattern}"
    )

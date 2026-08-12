"""Five internal minds — decision lenses, never creator-facing personalities."""

from __future__ import annotations

import re
from typing import Any

from .contracts import CreativeStage, InitiativeLevel, UserNeed


def _word_count(text: str) -> int:
    return len((text or "").split())


def interpret_user_need(user_message: str) -> UserNeed:
    lower = (user_message or "").lower()
    if re.search(r"\b(actually|correction|correct|merge|not separate|wrong|rename|fix that)\b", lower):
        return "CORRECTION"
    if re.search(r"\b(critique|honest feedback|what.?s weak|tighten|pacing problem)\b", lower):
        return "CRITIQUE"
    if re.search(r"\b(generate|render|execute|place on timeline|run|build the asset)\b", lower):
        return "EXECUTION"
    if re.search(r"\b(schedule|budget|shot list|call sheet|production plan|breakdown)\b", lower):
        return "PRODUCTION"
    if re.search(r"\b(research|look up|find references|comparables)\b", lower):
        return "RESEARCH"
    if re.search(
        r"\b(develop|outline|treatment|what should happen next|help me (?:shape|think|develop)|next episode|next installment)\b",
        lower,
    ):
        return "DEVELOPMENT"
    if re.search(r"\b(encourage|does this work|is this interesting|am i onto something)\b", lower):
        return "ENCOURAGEMENT"
    # Long flowing narrative → listen
    if _word_count(user_message) >= 40 and not re.search(r"\?", user_message):
        return "LISTEN"
    if re.search(r"\?$", (user_message or "").strip()):
        return "DEVELOPMENT"
    return "LISTEN"


def map_creative_stage(discovery_stage: str | None, word_count: int, need: UserNeed) -> CreativeStage:
    stage = (discovery_stage or "").upper()
    mapping = {
        "EMERGENCE": "EMERGING",
        "EXPLORATION": "FORMING",
        "FORMATION": "STRUCTURING",
        "EVALUATION": "REFINING",
        "PRODUCTION": "PRODUCING",
    }
    mapped = mapping.get(stage)
    if mapped:
        if need == "CRITIQUE" and mapped in {"EMERGING", "FORMING"}:
            return "REFINING"
        if need == "PRODUCTION":
            return "PRODUCING"
        return mapped  # type: ignore[return-value]
    if word_count < 30:
        return "EMERGING"
    if word_count < 80:
        return "FORMING"
    if need in {"PRODUCTION", "EXECUTION"}:
        return "PRODUCING"
    if need == "CRITIQUE":
        return "REFINING"
    return "STRUCTURING"


def evaluate_minds(
    *,
    user_message: str,
    user_need: UserNeed,
    creative_stage: CreativeStage,
    initiative: InitiativeLevel,
    project_format: str,
    has_conflicts: bool = False,
) -> dict[str, str]:
    """Return compact internal notes from five minds (never spoken raw)."""
    flowing = user_need == "LISTEN" and _word_count(user_message) >= 40
    companion = (
        "Protect momentum; listen only; no questionnaire."
        if flowing or initiative == "QUIET_PARTNER"
        else "Offer partnership without taking authorship."
    )
    if user_need == "ENCOURAGEMENT":
        companion = "Creator seeks specific encouragement — evidence over flattery."

    storyteller = "Notice distinctive emotional core and emerging conflict."
    if creative_stage in {"EMERGING", "FORMING"}:
        storyteller = "Protect discovery; highlight what is compelling; avoid heavy critique."
    elif creative_stage in {"REFINING", "LOCKING"}:
        storyteller = "Analyze structure, motivation, and scene purpose carefully."

    bible = "Classify new knowledge; separate confirmed from speculative; avoid transcript dump."
    if user_need == "CORRECTION":
        bible = "Creator correction has high authority; prepare structural merge/reclassify preview."

    producer = "Stay one development unit ahead; no franchise overplanning."
    if creative_stage in {"EMERGING", "FORMING"}:
        producer = "No production pressure; organization only."
    elif creative_stage == "PRODUCING":
        producer = "Prioritize assets, dependencies, continuity, and delivery."

    guardian = "Protect tone, identity, and locked canon."
    if has_conflicts:
        guardian = "Continuity or vision risk detected — advise gently before following change."

    return {
        "companion": companion,
        "storyteller": storyteller,
        "projectBibleSteward": bible,
        "producer": f"{producer} Format={project_format}.",
        "guardianOfTheVision": guardian,
    }


def listening_only(*, user_need: UserNeed, initiative: InitiativeLevel, user_message: str) -> bool:
    if initiative == "QUIET_PARTNER" and user_need == "LISTEN":
        return True
    if user_need == "LISTEN" and _word_count(user_message) >= 35 and "?" not in (user_message or ""):
        return True
    return False


def extract_insight_seeds(user_message: str) -> list[str]:
    """Lightweight distinctive-observation seeds (not fixture-specific)."""
    text = (user_message or "").strip()
    if len(text) < 40:
        return []
    seeds: list[str] = []
    # Capture short clauses that sound like creative claims.
    for match in re.finditer(
        r"\b([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,3})\b",
        text,
    ):
        name = match.group(1).strip()
        if name.lower() in {"the", "this", "that", "when", "after", "before"}:
            continue
        if len(name) >= 3:
            seeds.append(name)
        if len(seeds) >= 3:
            break
    # Emotional / thematic markers
    for pattern, label in (
        (r"\b(memory|evidence|truth|testimony)\b", "memory and contested truth"),
        (r"\b(quiet|whisper|listen|conversation)\b", "quiet conversational intensity"),
        (r"\b(identity|alias|cover|true name)\b", "identity and revelation"),
        (r"\b(found(?:er|ing)|organization|agency)\b", "institutional origin story"),
    ):
        if re.search(pattern, text, re.I):
            seeds.append(label)
    # Dedup preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in seeds:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:5]


def extract_open_questions(user_message: str) -> list[str]:
    """Detect unanswered dimensions without inventing fixture lore."""
    lower = (user_message or "").lower()
    questions: list[str] = []
    if re.search(r"\b(character|protagonist|lead)\b", lower) and not re.search(
        r"\b(want|motive|why|because)\b", lower
    ):
        questions.append("What does this character want most deeply right now?")
    if re.search(r"\b(relationship|together|partner)\b", lower) and not re.search(
        r"\b(history|met|when they)\b", lower
    ):
        questions.append("What shared history shapes this relationship?")
    if re.search(r"\b(location|place|set|room)\b", lower) and not re.search(
        r"\b(looks|sounds|light|atmosphere)\b", lower
    ):
        questions.append("How should this place look and sound on screen?")
    if re.search(r"\b(rule|world|system)\b", lower) and not re.search(r"\b(consequence|cost|if)\b", lower):
        questions.append("What consequence follows when this world rule is broken?")
    return questions[:3]

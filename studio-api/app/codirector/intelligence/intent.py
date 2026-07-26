"""Heuristic intent classifier for Co-Director M2.4."""

from __future__ import annotations

import re
from typing import Optional

from .schemas import IntentClassification, IntentKind

_SIMPLE_QA_PATTERNS = (
    re.compile(r"^(what|who|where|when|why|how|which|can you explain|tell me about)\b", re.I),
    re.compile(r"^(is|are|do|does|did|will|would|should)\b", re.I),
    re.compile(r"\?$"),
)

_INTENT_RULES: tuple[tuple[re.Pattern[str], IntentKind, str], ...] = (
    (re.compile(r"\b(create|recommend|prepare).*\b(storyboard|two-shot|shot)\b", re.I), "create_storyboard", "storyboard"),
    (re.compile(r"\b(storyboard|board shot|next shot)\b", re.I), "create_storyboard", "storyboard"),
    (re.compile(r"\b(revise|rewrite)\b.*\bdialogue\b", re.I), "revise_dialogue", "dialogue"),
    (re.compile(r"\bmake\b.*\bdialogue\b.*\b(sarcastic|emotional|funny|sharper)\b", re.I), "revise_dialogue", "dialogue"),
    (re.compile(r"\bplan\b.*\b(conversation|scene|blocking|coverage|corridor)\b", re.I), "plan_scene", "scene plan"),
    (re.compile(r"\bplan (the |this )?scene\b", re.I), "plan_scene", "scene plan"),
    (re.compile(r"\b(stage|blocking|coverage)\b", re.I), "plan_scene", "scene staging"),
    (re.compile(r"\bdesign (a |the )?location\b", re.I), "design_location", "location"),
    (re.compile(r"\b(action sequence|fight scene|choreograph)\b", re.I), "plan_scene", "action"),
    (re.compile(r"\b(prepare|generate).*\b(storyboard )?image\b", re.I), "prepare_image_generation", "image"),
    (re.compile(r"\b(prepare|generate).*\bvideo\b", re.I), "prepare_video_generation", "video"),
    (re.compile(r"\b(review|check).*\b(asset|render|result|image|video)\b", re.I), "review_asset", "review"),
    (re.compile(r"\b(shot list|create shots)\b", re.I), "create_shot_list", "shot list"),
    (re.compile(r"\b(write|draft).*\bscene\b", re.I), "write_scene", "write scene"),
    (re.compile(r"\b(outline|story structure)\b", re.I), "write_story", "story"),
    (re.compile(r"\b(concept|logline|premise)\b", re.I), "develop_concept", "concept"),
    (re.compile(r"\b(character|build character)\b", re.I), "create_character", "character"),
    (re.compile(r"\b(change|update).*\b(eye color|locked|bible|canon|character)\b", re.I), "update_production_bible", "bible"),
    (re.compile(r"\b(update|change).*\b(bible|canon|character)\b", re.I), "update_production_bible", "bible"),
    (re.compile(r"\b(assemble|sequence|edit)\b", re.I), "assemble_sequence", "edit"),
    (re.compile(r"\b(cinematic|look more cinematic)\b", re.I), "plan_scene", "cinematic"),
    (
        re.compile(
            r"\b(sound design|sfx|foley|ambience|audio cues?)\b",
            re.I,
        ),
        "plan_audio",
        "sound",
    ),
    (
        re.compile(r"\b(music cue|score|soundtrack|music supervisor)\b", re.I),
        "plan_audio",
        "music",
    ),
    (
        re.compile(
            r"\b(production intelligence|co-?director pipeline|orchestrat(e|ion)|full production plan)\b",
            re.I,
        ),
        "production_intelligence",
        "m211",
    ),
    (
        re.compile(
            r"\b(create a .*(scene|laboratory|scientists)|suspenseful .*scene)\b",
            re.I,
        ),
        "production_intelligence",
        "scene brief",
    ),
)


def _looks_simple_question(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 220:
        return False
    if any(pattern.search(stripped) for pattern in _SIMPLE_QA_PATTERNS):
        if not any(
            keyword in stripped.lower()
            for keyword in ("storyboard", "generate", "create the", "plan the", "design", "revise dialogue")
        ):
            return True
    return False


def classify_intent(
    user_message: str,
    *,
    scene_id: Optional[str] = None,
    mode: str = "chat",
) -> IntentClassification:
    text = (user_message or "").strip()
    lowered = text.lower()
    reasons: list[str] = []
    primary: IntentKind = "unknown"
    playbook_id: str | None = None

    for pattern, intent, reason in _INTENT_RULES:
        if pattern.search(text):
            primary = intent
            reasons.append(reason)
            break

    if primary == "unknown" and _looks_simple_question(text):
        primary = "answer_question"
        reasons.append("simple question heuristic")

    if primary == "create_storyboard":
        playbook_id = "create-storyboard-shot"
    elif primary == "revise_dialogue":
        playbook_id = "revise-dialogue"
    elif primary == "plan_scene":
        playbook_id = "plan-scene"
    elif primary == "design_location":
        playbook_id = "design-location"
    elif primary == "prepare_image_generation":
        playbook_id = "prepare-image-generation"
    elif primary == "prepare_video_generation":
        playbook_id = "prepare-video-generation"
    elif primary == "review_asset":
        playbook_id = "review-visual-result"
    elif primary == "production_intelligence":
        playbook_id = "plan-scene"
    elif primary == "plan_audio":
        playbook_id = "plan-scene"

    complexity: str = "standard"
    if primary == "answer_question":
        complexity = "simple"
    elif primary in (
        "create_storyboard",
        "prepare_video_generation",
        "assemble_sequence",
        "production_intelligence",
    ):
        complexity = "complex"

    requires_approval = primary in {
        "create_storyboard",
        "prepare_image_generation",
        "prepare_video_generation",
        "update_production_bible",
        "execute_project_action",
    }

    is_simple = primary == "answer_question" and _looks_simple_question(text)
    if mode == "setup":
        primary = "plan_scene"
        playbook_id = "plan-scene"
        is_simple = False
        complexity = "standard"
        reasons.append("setup mode nudge")

    if not text:
        return IntentClassification(
            primaryIntent="unknown",
            needsClarification=True,
            clarificationQuestion="What would you like to work on in this project?",
            confidence=0.2,
            reasons=["empty message"],
        )

    return IntentClassification(
        primaryIntent=primary,
        productionStage="production" if primary in ("create_storyboard", "prepare_image_generation", "prepare_video_generation") else "preproduction",
        playbookId=playbook_id,
        targetSceneId=scene_id,
        complexity=complexity,  # type: ignore[arg-type]
        requiresApproval=requires_approval,
        isSimpleQuestion=is_simple,
        confidence=0.85 if primary != "unknown" else 0.45,
        reasons=reasons or ["default classification"],
    )

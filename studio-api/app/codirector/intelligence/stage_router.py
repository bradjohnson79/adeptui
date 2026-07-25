"""Map classified intents to production stages."""

from __future__ import annotations

from .schemas import IntentClassification, IntentKind, ProductionStage

_INTENT_STAGE: dict[IntentKind, ProductionStage] = {
    "answer_question": "project_management",
    "develop_concept": "development",
    "write_story": "writing",
    "revise_story": "writing",
    "create_character": "preproduction",
    "revise_character": "preproduction",
    "design_location": "preproduction",
    "plan_scene": "preproduction",
    "write_scene": "writing",
    "revise_dialogue": "writing",
    "create_shot_list": "preproduction",
    "create_storyboard": "production",
    "prepare_image_generation": "production",
    "prepare_video_generation": "production",
    "review_asset": "postproduction",
    "review_continuity": "postproduction",
    "assemble_sequence": "postproduction",
    "plan_audio": "postproduction",
    "plan_vfx": "postproduction",
    "manage_production": "project_management",
    "update_production_bible": "project_management",
    "execute_project_action": "production",
    "unknown": "project_management",
}


def route_stage(intent: IntentClassification) -> ProductionStage:
    return _INTENT_STAGE.get(intent.primaryIntent, "project_management")

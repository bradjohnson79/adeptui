"""Shot planner for storyboard generation.

Spec §33: "For N requested frames: generate N distinct shot concepts.
Not N random variations of the same composition."

Shot planning considers: scene action, dialogue, emotional beat, characters,
location, continuity, cinematic coverage, user instructions.

Uses the preserved storyboard_studio shot intelligence (framing, coverage,
timing) — does NOT reimplement it.

Framing vocabulary (spec §33): establishing, wide, medium, close-up,
extreme close-up, OTS, POV, insert, reaction, low angle, high angle, tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShotConcept:
    """One planned shot/frame for a storyboard."""

    index: int
    framing: str = "medium"
    shot_size: str = ""
    composition: str = ""
    prompt_fragment: str = ""
    character_ids: list[str] = field(default_factory=list)
    character_names: list[str] = field(default_factory=list)
    location: str = ""
    action_beat: str = ""
    dialogue_hint: str = ""
    emotional_beat: str = ""
    duration_estimate: float = 3.0


# Framing vocabulary from spec §33 — ordered for cinematic coverage.
_FRAMING_SEQUENCE = [
    "establishing",
    "medium",
    "close-up",
    "OTS",
    "reaction",
    "insert",
    "wide",
    "extreme close-up",
    "POV",
    "tracking",
    "low angle",
    "high angle",
]

# Composition templates per framing.
_COMPOSITION_TEMPLATES = {
    "establishing": "wide establishing shot of {location}, establishing the scene and spatial context",
    "medium": "medium shot of {characters} {action}",
    "close-up": "close-up of {primary_character}, {emotional_beat}",
    "OTS": "over-the-shoulder shot behind {primary_character} looking at {secondary_character}",
    "reaction": "reaction shot of {primary_character} responding to {action_beat}",
    "insert": "insert shot of {action_beat} detail",
    "wide": "wide shot of {location} with {characters}",
    "extreme close-up": "extreme close-up of {primary_character}'s {detail}",
    "POV": "point-of-view shot from {primary_character}'s perspective of {action_beat}",
    "tracking": "tracking shot following {primary_character} {action}",
    "low angle": "low angle shot of {primary_character}, {emotional_beat}",
    "high angle": "high angle shot of {location} with {characters}",
}


def plan_shots(
    scene_context: dict[str, Any] | None,
    character_refs: list[dict[str, Any]] | None,
    count: int,
    *,
    user_instructions: str = "",
    project_style: str = "",
) -> list[ShotConcept]:
    """Plan N distinct shots for a storyboard.

    Not N random variations — N distinct cinematic compositions with varied
    framing, each serving a narrative purpose.

    Args:
        scene_context: dict with scene_number, action, dialogue, location, emotional_beat
        character_refs: list of {id, name} for characters in the scene
        count: number of frames requested
        user_instructions: any specific shot requests from the user
        project_style: visual style hint
    """
    scene = scene_context or {}
    chars = character_refs or []
    count = max(1, min(count, 12))

    location = scene.get("location", "the scene")
    action = scene.get("action", scene.get("action_beat", "the action"))
    emotional_beat = scene.get("emotional_beat", "")
    dialogue = scene.get("dialogue", "")

    primary = chars[0] if chars else {}
    secondary = chars[1] if len(chars) > 1 else {}

    primary_name = primary.get("name", "the character")
    secondary_name = secondary.get("name", "the other character")
    char_names = [c.get("name", "") for c in chars if c.get("name")]

    shots: list[ShotConcept] = []

    for i in range(count):
        framing = _FRAMING_SEQUENCE[i % len(_FRAMING_SEQUENCE)]

        composition = _COMPOSITION_TEMPLATES.get(framing, "shot of {characters} {action}")
        composition = composition.format(
            location=location,
            characters=", ".join(char_names) or "the characters",
            action=action,
            primary_character=primary_name,
            secondary_character=secondary_name,
            emotional_beat=emotional_beat or "expressing the scene's emotion",
            action_beat=action,
            detail="eyes" if framing == "extreme close-up" else "expression",
        )

        # If user specified instructions, incorporate them.
        if user_instructions and i == 0:
            composition = f"{user_instructions}. {composition}"

        prompt_fragment = composition
        if project_style:
            prompt_fragment = f"{project_style} style. {composition}"

        shots.append(ShotConcept(
            index=i,
            framing=framing,
            shot_size=framing,
            composition=composition,
            prompt_fragment=prompt_fragment,
            character_ids=[c.get("id", "") for c in chars],
            character_names=char_names,
            location=location,
            action_beat=action,
            dialogue_hint=dialogue[:200] if dialogue else "",
            emotional_beat=emotional_beat,
            duration_estimate=3.0 + (i % 3),
        ))

    return shots


def shots_to_prompt_metadata(shots: list[ShotConcept]) -> list[dict[str, Any]]:
    """Convert ShotConcepts to the metadata dicts for ExecutionStep/ChildJobView."""
    return [
        {
            "framing": s.framing,
            "shot_size": s.shot_size,
            "composition": s.composition,
            "prompt_fragment": s.prompt_fragment,
            "character_ids": s.character_ids,
            "character_names": s.character_names,
            "location": s.location,
            "action_beat": s.action_beat,
            "emotional_beat": s.emotional_beat,
            "duration_estimate": s.duration_estimate,
            "label": f"Frame {s.index + 1} — {s.framing.title()}",
        }
        for s in shots
    ]


def plan_four_panel_storyboard_sheets(
    scene_context: dict[str, Any] | None,
    character_refs: list[dict[str, Any]],
    count: int = 4,
    user_instructions: str = "",
    project_style: str = "",
) -> list[dict[str, Any]]:
    """Plan N four-panel storyboard sheet outputs.

    Each output represents ONE generated image containing 4 storyboard panels
    arranged as a 2x2 grid. N outputs = N GPU jobs = N*4 panels total.

    Returns a list of dicts, each representing one output image containing
    4 storyboard panels in a 2x2 grid. Each dict has:
    - output_index: int
    - output_type: "four_panel_storyboard"
    - panels: list[ShotConcept] (4 panels per output)
    - compiled_prompt: str (single prompt requesting 4 panels in one image)
    - framing_slots: list[str] (4 framings, one per panel)
    """
    scene = scene_context or {}
    chars = character_refs or []
    count = max(1, min(count, 8))

    location = scene.get("location", "the scene")
    action = scene.get("action", scene.get("action_beat", "the action"))
    emotional_beat = scene.get("emotional_beat", "")
    dialogue = scene.get("dialogue", "")

    primary = chars[0] if chars else {}
    secondary = chars[1] if len(chars) > 1 else {}

    primary_name = primary.get("name", "the character")
    secondary_name = secondary.get("name", "the other character")
    char_names = [c.get("name", "") for c in chars if c.get("name")]
    char_ids = [c.get("id", "") for c in chars]

    panel_framings = ["establishing", "medium", "close-up", "reaction"]
    position_labels = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"]

    sheets: list[dict[str, Any]] = []

    for output_idx in range(count):
        panels: list[ShotConcept] = []

        for panel_idx, framing in enumerate(panel_framings):
            composition = _COMPOSITION_TEMPLATES.get(framing, "shot of {characters} {action}")
            composition = composition.format(
                location=location,
                characters=", ".join(char_names) or "the characters",
                action=action,
                primary_character=primary_name,
                secondary_character=secondary_name,
                emotional_beat=emotional_beat or "expressing the scene's emotion",
                action_beat=action,
                detail="eyes" if framing == "extreme close-up" else "expression",
            )

            panel = ShotConcept(
                index=panel_idx,
                framing=framing,
                shot_size=framing,
                composition=composition,
                prompt_fragment=composition,
                character_ids=char_ids,
                character_names=char_names,
                location=location,
                action_beat=action,
                dialogue_hint=dialogue[:200] if dialogue else "",
                emotional_beat=emotional_beat,
                duration_estimate=3.0,
            )
            panels.append(panel)

        panel_descriptions: list[str] = []
        for panel_idx, panel in enumerate(panels):
            panel_descriptions.append(
                f"Panel {panel_idx + 1} ({position_labels[panel_idx]}, "
                f"{panel.framing.title()}): {panel.composition}"
            )

        char_line = ", ".join(char_names) if char_names else (primary_name or "the character")
        location_line = location

        compiled_prompt = (
            f"Generate a single image containing exactly four distinct storyboard "
            f"panels arranged as a 2x2 grid layout, creating one cohesive storyboard "
            f"sheet. All panels share the same environment ({location_line}) "
            f"and feature the same character(s): {char_line}."
        )
        for pd in panel_descriptions:
            compiled_prompt += f"\n\n{pd}"
        compiled_prompt += (
            f"\n\nMaintain consistent character appearance, same {location_line} "
            f"environment, cohesive color palette, and clear panel borders throughout."
        )
        if project_style:
            compiled_prompt += f" Style: {project_style}."
        if user_instructions:
            compiled_prompt += f" Additional instructions: {user_instructions}"

        sheets.append({
            "output_index": output_idx,
            "output_type": "four_panel_storyboard",
            "panels": panels,
            "compiled_prompt": compiled_prompt,
            "framing_slots": list(panel_framings),
        })

    return sheets

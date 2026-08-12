"""Creative state machine heuristics for creator conversations."""

from __future__ import annotations

STAGES_IN_ORDER: list[str] = [
    "Project Creation",
    "Vision",
    "World Building",
    "Characters",
    "Episode Structure",
    "Scenes",
    "Dialogue",
    "Production Planning",
    "Generation",
    "Editing",
    "Final Delivery",
]

DEFAULT_SUBSTATES: dict[str, str | None] = {
    "Project Creation": "Naming",
    "Vision": "Premise",
    "World Building": "Lore",
    "Characters": "Lead Character",
    "Episode Structure": "Season Arc",
    "Scenes": "Scene Goals",
    "Dialogue": None,
    "Production Planning": None,
    "Generation": None,
    "Editing": None,
    "Final Delivery": None,
}

STAGE_SUBSTATES: dict[str, list[str]] = {
    "Vision": ["Premise", "Tone", "Format"],
    "World Building": ["Lore", "Setting", "Rules"],
    "Characters": ["Lead Character", "Supporting Cast", "Antagonists", "Relationships"],
    "Episode Structure": ["Season Arc", "Episode Beats", "Sequence Order"],
    "Scenes": ["Scene Goals", "Scene Beats", "Transitions"],
}


def _clean(text: str) -> str:
    return " ".join((text or "").lower().split())


def _normalized_stage(stage: str | None) -> str:
    if stage in STAGES_IN_ORDER:
        return stage
    return "Project Creation"


def _normalized_substate(stage: str, substate: str | None) -> str | None:
    allowed = STAGE_SUBSTATES.get(stage)
    if not allowed:
        return None
    if substate in allowed:
        return substate
    return DEFAULT_SUBSTATES.get(stage)


def _matches_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _infer_target(text: str) -> tuple[str | None, str | None]:
    if _matches_any(text, ("main character", "lead character")):
        return "Characters", "Lead Character"

    if _matches_any(text, ("supporting cast", "side character", "supporting character")):
        return "Characters", "Supporting Cast"

    if _matches_any(text, ("antagonist", "villain")):
        return "Characters", "Antagonists"

    if _matches_any(text, ("relationship", "dynamic between", "chemistry between")):
        return "Characters", "Relationships"

    if _matches_any(text, ("let me explain the lore", "explain the lore", "worldbuilding", "world building")):
        return "World Building", "Lore"

    if _matches_any(text, (" lore ", " setting ", " mythology", " kingdom", " planet", " city ", " world ")):
        return "World Building", "Lore"

    if _matches_any(text, ("title", "name the project", "call this project")):
        return "Project Creation", "Naming"

    if _matches_any(text, ("premise", "tone", "genre", "format", "series", "season objective")):
        return "Vision", "Premise"

    if _matches_any(text, ("episode arc", "season arc", "episode structure", "story beats")):
        return "Episode Structure", "Season Arc"

    if _matches_any(text, ("scene", "cold open", "beat sheet", "scene beats")):
        return "Scenes", "Scene Goals"

    if _matches_any(text, ("dialogue", "line reading", "what would they say")):
        return "Dialogue", None

    if _matches_any(text, ("shoot plan", "production plan", "schedule", "budget", "pipeline")):
        return "Production Planning", None

    if _matches_any(text, ("generate", "render", "image pass", "video pass")):
        return "Generation", None

    if _matches_any(text, ("edit", "trim", "cut together", "revise the cut")):
        return "Editing", None

    if _matches_any(text, ("deliver", "export", "final file", "handoff")):
        return "Final Delivery", None

    return None, None


def update_creative_state(
    current_stage: str | None,
    current_substate: str | None,
    user_message: str,
) -> tuple[str, str | None, bool]:
    """Return the updated creative stage, substate, and whether it changed."""

    stage = _normalized_stage(current_stage)
    substate = _normalized_substate(stage, current_substate)
    text = f" {_clean(user_message)} "

    if not text.strip():
        default_substate = DEFAULT_SUBSTATES.get(stage)
        return stage, default_substate if substate is None else substate, False

    if _matches_any(
        text,
        (
            "what should we do next",
            "what should we define next",
            "what do we do next",
            "what do we define next",
            "what should we do now",
            "best next three steps",
            "next three steps",
        ),
    ):
        final_substate = substate if substate is not None else DEFAULT_SUBSTATES.get(stage)
        return stage, final_substate, False

    inferred_stage, inferred_substate = _infer_target(text)
    if inferred_stage is None:
        if current_stage is None:
            return "Project Creation", "Naming", True
        final_substate = substate if substate is not None else DEFAULT_SUBSTATES.get(stage)
        return stage, final_substate, False

    new_stage = inferred_stage
    new_substate = _normalized_substate(new_stage, inferred_substate)
    changed = new_stage != stage or new_substate != substate
    return new_stage, new_substate, changed

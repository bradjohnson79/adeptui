from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

LearningCategory = Literal[
    "prompts",
    "camera",
    "pacing",
    "engines",
    "continuity",
    "render",
    "dialogue",
    "motion",
    "genre",
    "profiles",
    "storyboard",
    "spatial",
    "coverage",
    "script_structure",
]

ALL_CATEGORIES: tuple[LearningCategory, ...] = (
    "prompts",
    "camera",
    "pacing",
    "engines",
    "continuity",
    "render",
    "dialogue",
    "motion",
    "genre",
    "profiles",
    "storyboard",
    "spatial",
    "coverage",
    "script_structure",
)


class LearnedItem(BaseModel):
    id: str
    category: LearningCategory
    text: str
    enabled: bool = True


class LearningState(BaseModel):
    enabled: dict[str, bool] = Field(
        default_factory=lambda: {c: True for c in ALL_CATEGORIES}
    )
    items: list[LearnedItem] = Field(default_factory=list)
    dismissed_continuity: list[str] = Field(default_factory=list)


def default_learning() -> LearningState:
    return LearningState()


def parse_learning(raw: str | None, enabled_raw: str | None = None) -> LearningState:
    state = default_learning()
    if raw and str(raw).strip():
        try:
            data = json.loads(raw)
            state = LearningState.model_validate(data)
        except Exception:
            pass
    if enabled_raw and str(enabled_raw).strip():
        try:
            en = json.loads(enabled_raw)
            if isinstance(en, dict):
                state.enabled = {**state.enabled, **{str(k): bool(v) for k, v in en.items()}}
        except Exception:
            pass
    return state


def dumps_learning(state: LearningState) -> tuple[str, str]:
    return state.model_dump_json(), json.dumps(state.enabled)


def learning_context_block(state: LearningState) -> str:
    lines = []
    for item in state.items:
        if not item.enabled:
            continue
        if not state.enabled.get(item.category, True):
            continue
        lines.append(f"- [{item.category}] {item.text}")
    if not lines:
        return ""
    return "Project learning preferences (user-approved):\n" + "\n".join(lines)


def continuity_suggestions(scenes: list[Any], dismissed: list[str]) -> list[dict[str, Any]]:
    """Heuristic continuity suggestions between adjacent scenes."""
    out: list[dict[str, Any]] = []
    ordered = sorted(scenes, key=lambda s: getattr(s, "index", 0))
    for i in range(1, len(ordered)):
        a, b = ordered[i - 1], ordered[i]
        sid = f"{a.id}->{b.id}"
        if sid in dismissed:
            continue
        # lighting / time cues from camera_note + prompt
        a_text = f"{getattr(a, 'camera_note', '')} {getattr(a, 'prompt', '')}".lower()
        b_text = f"{getattr(b, 'camera_note', '')} {getattr(b, 'prompt', '')}".lower()
        for word in ("night", "day", "dusk", "dawn", "rain", "snow"):
            if word in a_text and word not in b_text and word not in ("",):
                out.append(
                    {
                        "id": f"{sid}:tod:{word}",
                        "kind": "time_of_day",
                        "message": f"Scene “{a.name}” mentions {word}; “{b.name}” does not — check continuity.",
                        "scene_a": a.id,
                        "scene_b": b.id,
                    }
                )
                break
        # wardrobe lock mismatch via continuity_json
        try:
            ca = json.loads(getattr(a, "continuity_json", "") or "{}")
            cb = json.loads(getattr(b, "continuity_json", "") or "{}")
            if ca.get("wardrobe") == "locked" and cb.get("wardrobe") == "unlocked":
                out.append(
                    {
                        "id": f"{sid}:wardrobe",
                        "kind": "wardrobe",
                        "message": f"Wardrobe locked in “{a.name}” but unlocked in “{b.name}”.",
                        "scene_a": a.id,
                        "scene_b": b.id,
                    }
                )
        except Exception:
            pass
    return out[:20]

"""Mini Production Prompt Compiler — deterministic production prompt.

Input: a compiled CameraShotPacket (facts are LOCKED).
Output: the generator prompt. Co-Director may format and creatively enrich;
it may not change packet facts.

Rule:
    DETERMINISTIC PRODUCTION FACTS -> LOCKED
    CREATIVE PRESENTATION          -> FLEXIBLE

Shot size is framing language only. Changing Wide -> Close-Up never
authorizes camera relocation; the model adjusts scale, framing, crop and
composition within the canonical camera geography.
"""

from __future__ import annotations

from typing import Any

from .camera_shot_packet import CameraShotPacket

_GENERATOR_PRESENTATION: dict[str, str] = {
    "qwen2512": (
        "Documentary still photograph, natural lens perspective, "
        "clean production photography."
    ),
    "gpt-image-2": (
        "Photorealistic cinematic still, natural lens perspective, "
        "clean production photography."
    ),
}

_FRAME_LANGUAGE = {
    "wide": (
        "Shot size: WIDE — the room and its major fixtures dominate the frame; "
        "the subject is small within the environment but must remain present."
    ),
    "medium_wide": (
        "Shot size: MEDIUM WIDE — the subject is clearly visible from head to "
        "mid-thigh with generous environment context."
    ),
    "medium": (
        "Shot size: MEDIUM — the subject is framed from the waist up; "
        "the environment remains clearly readable around them."
    ),
    "medium_close": (
        "Shot size: MEDIUM CLOSE — the subject is framed from the chest up; "
        "the environment is present but secondary."
    ),
    "close_up": (
        "Shot size: CLOSE UP — the subject's face and shoulders dominate the frame; "
        "enough environment remains to prove the location."
    ),
    "extreme_close": (
        "Shot size: EXTREME CLOSE — a tight detail on the subject's face or "
        "feature, environment visible only as background texture."
    ),
}


def shot_size_framing_line(shot_size: str) -> str:
    key = str(shot_size or "auto").strip().lower()
    if key in _FRAME_LANGUAGE:
        return _FRAME_LANGUAGE[key]
    return ""


def compile_production_prompt(
    packet: CameraShotPacket | dict[str, Any],
    *,
    generator: str = "gpt-image-2",
    aspect: str = "16:9",
    variation: str = "A",
) -> str:
    """Compile the deterministic production prompt for one Mini variation."""
    if isinstance(packet, dict):
        packet = CameraShotPacket.model_validate(packet)

    cam = packet.camera
    label = cam.label or "Camera"
    presentation = _GENERATOR_PRESENTATION.get(
        str(generator or "").strip().lower(), _GENERATOR_PRESENTATION["gpt-image-2"]
    )
    lines: list[str] = [
        f"Still photograph from Spatial Map camera {label}.",
        f"OUTPUT: {presentation}",
        "OUTPUT: one continuous photographic still filling the entire frame.",
        "Do not draw an Environment Reference Sheet, contact sheet, storyboard, map, grid, camera glyphs, C1-C4 labels, checklists, or any multi-panel layout.",
        "If the reference image is a sheet or a titled panel, use it only for place identity. Photograph the room from this camera.",
        "CAMERA PLACEMENT IS CANONICAL. Do not relocate the camera, rotate the room, or mirror the environment.",
        "NORTH LOCK: NORTH. Same grid as the Spatial Map.",
        f"Frame size: {aspect}.",
    ]

    # LOCKED production facts (character presence, placement locks, shot size,
    # camera geography, anti-substitution rules).
    locked = list(packet.lockedFacts or [])
    seen: set[str] = set()
    for fact in locked:
        key = fact.strip()
        if key and key not in seen:
            seen.add(key)
            lines.append(key)

    # Shot-size framing language (never camera relocation).
    framing = shot_size_framing_line(cam.shotSize)
    if framing:
        lines.append(framing)

    # Camera relational facts (region plant, facing, FOV, ahead/behind notes).
    for fact in cam.relationalFacts or []:
        key = fact.strip()
        if key and key not in seen:
            seen.add(key)
            lines.append(key)

    # Scene intent (creative context from saved production state).
    intent = packet.sceneIntent
    if (intent.summary or "").strip():
        lines.append(f"Scene: {intent.summary.strip()}")
    if (intent.productionIntent or "").strip():
        lines.append(f"Intent: {intent.productionIntent.strip()}")
    if (intent.userSceneDirection or "").strip():
        lines.append(f"Direction: {intent.userSceneDirection.strip()}")
    for constraint in intent.continuityConstraints or []:
        if str(constraint).strip():
            lines.append(f"Continuity: {constraint.strip()}")

    if variation == "A":
        lines.append(
            "Variation A: natural micro-expression and modest framing within this exact camera geography."
        )
    else:
        lines.append(
            "Variation B: alternate pose nuance and lighting within this exact camera geography. "
            "Do not change camera position, region, or facing. "
            "Do not substitute a lounge-forward or entrance-forward composition."
        )
    lines.append("Do not invent architecture, move major fixtures, or change character locations.")
    return "\n".join(line for line in lines if line)

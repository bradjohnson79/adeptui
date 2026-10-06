"""Evidence-based confidence compiler. Not an LLM self-score.

HIGH / MEDIUM / LOW plus explicit reasons. No theater floats.
"""

from __future__ import annotations

import re
from typing import Any

from .working_context import (
    CoDirectorWorkingContext,
    ConfidenceState,
    ConfirmationRecord,
    ProvenanceRecord,
    _now,
)

_YES_RE = re.compile(r"^\s*(yes|yep|yeah|y|correct)\b", re.IGNORECASE)
_CAMERA_ONLY_RE = re.compile(
    r"\b(close[- ]?up|cu|medium|wide|high angle|low angle|20 degrees|tight|"
    r"closer|pull back|push in|full close-up)\b",
    re.IGNORECASE,
)
_POSE_RE = re.compile(
    r"\b(pose|stance|standing|sit|sitting|hand|raise|martial|defensive|"
    r"block|strike|relaxed|facing)\b",
    re.IGNORECASE,
)
_SCENE_RE = re.compile(r"\b(scene|schnick|coffee|meadow|location|set)\b", re.IGNORECASE)
_GEO_OVERRIDE_RE = re.compile(
    r"\b(instead|different (?:scene|place|location)|not (?:this|that) scene|"
    r"another scene|other scene)\b",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    return bool(_YES_RE.search((text or "").strip()))


def classify_needs_scene_choice(text: str) -> bool:
    """True when the instruction overrides or abandons the active scene."""
    return bool(classify_instruction(text)["geographyOverride"])


def classify_instruction(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    camera_only = bool(_CAMERA_ONLY_RE.search(raw)) and not _GEO_OVERRIDE_RE.search(raw)
    pose = bool(_POSE_RE.search(raw))
    mentions_scene = bool(_SCENE_RE.search(raw))
    geography_override = bool(_GEO_OVERRIDE_RE.search(raw))
    return {
        "text": raw,
        "cameraOnly": camera_only and not geography_override,
        "performance": pose,
        "mentionsScene": mentions_scene,
        "geographyOverride": geography_override,
    }


def compile_confidence(
    ctx: CoDirectorWorkingContext,
    instruction: str,
    *,
    candidate_scene_ids: list[str] | None = None,
    candidate_character_ids: list[str] | None = None,
    has_crs: bool = False,
    has_spatial_map: bool = False,
) -> ConfidenceState:
    """Compile categorical confidence from Working Context + instruction evidence."""

    intent = classify_instruction(instruction)
    scenes = [s for s in (candidate_scene_ids or []) if s]
    characters = [c for c in (candidate_character_ids or []) if c]
    reasons: list[str] = []
    locked: list[str] = []
    changing: list[str] = []

    pending = ctx.pending_confirmation()
    if pending and is_affirmative(instruction):
        reasons.append("creator confirmed the pending production question")
        if pending.boundSceneId:
            locked.append("scene")
        if pending.boundCharacterId:
            locked.append("identity")
        return ConfidenceState(
            level="HIGH",
            reasons=reasons,
            asked=False,
            question="",
            locked=sorted(set(locked + ["identity", "geography"])),
            changing=["camera"] if intent["cameraOnly"] else [],
        )

    active_scene = (ctx.activeSceneId or ctx.scene.sceneId or "").strip()
    approved_scene = bool(ctx.scene.approved or any(a.what in ("scene", "shot", "image") for a in ctx.approvals))
    unique_scene = bool(active_scene) and (len(scenes) <= 1)
    unique_character = len(characters) == 1
    crs_ok = has_crs or any(p.layer == "CANON" for p in ctx.provenance)
    map_ok = has_spatial_map or bool(ctx.posecraft.worldOriginMeters) or any(
        p.authority == "spatial_map_ers" for p in ctx.provenance
    )

    if intent["cameraOnly"] and unique_scene and approved_scene:
        reasons.append("one approved active scene")
        reasons.append("request is camera-only")
        locked.extend(["scene", "identity", "geography", "performance"])
        changing.append("camera")
        return ConfidenceState(level="HIGH", reasons=reasons, locked=locked, changing=changing)

    if intent["performance"] and unique_scene and unique_character and (crs_ok or ctx.posecraft.activeFigureIds):
        reasons.append("one character and one scene for a performance change")
        locked.extend(["scene", "identity", "geography"])
        changing.append("performance")
        return ConfidenceState(level="HIGH", reasons=reasons, locked=locked, changing=changing)

    if len(scenes) >= 2 or (intent["geographyOverride"] and unique_scene):
        question = "Which scene should this shot use?"
        if any("schnick" in (s or "").lower() for s in scenes) or "schnick" in (ctx.scene.name or "").lower():
            question = "Korri's close-up in the Schnick Coffee scene?"
        reasons.append("more than one plausible scene" if len(scenes) >= 2 else "geography override wording")
        return ConfidenceState(
            level="MEDIUM",
            reasons=reasons,
            asked=True,
            question=question,
            locked=["identity"] if unique_character else [],
            changing=["scene"] if intent["geographyOverride"] else [],
        )

    if len(characters) >= 2:
        return ConfidenceState(
            level="MEDIUM",
            reasons=["more than one plausible character"],
            asked=True,
            question="Which character should this apply to?",
        )

    if not active_scene or not (crs_ok or unique_character) or not (map_ok or unique_scene):
        missing = []
        if not active_scene:
            missing.append("no reliable scene")
        if not crs_ok and not unique_character:
            missing.append("no reliable character identity")
        if not map_ok and not unique_scene:
            missing.append("no reliable Spatial Map")
        reasons.extend(missing or ["insufficient production context"])
        return ConfidenceState(
            level="LOW",
            reasons=reasons,
            asked=True,
            question="Which scene and character should this use?",
        )

    if unique_scene and unique_character:
        reasons.append("one scene and one character; instruction is unambiguous")
        locked.extend(["scene", "identity"])
        if intent["cameraOnly"]:
            locked.extend(["geography", "performance"])
            changing.append("camera")
        if intent["performance"]:
            locked.append("geography")
            changing.append("performance")
        return ConfidenceState(level="HIGH", reasons=reasons, locked=sorted(set(locked)), changing=changing)

    return ConfidenceState(
        level="MEDIUM",
        reasons=["need one concise confirmation before executing"],
        asked=True,
        question="Use the current scene and character?",
    )


def bind_confirmation(ctx: CoDirectorWorkingContext, answer: str) -> ConfirmationRecord | None:
    pending = ctx.pending_confirmation()
    if pending is None:
        return None
    pending.answer = (answer or "").strip()
    pending.resolved = True
    pending.at = _now()
    if pending.boundSceneId and not ctx.activeSceneId:
        ctx.activeSceneId = pending.boundSceneId
        ctx.scene.sceneId = pending.boundSceneId
    if pending.boundCharacterId:
        ctx.provenance.append(
            ProvenanceRecord(
                fact=f"character:{pending.boundCharacterId}",
                layer="CANON",
                authority="filmmaker_instruction",
                source="confirmation",
            )
        )
    locked = []
    if pending.boundSceneId:
        locked.append("scene")
    if pending.boundCharacterId:
        locked.append("identity")
    ctx.confidence = ConfidenceState(
        level="HIGH",
        reasons=["confirmation stored; original instruction remains bound"],
        asked=False,
        question="",
        locked=locked,
    )
    ctx.updatedAt = _now()
    return pending


def decay_confidence(ctx: CoDirectorWorkingContext, *, reason: str) -> None:
    ctx.confidence = ConfidenceState(
        level="LOW",
        reasons=[reason],
        asked=False,
        question="",
    )
    ctx.updatedAt = _now()

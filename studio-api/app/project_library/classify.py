"""Explainable asset classification → canonical systemKey."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .schema import Classification
from .taxonomy import (
    SUPPORTED_3D_EXTENSIONS,
    UNSUPPORTED_3D_EXTENSIONS,
    display_path_for_system_key,
)

LOW_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class ClassifyInput:
    kind: str = ""
    provider: str = ""
    role: str = ""
    tag: str = ""
    filename: str = ""
    engine: str = ""
    mime: str = ""
    hints: dict[str, Any] | None = None


def _ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def classify_asset(payload: ClassifyInput, *, classified_by: str = "auto") -> Classification:
    """Map kind/provider/role → systemKey with reason and confidence."""
    hints = payload.hints or {}
    ext = _ext(payload.filename)
    kind = (payload.kind or "").lower()
    provider = (payload.provider or "").lower()
    role = (payload.role or "").lower()
    tag = (payload.tag or "").lower()
    engine = (payload.engine or "").lower()

    # Explicit override from caller (e.g. Co-Director preflight)
    if hints.get("systemKey"):
        key = str(hints["systemKey"])
        return Classification(
            category=key.split(".")[0],
            subtype=key.split(".")[-1] if "." in key else "",
            target_folder=key,
            reason=str(hints.get("reason") or "Explicit systemKey hint"),
            confidence=float(hints.get("confidence") or 0.99),
            classified_by=classified_by,
            needs_clarification=False,
        )

    # Native 3D mesh formats are deferred to Version 1.2 (not a technical failure).
    if ext in UNSUPPORTED_3D_EXTENSIONS or ext in SUPPORTED_3D_EXTENSIONS or kind in (
        "model",
        "mesh",
        "3d",
    ):
        return Classification(
            category="three_d",
            subtype="DEFERRED_VERSION_1_2",
            target_folder="miscellaneous",
            reason=(
                "Native 3D importing and animation are planned for Adept UI Version 1.2. "
                "Version 1.1 uses 360 panoramic environments and Spatial Map production."
            ),
            confidence=0.99,
            classified_by=classified_by,
            needs_clarification=True,
        )

    # --- Audio ---
    music_signals = (
        role in ("music", "score", "soundtrack")
        or "music" in tag
        or provider in ("ace_step", "ace-step", "musicgen")
        or "music.generate" in provider
        or hints.get("audioIntent") == "music"
    )
    if kind == "audio" and music_signals:
        return _result("audio", "music", "audio.music", "Audio kind with music role/provider/tag", 0.92, classified_by)

    if kind == "audio" and role in ("sfx", "sound_effect", "sound-effect"):
        return _result("audio", "sfx", "audio.sfx", "Audio kind with SFX role", 0.9, classified_by)

    if kind == "audio" and role in ("dialogue", "speech", "voice"):
        return _result("audio", "dialogue", "audio.dialogue", "Audio kind with dialogue role", 0.9, classified_by)

    if kind == "audio" and role in ("ambience", "ambient", "atmosphere"):
        return _result("audio", "ambience", "audio.ambience", "Audio kind with ambience role", 0.88, classified_by)

    if kind == "audio" and "voice" in tag:
        return _result("audio", "voice_references", "audio.voice_references", "Audio tagged as voice reference", 0.85, classified_by)

    if kind == "audio":
        return _result(
            "audio",
            "music",
            "audio.music",
            "Generic audio asset defaulting to Music (low specificity)",
            0.55,
            classified_by,
            needs_clarification=True,
        )

    # --- Video ---
    if kind == "video":
        if role in ("lipsync", "lip_sync", "lip-sync") or "lipsync" in tag:
            return _result("video", "lipsync", "video.lipsync", "Video with lip-sync role/tag", 0.9, classified_by)
        if role in ("render", "final", "master") or engine in ("ltx", "wan"):
            if "import" in tag or hints.get("source") == "import":
                return _result("video", "imported", "video.imported", "Imported video asset", 0.88, classified_by)
            return _result("video", "generated", "video.generated", "Generated video (engine/provider)", 0.85, classified_by)
        if "import" in tag or hints.get("source") == "import":
            return _result("video", "imported", "video.imported", "Imported video", 0.82, classified_by)
        return _result("video", "generated", "video.generated", "Video asset defaulting to Generated", 0.7, classified_by)

    # HDRI / environment maps remain useful for lighting reference in Version 1.1.
    if "hdri" in tag or ext == ".hdr":
        return _result("three_d", "hdri", "three_d.hdri", "HDRI / environment map", 0.85, classified_by)

    # --- Image / storyboard / character / prop / scene ---
    if kind == "image":
        if "storyboard" in tag or role == "storyboard":
            return _result("storyboards", "storyboard", "storyboards", "Image tagged as storyboard", 0.88, classified_by)
        if "character" in tag or hints.get("entityType") == "character":
            return _result(
                "characters",
                "identity_references",
                "characters.identity_references",
                "Character reference image",
                0.86,
                classified_by,
            )
        if "prop" in tag or hints.get("entityType") == "prop":
            return _result("props", "references", "props.references", "Prop reference image", 0.84, classified_by)
        if "scene" in tag or "background" in tag or hints.get("entityType") == "scene":
            return _result("scenes", "backgrounds", "scenes.backgrounds", "Scene/background image", 0.82, classified_by)
        return _result(
            "miscellaneous",
            "image",
            "miscellaneous",
            "Image without specific production role",
            0.5,
            classified_by,
            needs_clarification=True,
        )

    if kind in ("script", "screenplay", "text") or ext in (".txt", ".md", ".fdx"):
        return _result("scripts", "document", "scripts", "Script or text document", 0.8, classified_by)

    if "export" in tag or role in ("export", "delivery"):
        if "final" in tag or role == "final":
            return _result("exports", "final", "exports.final", "Final export deliverable", 0.88, classified_by)
        return _result("exports", "drafts", "exports.drafts", "Draft export deliverable", 0.85, classified_by)

    if "bible" in tag or role == "bible":
        return _result("production_bible", "reference", "production_bible", "Production Bible linked asset", 0.82, classified_by)

    return _result(
        "miscellaneous",
        kind or "unknown",
        "miscellaneous",
        f"No strong signal for kind={kind!r}, role={role!r}, tag={tag!r}",
        0.45,
        classified_by,
        needs_clarification=True,
    )


def _result(
    category: str,
    subtype: str,
    system_key: str,
    reason: str,
    confidence: float,
    classified_by: str,
    *,
    needs_clarification: Optional[bool] = None,
) -> Classification:
    low = confidence < LOW_CONFIDENCE_THRESHOLD
    return Classification(
        category=category,
        subtype=subtype,
        target_folder=system_key,
        reason=reason,
        confidence=confidence,
        classified_by=classified_by,
        needs_clarification=low if needs_clarification is None else needs_clarification,
    )


def classification_display_path(classification: Classification) -> str:
    return display_path_for_system_key(classification.target_folder)

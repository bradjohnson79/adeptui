"""Format-aware project classification — never hardcodes fixture titles."""

from __future__ import annotations

import re

from .contracts import ProjectFormat

_FORMAT_PATTERNS: list[tuple[ProjectFormat, re.Pattern[str]]] = [
    ("EPISODIC_SERIES", re.compile(r"\b(episode|episodic|series|season|web series|tv show)\b", re.I)),
    ("DOCUMENTARY", re.compile(r"\b(documentary|interview subject|archival|non[- ]fiction)\b", re.I)),
    ("GAME", re.compile(r"\b(game|quest|npc|gameplay|mechanic|playable)\b", re.I)),
    ("NOVEL", re.compile(r"\b(novel|chapter|manuscript|point of view|pov)\b", re.I)),
    ("MUSIC_VIDEO", re.compile(r"\b(music video|choreograph|song structure|performer wardrobe)\b", re.I)),
    ("COMMERCIAL", re.compile(r"\b(commercial|brand beat|product demo|spot)\b", re.I)),
    ("PODCAST", re.compile(r"\b(podcast|audio series)\b", re.I)),
    ("THEATRE", re.compile(r"\b(theatre|theater|stage play|act one)\b", re.I)),
    ("SHORT_FILM", re.compile(r"\b(short film|short)\b", re.I)),
    ("FEATURE_FILM", re.compile(r"\b(feature film|feature|act structure|midpoint|climax)\b", re.I)),
    ("ANIMATION", re.compile(r"\b(animation|animated)\b", re.I)),
    ("EDUCATIONAL", re.compile(r"\b(educational|lesson|curriculum)\b", re.I)),
    ("EXPERIMENTAL", re.compile(r"\b(experimental)\b", re.I)),
]

_PROJECT_TYPE_MAP: dict[str, ProjectFormat] = {
    "series": "EPISODIC_SERIES",
    "web_series": "EPISODIC_SERIES",
    "tv": "EPISODIC_SERIES",
    "episodic": "EPISODIC_SERIES",
    "documentary": "DOCUMENTARY",
    "doc": "DOCUMENTARY",
    "game": "GAME",
    "interactive": "GAME",
    "novel": "NOVEL",
    "book": "NOVEL",
    "music_video": "MUSIC_VIDEO",
    "music-video": "MUSIC_VIDEO",
    "commercial": "COMMERCIAL",
    "ad": "COMMERCIAL",
    "feature": "FEATURE_FILM",
    "feature_film": "FEATURE_FILM",
    "film": "FEATURE_FILM",
    "short": "SHORT_FILM",
    "short_film": "SHORT_FILM",
    "animation": "ANIMATION",
    "podcast": "PODCAST",
    "theatre": "THEATRE",
    "theater": "THEATRE",
}


def detect_project_format(
    *,
    primary_project_type: str | None = None,
    snapshot_format: str | None = None,
    user_message: str = "",
    prior: ProjectFormat | None = None,
) -> ProjectFormat:
    for raw in (primary_project_type, snapshot_format):
        key = (raw or "").strip().lower().replace(" ", "_")
        if key in _PROJECT_TYPE_MAP:
            return _PROJECT_TYPE_MAP[key]
    text = user_message or ""
    for fmt, pattern in _FORMAT_PATTERNS:
        if pattern.search(text):
            return fmt
    if prior and prior != "UNKNOWN":
        return prior
    return "UNKNOWN"


def uses_episodes(fmt: ProjectFormat) -> bool:
    return fmt == "EPISODIC_SERIES"


def next_unit_label(fmt: ProjectFormat) -> str:
    return {
        "EPISODIC_SERIES": "next episode purpose",
        "FEATURE_FILM": "next sequence / structural turn",
        "SHORT_FILM": "next sequence",
        "DOCUMENTARY": "missing perspective or research need",
        "GAME": "next quest or mechanic dependency",
        "NOVEL": "next chapter or POV gap",
        "MUSIC_VIDEO": "next visual sequence",
        "COMMERCIAL": "missing brand beat or deliverable",
        "PODCAST": "next episode segment",
        "THEATRE": "next scene / act beat",
        "ANIMATION": "next sequence",
        "EDUCATIONAL": "next learning beat",
        "EXPERIMENTAL": "next exploratory beat",
        "UNKNOWN": "next natural development unit",
    }.get(fmt, "next natural development unit")

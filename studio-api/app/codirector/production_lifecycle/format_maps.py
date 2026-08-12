"""FORMAT_AWARE_LIFECYCLE — never assume every project is episodic fiction."""

from __future__ import annotations

FORMAT_PROFILES: dict[str, dict] = {
    "narrative_visual": {
        "requiresScriptForCasting": True,
        "requiresCastForProduction": True,
        "stages": [
            "STORY",
            "SCRIPT",
            "CASTING",
            "PRODUCTION_PLANNING",
            "PRODUCTION",
            "TIMELINE_ASSEMBLY",
            "POST_PRODUCTION",
            "FINAL_QC",
            "COMPLETE",
        ],
    },
    "documentary": {
        "requiresScriptForCasting": False,
        "requiresCastForProduction": False,
        "stages": [
            "STORY",
            "SCRIPT",
            "PRODUCTION_PLANNING",
            "PRODUCTION",
            "TIMELINE_ASSEMBLY",
            "POST_PRODUCTION",
            "FINAL_QC",
            "COMPLETE",
        ],
    },
    "music_video": {
        "requiresScriptForCasting": False,
        "requiresCastForProduction": True,
        "stages": [
            "STORY",
            "SCRIPT",
            "CASTING",
            "PRODUCTION_PLANNING",
            "PRODUCTION",
            "TIMELINE_ASSEMBLY",
            "POST_PRODUCTION",
            "FINAL_QC",
            "COMPLETE",
        ],
    },
    "commercial": {
        "requiresScriptForCasting": True,
        "requiresCastForProduction": True,
        "stages": [
            "STORY",
            "SCRIPT",
            "CASTING",
            "PRODUCTION_PLANNING",
            "PRODUCTION",
            "TIMELINE_ASSEMBLY",
            "POST_PRODUCTION",
            "FINAL_QC",
            "COMPLETE",
        ],
    },
    "game": {
        "requiresScriptForCasting": False,
        "requiresCastForProduction": False,
        "stages": [
            "STORY",
            "SCRIPT",
            "CASTING",
            "PRODUCTION_PLANNING",
            "PRODUCTION",
            "FINAL_QC",
            "COMPLETE",
        ],
    },
}


def profile_for_project_type(primary_project_type: str | None, project_format: str | None = None) -> str:
    blob = f"{primary_project_type or ''} {project_format or ''}".lower()
    if "document" in blob:
        return "documentary"
    if "music" in blob:
        return "music_video"
    if "commercial" in blob or "ad" in blob:
        return "commercial"
    if "game" in blob:
        return "game"
    return "narrative_visual"


# Creator-facing specialist roles by production stage (subordinate to Co-Director voice).
STAGE_SPECIALISTS: dict[str, list[str]] = {
    "STORY": ["Storyteller", "Story Editor", "Writer", "Producer", "Bible Steward"],
    "SCRIPT": ["Screenwriter", "Story Editor", "Script Supervisor", "Producer"],
    "CASTING": [
        "Character Designer",
        "Casting Director",
        "Costume",
        "Voice",
        "Director",
    ],
    "PRODUCTION_PLANNING": [
        "Director",
        "Production Coordinator",
        "Script Supervisor",
        "Producer",
    ],
    "PRODUCTION": [
        "Director",
        "Director of Photography",
        "Production Designer",
        "Props",
        "Costume",
        "Sound",
        "VFX",
    ],
    "TIMELINE_ASSEMBLY": ["Editor", "Producer"],
    "POST_PRODUCTION": [
        "Editor",
        "Sound",
        "Composer",
        "VFX",
        "Continuity",
        "Director",
    ],
    "FINAL_QC": ["Producer", "Director", "Script Supervisor", "Editor"],
    "COMPLETE": [],
}


def specialists_for_stage(stage: str) -> list[str]:
    return list(STAGE_SPECIALISTS.get(stage, []))

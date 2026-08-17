"""Provider-neutral cinematic color-grade presets for Image Plan compile.

Natural / unknown / missing → no extra prompt tokens.
Do not apply LUTs or CSS filters; compile a short Color grade: clause only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_PRESET_ID = "natural"


@dataclass(frozen=True)
class ColorGradePreset:
    id: str
    label: str
    instructions: tuple[str, ...]


def _p(preset_id: str, label: str, *instructions: str) -> ColorGradePreset:
    return ColorGradePreset(id=preset_id, label=label, instructions=instructions)


PRESETS: tuple[ColorGradePreset, ...] = (
    _p("natural", "Natural / None"),
    _p(
        "cinematic_neutral",
        "Cinematic Neutral",
        "balanced filmic contrast",
        "neutral midtones",
        "controlled highlights",
        "restrained saturation",
    ),
    _p(
        "teal_orange",
        "Teal & Orange",
        "cool teal shadows",
        "warm skin and highlights",
        "cinematic contrast",
        "restrained saturation",
    ),
    _p(
        "warm_hollywood",
        "Warm Hollywood",
        "warm golden midtones",
        "soft amber highlights",
        "gentle shadow lift",
        "flattering skin warmth",
    ),
    _p(
        "cool_steel",
        "Cool Steel",
        "cool steel-blue shadows",
        "crisp silver highlights",
        "lean saturation",
        "clean industrial contrast",
    ),
    _p(
        "bleach_bypass",
        "Bleach Bypass",
        "silvered highlights",
        "crushed but readable shadows",
        "desaturated color",
        "harsh contrast",
    ),
    _p(
        "filmic_contrast",
        "Filmic Contrast",
        "S-curve contrast",
        "protected skin tones",
        "deep but open shadows",
        "natural color",
    ),
    _p(
        "warm_film",
        "Warm Film",
        "warm print stock",
        "soft amber highlights",
        "gentle grain-friendly contrast",
        "slightly lifted blacks",
    ),
    _p(
        "golden_film",
        "Golden Film",
        "golden hour warmth",
        "honey midtones",
        "soft wraparound light color",
        "mild highlight roll-off",
    ),
    _p(
        "fuji_inspired",
        "Fuji-Inspired",
        "clean greens",
        "airy highlights",
        "gentle contrast",
        "natural skin",
    ),
    _p(
        "technicolor_inspired",
        "Technicolor-Inspired",
        "rich primaries",
        "deep reds and greens",
        "high but controlled saturation",
        "classic print contrast",
    ),
    _p(
        "vintage_1970s",
        "Vintage 1970s",
        "warm faded print",
        "soft contrast",
        "slightly muddy shadows",
        "period saturation",
    ),
    _p(
        "vintage_1980s",
        "Vintage 1980s",
        "slightly cyan shadows",
        "magenta-leaning highlights",
        "medium contrast",
        "era print saturation",
    ),
    _p(
        "vintage_1990s",
        "Vintage 1990s",
        "clean 90s print",
        "neutral-cool shadows",
        "moderate contrast",
        "natural saturation",
    ),
    _p(
        "noir_monochrome",
        "Noir / Monochrome",
        "black and white",
        "deep blacks",
        "hard key contrast",
        "silver midtones",
    ),
    _p(
        "silver_retention",
        "Silver Retention",
        "metallic highlights",
        "desaturated color",
        "heavy contrast",
        "cool silver shadows",
    ),
    _p(
        "high_key_commercial",
        "High-Key Commercial",
        "bright open shadows",
        "clean whites",
        "low drama contrast",
        "fresh saturation",
    ),
    _p(
        "low_key_dramatic",
        "Low-Key Dramatic",
        "deep shadows",
        "selective highlights",
        "high drama contrast",
        "muted color",
    ),
    _p(
        "golden_hour",
        "Golden Hour",
        "low-angle warm sunlight color",
        "long warm highlights",
        "soft orange rim",
        "gentle contrast",
    ),
    _p(
        "moonlight_blue",
        "Moonlight Blue",
        "cool moonlight",
        "blue-cyan shadows",
        "low key",
        "desaturated night color",
    ),
    _p(
        "neon_cyberpunk",
        "Neon Cyberpunk",
        "magenta and cyan neon",
        "deep night blacks",
        "electric highlights",
        "high saturation accents",
    ),
    _p(
        "emerald_sci_fi",
        "Emerald Sci-Fi",
        "emerald-green ambient",
        "cool teal shadows",
        "clean sci-fi contrast",
        "controlled saturation",
    ),
    _p(
        "desert_warm",
        "Desert Warm",
        "dry sand warmth",
        "hot highlights",
        "dusty midtones",
        "open contrast",
    ),
    _p(
        "arctic_cool",
        "Arctic Cool",
        "icy blue-white",
        "crisp highlights",
        "cold shadows",
        "low saturation",
    ),
    _p(
        "pastel_dream",
        "Pastel Dream",
        "soft pastel hues",
        "lifted shadows",
        "low contrast",
        "gentle saturation",
    ),
    _p(
        "muted_drama",
        "Muted Drama",
        "desaturated drama",
        "soft crushed color",
        "medium-high contrast",
        "somber midtones",
    ),
    _p(
        "rich_fantasy",
        "Rich Fantasy",
        "jewel-tone color",
        "deep saturation",
        "painterly contrast",
        "warm-cool mix",
    ),
    _p(
        "anime_cinematic",
        "Anime Cinematic",
        "clear cel color",
        "stylized contrast",
        "clean highlights",
        "cinematic grade, not a screenshot",
    ),
    _p(
        "clean_studio",
        "Clean Studio",
        "neutral studio color",
        "even lighting color",
        "low cast",
        "commercial contrast",
    ),
    _p(
        "documentary_natural",
        "Documentary Natural",
        "unlooked-after natural color",
        "modest contrast",
        "true-to-scene saturation",
        "no stylized grade",
    ),
    _p(
        "horror_cold",
        "Horror Cold",
        "sickly cool shadows",
        "drained midtones",
        "harsh contrast",
        "low warmth",
    ),
    _p(
        "romantic_warm",
        "Romantic Warm",
        "soft rose-gold warmth",
        "flattering skin",
        "gentle contrast",
        "glowing highlights",
    ),
    _p(
        "sci_fi_cyan",
        "Sci-Fi Cyan",
        "cyan-teal palette",
        "cool highlights",
        "clean contrast",
        "futuristic saturation",
    ),
    _p(
        "epic_blockbuster",
        "Epic Blockbuster",
        "wide contrast",
        "rich color",
        "warm highlights, cool shadows",
        "theatrical punch",
    ),
)

PRESETS_BY_ID: dict[str, ColorGradePreset] = {p.id: p for p in PRESETS}

LEGACY_COLOR_TREATMENT_MAP: dict[str, str] = {
    "neutral cinematic": "cinematic_neutral",
    "cinematic neutral": "cinematic_neutral",
    "teal & orange": "teal_orange",
    "teal and orange": "teal_orange",
    "teal-orange": "teal_orange",
    "desaturated drama": "muted_drama",
    "muted drama": "muted_drama",
    "warm tungsten": "warm_hollywood",
    "warm hollywood": "warm_hollywood",
    "cool steel": "cool_steel",
    "period kodachrome": "vintage_1970s",
    "noir": "noir_monochrome",
    "noir / monochrome": "noir_monochrome",
    "natural": "natural",
    "natural / none": "natural",
    "none": "natural",
}


def _norm_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def resolve_color_grade_id(
    preset_id: str | None = None,
    color_treatment: str | None = None,
) -> str:
    raw = str(preset_id or "").strip()
    if raw:
        if raw in PRESETS_BY_ID:
            return raw
        mapped = LEGACY_COLOR_TREATMENT_MAP.get(_norm_key(raw))
        if mapped:
            return mapped
    treatment = str(color_treatment or "").strip()
    if treatment:
        if treatment in PRESETS_BY_ID:
            return treatment
        mapped = LEGACY_COLOR_TREATMENT_MAP.get(_norm_key(treatment))
        if mapped:
            return mapped
    return DEFAULT_PRESET_ID


def resolve_color_grade_preset(
    preset_id: str | None = None,
    color_treatment: str | None = None,
) -> ColorGradePreset:
    return PRESETS_BY_ID[resolve_color_grade_id(preset_id, color_treatment)]


def color_grade_prompt_clause(
    preset_id: str | None = None,
    color_treatment: str | None = None,
) -> str:
    preset = resolve_color_grade_preset(preset_id, color_treatment)
    if preset.id == DEFAULT_PRESET_ID or not preset.instructions:
        return ""
    bullets = "; ".join(preset.instructions)
    return f"Color grade: {preset.label} — {bullets}"


def list_color_grades() -> list[dict[str, Any]]:
    return [
        {
            "id": p.id,
            "label": p.label,
            "instructions": list(p.instructions),
            "default": p.id == DEFAULT_PRESET_ID,
        }
        for p in PRESETS
    ]

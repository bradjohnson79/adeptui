/** Thin frontend mirror of studio-api/app/image_studio/color_grades.py */

export type ColorGradePresetId =
  | "natural"
  | "cinematic_neutral"
  | "teal_orange"
  | "warm_hollywood"
  | "cool_steel"
  | "bleach_bypass"
  | "filmic_contrast"
  | "warm_film"
  | "golden_film"
  | "fuji_inspired"
  | "technicolor_inspired"
  | "vintage_1970s"
  | "vintage_1980s"
  | "vintage_1990s"
  | "noir_monochrome"
  | "silver_retention"
  | "high_key_commercial"
  | "low_key_dramatic"
  | "golden_hour"
  | "moonlight_blue"
  | "neon_cyberpunk"
  | "emerald_sci_fi"
  | "desert_warm"
  | "arctic_cool"
  | "pastel_dream"
  | "muted_drama"
  | "rich_fantasy"
  | "anime_cinematic"
  | "clean_studio"
  | "documentary_natural"
  | "horror_cold"
  | "romantic_warm"
  | "sci_fi_cyan"
  | "epic_blockbuster";

export type ColorGradeOption = {
  id: ColorGradePresetId;
  label: string;
};

export const DEFAULT_COLOR_GRADE: ColorGradePresetId = "natural";

export const COLOR_GRADE_OPTIONS: ColorGradeOption[] = [
  { id: "natural", label: "Natural / None" },
  { id: "cinematic_neutral", label: "Cinematic Neutral" },
  { id: "teal_orange", label: "Teal & Orange" },
  { id: "warm_hollywood", label: "Warm Hollywood" },
  { id: "cool_steel", label: "Cool Steel" },
  { id: "bleach_bypass", label: "Bleach Bypass" },
  { id: "filmic_contrast", label: "Filmic Contrast" },
  { id: "warm_film", label: "Warm Film" },
  { id: "golden_film", label: "Golden Film" },
  { id: "fuji_inspired", label: "Fuji-Inspired" },
  { id: "technicolor_inspired", label: "Technicolor-Inspired" },
  { id: "vintage_1970s", label: "Vintage 1970s" },
  { id: "vintage_1980s", label: "Vintage 1980s" },
  { id: "vintage_1990s", label: "Vintage 1990s" },
  { id: "noir_monochrome", label: "Noir / Monochrome" },
  { id: "silver_retention", label: "Silver Retention" },
  { id: "high_key_commercial", label: "High-Key Commercial" },
  { id: "low_key_dramatic", label: "Low-Key Dramatic" },
  { id: "golden_hour", label: "Golden Hour" },
  { id: "moonlight_blue", label: "Moonlight Blue" },
  { id: "neon_cyberpunk", label: "Neon Cyberpunk" },
  { id: "emerald_sci_fi", label: "Emerald Sci-Fi" },
  { id: "desert_warm", label: "Desert Warm" },
  { id: "arctic_cool", label: "Arctic Cool" },
  { id: "pastel_dream", label: "Pastel Dream" },
  { id: "muted_drama", label: "Muted Drama" },
  { id: "rich_fantasy", label: "Rich Fantasy" },
  { id: "anime_cinematic", label: "Anime Cinematic" },
  { id: "clean_studio", label: "Clean Studio" },
  { id: "documentary_natural", label: "Documentary Natural" },
  { id: "horror_cold", label: "Horror Cold" },
  { id: "romantic_warm", label: "Romantic Warm" },
  { id: "sci_fi_cyan", label: "Sci-Fi Cyan" },
  { id: "epic_blockbuster", label: "Epic Blockbuster" },
];

const LEGACY_COLOR_TREATMENT: Record<string, ColorGradePresetId> = {
  "neutral cinematic": "cinematic_neutral",
  "cinematic neutral": "cinematic_neutral",
  "teal & orange": "teal_orange",
  "teal and orange": "teal_orange",
  "desaturated drama": "muted_drama",
  "warm tungsten": "warm_hollywood",
  "cool steel": "cool_steel",
  "period kodachrome": "vintage_1970s",
  noir: "noir_monochrome",
};

export function resolveColorGradeId(value?: string | null): ColorGradePresetId {
  const raw = (value || "").trim();
  if (!raw) return DEFAULT_COLOR_GRADE;
  if (COLOR_GRADE_OPTIONS.some((g) => g.id === raw)) return raw as ColorGradePresetId;
  const mapped = LEGACY_COLOR_TREATMENT[raw.toLowerCase()];
  return mapped || DEFAULT_COLOR_GRADE;
}

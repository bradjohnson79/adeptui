/** Live MAGI grade preview — CSS filter of finishing.clipGrades (preset + sliders).
 *
 * Merge order matches studio-api/app/magi/color_grading.py apply_color_grade_to_asset:
 * preset params first, then clip params (manual sliders override).
 * Live CSS covers brightness / contrast / saturation / temperature / highlights / shadows.
 * Gamma, tint, and channel mixer stay bake-only.
 */

export const MAGI_LIGHTING_PRESETS: Record<string, Record<string, number>> = {
  none: {},
  soft_bright: { brightness: 0.08, shadows: 0.06, highlights: -0.02, temperature: 0.02 },
  warm: { temperature: 0.14, highlights: 0.04, shadows: -0.02 },
  cool: { temperature: -0.14, shadows: -0.04, highlights: 0.02 },
  high_contrast: { highlights: 0.12, shadows: -0.14, contrast: 0.18 },
  low_light_lift: { brightness: 0.06, shadows: 0.14, highlights: -0.04 },
};

export type LiveGradeParams = {
  brightness?: number;
  contrast?: number;
  saturation?: number;
  temperature?: number;
};

/** Full backend COLOR_PRESETS maps (live + bake-only channels). */
export const MAGI_PRESET_PARAMS: Record<string, Record<string, number>> = {
  none: {},
  cinematic_neutral: {
    contrast: 0.15,
    saturation: 0.9,
    gamma: 0.95,
    shadows: -0.05,
    highlights: 0.03,
  },
  cinematic_warm: {
    contrast: 0.18,
    saturation: 0.95,
    gamma: 0.92,
    temperature: 0.08,
    shadows: -0.06,
    highlights: 0.04,
  },
  cinematic_cool: {
    contrast: 0.2,
    saturation: 0.85,
    gamma: 0.9,
    temperature: -0.1,
    shadows: -0.08,
    highlights: 0.02,
  },
  golden_hour: {
    contrast: 0.12,
    saturation: 1.1,
    gamma: 0.88,
    temperature: 0.15,
    tint: 0.05,
    shadows: -0.03,
    highlights: 0.08,
  },
  teal_orange: {
    contrast: 0.22,
    saturation: 0.9,
    gamma: 0.85,
    temperature: -0.05,
    shadows: -0.1,
    highlights: 0.05,
    shadow_red: -0.15,
    shadow_blue: 0.12,
    highlight_red: 0.08,
    highlight_blue: -0.05,
  },
  film_print: {
    contrast: 0.25,
    saturation: 0.8,
    gamma: 0.82,
    shadows: -0.12,
    highlights: 0.06,
    shadow_red: 0.05,
    shadow_green: -0.03,
    shadow_blue: -0.05,
    highlight_red: -0.03,
    highlight_green: 0.02,
  },
  vintage: {
    contrast: 0.15,
    saturation: 0.65,
    gamma: 0.9,
    temperature: 0.08,
    shadows: -0.05,
    highlight_red: -0.05,
    highlight_green: -0.02,
    highlight_blue: 0.08,
  },
  high_contrast: {
    contrast: 0.4,
    saturation: 1.05,
    brightness: -0.03,
    gamma: 0.8,
    shadows: -0.15,
    highlights: 0.1,
  },
  low_contrast: {
    contrast: -0.15,
    saturation: 0.85,
    brightness: 0.03,
    gamma: 1.05,
    shadows: 0.05,
    highlights: -0.03,
  },
  bleach_bypass: {
    contrast: 0.35,
    saturation: 0.5,
    gamma: 0.78,
    shadows: -0.18,
    highlights: 0.08,
    shadow_red: 0.05,
    shadow_blue: -0.05,
  },
  dreamy: {
    contrast: -0.08,
    saturation: 0.75,
    gamma: 1.08,
    brightness: 0.05,
    temperature: 0.06,
    shadows: 0.05,
    highlights: 0.05,
  },
  noir: {
    contrast: 0.3,
    saturation: -1.0,
    gamma: 0.85,
    shadows: -0.15,
    highlights: 0.1,
  },
  anime_vibrant: {
    contrast: 0.1,
    saturation: 1.3,
    brightness: 0.02,
    gamma: 0.95,
    temperature: 0.03,
  },
  muted_drama: {
    contrast: 0.2,
    saturation: 0.6,
    gamma: 0.88,
    shadows: -0.1,
    highlights: 0.03,
    shadow_blue: 0.05,
    highlight_red: -0.03,
  },
  night_moonlight: {
    contrast: 0.25,
    saturation: 0.5,
    gamma: 0.75,
    brightness: -0.1,
    temperature: -0.15,
    shadows: -0.15,
    highlights: -0.1,
  },
};

/** @deprecated Use MAGI_PRESET_PARAMS — live-only slice is derived at compose time. */
export const MAGI_LIVE_PRESET_PARAMS = MAGI_PRESET_PARAMS;

const LIVE_KEYS = new Set(["brightness", "contrast", "saturation", "temperature", "highlights", "shadows"]);

export function composeLiveGrade(
  presetId?: string | null,
  params?: Record<string, number> | null,
): Record<string, number> {
  const preset = String(presetId || "").trim();
  const base = { ...(MAGI_PRESET_PARAMS[preset] || {}) };
  for (const [key, value] of Object.entries(params || {})) {
    if (!Number.isFinite(value)) continue;
    base[key] = value;
  }
  return base;
}

export function hasLiveGrade(
  presetId?: string | null,
  params?: Record<string, number> | null,
): boolean {
  const composed = composeLiveGrade(presetId, params);
  return Object.entries(composed).some(([key, value]) => LIVE_KEYS.has(key) && Math.abs(Number(value) || 0) >= 0.001);
}

export function liveGradeCssFilter(
  params?: LiveGradeParams | Record<string, number> | null,
  presetId?: string | null,
): string {
  const composed = presetId != null || params ? composeLiveGrade(presetId, params as Record<string, number> | null) : params || {};
  const shadows = Number(composed.shadows ?? 0);
  const highlights = Number(composed.highlights ?? 0);
  const brightness = Number(composed.brightness ?? 0) + shadows * 0.35 + highlights * 0.12;
  const contrast = Number(composed.contrast ?? 0) + highlights * 0.55 - shadows * 0.2;
  const saturation = Number(composed.saturation ?? 0);
  const temperature = Number(composed.temperature ?? 0);
  if (![brightness, contrast, saturation, temperature, shadows, highlights].every((n) => Number.isFinite(n))) return "";
  if (
    Math.abs(brightness) < 0.001 &&
    Math.abs(contrast) < 0.001 &&
    Math.abs(saturation) < 0.001 &&
    Math.abs(temperature) < 0.001
  ) {
    return "";
  }
  const parts = [
    `brightness(${1 + brightness})`,
    `contrast(${1 + contrast})`,
    `saturate(${Math.max(0, 1 + saturation)})`,
  ];
  if (Math.abs(temperature) >= 0.001) {
    parts.push(`hue-rotate(${(-temperature * 28).toFixed(2)}deg)`);
  }
  return parts.join(" ");
}

export function liveGradeHasNonLiveChannels(
  params?: Record<string, number> | null,
  presetId?: string | null,
): boolean {
  const composed = composeLiveGrade(presetId, params);
  return Object.entries(composed).some(
    ([key, value]) => !LIVE_KEYS.has(key) && Math.abs(Number(value) || 0) >= 0.001,
  );
}

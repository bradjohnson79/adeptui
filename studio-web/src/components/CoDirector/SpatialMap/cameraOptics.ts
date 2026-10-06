/**
 * Camera lens, FOV, and lighting mood helpers.
 * Canonical sensor (not exposed in UI): Full Frame 36 mm horizontal.
 */

export const LENS_VALUES = [
  "auto",
  "18",
  "24",
  "28",
  "35",
  "40",
  "50",
  "65",
  "85",
  "100",
  "135",
  "fisheye",
] as const;
export type CameraLens = (typeof LENS_VALUES)[number];

export const LIGHTING_MOODS = [
  "auto",
  "daylight",
  "overcast",
  "golden_hour",
  "blue_hour",
  "twilight",
  "night",
  "moonlight",
  "interior_warm",
  "interior_cool",
  "practical_lamps",
  "candlelight",
  "high_key",
  "low_key",
  "dramatic",
  "soft_diffused",
  "hard_sun",
  "neon",
  "sci_fi",
  "fantasy",
  "horror",
] as const;
export type LightingMood = (typeof LIGHTING_MOODS)[number];

export const LIGHTING_MOOD_LABELS: Record<LightingMood, string> = {
  auto: "Auto",
  daylight: "Daylight",
  overcast: "Overcast",
  golden_hour: "Golden Hour",
  blue_hour: "Blue Hour",
  twilight: "Twilight",
  night: "Night",
  moonlight: "Moonlight",
  interior_warm: "Interior Warm",
  interior_cool: "Interior Cool",
  practical_lamps: "Practical Lamps",
  candlelight: "Candlelight",
  high_key: "High Key",
  low_key: "Low Key",
  dramatic: "Dramatic",
  soft_diffused: "Soft Diffused",
  hard_sun: "Hard Sun",
  neon: "Neon",
  sci_fi: "Sci-Fi",
  fantasy: "Fantasy",
  horror: "Horror",
};

export const FULL_FRAME_HORIZONTAL_MM = 36;

export function isFisheyeLens(value: string | number | null | undefined): boolean {
  const raw = String(value ?? "").trim().toLowerCase().replace(/[ _]/g, "-");
  return raw === "fisheye" || raw === "fish-eye";
}

export function hydrateLens(value: string | number | null | undefined): CameraLens {
  if (isFisheyeLens(value)) return "fisheye";
  const raw = String(value ?? "auto").trim().toLowerCase().replace(/mm$/, "").trim();
  if ((LENS_VALUES as readonly string[]).includes(raw)) return raw as CameraLens;
  const asInt = String(Math.round(Number(raw)));
  if ((LENS_VALUES as readonly string[]).includes(asInt)) return asInt as CameraLens;
  return "auto";
}

export function hydrateLightingMood(value: string | null | undefined): LightingMood {
  const raw = String(value ?? "auto").trim().toLowerCase().replace(/[ -]/g, "_");
  const aliased = raw === "scifi" || raw === "science_fiction" ? "sci_fi" : raw;
  return (LIGHTING_MOODS as readonly string[]).includes(aliased) ? (aliased as LightingMood) : "auto";
}

export function lightingMoodLabel(value: string | null | undefined): string {
  return LIGHTING_MOOD_LABELS[hydrateLightingMood(value)];
}

export function lensLabel(value: string | number | null | undefined): string {
  const key = hydrateLens(value);
  if (key === "auto") return "Auto";
  if (key === "fisheye") return "Fisheye";
  return `${key}mm`;
}

export function fovDegreesFromLensMm(lensMm: number, sensorMm = FULL_FRAME_HORIZONTAL_MM): number {
  const mm = Number.isFinite(lensMm) && lensMm > 0 ? lensMm : 35;
  return 2 * (Math.atan(sensorMm / 2 / mm) * (180 / Math.PI));
}

export function snapFovPreset(fovDegrees: number): "narrow" | "medium" | "wide" {
  if (fovDegrees >= 65) return "wide";
  if (fovDegrees <= 35) return "narrow";
  return "medium";
}

export function lensMmFor(lens: string, fallback = 35): number {
  const key = hydrateLens(lens);
  if (key === "auto" || key === "fisheye") return Number.isFinite(fallback) ? fallback : 35;
  return Number(key);
}

export function applyLensChange(
  lens: string,
  currentLensMm = 35,
  currentFov: "narrow" | "medium" | "wide" = "medium",
): {
  lens: CameraLens;
  lensMm: number;
  fovPreset: "narrow" | "medium" | "wide";
  fovDegrees: number | null;
} {
  const key = hydrateLens(lens);
  if (key === "auto") {
    return { lens: "auto", lensMm: currentLensMm, fovPreset: currentFov, fovDegrees: null };
  }
  if (key === "fisheye") {
    return { lens: "fisheye", lensMm: currentLensMm, fovPreset: "wide", fovDegrees: null };
  }
  const mm = Number(key);
  const fovDegrees = fovDegreesFromLensMm(mm);
  return { lens: key, lensMm: mm, fovPreset: snapFovPreset(fovDegrees), fovDegrees };
}

export function applyFovChange(fovPreset: string): {
  lens: "auto";
  fovPreset: "narrow" | "medium" | "wide";
} {
  const fov = String(fovPreset || "medium").trim().toLowerCase();
  const snapped = fov === "narrow" || fov === "wide" ? fov : "medium";
  return { lens: "auto", fovPreset: snapped };
}

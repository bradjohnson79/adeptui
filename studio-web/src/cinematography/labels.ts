/**
 * Display labels for Adept camera language IDs.
 * Seeded from Spatial Map shotSizeLabel / lensLabel / LIGHTING_MOOD_LABELS.
 * Camera modal and clip labels must import from this module only.
 */

import {
  CAMERA_FOCUS_ENVIRONMENT_ID,
  CAMERA_LENS_IDS,
  CAMERA_SHOT_IDS,
  LIGHTING_PRESET_IDS,
  type CameraLensId,
  type CameraShotId,
  type LightingPresetId,
} from "./types";

export const CAMERA_SHOT_LABELS: Record<CameraShotId, string> = {
  auto: "Auto",
  wide: "Wide",
  medium_wide: "Medium Wide",
  medium: "Medium",
  medium_close: "Medium Close",
  close_up: "Close Up",
  extreme_close: "Extreme Close",
};

export const CAMERA_LENS_LABELS: Record<CameraLensId, string> = {
  auto: "Auto",
  "18": "18mm",
  "24": "24mm",
  "28": "28mm",
  "35": "35mm",
  "40": "40mm",
  "50": "50mm",
  "65": "65mm",
  "85": "85mm",
  "100": "100mm",
  "135": "135mm",
  fisheye: "Fisheye",
};

export const LIGHTING_PRESET_LABELS: Record<LightingPresetId, string> = {
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

export function hydrateCameraShot(value: string | null | undefined): CameraShotId {
  const v = String(value || "auto").trim().toLowerCase().replace(/[ -]/g, "_");
  return (CAMERA_SHOT_IDS as readonly string[]).includes(v) ? (v as CameraShotId) : "auto";
}

export function hydrateCameraLens(value: string | number | null | undefined): CameraLensId {
  const raw = String(value ?? "auto").trim().toLowerCase().replace(/[ _]/g, "-").replace(/mm$/, "").trim();
  if (raw === "fisheye" || raw === "fish-eye") return "fisheye";
  if ((CAMERA_LENS_IDS as readonly string[]).includes(raw)) return raw as CameraLensId;
  const asInt = String(Math.round(Number(raw)));
  if ((CAMERA_LENS_IDS as readonly string[]).includes(asInt)) return asInt as CameraLensId;
  return "auto";
}

export function hydrateLightingPreset(value: string | null | undefined): LightingPresetId {
  const raw = String(value ?? "auto").trim().toLowerCase().replace(/[ -]/g, "_");
  const aliased = raw === "scifi" || raw === "science_fiction" ? "sci_fi" : raw;
  return (LIGHTING_PRESET_IDS as readonly string[]).includes(aliased)
    ? (aliased as LightingPresetId)
    : "auto";
}

export function cameraShotLabel(value: string | null | undefined): string {
  return CAMERA_SHOT_LABELS[hydrateCameraShot(value)];
}

export function cameraLensLabel(value: string | number | null | undefined): string {
  return CAMERA_LENS_LABELS[hydrateCameraLens(value)];
}

export function lightingPresetLabel(value: string | null | undefined): string {
  return LIGHTING_PRESET_LABELS[hydrateLightingPreset(value)];
}

export function cameraFocusLabel(focusId: string | null | undefined, focusName?: string | null): string {
  const id = String(focusId || "").trim();
  if (!id || id === CAMERA_FOCUS_ENVIRONMENT_ID) {
    return id === CAMERA_FOCUS_ENVIRONMENT_ID ? "Environment" : "";
  }
  const name = String(focusName || "").trim();
  if (!name) return "";
  return name.startsWith("@") ? name : `@${name.replace(/\s+/g, "")}`;
}

/**
 * Compact camera clip label: "Close Up · 50mm · @Vana · Dolly In".
 * Omits unset segments so a motion-only clip still reads as "Dolly In".
 */
export function formatCameraClipLabel(parts: {
  shotId?: string | null;
  lensId?: string | number | null;
  focusId?: string | null;
  focusName?: string | null;
  motionLabel?: string | null;
}): string {
  const chunks: string[] = [];
  if (parts.shotId && parts.shotId !== "auto") chunks.push(cameraShotLabel(parts.shotId));
  if (parts.lensId && String(parts.lensId) !== "auto") chunks.push(cameraLensLabel(parts.lensId));
  const focus = cameraFocusLabel(parts.focusId, parts.focusName);
  if (focus) chunks.push(focus);
  const motion = String(parts.motionLabel || "").trim();
  if (motion) chunks.push(motion);
  return chunks.join(" · ");
}

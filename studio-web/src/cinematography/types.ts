/**
 * Adept camera language — stable IDs only.
 *
 * Seeded from Spatial Map (copied, not imported):
 *   - SHOT_SIZES in studio-web/src/components/CoDirector/SpatialMap/types.ts
 *   - LENS_VALUES + LIGHTING_MOODS in SpatialMap/cameraOptics.ts
 *
 * Spatial Map SHOT_SIZES does not include Extreme Wide or Full. Those names
 * are not invented here.
 *
 * Do not import Spatial Map UI (SpatialMapPanel, CameraInspector, SceneCreatorMini).
 * Generation should twin these IDs when compiling camera clips.
 */

export const CAMERA_SHOT_IDS = [
  "auto",
  "wide",
  "medium_wide",
  "medium",
  "medium_close",
  "close_up",
  "extreme_close",
] as const;
export type CameraShotId = (typeof CAMERA_SHOT_IDS)[number];

export const CAMERA_LENS_IDS = [
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
export type CameraLensId = (typeof CAMERA_LENS_IDS)[number];

export const LIGHTING_PRESET_IDS = [
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
export type LightingPresetId = (typeof LIGHTING_PRESET_IDS)[number];

/** Built-in Camera Focus option. Live project characters are appended at runtime. */
export const CAMERA_FOCUS_ENVIRONMENT_ID = "environment" as const;
export type CameraFocusEnvironmentId = typeof CAMERA_FOCUS_ENVIRONMENT_ID;

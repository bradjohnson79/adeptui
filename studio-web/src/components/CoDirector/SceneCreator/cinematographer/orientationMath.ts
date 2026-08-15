/**
 * Display + command-payload math for 3D camera orientation.
 * Does not move Spatial Map grid cells — backend owns placement.
 */

export const PITCH_MIN = -60;
export const PITCH_MAX = 60;
export const ROLL_MIN = -25;
export const ROLL_MAX = 25;
export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 3;
export const DEFAULT_BASE_LENS_MM = 35;

export type AxisLocks = {
  yaw?: boolean;
  pitch?: boolean;
  roll?: boolean;
  zoom?: boolean;
};

export type SnapPresetId =
  | "front"
  | "three_quarter_left"
  | "three_quarter_right"
  | "profile_left"
  | "profile_right"
  | "rear_three_quarter_left"
  | "rear_three_quarter_right"
  | "rear"
  | "eye_level"
  | "high_angle"
  | "low_angle"
  | "birds_eye"
  | "worms_eye";

export type SnapPreset = {
  id: SnapPresetId;
  label: string;
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
};

export const SNAP_PRESETS: readonly SnapPreset[] = [
  { id: "front", label: "Front", yawDegrees: 0, pitchDegrees: 0, rollDegrees: 0 },
  { id: "three_quarter_left", label: "3/4 Left", yawDegrees: -45, pitchDegrees: 0, rollDegrees: 0 },
  { id: "three_quarter_right", label: "3/4 Right", yawDegrees: 45, pitchDegrees: 0, rollDegrees: 0 },
  { id: "profile_left", label: "Profile Left", yawDegrees: -90, pitchDegrees: 0, rollDegrees: 0 },
  { id: "profile_right", label: "Profile Right", yawDegrees: 90, pitchDegrees: 0, rollDegrees: 0 },
  { id: "rear_three_quarter_left", label: "Rear 3/4 Left", yawDegrees: -135, pitchDegrees: 0, rollDegrees: 0 },
  { id: "rear_three_quarter_right", label: "Rear 3/4 Right", yawDegrees: 135, pitchDegrees: 0, rollDegrees: 0 },
  { id: "rear", label: "Rear", yawDegrees: 180, pitchDegrees: 0, rollDegrees: 0 },
  { id: "eye_level", label: "Eye Level", yawDegrees: 0, pitchDegrees: 0, rollDegrees: 0 },
  { id: "high_angle", label: "High Angle", yawDegrees: 0, pitchDegrees: -30, rollDegrees: 0 },
  { id: "low_angle", label: "Low Angle", yawDegrees: 0, pitchDegrees: 30, rollDegrees: 0 },
  { id: "birds_eye", label: "Bird's Eye", yawDegrees: 0, pitchDegrees: -60, rollDegrees: 0 },
  { id: "worms_eye", label: "Worm's Eye", yawDegrees: 0, pitchDegrees: 60, rollDegrees: 0 },
];

function finiteOr(value: number, fallback: number): number {
  return Number.isFinite(value) ? value : fallback;
}

/** Wrap yaw into (-180, 180]. */
export function wrapYaw(degrees: number): number {
  let yaw = finiteOr(degrees, 0) % 360;
  if (yaw > 180) yaw -= 360;
  if (yaw <= -180) yaw += 360;
  return yaw;
}

export function clampPitch(degrees: number): number {
  return Math.max(PITCH_MIN, Math.min(PITCH_MAX, finiteOr(degrees, 0)));
}

export function clampRoll(degrees: number): number {
  return Math.max(ROLL_MIN, Math.min(ROLL_MAX, finiteOr(degrees, 0)));
}

export function clampZoom(zoom: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, finiteOr(zoom, 1)));
}

/** Optical zoom → lens mm. Zoom 1 = base lens; does not dolly the camera. */
export function zoomToLens(zoom: number, baseLens = DEFAULT_BASE_LENS_MM): number {
  return finiteOr(baseLens, DEFAULT_BASE_LENS_MM) * clampZoom(zoom);
}

export function getSnapPreset(id: string): SnapPreset | undefined {
  return SNAP_PRESETS.find((preset) => preset.id === id);
}

export function applyAxisLocks<T extends { yawDegrees?: number; pitchDegrees?: number; rollDegrees?: number; zoom?: number }>(
  next: T,
  current: { yawDegrees: number; pitchDegrees: number; rollDegrees: number; zoom: number },
  locks?: AxisLocks,
): T {
  if (!locks) return next;
  return {
    ...next,
    yawDegrees: locks.yaw ? current.yawDegrees : next.yawDegrees,
    pitchDegrees: locks.pitch ? current.pitchDegrees : next.pitchDegrees,
    rollDegrees: locks.roll ? current.rollDegrees : next.rollDegrees,
    zoom: locks.zoom ? current.zoom : next.zoom,
  };
}

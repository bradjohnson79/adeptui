/**
 * Scene Creator cinematographer command engine.
 * Mirrors studio-api/app/scene_creator/cinematographer.py for validation + prompts.
 * Spatial mutation is applied on the backend; this module does not invent a second camera system.
 */
export const CAMERA_OPERATIONS = [
  { id: "step_forward", category: "movement", label: "Step Forward", needsSubject: false, physical: true, optical: false },
  { id: "step_back", category: "movement", label: "Step Back", needsSubject: false, physical: true, optical: false },
  { id: "step_left", category: "movement", label: "Step Left", needsSubject: false, physical: true, optical: false },
  { id: "step_right", category: "movement", label: "Step Right", needsSubject: false, physical: true, optical: false },
  { id: "step_up", category: "movement", label: "Step Up", needsSubject: false, physical: true, optical: false },
  { id: "step_down", category: "movement", label: "Step Down", needsSubject: false, physical: true, optical: false },
  { id: "extreme_close_up", category: "framing", label: "Extreme Close-Up", needsSubject: true, physical: false, optical: false },
  { id: "close_up", category: "framing", label: "Close-Up", needsSubject: true, physical: false, optical: false },
  { id: "medium_close_up", category: "framing", label: "Medium Close-Up", needsSubject: true, physical: false, optical: false },
  { id: "medium", category: "framing", label: "Medium Shot", needsSubject: true, physical: false, optical: false },
  { id: "cowboy", category: "framing", label: "Cowboy Shot", needsSubject: true, physical: false, optical: false },
  { id: "full", category: "framing", label: "Full Shot", needsSubject: true, physical: false, optical: false },
  { id: "wide", category: "framing", label: "Wide Shot", needsSubject: true, physical: false, optical: false },
  { id: "extreme_wide", category: "framing", label: "Extreme Wide Shot", needsSubject: true, physical: false, optical: false },
  { id: "dolly_in", category: "dolly", label: "Dolly In", needsSubject: false, physical: true, optical: false },
  { id: "dolly_out", category: "dolly", label: "Dolly Out", needsSubject: false, physical: true, optical: false },
  { id: "high_angle", category: "angle", label: "High Angle", needsSubject: true, physical: false, optical: false },
  { id: "eye_level", category: "angle", label: "Eye Level", needsSubject: true, physical: false, optical: false },
  { id: "low_angle", category: "angle", label: "Low Angle", needsSubject: true, physical: false, optical: false },
  { id: "orbit_left", category: "orbit", label: "Orbit Left", needsSubject: false, physical: true, optical: false },
  { id: "orbit_right", category: "orbit", label: "Orbit Right", needsSubject: false, physical: true, optical: false },
  { id: "zoom_in", category: "optical", label: "Zoom In", needsSubject: false, physical: false, optical: true },
  { id: "zoom_out", category: "optical", label: "Zoom Out", needsSubject: false, physical: false, optical: true },
] as const;

export type CameraOperationId = (typeof CAMERA_OPERATIONS)[number]["id"];
export type CameraOperation = (typeof CAMERA_OPERATIONS)[number];

export const SHOT_TYPE_LABELS: Record<string, string> = {
  extreme_close_up: "EXTREME CLOSE-UP",
  close_up: "CLOSE-UP",
  medium_close_up: "MEDIUM CLOSE-UP",
  medium: "MEDIUM SHOT",
  cowboy: "COWBOY SHOT",
  full: "FULL SHOT",
  wide: "WIDE SHOT",
  extreme_wide: "EXTREME WIDE SHOT",
};

export function getOperation(id: string): CameraOperation | undefined {
  return CAMERA_OPERATIONS.find((op) => op.id === id);
}

export function validateCameraCommand(
  operationId: string,
  characterId: string,
  propId: string,
): { ok: true; operation: CameraOperation } | { ok: false; error: string } {
  const operation = getOperation(operationId);
  if (!operation) return { ok: false, error: "That camera move is not available." };
  if (operation.needsSubject && !characterId.trim() && !propId.trim()) {
    return { ok: false, error: "Choose a character or a prop for this shot." };
  }
  return { ok: true, operation };
}

export function buildDisplayInstruction(input: {
  cameraSlot: number;
  operationId: string;
  characterId?: string;
  propId?: string;
  characterName?: string;
  propName?: string;
  characterSlot?: number | null;
  propSlot?: number | null;
}): string {
  const operation = getOperation(input.operationId);
  if (!operation) return "";
  const cam = `CAMERA ${input.cameraSlot + 1}`;
  let charLabel = "";
  if (input.characterId) {
    const n = input.characterSlot || 1;
    charLabel = `CHARACTER ${n}`;
    if (input.characterName) charLabel = `${charLabel}, ${input.characterName}`;
  }
  let propLabel = "";
  if (input.propId) {
    const n = input.propSlot || 1;
    propLabel = `PROP ${n}`;
    if (input.propName) propLabel = `${propLabel}, ${input.propName}`;
  }
  if (operation.category === "movement") {
    const words: Record<string, string> = {
      step_forward: "ONE STEP FORWARD",
      step_back: "ONE STEP BACK",
      step_left: "ONE STEP LEFT",
      step_right: "ONE STEP RIGHT",
      step_up: "ONE STEP UP",
      step_down: "ONE STEP DOWN",
    };
    return `${cam} move ${words[operation.id]}.`;
  }
  if (operation.category === "dolly") {
    const verb = operation.id === "dolly_in" ? "DOLLY IN toward" : "DOLLY OUT from";
    return `${cam} ${verb} ${charLabel || propLabel || "the subject"}.`;
  }
  if (operation.category === "orbit") {
    return `${cam} ORBIT ${operation.id === "orbit_left" ? "LEFT" : "RIGHT"}.`;
  }
  if (operation.category === "optical") {
    return `${cam} ZOOM ${operation.id === "zoom_in" ? "IN" : "OUT"}.`;
  }
  if (operation.category === "angle") {
    const angle =
      operation.id === "high_angle" ? "HIGH ANGLE" : operation.id === "low_angle" ? "LOW ANGLE" : "EYE LEVEL";
    if (charLabel && propLabel) {
      return `${cam} take ${angle} on ${charLabel} with ${propLabel} included in composition.`;
    }
    return `${cam} take ${angle} on ${charLabel || propLabel || "the subject"}.`;
  }
  const shot = SHOT_TYPE_LABELS[operation.id] || operation.label.toUpperCase();
  if (charLabel && propLabel) {
    return `${cam} take ${shot} on ${charLabel} with ${propLabel} included in composition.`;
  }
  if (charLabel) return `${cam} take ${shot} on ${charLabel}.`;
  if (propLabel) return `${cam} take ${shot} on ${propLabel}.`;
  return `${cam} take ${shot}.`;
}

export type CameraLineage = {
  cameraId: string;
  cameraStateVersion: number;
  cameraStateHash: string;
  previewJobId?: string;
  previewAssetId?: string;
  previewStateVersion?: number;
  previewStateHash?: string;
  locked?: boolean;
  lockedStateVersion?: number;
  lockedStateHash?: string;
  finalJobId?: string;
  finalAssetId?: string;
  finalStateVersion?: number;
  previewStatus?: "none" | "stale" | "generating" | "ready" | "failed";
  previewError?: string;
};

export type CameraPose = {
  cameraId: string;
  cameraSlot: number;
  label: string;
  enabled?: boolean;
  gridColumn: number;
  gridRow: number;
  normalizedX: number;
  normalizedY: number;
  yawDegrees: number;
  pitchDegrees: number;
  heightMeters: number;
  orientation: string;
  fovPreset: string;
  lensMm: number;
  opticalZoomStep: number;
  physicalStepOffset: { forwardBack: number; leftRight: number; vertical: number };
  anglePreset: "low" | "eye_level" | "high";
  shotType: string;
  targetEntityId: string;
  targetEntityType?: "character" | "prop" | null;
  inclusionPropId?: string;
};

export type SceneCameraRecord = {
  cameraId: string;
  cameraSlot: number;
  label: string;
  enabled: boolean;
  baseline: CameraPose;
  current: CameraPose;
  history: unknown[];
  cameraStateVersion: number;
  cameraStateHash: string;
  structuredCommand: Record<string, unknown>;
  displayInstruction: string;
  userCameraPromptDelta: string;
  lineage: CameraLineage;
};

export type SceneCinematographerPack = {
  scene_id: string;
  project_id?: string;
  density: number;
  selected_camera_id: string;
  cameras: SceneCameraRecord[];
};

export function lockIsValid(record: SceneCameraRecord): boolean {
  const lin = record.lineage || {};
  if (!lin.locked) return false;
  if (lin.lockedStateVersion !== record.cameraStateVersion) return false;
  if (lin.lockedStateHash && lin.lockedStateHash !== record.cameraStateHash) return false;
  return true;
}

export function canLockCamera(record: SceneCameraRecord): boolean {
  const lin = record.lineage || {};
  return (
    lin.previewStatus === "ready" &&
    lin.previewStateVersion === record.cameraStateVersion &&
    (!lin.previewStateHash || lin.previewStateHash === record.cameraStateHash)
  );
}

export function previewIsStale(record: SceneCameraRecord): boolean {
  const lin = record.lineage || {};
  if (lin.previewStatus === "none" || lin.previewStatus === "failed") return lin.previewStatus !== "none";
  return lin.previewStateVersion !== record.cameraStateVersion;
}

export function groupedOperations(): { category: string; label: string; ops: CameraOperation[] }[] {
  const labels: Record<string, string> = {
    movement: "Camera Movement",
    framing: "Framing",
    dolly: "Dolly",
    angle: "Angle",
    orbit: "Orbit / Arc",
    optical: "Optical",
  };
  const order = ["movement", "framing", "dolly", "angle", "orbit", "optical"];
  return order.map((category) => ({
    category,
    label: labels[category],
    ops: CAMERA_OPERATIONS.filter((op) => op.category === category),
  }));
}

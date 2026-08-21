import type {
  ArchetypeSpec,
  CameraAspectPreset,
  CameraPreset,
  FigureColorSpec,
  JointLimitMap,
  JointName,
  PoseMap,
  PosePreset,
} from "./types";

export const FIGURE_ARCHETYPES: ArchetypeSpec[] = [
  {
    id: "adult-male",
    label: "Adult Male",
    height: 1.84,
    torsoHeight: 0.72,
    shoulderWidth: 0.48,
    hipWidth: 0.26,
    upperArm: 0.31,
    lowerArm: 0.29,
    upperLeg: 0.46,
    lowerLeg: 0.45,
    limbThickness: 0.12,
    modelId: "adult-male-lowpoly-v3",
  },
  {
    id: "adult-female",
    label: "Adult Female",
    height: 1.7,
    torsoHeight: 0.66,
    shoulderWidth: 0.34,
    hipWidth: 0.32,
    upperArm: 0.27,
    lowerArm: 0.25,
    upperLeg: 0.43,
    lowerLeg: 0.42,
    limbThickness: 0.09,
    modelId: "adult-female-lowpoly-v3",
  },
  {
    id: "child-boy",
    label: "Child Boy",
    height: 1.32,
    torsoHeight: 0.48,
    shoulderWidth: 0.29,
    hipWidth: 0.2,
    upperArm: 0.21,
    lowerArm: 0.2,
    upperLeg: 0.3,
    lowerLeg: 0.29,
    limbThickness: 0.08,
    modelId: "child-boy-lowpoly-v3",
  },
  {
    id: "child-girl",
    label: "Child Girl",
    height: 1.28,
    torsoHeight: 0.47,
    shoulderWidth: 0.27,
    hipWidth: 0.2,
    upperArm: 0.2,
    lowerArm: 0.19,
    upperLeg: 0.29,
    lowerLeg: 0.28,
    limbThickness: 0.08,
    modelId: "child-girl-lowpoly-v3",
  },
];

export const FIGURE_COLORS: FigureColorSpec[] = [
  { id: "seaglass", label: "Sea Glass", hex: "#0f766e" },
  { id: "blue", label: "Blue", hex: "#2563eb" },
  { id: "green", label: "Green", hex: "#16a34a" },
  { id: "red", label: "Red", hex: "#dc2626" },
  { id: "purple", label: "Purple", hex: "#7c3aed" },
  { id: "orange", label: "Orange", hex: "#ea580c" },
];

/** Co-Director scene-label figure roles (optional; default Unspecified). */
export const FIGURE_ROLES: { id: import("./types").FigureRole; label: string }[] = [
  { id: "unspecified", label: "Unspecified" },
  { id: "lead", label: "Lead" },
  { id: "supporting", label: "Supporting" },
  { id: "background", label: "Background" },
  { id: "extra", label: "Extra" },
];

export const JOINT_NAMES: JointName[] = [
  "pelvis",
  "spine",
  "chest",
  "neck",
  "head",
  "leftShoulder",
  "leftElbow",
  "leftWrist",
  "rightShoulder",
  "rightElbow",
  "rightWrist",
  "leftHip",
  "leftKnee",
  "leftAnkle",
  "rightHip",
  "rightKnee",
  "rightAnkle",
];

export const JOINT_LABELS: Record<JointName, string> = {
  pelvis: "Pelvis",
  spine: "Spine",
  chest: "Chest",
  neck: "Neck",
  head: "Head",
  leftShoulder: "Left Shoulder",
  leftElbow: "Left Elbow",
  leftWrist: "Left Wrist",
  rightShoulder: "Right Shoulder",
  rightElbow: "Right Elbow",
  rightWrist: "Right Wrist",
  leftHip: "Left Hip",
  leftKnee: "Left Knee",
  leftAnkle: "Left Ankle",
  rightHip: "Right Hip",
  rightKnee: "Right Knee",
  rightAnkle: "Right Ankle",
};

export const JOINT_LIMITS: JointLimitMap = {
  pelvis: { x: [-20, 20], y: [-50, 50], z: [-15, 15] },
  spine: { x: [-25, 25], y: [-25, 25], z: [-20, 20] },
  chest: { x: [-30, 30], y: [-35, 35], z: [-25, 25] },
  neck: { x: [-30, 30], y: [-50, 50], z: [-30, 30] },
  head: { x: [-35, 25], y: [-60, 60], z: [-30, 30] },
  leftShoulder: { x: [-110, 110], y: [-75, 75], z: [-90, 90] },
  leftElbow: { x: [-5, 145], y: [-35, 35], z: [-25, 25] },
  leftWrist: { x: [-35, 35], y: [-45, 45], z: [-35, 35] },
  rightShoulder: { x: [-110, 110], y: [-75, 75], z: [-90, 90] },
  rightElbow: { x: [-5, 145], y: [-35, 35], z: [-25, 25] },
  rightWrist: { x: [-35, 35], y: [-45, 45], z: [-35, 35] },
  leftHip: { x: [-95, 60], y: [-40, 40], z: [-35, 35] },
  leftKnee: { x: [-5, 145], y: [-10, 10], z: [-10, 10] },
  leftAnkle: { x: [-35, 35], y: [-20, 20], z: [-20, 20] },
  rightHip: { x: [-95, 60], y: [-40, 40], z: [-35, 35] },
  rightKnee: { x: [-5, 145], y: [-10, 10], z: [-10, 10] },
  rightAnkle: { x: [-35, 35], y: [-20, 20], z: [-20, 20] },
};

export function makeNeutralPose(): PoseMap {
  return JOINT_NAMES.reduce<PoseMap>((acc, joint) => {
    acc[joint] = { x: 0, y: 0, z: 0 };
    return acc;
  }, {} as PoseMap);
}

export const POSE_LIBRARY: PosePreset[] = [
  {
    id: "neutral-hero",
    label: "Hero Stand",
    category: "neutral",
    description: "Balanced weight, open chest, ready for a poster frame.",
    joints: {
      chest: { x: 6, y: 0, z: 0 },
      leftShoulder: { x: 14, y: 0, z: -10 },
      rightShoulder: { x: 14, y: 0, z: 10 },
    },
  },
  {
    id: "neutral-listening",
    label: "Listening",
    category: "dialogue",
    description: "A relaxed conversational stance with a soft lean.",
    joints: {
      pelvis: { x: -4, y: 8, z: 0 },
      chest: { x: 12, y: -8, z: 0 },
      head: { x: -8, y: 10, z: 0 },
      leftShoulder: { x: 18, y: 12, z: -6 },
      rightShoulder: { x: 12, y: -8, z: 8 },
    },
  },
  {
    id: "power-hands-on-hips",
    label: "Hands on Hips",
    category: "power",
    description: "Confident stance for a reveal or challenge beat.",
    joints: {
      chest: { x: 10, y: 0, z: 0 },
      leftShoulder: { x: 52, y: 10, z: -18 },
      leftElbow: { x: 84, y: 0, z: 0 },
      rightShoulder: { x: 52, y: -10, z: 18 },
      rightElbow: { x: 84, y: 0, z: 0 },
    },
  },
  {
    id: "power-walk-up",
    label: "Stride Forward",
    category: "motion",
    description: "A simple walking key pose for blocking entrances.",
    joints: {
      leftHip: { x: 22, y: 0, z: 0 },
      leftKnee: { x: 18, y: 0, z: 0 },
      rightHip: { x: -18, y: 0, z: 0 },
      rightKnee: { x: 26, y: 0, z: 0 },
      leftShoulder: { x: -18, y: 0, z: 0 },
      rightShoulder: { x: 24, y: 0, z: 0 },
    },
  },
  {
    id: "emotion-pleading",
    label: "Pleading",
    category: "emotion",
    description: "Raised arms and forward chest for an emotional appeal.",
    joints: {
      spine: { x: 10, y: 0, z: 0 },
      chest: { x: 14, y: 0, z: 0 },
      head: { x: -12, y: 0, z: 0 },
      leftShoulder: { x: 72, y: 0, z: -25 },
      leftElbow: { x: 56, y: 0, z: 0 },
      rightShoulder: { x: 72, y: 0, z: 25 },
      rightElbow: { x: 56, y: 0, z: 0 },
    },
  },
  {
    id: "duo-over-shoulder",
    label: "Over Shoulder",
    category: "duo",
    description: "One shoulder opens toward the camera for a dialogue setup.",
    joints: {
      pelvis: { x: 0, y: 20, z: 0 },
      chest: { x: 0, y: -16, z: 0 },
      head: { x: -4, y: -8, z: 0 },
      leftShoulder: { x: 18, y: 14, z: -10 },
      rightShoulder: { x: 8, y: -25, z: 10 },
    },
  },
  {
    id: "motion-kneel",
    label: "Kneel Down",
    category: "motion",
    description: "A low blocking pose for landing, grief, or scale contrast.",
    joints: {
      pelvis: { x: -10, y: 0, z: 0 },
      leftHip: { x: 52, y: 0, z: 0 },
      leftKnee: { x: 96, y: 0, z: 0 },
      rightHip: { x: -8, y: 0, z: 0 },
      rightKnee: { x: 30, y: 0, z: 0 },
    },
  },
  {
    id: "dialogue-seated-ish",
    label: "Perch Sit",
    category: "dialogue",
    description: "A perched pose that works with a box or low platform.",
    joints: {
      pelvis: { x: -14, y: 0, z: 0 },
      leftHip: { x: 62, y: 0, z: 0 },
      leftKnee: { x: 92, y: 0, z: 0 },
      rightHip: { x: 58, y: 0, z: 0 },
      rightKnee: { x: 88, y: 0, z: 0 },
      chest: { x: 10, y: 0, z: 0 },
    },
  },
];

export const CAMERA_PRESETS: CameraPreset[] = [
  { lensMm: 18, label: "18mm", intent: "Big stage, dramatic depth" },
  { lensMm: 24, label: "24mm", intent: "Wide blocking with mild stretch" },
  { lensMm: 35, label: "35mm", intent: "Natural master or medium" },
  { lensMm: 50, label: "50mm", intent: "Classic portrait balance" },
  { lensMm: 85, label: "85mm", intent: "Compressed close coverage" },
  { lensMm: 135, label: "135mm", intent: "Tight, distant, compressed" },
];

export const CAMERA_ASPECTS: CameraAspectPreset[] = [
  { id: "16:9", label: "16:9", ratio: 16 / 9 },
  { id: "2.39:1", label: "2.39:1", ratio: 2.39 },
  { id: "1:1", label: "1:1", ratio: 1 },
  { id: "4:5", label: "4:5", ratio: 4 / 5 },
  { id: "9:16", label: "9:16", ratio: 9 / 16 },
];

export const CAMERA_GUIDES = [
  { id: "safe", label: "Safe Margins" },
  { id: "center", label: "Center Mark" },
  { id: "thirds", label: "Rule of Thirds" },
] as const;

// ---------------------------------------------------------------------------
// Gate H — Furniture presets. Real Babylon objects (boxes/cylinders) with
// neutral materials. Used by the Furniture accordion and the coffee-shop
// staging scenario (table + two chairs + conversation).
// ---------------------------------------------------------------------------
export type FurniturePreset = {
  kind: import("./types").FurnitureKind;
  label: string;
  description: string;
  size: { x: number; y: number; z: number };
  color: string;
};

export const FURNITURE_PRESETS: FurniturePreset[] = [
  { kind: "block-small", label: "Small Block", description: "Low apple-box height prop for sitting or stepping.", size: { x: 0.6, y: 0.4, z: 0.4 }, color: "#9ca3af" },
  { kind: "block-medium", label: "Medium Block", description: "Mid-height block for resting elbows or staging.", size: { x: 0.7, y: 0.6, z: 0.5 }, color: "#9ca3af" },
  { kind: "block-large", label: "Large Block", description: "Tall block for a high perch or pillar.", size: { x: 0.8, y: 0.9, z: 0.6 }, color: "#9ca3af" },
  { kind: "block-chair", label: "Block Chair", description: "Simple seat-height block chair for a coffee-shop.", size: { x: 0.55, y: 0.5, z: 0.55 }, color: "#8b5e3c" },
  { kind: "table-small", label: "Small Table", description: "Small cafe table for a tight two-shot.", size: { x: 0.7, y: 0.72, z: 0.7 }, color: "#6b4f2a" },
  { kind: "table-medium", label: "Medium Table", description: "Standard cafe table for two.", size: { x: 0.9, y: 0.74, z: 0.9 }, color: "#6b4f2a" },
  { kind: "table-large", label: "Large Table", description: "Wide table for a group blocking setup.", size: { x: 1.2, y: 0.76, z: 1.2 }, color: "#6b4f2a" },
  // Final Mandatory GO — Walls (thin tall boxes) and Walls with Window.
  { kind: "wall-small", label: "Wall Small", description: "Short neutral staging wall for dividing a set.", size: { x: 1.6, y: 1.2, z: 0.12 }, color: "#9ca3af" },
  { kind: "wall-medium", label: "Wall Medium", description: "Mid-height staging wall behind a two-shot.", size: { x: 2.4, y: 1.8, z: 0.12 }, color: "#9ca3af" },
  { kind: "wall-large", label: "Wall Large", description: "Tall staging wall for a full backdrop.", size: { x: 3.2, y: 2.6, z: 0.14 }, color: "#9ca3af" },
  { kind: "wall-window-small", label: "Wall w/ Window Small", description: "Short wall with a framed window opening.", size: { x: 1.6, y: 1.2, z: 0.12 }, color: "#9ca3af" },
  { kind: "wall-window-medium", label: "Wall w/ Window Medium", description: "Mid-height wall with a window opening for a coffee-shop.", size: { x: 2.4, y: 1.8, z: 0.12 }, color: "#9ca3af" },
  { kind: "wall-window-large", label: "Wall w/ Window Large", description: "Tall backdrop wall with a large window opening.", size: { x: 3.2, y: 2.6, z: 0.14 }, color: "#9ca3af" },
];

export function getFurniturePreset(kind: string): FurniturePreset | undefined {
  return FURNITURE_PRESETS.find((entry) => entry.kind === kind);
}

// ---------------------------------------------------------------------------
// Gate A — Layout bounds for resizable panes.
// ---------------------------------------------------------------------------
export const POSECRAFT_LAYOUT_BOUNDS = {
  leftMin: 260,
  leftMax: 520,
  rightMin: 280,
  rightMax: 560,
  viewportMinPct: 50,
  // Default widths (px) at 1920 workspace width.
  defaultLeft: 320,
  defaultRight: 340,
} as const;

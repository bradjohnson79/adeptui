export const POSECRAFT_SCHEMA_VERSION = 2;

export type ArchetypeId =
  | "adult-male"
  | "adult-female"
  | "child-boy"
  | "child-girl";

export type FigureColorId =
  | "seaglass"
  | "blue"
  | "green"
  | "red"
  | "purple"
  | "yellow"
  | "orange";

export type JointName =
  | "pelvis"
  | "spine"
  | "chest"
  | "neck"
  | "head"
  | "leftShoulder"
  | "leftElbow"
  | "leftWrist"
  | "rightShoulder"
  | "rightElbow"
  | "rightWrist"
  | "leftHip"
  | "leftKnee"
  | "leftAnkle"
  | "rightHip"
  | "rightKnee"
  | "rightAnkle";

export type JointAxis = "x" | "y" | "z";

export type JointRotation = {
  x: number;
  y: number;
  z: number;
};

export type PoseMap = Record<JointName, JointRotation>;

export type PoseCategoryId =
  | "neutral"
  | "dialogue"
  | "power"
  | "motion"
  | "emotion"
  | "duo"
  | "action"
  | "rest"
  | "gesture"
  | "custom";

export type PosePreset = {
  id: string;
  label: string;
  category: PoseCategoryId;
  description: string;
  joints: Partial<PoseMap>;
  // Archetypes this pose is compatible with. Empty/absent means all archetypes.
  archetypes?: ArchetypeId[];
  // Build-time-rendered thumbnail (SVG string generated from canonical joint
  // data). Real matching thumbnail — derived from this pose's exact joints.
  thumbnail?: string;
};

export type CameraAspectId = "16:9" | "2.39:1" | "1:1" | "4:5" | "9:16";

export type CameraGuideId = "safe" | "center" | "thirds";

export type CameraState = {
  lensMm: number;
  aspect: CameraAspectId;
  guides: CameraGuideId[];
  alpha: number;
  beta: number;
  radius: number;
  target: {
    x: number;
    y: number;
    z: number;
  };
};

/** Co-Director scene labels — optional figure emphasis role (separate from name). */
export type FigureRole = "lead" | "supporting" | "background" | "extra" | "unspecified";

export type FigureInstance = {
  /** Permanent machine identity — never changes on rename. */
  id: string;
  /** Creator-facing scene label (Cast Browser name). Co-Director reads this as `label`. */
  name: string;
  archetypeId: ArchetypeId;
  colorId: FigureColorId;
  position: {
    x: number;
    z: number;
  };
  rotationY: number;
  scale: number;
  pose: PoseMap;
  // Optional association to a project character/identity (Co-Director mapping).
  characterId?: string | null;
  identityId?: string | null;
  /** Optional Co-Director emphasis role. Defaults to unspecified. */
  role?: FigureRole;
  poseId?: string | null;
  poseLabel?: string | null;
  eyelineTargetId?: string | null;
  visible?: boolean;
  locked?: boolean;
  // Backward-compat: joint data for joints that were valid in an older
  // schemaVersion but are no longer in JOINT_NAMES is retained here rather
  // than discarded silently when a scene is migrated to the current schema.
  legacyJointData?: Record<string, JointRotation>;
  // Final Mandatory GO: custom imported mesh figure. When kind === "custom",
  // archetypeId is "adult-male" (a placeholder for rig/color) but the figure
  // is rendered from customAssetId (a project Library asset). Custom figures
  // support Move/Rotate/Scale only — no skeletal pose this milestone.
  kind?: "archetype" | "custom";
  customAssetId?: string | null;
  customAssetName?: string | null;
};

export type PrimitiveKind =
  | "apple-box"
  | "cube"
  | "platform"
  | "block-small"
  | "block-medium"
  | "block-large"
  | "block-chair"
  | "table-small"
  | "table-medium"
  | "table-large"
  | "wall-small"
  | "wall-medium"
  | "wall-large"
  | "wall-window-small"
  | "wall-window-medium"
  | "wall-window-large";

export type FurnitureKind =
  | "block-small"
  | "block-medium"
  | "block-large"
  | "block-chair"
  | "table-small"
  | "table-medium"
  | "table-large"
  | "wall-small"
  | "wall-medium"
  | "wall-large"
  | "wall-window-small"
  | "wall-window-medium"
  | "wall-window-large";

export type BlockingPrimitive = {
  /** Permanent machine identity — never changes on rename. */
  id: string;
  /** Creator-facing scene label. */
  name: string;
  kind: PrimitiveKind;
  position: {
    x: number;
    z: number;
  };
  rotationY?: number;
  scale?: number;
  size: {
    x: number;
    y: number;
    z: number;
  };
  color: string;
  visible?: boolean;
  locked?: boolean;
};

export type PoseCraftLayoutPrefs = {
  leftWidth: number;
  rightWidth: number;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  leftOpenAccordions: string[];
  rightOpenAccordions: string[];
  fullscreen: boolean;
};

export type PoseCraftProvenance = {
  // Schema version this scene was migrated from, if it was migrated.
  migratedFrom?: number;
  migratedAt?: string;
  // Free-form migration notes (e.g. which legacy joints were retained).
  notes?: string;
};

export type PoseCraftScene = {
  schemaVersion: number;
  revision: number;
  updatedAt: string;
  name: string;
  notes: string;
  stage: {
    gridSize: number;
    showAxes: boolean;
    showPrimitives: boolean;
    /** Viewport floating scene labels (convenience; Cast Browser remains SoT). */
    showLabels?: boolean;
  };
  camera: CameraState;
  figures: FigureInstance[];
  primitives: BlockingPrimitive[];
  selectedFigureId: string | null;
  selectedJoint: JointName;
  /** Final Mandatory GO (D6): selected blocking/furniture primitive for
   * keyboard Delete/Backspace. Optional for backward-compat with older scenes. */
  selectedPrimitiveId?: string | null;
  // Backward-compat provenance: records when/how a scene was migrated from an
  // older schemaVersion so legacy joint data is traceable, not silently lost.
  provenance?: PoseCraftProvenance;
};

export type PoseCraftVersion = {
  id: string;
  label: string;
  savedAt: string;
  revision: number;
  scene: PoseCraftScene;
};

/**
 * PoseCraft Snapshot — one exact camera composition frozen for production
 * handoff. A Snapshot is NOT a scene save: it captures the camera framing
 * and the staged figures/primitives/semanticSummary at capture time as
 * IMMUTABLE frozen copies. Rename is the only mutating op that touches a
 * Snapshot (and it only changes `name`). Scene autosave/flush stays
 * independent and never PNG-captures.
 */
export type PoseCraftSnapshot = {
  snapshotId: string;
  projectId: string;
  sceneId: string;
  sceneRevision: number;
  name: string;
  /** Project Library asset id for the clean PNG capture. */
  imageAssetId: string;
  /** Frozen camera composition at capture time. */
  camera: CameraState;
  /** Frozen figures at capture time (immutable copy). */
  figures: FigureInstance[];
  /** Frozen primitives at capture time (immutable copy). */
  primitives: BlockingPrimitive[];
  /** Frozen custom-figure subset (figures with kind === "custom"). */
  customFigures: FigureInstance[];
  /** Human-readable scene summary using labels (not colors) at capture time. */
  semanticSummary: string;
  createdAt: string;
  updatedAt: string;
};

export type PoseCraftDocument = {
  schemaVersion: number;
  currentScene: PoseCraftScene;
  savedVersions: PoseCraftVersion[];
  /** Frozen camera-composition Snapshots for production handoff. */
  snapshots?: PoseCraftSnapshot[];
  /** The Snapshot currently selected for handoff (null = none selected). */
  selectedSnapshotId?: string | null;
  layoutPrefs?: PoseCraftLayoutPrefs;
};

export type ArchetypeSpec = {
  id: ArchetypeId;
  label: string;
  height: number;
  torsoHeight: number;
  shoulderWidth: number;
  hipWidth: number;
  upperArm: number;
  lowerArm: number;
  upperLeg: number;
  lowerLeg: number;
  limbThickness: number;
  /** Final Mandatory GO: v2 low-poly human model identifier. */
  modelId: string;
};

export type FigureColorSpec = {
  id: FigureColorId;
  label: string;
  hex: string;
};

export type JointLimit = {
  x: [number, number];
  y: [number, number];
  z: [number, number];
};

export type JointLimitMap = Record<JointName, JointLimit>;

export type CameraPreset = {
  lensMm: number;
  label: string;
  intent: string;
};

export type CameraAspectPreset = {
  id: CameraAspectId;
  label: string;
  ratio: number;
};

export type PoseCraftExportMetadata = {
  schemaVersion: number;
  revision: number;
  exportedAt: string;
  sceneName: string;
  figureCount: number;
  primitiveCount: number;
  lensMm: number;
  aspect: CameraAspectId;
  renderer: "webgl" | "webgpu";
};

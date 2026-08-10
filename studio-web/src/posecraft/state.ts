import {
  CAMERA_PRESETS,
  FIGURE_ARCHETYPES,
  FIGURE_COLORS,
  FURNITURE_PRESETS,
  JOINT_LIMITS,
  JOINT_NAMES,
  POSECRAFT_LAYOUT_BOUNDS,
  makeNeutralPose,
} from "./constants";
import type {
  ArchetypeId,
  BlockingPrimitive,
  CameraState,
  FigureColorId,
  FigureInstance,
  FigureRole,
  FurnitureKind,
  JointAxis,
  JointName,
  JointRotation,
  PoseCraftDocument,
  PoseCraftLayoutPrefs,
  PoseCraftScene,
  PoseCraftSnapshot,
  PoseCraftVersion,
  PoseMap,
  PosePreset,
  PrimitiveKind,
} from "./types";
import { POSECRAFT_SCHEMA_VERSION } from "./types";

function nowIso() {
  return new Date().toISOString();
}

function uid(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2, 10)}`;
}

function cloneScene<T>(value: T): T {
  return structuredClone(value);
}

function withRevision(scene: PoseCraftScene, mutator: (draft: PoseCraftScene) => void): PoseCraftScene {
  const draft = cloneScene(scene);
  mutator(draft);
  draft.revision = scene.revision + 1;
  draft.updatedAt = nowIso();
  return draft;
}

function countByArchetype(figures: FigureInstance[], archetypeId: ArchetypeId) {
  return figures.filter((figure) => figure.archetypeId === archetypeId).length;
}

export function getArchetypeSpec(archetypeId: ArchetypeId) {
  return FIGURE_ARCHETYPES.find((entry) => entry.id === archetypeId) ?? FIGURE_ARCHETYPES[0];
}

export function getColorSpec(colorId: FigureColorId) {
  return FIGURE_COLORS.find((entry) => entry.id === colorId) ?? FIGURE_COLORS[0];
}

const KNOWN_JOINT_SET = new Set<JointName>(JOINT_NAMES);

// Legacy staging color IDs (schemaVersion 1) → current canonical IDs.
// The visual hex is preserved (teal/seaglass share #0f766e, coral/orange share
// #ea580c, etc.); sky→blue and rose→red are the closest current matches.
// This remap keeps legacy scenes rendering at the same visual color while
// upgrading the stored id to a valid current one.
const LEGACY_COLOR_REMAP: Record<string, FigureColorId> = {
  teal: "seaglass",
  coral: "orange",
  violet: "purple",
  sky: "blue",
  gold: "yellow",
  rose: "red",
};

function remapColorId(colorId: string | undefined): FigureColorId | undefined {
  if (!colorId) return undefined;
  if (LEGACY_COLOR_REMAP[colorId]) return LEGACY_COLOR_REMAP[colorId];
  return colorId as FigureColorId;
}

/**
 * Migrate a PoseCraftScene to the current schemaVersion (2).
 *
 * Backward-compat gate (Master Program Phase 4.5). This runs on every load
 * (client storage + API). It preserves protected fields and never corrupts
 * an existing project merely because the figure mesh / joint system improved:
 *
 *  - scene id, revision, name, notes, stage, camera, primitives, selectedFigureId,
 *    selectedJoint are preserved verbatim;
 *  - each figure's id, name, archetypeId, colorId, position, rotationY, scale,
 *    characterId, identityId are preserved verbatim;
 *  - for each figure.pose: known joints are kept; missing known joints are
 *    filled with neutral (0,0,0); joints that are no longer in JOINT_NAMES
 *    (unsupported legacy joints) are moved to figure.legacyJointData (provenance)
 *    rather than discarded silently;
 *  - scene.schemaVersion is set to the current version and scene.provenance
 *    records the migration when an actual migration occurred.
 *
 * Idempotent: a scene already at the current version is only normalized
 * (missing known joints filled) without recording a new migration.
 */
export function migrateSceneToCurrent(input: PoseCraftScene): PoseCraftScene {
  const scene = cloneScene(input);
  const migratedFrom = Number(scene.schemaVersion || 1);
  const needsMigration = migratedFrom < POSECRAFT_SCHEMA_VERSION;

  scene.schemaVersion = POSECRAFT_SCHEMA_VERSION;
  scene.figures = scene.figures.map((figure) => {
    const nextPose: PoseMap = makeNeutralPose();
    const legacyJointData: Record<string, JointRotation> = {
      ...(figure.legacyJointData ?? {}),
    };
    const incoming = figure.pose ?? ({} as PoseMap);
    for (const [joint, rotation] of Object.entries(incoming) as [string, JointRotation][]) {
      if (KNOWN_JOINT_SET.has(joint as JointName)) {
        nextPose[joint as JointName] = {
          x: clampRotation(joint as JointName, "x", rotation.x ?? 0),
          y: clampRotation(joint as JointName, "y", rotation.y ?? 0),
          z: clampRotation(joint as JointName, "z", rotation.z ?? 0),
        };
      } else {
        // Unsupported legacy joint → provenance, not discarded.
        legacyJointData[joint] = { x: rotation.x ?? 0, y: rotation.y ?? 0, z: rotation.z ?? 0 };
      }
    }
    const { pose: _dropped, ...figureWithoutPose } = figure;
    return {
      ...figureWithoutPose,
      pose: nextPose,
      colorId: remapColorId(figure.colorId) ?? figure.colorId,
      legacyJointData: Object.keys(legacyJointData).length ? legacyJointData : undefined,
    };
  });

  if (needsMigration) {
    scene.provenance = {
      migratedFrom,
      migratedAt: nowIso(),
      notes:
        migratedFrom < 2
          ? "Migrated from schemaVersion 1 (block-figure) to 2 (humanoid rig). Unsupported legacy joints retained in figure.legacyJointData."
          : "Schema normalized to current version.",
    };
  }
  return scene;
}

export function clampRotation(joint: JointName, axis: JointAxis, value: number) {
  const [min, max] = JOINT_LIMITS[joint][axis];
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function createFigure(archetypeId: ArchetypeId, colorId?: FigureColorId): FigureInstance {
  const spec = getArchetypeSpec(archetypeId);
  return {
    id: uid("figure"),
    name: spec.label,
    archetypeId,
    colorId: colorId ?? FIGURE_COLORS[0].id,
    position: { x: 0, z: 0 },
    rotationY: 0,
    scale: 1,
    pose: makeNeutralPose(),
    role: "unspecified",
    visible: true,
    locked: false,
  };
}

/**
 * Final Mandatory GO (IMPORT): create a custom-mesh figure. The mesh itself
 * is stored in the open project's Library (assetId); the PoseCraft scene only
 * stores the asset reference + transform. Custom figures support Move /
 * Rotate / Scale only — no skeletal pose this milestone.
 */
export function createCustomFigure(assetId: string, assetName: string, colorId?: FigureColorId): FigureInstance {
  const base = createFigure("adult-male", colorId);
  return {
    ...base,
    name: assetName.replace(/\.[^.]+$/, "") || "Custom Figure",
    kind: "custom",
    customAssetId: assetId,
    customAssetName: assetName,
    // Custom figures have no pose rig; pose stays neutral and is not editable.
  };
}

export function addCustomFigureToScene(scene: PoseCraftScene, assetId: string, assetName: string) {
  return withRevision(scene, (draft) => {
    const figure = createCustomFigure(assetId, assetName);
    figure.position = {
      x: -1.4 + draft.figures.length * 0.8,
      z: draft.figures.length % 2 === 0 ? 0 : 0.6,
    };
    draft.figures.push(figure);
    draft.selectedFigureId = figure.id;
  });
}

export function createPrimitive(name = "Apple Box"): BlockingPrimitive {
  return {
    id: uid("primitive"),
    name,
    kind: "apple-box",
    position: { x: 0.9, z: 0.6 },
    size: { x: 0.6, y: 0.5, z: 0.4 },
    color: "#94a3b8",
  };
}

/**
 * Gate H — Create a furniture primitive from a FurnitureKind preset.
 * Real Babylon objects (boxes/cylinders) with neutral materials.
 */
export function createFurniture(kind: FurnitureKind, index = 1): BlockingPrimitive {
  const preset = FURNITURE_PRESETS.find((entry) => entry.kind === kind) ?? FURNITURE_PRESETS[0];
  return {
    id: uid("furniture"),
    name: `${preset.label} ${index}`,
    kind: kind as PrimitiveKind,
    position: { x: -0.4 + index * 0.5, z: 0.4 },
    size: { ...preset.size },
    color: preset.color,
  };
}

export function addFurnitureToScene(scene: PoseCraftScene, kind: FurnitureKind) {
  return withRevision(scene, (draft) => {
    const next = createFurniture(kind, draft.primitives.length + 1);
    draft.primitives.push(next);
  });
}

// ---------------------------------------------------------------------------
// Gate I — Layout preferences (persisted via the API document SoT).
// ---------------------------------------------------------------------------
export function createDefaultLayoutPrefs(): PoseCraftLayoutPrefs {
  return {
    leftWidth: POSECRAFT_LAYOUT_BOUNDS.defaultLeft,
    rightWidth: POSECRAFT_LAYOUT_BOUNDS.defaultRight,
    leftCollapsed: false,
    rightCollapsed: false,
    leftOpenAccordions: ["cast", "pose-library", "furniture", "scene"],
    rightOpenAccordions: ["figure", "transform", "pose", "camera", "export"],
    fullscreen: false,
  };
}

export function updateLayoutPrefs(document: PoseCraftDocument, patch: Partial<PoseCraftLayoutPrefs>): PoseCraftDocument {
  return {
    ...document,
    layoutPrefs: { ...(document.layoutPrefs ?? createDefaultLayoutPrefs()), ...patch },
  };
}

export function createDefaultCamera(): CameraState {
  return {
    lensMm: CAMERA_PRESETS[2]?.lensMm ?? 35,
    aspect: "16:9",
    guides: ["safe", "center", "thirds"],
    alpha: -Math.PI / 2,
    beta: 1.12,
    radius: 7.5,
    target: { x: 0, y: 1.2, z: 0 },
  };
}

export function createDefaultScene(): PoseCraftScene {
  const lead = createFigure("adult-female", "seaglass");
  lead.name = "Lead";
  lead.position = { x: -0.75, z: 0 };

  const partner = createFigure("adult-male", "orange");
  partner.name = "Partner";
  partner.position = { x: 0.95, z: 0.25 };
  partner.rotationY = -18;

  return {
    schemaVersion: POSECRAFT_SCHEMA_VERSION,
    revision: 1,
    updatedAt: nowIso(),
    name: "PoseCraft Blocking Study",
    notes: "Use PoseCraft to answer who stands where, how they pose, and where the camera lands.",
    stage: {
      gridSize: 12,
      showAxes: true,
      showPrimitives: true,
      showLabels: false,
    },
    camera: createDefaultCamera(),
    figures: [lead, partner],
    primitives: [createPrimitive()],
    selectedFigureId: lead.id,
    selectedJoint: "head",
  };
}

export function createDefaultDocument(): PoseCraftDocument {
  return {
    schemaVersion: POSECRAFT_SCHEMA_VERSION,
    currentScene: createDefaultScene(),
    savedVersions: [],
  };
}

export function renameScene(scene: PoseCraftScene, name: string) {
  return withRevision(scene, (draft) => {
    draft.name = name || "Untitled PoseCraft Scene";
  });
}

export function updateSceneNotes(scene: PoseCraftScene, notes: string) {
  return withRevision(scene, (draft) => {
    draft.notes = notes;
  });
}

export function addFigure(scene: PoseCraftScene, archetypeId: ArchetypeId) {
  return withRevision(scene, (draft) => {
    const nextIndex = countByArchetype(draft.figures, archetypeId) + 1;
    const figure = createFigure(archetypeId, FIGURE_COLORS[draft.figures.length % FIGURE_COLORS.length]?.id);
    figure.name = `${getArchetypeSpec(archetypeId).label} ${nextIndex}`;
    figure.position = {
      x: -1.4 + draft.figures.length * 0.8,
      z: draft.figures.length % 2 === 0 ? 0 : 0.6,
    };
    draft.figures.push(figure);
    draft.selectedFigureId = figure.id;
  });
}

export function duplicateFigure(scene: PoseCraftScene, figureId: string) {
  return withRevision(scene, (draft) => {
    const source = draft.figures.find((figure) => figure.id === figureId);
    if (!source) return;
    const duplicate = cloneScene(source);
    duplicate.id = uid("figure");
    duplicate.name = `${source.name} Copy`;
    duplicate.position.x += 0.7;
    duplicate.position.z += 0.35;
    draft.figures.push(duplicate);
    draft.selectedFigureId = duplicate.id;
  });
}

export function removeFigure(scene: PoseCraftScene, figureId: string) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.filter((figure) => figure.id !== figureId);
    draft.selectedFigureId = draft.figures[0]?.id ?? null;
  });
}

/** Final Mandatory GO (D5): rename a figure (inline/menu). Empty names fall
 * back to the archetype label so a figure never becomes unnamed. */
export function renameFigure(scene: PoseCraftScene, figureId: string, name: string) {
  return withRevision(scene, (draft) => {
    const spec = getArchetypeSpec(draft.figures.find((f) => f.id === figureId)?.archetypeId ?? "adult-male");
    draft.figures = draft.figures.map((figure) =>
      figure.id === figureId ? { ...figure, name: name.trim() || spec.label } : figure,
    );
  });
}

/** Co-Director scene labels — set optional figure role without changing id/name. */
export function setFigureRole(scene: PoseCraftScene, figureId: string, role: FigureRole) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.map((figure) =>
      figure.id === figureId ? { ...figure, role } : figure,
    );
  });
}

/** Rename a furniture/blocking primitive (scene label). Id is unchanged. */
export function renamePrimitive(scene: PoseCraftScene, primitiveId: string, name: string) {
  return withRevision(scene, (draft) => {
    draft.primitives = draft.primitives.map((primitive) =>
      primitive.id === primitiveId
        ? { ...primitive, name: name.trim() || primitive.kind }
        : primitive,
    );
  });
}

/** Final Mandatory GO (D6): select a blocking/furniture primitive so the
 * keyboard Delete/Backspace contract can target it. Clears any figure
 * selection so the keyboard delete contract targets exactly one object. */
export function selectPrimitive(scene: PoseCraftScene, primitiveId: string | null) {
  return { ...scene, selectedPrimitiveId: primitiveId, selectedFigureId: primitiveId ? null : scene.selectedFigureId };
}

export function selectFigure(scene: PoseCraftScene, figureId: string | null) {
  return {
    ...scene,
    selectedFigureId: figureId,
    selectedPrimitiveId: figureId ? null : scene.selectedPrimitiveId,
  };
}

export function selectJoint(scene: PoseCraftScene, joint: JointName) {
  return {
    ...scene,
    selectedJoint: joint,
  };
}

export function updateFigure(scene: PoseCraftScene, figureId: string, patch: Partial<FigureInstance>) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.map((figure) =>
      figure.id === figureId ? { ...figure, ...cloneScene(patch) } : figure,
    );
  });
}

export function updateFigureJoint(
  scene: PoseCraftScene,
  figureId: string,
  joint: JointName,
  axis: JointAxis,
  value: number,
) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.map((figure) => {
      if (figure.id !== figureId) return figure;
      const nextPose = cloneScene(figure.pose);
      nextPose[joint] = {
        ...nextPose[joint],
        [axis]: clampRotation(joint, axis, value),
      };
      return {
        ...figure,
        pose: nextPose,
      };
    });
  });
}

export function resetFigurePose(scene: PoseCraftScene, figureId: string) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.map((figure) =>
      figure.id === figureId
        ? {
            ...figure,
            pose: makeNeutralPose(),
          }
        : figure,
    );
  });
}

export function applyPosePreset(scene: PoseCraftScene, figureId: string, preset: PosePreset) {
  return withRevision(scene, (draft) => {
    draft.figures = draft.figures.map((figure) => {
      if (figure.id !== figureId) return figure;
      const nextPose = cloneScene(figure.pose);
      for (const joint of JOINT_NAMES) {
        const patch = preset.joints[joint];
        if (!patch) continue;
        nextPose[joint] = {
          x: clampRotation(joint, "x", patch.x ?? nextPose[joint].x),
          y: clampRotation(joint, "y", patch.y ?? nextPose[joint].y),
          z: clampRotation(joint, "z", patch.z ?? nextPose[joint].z),
        };
      }
      return {
        ...figure,
        pose: nextPose,
      };
    });
  });
}

export function updateCamera(scene: PoseCraftScene, patch: Partial<CameraState>) {
  return withRevision(scene, (draft) => {
    draft.camera = {
      ...draft.camera,
      ...cloneScene(patch),
      target: {
        ...draft.camera.target,
        ...cloneScene(patch.target ?? {}),
      },
    };
  });
}

export function toggleStageFlag(scene: PoseCraftScene, key: "showAxes" | "showPrimitives" | "showLabels") {
  return withRevision(scene, (draft) => {
    draft.stage[key] = !Boolean(draft.stage[key]);
  });
}

export function addPrimitiveToScene(scene: PoseCraftScene) {
  return withRevision(scene, (draft) => {
    draft.primitives.push(createPrimitive(`Apple Box ${draft.primitives.length + 1}`));
  });
}

export function removePrimitiveFromScene(scene: PoseCraftScene, primitiveId: string) {
  return withRevision(scene, (draft) => {
    draft.primitives = draft.primitives.filter((primitive) => primitive.id !== primitiveId);
  });
}

export function updatePrimitive(
  scene: PoseCraftScene,
  primitiveId: string,
  patch: Partial<BlockingPrimitive>,
) {
  return withRevision(scene, (draft) => {
    draft.primitives = draft.primitives.map((primitive) =>
      primitive.id === primitiveId ? { ...primitive, ...cloneScene(patch) } : primitive,
    );
  });
}

export function saveSceneVersion(document: PoseCraftDocument, label?: string): PoseCraftDocument {
  const version: PoseCraftVersion = {
    id: uid("version"),
    label: label?.trim() || `Revision ${document.currentScene.revision}`,
    savedAt: nowIso(),
    revision: document.currentScene.revision,
    scene: cloneScene(document.currentScene),
  };
  return {
    ...document,
    savedVersions: [version, ...document.savedVersions].slice(0, 12),
  };
}

export function restoreSceneVersion(document: PoseCraftDocument, versionId: string): PoseCraftDocument {
  const version = document.savedVersions.find((entry) => entry.id === versionId);
  if (!version) return document;
  const restored = cloneScene(version.scene);
  restored.revision += 1;
  restored.updatedAt = nowIso();
  return {
    ...document,
    currentScene: restored,
  };
}

export function renameSceneVersion(document: PoseCraftDocument, versionId: string, label: string): PoseCraftDocument {
  const next = label.trim().slice(0, 120);
  if (!next) return document;
  return {
    ...document,
    savedVersions: document.savedVersions.map((entry) =>
      entry.id === versionId ? { ...entry, label: next } : entry,
    ),
  };
}

export function duplicateSceneVersion(document: PoseCraftDocument, versionId: string): PoseCraftDocument {
  const version = document.savedVersions.find((entry) => entry.id === versionId);
  if (!version) return document;
  const copy: PoseCraftVersion = {
    id: uid("version"),
    label: `${version.label} Copy`,
    savedAt: nowIso(),
    revision: version.revision,
    scene: cloneScene(version.scene),
  };
  const idx = document.savedVersions.findIndex((entry) => entry.id === versionId);
  const next = [...document.savedVersions];
  // Insert the copy directly after the original so the creator sees it
  // adjacent to the source milestone.
  next.splice(idx + 1, 0, copy);
  return {
    ...document,
    savedVersions: next.slice(0, 12),
  };
}

export function deleteSceneVersion(document: PoseCraftDocument, versionId: string): PoseCraftDocument {
  return {
    ...document,
    savedVersions: document.savedVersions.filter((entry) => entry.id !== versionId),
  };
}

// ---------------------------------------------------------------------------
// PoseCraft Snapshot — frozen camera-composition handoff artifacts.
//
// A Snapshot is NOT a scene save. It freezes one exact camera composition
// (camera + figures + primitives + semanticSummary) at capture time as an
// IMMUTABLE copy. Rename is the only mutating op that touches a Snapshot
// (and only changes `name`). Scene autosave/flush stays independent and
// never PNG-captures. Cap ~48 snapshots per project.
// ---------------------------------------------------------------------------

export const POSECRAFT_SNAPSHOT_CAP = 48;

export function createSnapshot(
  document: PoseCraftDocument,
  projectId: string,
  imageAssetId: string,
  semanticSummary: string,
  name?: string,
): { document: PoseCraftDocument; snapshotId: string } {
  const scene = document.currentScene;
  const snapshotId = uid("snapshot");
  const now = nowIso();
  const customFigures = scene.figures.filter((f) => f.kind === "custom");
  const snapshot: PoseCraftSnapshot = {
    snapshotId,
    projectId,
    sceneId: scene.name,
    sceneRevision: scene.revision,
    name: (name?.trim() || `Snapshot ${scene.revision}`).slice(0, 200),
    imageAssetId,
    // Deep-frozen copies — structuredClone so later scene edits never mutate
    // the captured composition.
    camera: cloneScene(scene.camera),
    figures: cloneScene(scene.figures),
    primitives: cloneScene(scene.primitives),
    customFigures: cloneScene(customFigures),
    semanticSummary,
    createdAt: now,
    updatedAt: now,
  };
  const snapshots = [snapshot, ...(document.snapshots ?? [])].slice(0, POSECRAFT_SNAPSHOT_CAP);
  return {
    document: { ...document, snapshots, selectedSnapshotId: snapshotId },
    snapshotId,
  };
}

export function renameSnapshot(document: PoseCraftDocument, snapshotId: string, name: string): PoseCraftDocument {
  const next = name.trim().slice(0, 200);
  if (!next) return document;
  return {
    ...document,
    snapshots: (document.snapshots ?? []).map((s) =>
      s.snapshotId === snapshotId ? { ...s, name: next, updatedAt: nowIso() } : s,
    ),
  };
}

export function duplicateSnapshot(document: PoseCraftDocument, snapshotId: string): PoseCraftDocument {
  const source = (document.snapshots ?? []).find((s) => s.snapshotId === snapshotId);
  if (!source) return document;
  if ((document.snapshots ?? []).length >= POSECRAFT_SNAPSHOT_CAP) return document;
  const copy: PoseCraftSnapshot = {
    ...cloneScene(source),
    snapshotId: uid("snapshot"),
    name: `${source.name} Copy`.slice(0, 200),
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
  const idx = (document.snapshots ?? []).findIndex((s) => s.snapshotId === snapshotId);
  const next = [...(document.snapshots ?? [])];
  next.splice(idx + 1, 0, copy);
  return { ...document, snapshots: next.slice(0, POSECRAFT_SNAPSHOT_CAP), selectedSnapshotId: copy.snapshotId };
}

export function deleteSnapshot(document: PoseCraftDocument, snapshotId: string): PoseCraftDocument {
  const next = (document.snapshots ?? []).filter((s) => s.snapshotId !== snapshotId);
  const selectedSnapshotId =
    document.selectedSnapshotId === snapshotId ? null : document.selectedSnapshotId;
  return { ...document, snapshots: next, selectedSnapshotId };
}

export function selectSnapshot(document: PoseCraftDocument, snapshotId: string | null): PoseCraftDocument {
  if (snapshotId && !(document.snapshots ?? []).some((s) => s.snapshotId === snapshotId)) return document;
  return { ...document, selectedSnapshotId: snapshotId };
}

export function getSelectedSnapshot(document: PoseCraftDocument): PoseCraftSnapshot | null {
  const id = document.selectedSnapshotId;
  if (!id) return null;
  return (document.snapshots ?? []).find((s) => s.snapshotId === id) ?? null;
}

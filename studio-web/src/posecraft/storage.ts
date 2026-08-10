import { POSECRAFT_SCHEMA_VERSION } from "./types";
import type { PoseCraftDocument, PoseCraftScene } from "./types";
import { createDefaultDocument, createDefaultScene, migrateSceneToCurrent } from "./state";

export const POSECRAFT_STORAGE_KEY = "adept.posecraft.v1";

export type StorageLike = Pick<Storage, "getItem" | "setItem">;

function isSceneCandidate(value: unknown): value is Partial<PoseCraftScene> {
  return typeof value === "object" && value !== null;
}

function migrateScene(value: unknown): PoseCraftScene {
  if (!isSceneCandidate(value)) {
    return createDefaultScene();
  }
  const fallback = createDefaultScene();
  const merged: PoseCraftScene = {
    ...fallback,
    ...(value as PoseCraftScene),
    schemaVersion: POSECRAFT_SCHEMA_VERSION,
    stage: {
      ...fallback.stage,
      ...((value as PoseCraftScene).stage ?? {}),
    },
    camera: {
      ...fallback.camera,
      ...((value as PoseCraftScene).camera ?? {}),
      target: {
        ...fallback.camera.target,
        ...(((value as PoseCraftScene).camera ?? {}).target ?? {}),
      },
    },
    figures: Array.isArray((value as PoseCraftScene).figures)
      ? (value as PoseCraftScene).figures
      : fallback.figures,
    primitives: Array.isArray((value as PoseCraftScene).primitives)
      ? (value as PoseCraftScene).primitives
      : fallback.primitives,
  };
  // Run the backward-compat gate: fill missing joints, retain unsupported
  // legacy joints in figure.legacyJointData, set provenance.
  return migrateSceneToCurrent(merged);
}

export function parsePoseCraftDocument(raw: string | null): PoseCraftDocument {
  if (!raw) {
    return createDefaultDocument();
  }
  try {
    const parsed = JSON.parse(raw) as Partial<PoseCraftDocument>;
    return {
      schemaVersion: POSECRAFT_SCHEMA_VERSION,
      currentScene: migrateScene(parsed.currentScene),
      savedVersions: Array.isArray(parsed.savedVersions)
        ? parsed.savedVersions.map((version) => ({
            ...version,
            scene: migrateScene(version.scene),
          }))
        : [],
      // Snapshot contract migration: missing snapshots → [], missing
      // selectedSnapshotId → null. Frozen snapshots are never re-migrated.
      snapshots: Array.isArray(parsed.snapshots) ? parsed.snapshots : [],
      selectedSnapshotId: typeof parsed.selectedSnapshotId === "string" ? parsed.selectedSnapshotId : null,
    };
  } catch {
    return createDefaultDocument();
  }
}

export function loadPoseCraftDocument(storage: StorageLike | null | undefined): PoseCraftDocument {
  return parsePoseCraftDocument(storage?.getItem(POSECRAFT_STORAGE_KEY) ?? null);
}

export function savePoseCraftDocument(storage: StorageLike | null | undefined, document: PoseCraftDocument) {
  storage?.setItem(POSECRAFT_STORAGE_KEY, JSON.stringify(document));
}

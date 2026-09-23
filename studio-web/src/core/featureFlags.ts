export type ShelfStatus = "shelved_v1_1" | "active";
export type ShelfTarget = "v1_2_cloud" | null;

export type CreatorShelfFlag = {
  enabled: boolean;
  status: ShelfStatus;
  targetReturn: ShelfTarget;
};

export interface FeatureFlags {
  unifiedGenerate: boolean;
  story: boolean;
  sceneSheets: boolean;
  jobs: boolean;
  resources: boolean;
  futureRollout: boolean;
  /**
   * Creator-facing Spatial Map availability.
   * Shelved for Adept UI v1.1 — code/endpoints preserved; nav/CTAs gated only.
   */
  spatialMap: CreatorShelfFlag;
  /** Creator-facing PoseCraft availability. Shelved for Adept UI v1.1 / SceneCraft v1.2 Cloud. */
  poseCraft: CreatorShelfFlag;
  /** Fire3D reconstruction runtime. Shelved for Adept UI v1.1 / SceneCraft v1.2 Cloud. */
  fire3d: CreatorShelfFlag;
  /** SceneCraft product name reserved for v1.2 Cloud. Never creator-facing in v1.1. */
  sceneCraft: CreatorShelfFlag;
}

function envFlag(name: string, fallback = false): boolean {
  const value = import.meta.env[name];
  if (typeof value !== "string") return fallback;
  if (value.trim().toLowerCase() === "true") return true;
  if (value.trim().toLowerCase() === "false") return false;
  return fallback;
}

const SHELVED_V12: CreatorShelfFlag = Object.freeze({
  enabled: false,
  status: "shelved_v1_1" as const,
  targetReturn: "v1_2_cloud" as const,
});

export const featureFlags: Readonly<FeatureFlags> = Object.freeze({
  unifiedGenerate: envFlag("VITE_FEATURE_UNIFIED_GENERATE"),
  story: envFlag("VITE_FEATURE_STORY"),
  sceneSheets: envFlag("VITE_FEATURE_SCENE_SHEETS"),
  jobs: envFlag("VITE_FEATURE_JOBS"),
  resources: envFlag("VITE_FEATURE_RESOURCES"),
  futureRollout: envFlag("VITE_FEATURE_FUTURE_ROLLOUT"),
  // v1.1 product gate — do not scatter version strings; flip enabled here for return.
  spatialMap: SHELVED_V12,
  poseCraft: SHELVED_V12,
  fire3d: SHELVED_V12,
  sceneCraft: SHELVED_V12,
});

/** Single authority for creator-facing Spatial Map visibility / mount. */
export function isSpatialMapEnabled(): boolean {
  return featureFlags.spatialMap.enabled;
}

/** Single authority for creator-facing PoseCraft visibility / mount. */
export function isPoseCraftEnabled(): boolean {
  return featureFlags.poseCraft.enabled;
}

export function isFire3DEnabled(): boolean {
  return featureFlags.fire3d.enabled;
}

export function isSceneCraftEnabled(): boolean {
  return featureFlags.sceneCraft.enabled;
}

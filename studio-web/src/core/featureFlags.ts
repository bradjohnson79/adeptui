export interface FeatureFlags {
  unifiedGenerate: boolean;
  story: boolean;
  sceneSheets: boolean;
  jobs: boolean;
  resources: boolean;
  futureRollout: boolean;
}

function envFlag(name: string, fallback = false): boolean {
  const value = import.meta.env[name];
  if (typeof value !== "string") return fallback;
  if (value.trim().toLowerCase() === "true") return true;
  if (value.trim().toLowerCase() === "false") return false;
  return fallback;
}

export const featureFlags: Readonly<FeatureFlags> = Object.freeze({
  unifiedGenerate: envFlag("VITE_FEATURE_UNIFIED_GENERATE"),
  story: envFlag("VITE_FEATURE_STORY"),
  sceneSheets: envFlag("VITE_FEATURE_SCENE_SHEETS"),
  jobs: envFlag("VITE_FEATURE_JOBS"),
  resources: envFlag("VITE_FEATURE_RESOURCES"),
  futureRollout: envFlag("VITE_FEATURE_FUTURE_ROLLOUT"),
});

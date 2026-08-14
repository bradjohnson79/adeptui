/**
 * Shared generator plan helpers for Prop Creator (and later other products).
 *
 * Uses the committed shared plan in ./sharedGeneratorPlan.
 * Do not import Character Creator files. Do not start a second model registry.
 *
 * Prop product math: one candidate image per batch (not Character 4-view sheets).
 */
import {
  AUTO_SELECT_FAMILY,
  DEFAULT_CHARACTER_GENERATOR_PLAN,
  anyExplicitLocalFamilyEnabled,
  buildGeneratorSourcesPayload,
  clampBatchCount,
  hydratePlanFromPreferences,
  isAutoSelectActive,
  localFamilyLabel,
  mergePlanWithInventory,
  normalizeDiscoveredImageModel,
  planHasExecutableWork,
  providerDisplayName,
  returnToAutoSelectOnly,
  summarizeGenerationPlan,
  type CharacterApiModelPlan,
  type CharacterGeneratorPlan,
  type CharacterLocalFamilyPlan,
  type CharacterSheetGeneratorSourcesPayload,
  type GenerationPlanSummary,
  type NormalizedDiscoveredImageModel,
} from "./sharedGeneratorPlan";
import type { GeneratorOption } from "./types";

export {
  AUTO_SELECT_FAMILY,
  DEFAULT_CHARACTER_GENERATOR_PLAN,
  anyExplicitLocalFamilyEnabled,
  buildGeneratorSourcesPayload,
  clampBatchCount,
  hydratePlanFromPreferences,
  isAutoSelectActive,
  localFamilyLabel,
  mergePlanWithInventory,
  normalizeDiscoveredImageModel,
  planHasExecutableWork,
  providerDisplayName,
  returnToAutoSelectOnly,
  summarizeGenerationPlan,
};

export type {
  CharacterApiModelPlan,
  CharacterGeneratorPlan,
  CharacterLocalFamilyPlan,
  CharacterSheetGeneratorSourcesPayload,
  GenerationPlanSummary,
  NormalizedDiscoveredImageModel,
};

export type GeneratorPlan = CharacterGeneratorPlan;
export const DEFAULT_GENERATOR_PLAN = DEFAULT_CHARACTER_GENERATOR_PLAN;

export const GENERATOR_BATCH_MIN = 1;
export const GENERATOR_BATCH_MAX = 4;
export const GENERATOR_DEFAULT_BATCH_COUNT = 1;

export type StyleEnginePayload = {
  enabled: boolean;
  family?: string;
};

export type GeneratorSourcesPayload = CharacterSheetGeneratorSourcesPayload & {
  styleEngine?: StyleEnginePayload;
};

export type CandidatePlanSummary = GenerationPlanSummary & {
  /** Prop (and any 1-image-per-batch product): same as totalSheets. */
  totalImages: number;
};

/** Generation Plan totals are candidate images, not Character 4-view sheets. */
export function summarizeCandidatePlan(
  plan: CharacterGeneratorPlan,
  localOptions?: GeneratorOption[],
): CandidatePlanSummary {
  const summary = summarizeGenerationPlan(plan, localOptions);
  return { ...summary, totalImages: summary.totalSheets };
}

export function buildStyleEnginePayload(plan: CharacterGeneratorPlan): StyleEnginePayload {
  const enabled = !!plan.localEnabled && !!plan.stage2Enabled;
  return {
    enabled,
    family: enabled ? plan.stage2Family || undefined : undefined,
  };
}

export function buildPropGeneratorSourcesPayload(plan: CharacterGeneratorPlan): GeneratorSourcesPayload {
  const base = buildGeneratorSourcesPayload(plan);
  return {
    ...base,
    styleEngine: buildStyleEnginePayload(plan),
  };
}

export type GenerateScalarsFallback = {
  local_enabled: boolean;
  api_enabled: boolean;
  local_family: string;
  api_model: string;
  candidate_count: number;
};

/** Old generate scalars. candidate_count = sum of checked batches. */
export function fallbackGenerateScalars(plan: CharacterGeneratorPlan): GenerateScalarsFallback {
  const payload = buildGeneratorSourcesPayload(plan);
  const summary = summarizeCandidatePlan(plan);
  const firstLocal = payload.local?.find((row) => row.enabled);
  const firstApi = payload.api?.find((row) => row.enabled);
  return {
    local_enabled: payload.local != null && !!firstLocal,
    api_enabled: payload.api != null && !!firstApi,
    local_family: firstLocal?.family || "",
    api_model: firstApi?.model || firstApi?.modelId || "",
    candidate_count: summary.totalImages,
  };
}

export function propProvenanceLabel(opts: {
  sourceType: "local" | "api";
  modelLabel: string;
  providerLabel?: string;
  mode: string;
}): string {
  if (opts.sourceType === "local") {
    return `LOCAL — ${opts.modelLabel} — ${opts.mode}`;
  }
  const model = opts.providerLabel ? `${opts.providerLabel} / ${opts.modelLabel}` : opts.modelLabel;
  return `API — ${model} — ${opts.mode}`;
}

export function groupDiscoveredModelsByProvider(
  models: NormalizedDiscoveredImageModel[],
): Array<{ providerId: string; label: string; models: NormalizedDiscoveredImageModel[] }> {
  const preferred = ["kie", "fal", "wavespeed", "krea"];
  const map = new Map<string, NormalizedDiscoveredImageModel[]>();
  for (const model of models) {
    const key = model.providerId || "cloud";
    const list = map.get(key) || [];
    list.push(model);
    map.set(key, list);
  }
  const keys = [
    ...preferred.filter((id) => map.has(id)),
    ...[...map.keys()].filter((id) => !preferred.includes(id)),
  ];
  return keys.map((providerId) => ({
    providerId,
    label: providerDisplayName(providerId) || providerId,
    models: map.get(providerId) || [],
  }));
}

/**
 * Hydrate a plan from persisted Prop generator JSON.
 * Accepts the new local[]/api[]/styleEngine shape and the old scalar flags.
 */
export function hydrateGeneratorPlan(raw: unknown): CharacterGeneratorPlan {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_CHARACTER_GENERATOR_PLAN };
  }
  const src = raw as Record<string, unknown>;
  const hasNewShape =
    Array.isArray(src.local) ||
    Array.isArray(src.api) ||
    src.local === null ||
    src.api === null ||
    (src.styleEngine != null && typeof src.styleEngine === "object");

  if (hasNewShape) {
    const style =
      src.styleEngine && typeof src.styleEngine === "object"
        ? (src.styleEngine as Record<string, unknown>)
        : null;
    return hydratePlanFromPreferences(
      {
        local: src.local,
        api: src.api,
        stage2Enabled: style ? Boolean(style.enabled) : src.stage2Enabled,
        stage2Family: style ? String(style.family || "") : src.stage2Family,
      },
      [],
      [],
    );
  }

  const localEnabled = src.local_enabled !== false;
  const apiEnabled = Boolean(src.api_enabled);
  const localFamily = String(src.local_family || "").trim().toLowerCase();
  const apiModel = String(src.api_model || "").trim();
  return hydratePlanFromPreferences(
    {
      local: localEnabled
        ? localFamily && localFamily !== AUTO_SELECT_FAMILY
          ? { family: localFamily }
          : { family: AUTO_SELECT_FAMILY }
        : null,
      api: apiEnabled && apiModel ? [{ model: apiModel, enabled: true, batchCount: 1 }] : apiEnabled ? [] : null,
      stage2Enabled: Boolean(src.stage2Enabled),
      stage2Family: src.stage2Family,
    },
    [],
    [],
  );
}

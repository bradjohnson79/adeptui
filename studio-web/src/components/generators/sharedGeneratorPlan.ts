/**
 * Shared generator plan — per-source batches, Auto Select exclusivity,
 * and the Generation Plan shown before Generate.
 *
 * Committed shared copy for Prop Creator. Do not import Character Creator files.
 */
import {
  resolveCharacterGenerationMode,
  type GeneratorOption,
} from "./types";

export const CHARACTER_SHEET_BATCH_MIN = 1;
export const CHARACTER_SHEET_BATCH_MAX = 4;
/** Per-generator product default. Replaces the old global candidateCount=4. */
export const CHARACTER_SHEET_DEFAULT_BATCH_COUNT = 1;
export const CHARACTER_SHEET_VIEWS_PER_SHEET = 4;

export const AUTO_SELECT_FAMILY = "auto";

export type CharacterLocalFamilyPlan = {
  family: string;
  enabled: boolean;
  batchCount: number;
};

export type CharacterApiModelPlan = {
  /** Setup registry provider id, e.g. kie */
  providerId: string;
  /** Provider model id, e.g. nano-banana-pro */
  modelId: string;
  /** Dock/runtime id used by existing hosted enqueue, e.g. nano-banana-kie */
  model: string;
  displayName?: string;
  enabled: boolean;
  batchCount: number;
};

export type CharacterGeneratorPlan = {
  localEnabled: boolean;
  apiEnabled: boolean;
  autoSelect: { enabled: boolean; batchCount: number };
  localFamilies: CharacterLocalFamilyPlan[];
  apiModels: CharacterApiModelPlan[];
  stage2Enabled: boolean;
  stage2Family?: string;
};

export const DEFAULT_CHARACTER_GENERATOR_PLAN: CharacterGeneratorPlan = {
  localEnabled: true,
  apiEnabled: false,
  autoSelect: { enabled: true, batchCount: CHARACTER_SHEET_DEFAULT_BATCH_COUNT },
  localFamilies: [],
  apiModels: [],
  stage2Enabled: false,
  stage2Family: "",
};

export function clampBatchCount(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return CHARACTER_SHEET_DEFAULT_BATCH_COUNT;
  return Math.max(CHARACTER_SHEET_BATCH_MIN, Math.min(CHARACTER_SHEET_BATCH_MAX, Math.floor(n)));
}

export function anyExplicitLocalFamilyEnabled(plan: CharacterGeneratorPlan): boolean {
  return plan.localEnabled && plan.localFamilies.some((row) => row.enabled);
}

/** Auto Select is inactive whenever any explicit local family is checked. */
export function isAutoSelectActive(plan: CharacterGeneratorPlan): boolean {
  return plan.localEnabled && plan.autoSelect.enabled && !anyExplicitLocalFamilyEnabled(plan);
}

export function returnToAutoSelectOnly(plan: CharacterGeneratorPlan): CharacterGeneratorPlan {
  return {
    ...plan,
    localEnabled: true,
    autoSelect: { ...plan.autoSelect, enabled: true },
    localFamilies: plan.localFamilies.map((row) => ({ ...row, enabled: false })),
  };
}

export type PlannedSheet = {
  sourceType: "local" | "api";
  family?: string;
  providerId?: string;
  modelId?: string;
  model?: string;
  label: string;
  batchIndex: number;
  batchOf: number;
};

export type GenerationPlanSummary = {
  totalSheets: number;
  totalViews: number;
  apiSheetCount: number;
  localLines: { label: string; count: number }[];
  apiLines: { label: string; count: number }[];
  sheets: PlannedSheet[];
};

const LOCAL_FAMILY_LABELS: Record<string, string> = {
  illustrious: "Illustrious XL",
  qwen2512: "Qwen Image 2512",
  qwen: "Qwen Image 2512",
  zimage: "Z-Image Turbo",
  flux: "FLUX.1 Kontext",
  krea2: "Local Krea 2",
};

export function localFamilyLabel(family: string): string {
  return LOCAL_FAMILY_LABELS[family] || family;
}

export function apiModelLabel(row: Pick<CharacterApiModelPlan, "displayName" | "modelId" | "providerId">): string {
  const name = row.displayName || row.modelId || "Cloud model";
  if (name.includes(" — ")) return name;
  const provider = providerDisplayName(row.providerId);
  return provider ? `${name} — ${provider}` : name;
}

export function providerDisplayName(providerId: string): string {
  const id = (providerId || "").toLowerCase();
  if (id === "kie") return "Kie.ai";
  if (id === "fal") return "Fal";
  if (id === "wavespeed") return "Wavespeed";
  if (id === "krea") return "Krea";
  return providerId || "";
}

export function summarizeGenerationPlan(
  plan: CharacterGeneratorPlan,
  localOptions?: GeneratorOption[],
): GenerationPlanSummary {
  const sheets: PlannedSheet[] = [];
  const localLines: { label: string; count: number }[] = [];
  const apiLines: { label: string; count: number }[] = [];

  if (plan.localEnabled) {
    if (isAutoSelectActive(plan)) {
      const count = clampBatchCount(plan.autoSelect.batchCount);
      localLines.push({ label: "Auto Select", count });
      for (let i = 0; i < count; i += 1) {
        sheets.push({
          sourceType: "local",
          family: AUTO_SELECT_FAMILY,
          label: "Auto Select",
          batchIndex: i + 1,
          batchOf: count,
        });
      }
    } else {
      for (const row of plan.localFamilies) {
        if (!row.enabled) continue;
        const count = clampBatchCount(row.batchCount);
        const opt = localOptions?.find((o) => o.id === row.family);
        const label = opt?.label || localFamilyLabel(row.family);
        localLines.push({ label, count });
        for (let i = 0; i < count; i += 1) {
          sheets.push({
            sourceType: "local",
            family: row.family,
            label,
            batchIndex: i + 1,
            batchOf: count,
          });
        }
      }
    }
  }

  if (plan.apiEnabled) {
    for (const row of plan.apiModels) {
      if (!row.enabled) continue;
      const count = clampBatchCount(row.batchCount);
      const label = apiModelLabel(row);
      apiLines.push({ label, count });
      for (let i = 0; i < count; i += 1) {
        sheets.push({
          sourceType: "api",
          providerId: row.providerId,
          modelId: row.modelId,
          model: row.model,
          label,
          batchIndex: i + 1,
          batchOf: count,
        });
      }
    }
  }

  const apiSheetCount = sheets.filter((s) => s.sourceType === "api").length;
  return {
    totalSheets: sheets.length,
    totalViews: sheets.length * CHARACTER_SHEET_VIEWS_PER_SHEET,
    apiSheetCount,
    localLines,
    apiLines,
    sheets,
  };
}

export type CharacterSheetGeneratorSourcesPayload = {
  local: Array<{ family: string; enabled: boolean; batchCount: number }> | null;
  api: Array<{
    model: string;
    providerId: string;
    modelId: string;
    enabled: boolean;
    batchCount: number;
  }> | null;
  stage2Enabled?: boolean;
  stage2Family?: string;
};

export function buildGeneratorSourcesPayload(plan: CharacterGeneratorPlan): CharacterSheetGeneratorSourcesPayload {
  const local: CharacterSheetGeneratorSourcesPayload["local"] = plan.localEnabled
    ? [
        {
          family: AUTO_SELECT_FAMILY,
          enabled: isAutoSelectActive(plan),
          batchCount: clampBatchCount(plan.autoSelect.batchCount),
        },
        ...plan.localFamilies.map((row) => ({
          family: row.family,
          enabled: anyExplicitLocalFamilyEnabled(plan) ? row.enabled : false,
          batchCount: clampBatchCount(row.batchCount),
        })),
      ]
    : null;

  const api: CharacterSheetGeneratorSourcesPayload["api"] = plan.apiEnabled
    ? plan.apiModels.map((row) => ({
        model: row.model || row.modelId,
        providerId: row.providerId,
        modelId: row.modelId,
        enabled: row.enabled,
        batchCount: clampBatchCount(row.batchCount),
      }))
    : null;

  return {
    local,
    api,
    stage2Enabled: plan.localEnabled ? !!plan.stage2Enabled : false,
    stage2Family: plan.localEnabled && plan.stage2Enabled ? plan.stage2Family || undefined : undefined,
  };
}

export type NormalizedDiscoveredImageModel = {
  providerId: string;
  modelId: string;
  model: string;
  displayName: string;
  capabilities: string[];
  supportsReferences: boolean;
  availability: string;
  executable: boolean;
  credits?: number | null;
};

export function normalizeDiscoveredImageModel(
  raw: Record<string, unknown>,
  falBalance?: number | null,
): NormalizedDiscoveredImageModel | null {
  const providerId = String(raw.providerId || raw.provider || "").trim().toLowerCase();
  const modelId = String(raw.providerModelId || raw.modelId || "").trim();
  const dockId = String(raw.id || raw.dockModelId || raw.model || "").trim();
  const displayName = String(raw.displayName || raw.label || modelId || dockId || "").trim();
  if (!providerId && !modelId && !dockId) return null;
  const capabilities = Array.isArray(raw.capabilities)
    ? (raw.capabilities as unknown[]).map((c) => String(c))
    : [];
  const modality = String(raw.modality || "image").toLowerCase();
  if (modality && modality !== "image") return null;
  if (capabilities.length && !capabilities.some((c) => ["text_to_image", "edit", "image_to_image"].includes(c))) {
    return null;
  }
  const supportsReferences =
    Boolean(raw.supportsReferences) ||
    capabilities.includes("edit") ||
    capabilities.includes("image_to_image");
  const executable = raw.executable !== false && raw.selectable !== false;
  const credits = providerId === "fal" && typeof falBalance === "number" ? falBalance : null;
  const availability =
    String(raw.capabilityLabel || raw.readiness || raw.availability || "").trim() ||
    (credits == null ? "Connected" : "");
  return {
    providerId,
    modelId: modelId || dockId,
    model: dockId || modelId,
    displayName: displayName.includes(" — ") ? displayName : apiModelLabel({ displayName, modelId, providerId }),
    capabilities,
    supportsReferences,
    availability,
    executable,
    credits,
  };
}

export function mergePlanWithInventory(
  plan: CharacterGeneratorPlan,
  localOptions: GeneratorOption[],
  apiModels: NormalizedDiscoveredImageModel[],
): CharacterGeneratorPlan {
  const localFamilies = localOptions.map((opt) => {
    const prev = plan.localFamilies.find((row) => row.family === opt.id);
    return {
      family: opt.id,
      enabled: prev?.enabled ?? false,
      batchCount: clampBatchCount(prev?.batchCount),
    };
  });
  const nextApi = apiModels.map((m) => {
    const prev = plan.apiModels.find(
      (row) => row.providerId === m.providerId && row.modelId === m.modelId,
    );
    return {
      providerId: m.providerId,
      modelId: m.modelId,
      model: m.model,
      displayName: m.displayName,
      enabled: prev?.enabled ?? false,
      batchCount: clampBatchCount(prev?.batchCount),
    };
  });
  return { ...plan, localFamilies, apiModels: nextApi };
}

export function hydratePlanFromPreferences(
  raw: unknown,
  localOptions: GeneratorOption[],
  apiModels: NormalizedDiscoveredImageModel[],
): CharacterGeneratorPlan {
  const base = mergePlanWithInventory(DEFAULT_CHARACTER_GENERATOR_PLAN, localOptions, apiModels);
  if (!raw || typeof raw !== "object") return base;
  const src = raw as Record<string, unknown>;
  const local = src.local;
  const api = src.api;
  const localEnabled = local != null;
  const apiEnabled = api != null;

  let autoSelect = { ...base.autoSelect };
  let localFamilies = base.localFamilies.map((row) => ({ ...row }));
  if (Array.isArray(local)) {
    for (const item of local) {
      if (!item || typeof item !== "object") continue;
      const row = item as Record<string, unknown>;
      const family = String(row.family || "").trim().toLowerCase();
      const enabled = Boolean(row.enabled);
      const batchCount = clampBatchCount(row.batchCount);
      if (family === "" || family === AUTO_SELECT_FAMILY) {
        autoSelect = { enabled, batchCount };
        continue;
      }
      localFamilies = localFamilies.map((existing) =>
        existing.family === family ? { family, enabled, batchCount } : existing,
      );
    }
  } else if (local && typeof local === "object") {
    const family = String((local as Record<string, unknown>).family || "").trim().toLowerCase();
    if (!family || family === AUTO_SELECT_FAMILY) {
      autoSelect = { enabled: true, batchCount: CHARACTER_SHEET_DEFAULT_BATCH_COUNT };
    } else {
      autoSelect = { enabled: false, batchCount: CHARACTER_SHEET_DEFAULT_BATCH_COUNT };
      localFamilies = localFamilies.map((existing) =>
        existing.family === family
          ? { ...existing, enabled: true, batchCount: CHARACTER_SHEET_DEFAULT_BATCH_COUNT }
          : existing,
      );
    }
  }

  let apiRows = base.apiModels.map((row) => ({ ...row }));
  if (Array.isArray(api)) {
    for (const item of api) {
      if (!item || typeof item !== "object") continue;
      const row = item as Record<string, unknown>;
      const providerId = String(row.providerId || "").trim().toLowerCase();
      const modelId = String(row.modelId || "").trim();
      const model = String(row.model || "").trim();
      apiRows = apiRows.map((existing) => {
        const match =
          (providerId && modelId && existing.providerId === providerId && existing.modelId === modelId) ||
          (model && existing.model === model);
        if (!match) return existing;
        return {
          ...existing,
          enabled: Boolean(row.enabled),
          batchCount: clampBatchCount(row.batchCount),
        };
      });
    }
  }

  return {
    ...base,
    localEnabled,
    apiEnabled,
    autoSelect,
    localFamilies,
    apiModels: apiRows,
    stage2Enabled: Boolean(src.stage2Enabled),
    stage2Family: String(src.stage2Family || "") || "",
  };
}

export function planHasExecutableWork(plan: CharacterGeneratorPlan): boolean {
  return summarizeGenerationPlan(plan).totalSheets > 0;
}

export function firstPlannedGenerationMode(
  plan: CharacterGeneratorPlan,
  hasReference: boolean,
  localOptions: GeneratorOption[],
  apiOptions: GeneratorOption[],
): "profile_guided" | "reference_conditioned" | undefined {
  const summary = summarizeGenerationPlan(plan, localOptions);
  const first = summary.sheets[0];
  if (!first) return undefined;
  if (first.sourceType === "local") {
    if (first.family === AUTO_SELECT_FAMILY) return undefined;
    const opt = localOptions.find((o) => o.id === first.family);
    const mode = resolveCharacterGenerationMode(opt, hasReference);
    if (mode === "PROFILE_GUIDED") return "profile_guided";
    if (mode === "REFERENCE_CONDITIONED") return "reference_conditioned";
    return undefined;
  }
  const opt = apiOptions.find((o) => o.id === `${first.providerId}:${first.modelId}` || o.id === first.model);
  const mode = resolveCharacterGenerationMode(opt, hasReference);
  if (mode === "PROFILE_GUIDED") return "profile_guided";
  if (mode === "REFERENCE_CONDITIONED") return "reference_conditioned";
  return undefined;
}

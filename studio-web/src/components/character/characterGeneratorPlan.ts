/**
 * Character Creator generator plan — per-source batches, Auto Select exclusivity,
 * and the Generation Plan shown before Generate.
 *
 * Prop Creator keeps GeneratorSourceSelector. This module is Character-only.
 */
import {
  resolveCharacterGenerationMode,
  type GeneratorOption,
} from "../generators/types";

export const CHARACTER_SHEET_BATCH_MIN = 1;
export const CHARACTER_SHEET_BATCH_MAX = 4;
/** Per-generator product default. Replaces the old global candidateCount=4. */
export const CHARACTER_SHEET_DEFAULT_BATCH_COUNT = 1;
export const CHARACTER_SHEET_VIEWS_PER_SHEET = 4;

export const AUTO_SELECT_FAMILY = "auto";
/** Canonical Character Creator default generator (plan/state, not a checkbox). */
export const DEFAULT_GENERATOR_FAMILY = "qwen2512";
export const CRS_QWEN_FAMILY = "qwen2512";
export const CRS_GPT_IMAGE_2 = "gpt-image-2";
export type CrsGeneratorId = typeof CRS_QWEN_FAMILY | typeof CRS_GPT_IMAGE_2;

export function isGptImage2Row(row: { modelId?: string; model?: string; displayName?: string }): boolean {
  const blob = `${row.modelId || ""} ${row.model || ""} ${row.displayName || ""}`.toLowerCase();
  return blob.includes("gpt-image-2") || blob.includes("gpt_image_2");
}

export function selectedCrsGenerator(plan: CharacterGeneratorPlan): CrsGeneratorId {
  if (plan.apiEnabled && plan.apiModels.some((row) => row.enabled && isGptImage2Row(row))) {
    return CRS_GPT_IMAGE_2;
  }
  return CRS_QWEN_FAMILY;
}

export function setCrsGenerator(
  plan: CharacterGeneratorPlan,
  generator: CrsGeneratorId,
): CharacterGeneratorPlan {
  if (generator === CRS_GPT_IMAGE_2) {
    const hasGpt = plan.apiModels.some((row) => isGptImage2Row(row));
    const apiModels = hasGpt
      ? plan.apiModels.map((row) => ({
          ...row,
          enabled: isGptImage2Row(row),
          batchCount: 1,
        }))
      : [
          ...plan.apiModels.map((row) => ({ ...row, enabled: false, batchCount: 1 })),
          {
            providerId: "kie",
            modelId: "gpt-image-2",
            model: "gpt-image-2-kie",
            displayName: "GPT Image 2",
            enabled: true,
            batchCount: 1,
          },
        ];
    return {
      ...plan,
      localEnabled: false,
      apiEnabled: true,
      autoSelect: { ...plan.autoSelect, enabled: false, batchCount: 1 },
      localFamilies: plan.localFamilies.map((row) => ({ ...row, enabled: false, batchCount: 1 })),
      apiModels,
      stage2Enabled: false,
      defaultGenerator: CRS_QWEN_FAMILY,
    };
  }
  return {
    ...plan,
    localEnabled: true,
    apiEnabled: false,
    autoSelect: { ...plan.autoSelect, enabled: false, batchCount: 1 },
    localFamilies: plan.localFamilies.map((row) => ({
      ...row,
      enabled: row.family === CRS_QWEN_FAMILY || row.family === "qwen",
      batchCount: 1,
    })),
    apiModels: plan.apiModels.map((row) => ({ ...row, enabled: false, batchCount: 1 })),
    stage2Enabled: false,
    defaultGenerator: CRS_QWEN_FAMILY,
  };
}

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
  /** Explicit default when no stored prefs / idle plan. Never silently substitute. */
  defaultGenerator: string;
};

export const DEFAULT_CHARACTER_GENERATOR_PLAN: CharacterGeneratorPlan = {
  localEnabled: true,
  apiEnabled: false,
  autoSelect: { enabled: false, batchCount: CHARACTER_SHEET_DEFAULT_BATCH_COUNT },
  localFamilies: [],
  apiModels: [],
  stage2Enabled: false,
  stage2Family: "",
  defaultGenerator: DEFAULT_GENERATOR_FAMILY,
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

/** Auto Select alone is the old product default — treat as unspecified. */
export function planIsIdleForDefault(plan: CharacterGeneratorPlan): boolean {
  if (anyExplicitLocalFamilyEnabled(plan)) return false;
  if (plan.apiEnabled && plan.apiModels.some((row) => row.enabled)) return false;
  return true;
}

/** Enable Qwen as the explicit default when the plan has no executable work. */
export function applyDefaultGeneratorIfIdle(
  plan: CharacterGeneratorPlan,
  localOptions?: GeneratorOption[],
): CharacterGeneratorPlan {
  const next: CharacterGeneratorPlan = {
    ...plan,
    defaultGenerator: plan.defaultGenerator || DEFAULT_GENERATOR_FAMILY,
  };
  if (!planIsIdleForDefault(next)) return next;
  const family = next.defaultGenerator || DEFAULT_GENERATOR_FAMILY;
  if (!next.localFamilies.some((row) => row.family === family)) return next;
  if (!localFamilyIsExecutable(family, localOptions)) return next;
  return {
    ...next,
    localEnabled: true,
    autoSelect: { ...next.autoSelect, enabled: false },
    localFamilies: next.localFamilies.map((row) => ({
      ...row,
      enabled: row.family === family,
    })),
  };
}

export function primaryGeneratorValue(plan: CharacterGeneratorPlan): string {
  if (isAutoSelectActive(plan)) return AUTO_SELECT_FAMILY;
  const local = plan.localFamilies.find((row) => row.enabled);
  if (local) return local.family;
  const api = plan.apiEnabled ? plan.apiModels.find((row) => row.enabled) : undefined;
  if (api) return `api:${api.providerId}:${api.modelId}`;
  return plan.defaultGenerator || DEFAULT_GENERATOR_FAMILY;
}

export function setPrimaryLocalGenerator(
  plan: CharacterGeneratorPlan,
  family: string,
  batchCount?: number,
): CharacterGeneratorPlan {
  const count = clampBatchCount(batchCount ?? CHARACTER_SHEET_DEFAULT_BATCH_COUNT);
  if (family === AUTO_SELECT_FAMILY) {
    return {
      ...returnToAutoSelectOnly(plan),
      autoSelect: { enabled: true, batchCount: count },
    };
  }
  return {
    ...plan,
    localEnabled: true,
    apiEnabled: false,
    autoSelect: { ...plan.autoSelect, enabled: false },
    apiModels: plan.apiModels.map((row) => ({ ...row, enabled: false })),
    localFamilies: plan.localFamilies.map((row) => ({
      ...row,
      enabled: row.family === family,
      batchCount: row.family === family ? count : row.batchCount,
    })),
  };
}

export function primaryLocalBatchCount(plan: CharacterGeneratorPlan): number {
  if (isAutoSelectActive(plan)) return clampBatchCount(plan.autoSelect.batchCount);
  const local = plan.localFamilies.find((row) => row.enabled);
  if (local) return clampBatchCount(local.batchCount);
  return CHARACTER_SHEET_DEFAULT_BATCH_COUNT;
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
  if (id === "fal") return "fal.ai";
  if (id === "wavespeed") return "WaveSpeed.ai";
  if (id === "krea") return "Krea";
  return providerId || "";
}

/** Registry / discovery order. Headings use API labels when present. */
const PROVIDER_HEADING_ORDER = ["kie", "wavespeed", "fal"];

function providerLabelFromDiscoveredRow(raw: Record<string, unknown>, providerId: string): string {
  for (const key of ["providerDisplayName", "providerLabel", "providerName"] as const) {
    const value = raw[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  const label = String(raw.label || "");
  const sep = " — ";
  if (label.includes(sep)) {
    const tail = label.split(sep).pop()?.trim() || "";
    if (tail) return tail;
  }
  return providerDisplayName(providerId);
}

function adapterAvailableFromDiscoveredRow(raw: Record<string, unknown>): boolean {
  if (raw.adapterAvailable === true || raw.adapter_available === true) return true;
  if (raw.adapterAvailable === false || raw.adapter_available === false) return false;
  const readiness = String(raw.readiness || "").trim().toLowerCase();
  if (readiness === "requires adapter") return false;
  const capability = String(raw.capabilityLabel || raw.availability || "").trim().toLowerCase();
  if (capability === "unsupported") return false;
  return raw.executable !== false && raw.selectable !== false;
}

/**
 * True when the local runtime inventory reports at least one executable
 * family. Mirrors the backend Certified-executability gating: Auto Select and
 * explicit local families only count when an executable local source exists.
 * An undefined inventory is treated as unknown (legacy behavior preserved —
 * the plan never lies when no inventory data was provided).
 */
export function localInventoryHasExecutableSource(localOptions?: GeneratorOption[]): boolean {
  if (localOptions === undefined) return true;
  return localOptions.some((o) => o.executable !== false);
}

/** True when a specific family is executable per the inventory (unknown = yes). */
export function localFamilyIsExecutable(family: string, localOptions?: GeneratorOption[]): boolean {
  if (localOptions === undefined) return true;
  const opt = localOptions.find((o) => o.id === family);
  return opt ? opt.executable !== false : false;
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
      // CDX-009: Auto Select resolves to a local family at runtime — it is
      // only executable when the local inventory actually has one. With empty
      // or non-executable inventory (runtime down) it contributes zero sheets
      // instead of claiming sheets that fail at runtime.
      if (localInventoryHasExecutableSource(localOptions)) {
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
      }
    } else {
      for (const row of plan.localFamilies) {
        if (!row.enabled) continue;
        if (!localFamilyIsExecutable(row.family, localOptions)) continue;
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
  providerLabel?: string;
  capabilities: string[];
  supportsReferences: boolean;
  availability: string;
  executable: boolean;
  adapterAvailable?: boolean;
  accountAccessible?: boolean;
  credits?: number | null;
};

export type DiscoveredImageProviderGroup = {
  providerId: string;
  providerLabel: string;
  models: NormalizedDiscoveredImageModel[];
};

/** Group image rows by providerId. Heading only when the group has image rows and a configured key (DiscoveredApiModel.accountAccessible). */
export function groupDiscoveredImageModelsByProvider(
  models: NormalizedDiscoveredImageModel[],
): DiscoveredImageProviderGroup[] {
  const buckets = new Map<string, DiscoveredImageProviderGroup>();
  for (const model of models) {
    const providerId = (model.providerId || "").trim();
    if (!providerId) continue;
    const existing = buckets.get(providerId);
    if (existing) {
      existing.models.push(model);
      continue;
    }
    buckets.set(providerId, {
      providerId,
      providerLabel: model.providerLabel || providerDisplayName(providerId),
      models: [model],
    });
  }
  const rank = (id: string) => {
    const idx = PROVIDER_HEADING_ORDER.indexOf(id);
    return idx === -1 ? 100 + id.charCodeAt(0) : idx;
  };
  return [...buckets.values()]
    .filter((group) => group.models.length > 0 && group.models.some((m) => m.accountAccessible))
    .sort((a, b) => rank(a.providerId) - rank(b.providerId) || a.providerId.localeCompare(b.providerId));
}

export function cloudModelStatusLabel(model: NormalizedDiscoveredImageModel): string {
  if (!model.adapterAvailable) return "listed, adapter not ready";
  if (typeof model.credits === "number") return `${model.credits} credits`;
  const availability = (model.availability || "").trim();
  if (/certified/i.test(availability)) return "Certified";
  if (/^ready$/i.test(availability)) return "Ready";
  return availability || "Certified";
}

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
  const adapterAvailable = adapterAvailableFromDiscoveredRow(raw);
  const accountAccessible = raw.accountAccessible !== false && raw.account_accessible !== false;
  const availability =
    String(raw.capabilityLabel || raw.readiness || raw.availability || "").trim() ||
    (credits == null ? "Connected" : "");
  const providerLabel = providerLabelFromDiscoveredRow(raw, providerId);
  return {
    providerId,
    modelId: modelId || dockId,
    model: dockId || modelId,
    displayName: displayName.includes(" — ") ? displayName : apiModelLabel({ displayName, modelId, providerId }),
    providerLabel,
    capabilities,
    supportsReferences,
    availability,
    executable,
    adapterAvailable,
    accountAccessible,
    credits,
  };
}

function alignPlanWithInventory(
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

export function mergePlanWithInventory(
  plan: CharacterGeneratorPlan,
  localOptions: GeneratorOption[],
  apiModels: NormalizedDiscoveredImageModel[],
): CharacterGeneratorPlan {
  return alignPlanWithInventory(plan, localOptions, apiModels);
}

export function hydratePlanFromPreferences(
  raw: unknown,
  localOptions: GeneratorOption[],
  apiModels: NormalizedDiscoveredImageModel[],
): CharacterGeneratorPlan {
  // Overlay prefs onto an idle inventory-aligned plan. Do not start from the
  // Qwen default or a saved Illustrious/Auto/Cloud choice is clobbered.
  const base = alignPlanWithInventory(DEFAULT_CHARACTER_GENERATOR_PLAN, localOptions, apiModels);
  if (!raw || typeof raw !== "object") {
    return applyDefaultGeneratorIfIdle(base, localOptions);
  }
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

  const hydrated = applyDefaultGeneratorIfIdle(
    {
      ...base,
      localEnabled,
      apiEnabled,
      autoSelect,
      localFamilies,
      apiModels: apiRows,
      stage2Enabled: Boolean(src.stage2Enabled),
      stage2Family: String(src.stage2Family || "") || "",
      defaultGenerator: DEFAULT_GENERATOR_FAMILY,
    },
    localOptions,
  );
  return setCrsGenerator(hydrated, selectedCrsGenerator(hydrated));
}

export function planHasExecutableWork(plan: CharacterGeneratorPlan): boolean {
  return summarizeGenerationPlan(plan).totalSheets > 0;
}

/**
 * Executability truth for the Generate gate (CDX-009). Mirrors the backend
 * Certified-executability filtering:
 *
 * * An enabled Cloud model is executable (API rows come from discovery).
 * * An explicit local family is executable only when the inventory reports it
 *   (unknown inventory = legacy behavior).
 * * Auto Select is executable only when the local inventory has at least one
 *   executable family — empty/non-executable inventory (runtime down) yields
 *   zero executable sources.
 */
export function hasExecutableSource(
  plan: CharacterGeneratorPlan,
  localOptions?: GeneratorOption[],
): boolean {
  if (plan.apiEnabled && plan.apiModels.some((row) => row.enabled)) return true;
  if (!plan.localEnabled) return false;
  if (anyExplicitLocalFamilyEnabled(plan)) {
    return plan.localFamilies.some(
      (row) => row.enabled && localFamilyIsExecutable(row.family, localOptions),
    );
  }
  if (isAutoSelectActive(plan)) {
    return localInventoryHasExecutableSource(localOptions);
  }
  return false;
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

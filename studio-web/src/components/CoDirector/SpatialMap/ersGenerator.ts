/**
 * Narrow ERS generator catalog for Spatial Map (Express + Standard).
 * Official IDs are the live image-product / Kie catalog values — not invented.
 */
export type ErsGeneratorId = "qwen2512" | "gpt-image-2";

/** image-product officialModelId / modelFamilyPreference for local Qwen Image 2512. */
export const ERS_QWEN_OFFICIAL_ID = "qwen2512";
/** image-studio / production-dock provider id. */
export const ERS_QWEN_PROVIDER_ID = "qwen-image-2512-local";
/** Certified local image-to-image workflow key. ERS requires I2I (binding law):
 * the source environment image is consumed as pixels, never T2I. */
export const ERS_QWEN_WORKFLOW_KEY = "qwen2512.ref";

/** Kie dock / hostedModelId from the live catalog. */
export const ERS_GPT_HOSTED_ID = "gpt-image-2-kie";
/** Official Kie image-to-image Market id. Spatial Map / ERS must never pin T2I. */
export const ERS_GPT_OFFICIAL_ID = "gpt-image-2-image-to-image";
/** Legacy T2I Market id — forbidden for ERS; kept only to recognize old jobs. */
export const ERS_GPT_T2I_ID = "gpt-image-2-text-to-image";

/** Environment Reference Sheets use GPT Image 2 API only. */
export const ERS_GENERATOR_DEFAULT: ErsGeneratorId = "gpt-image-2";

/** Scene Creator Mini / Atlas engine catalogs may still list Qwen. ERS UI does not. */
export const ERS_GENERATOR_OPTIONS: ReadonlyArray<{ id: ErsGeneratorId; label: string }> = [
  { id: "qwen2512", label: "Qwen Image — Local" },
  { id: "gpt-image-2", label: "GPT Image 2 — API" },
];

/** Whether an ERS generator option may be selected at all. A generator that
 * cannot consume the source environment image (I2I) is surfaced as disabled at
 * selection time — the late runtime message alone is not honest enough (§17). */
export function ersGeneratorOptionDisabled(
  id: ErsGeneratorId,
  qwenI2IReady?: boolean | null,
  gptI2IReady?: boolean | null,
  gptReady?: boolean | null,
): boolean {
  if (id === "qwen2512" && qwenI2IReady === false) return true;
  // GPT: disable only when neither I2I nor general readiness is available.
  if (id === "gpt-image-2") {
    if (gptI2IReady === false && gptReady === false) return true;
    if (gptI2IReady === false && gptReady == null) return true;
  }
  return false;
}

export const QWEN_NOT_READY_MESSAGE =
  "Qwen Image is not ready. Choose GPT Image 2 or repair the local installation.";

export const QWEN_I2I_NOT_READY_MESSAGE =
  "Qwen Image image-to-image is not available for ERS. Environment Reference Sheets require a generator that consumes the source environment image (I2I). Choose GPT Image 2 or repair the local I2I workflow.";

export const GPT_NOT_READY_MESSAGE =
  "GPT Image 2 — Requires Setup. Add a Kie API key in Settings. Environment Reference Sheets cannot use Qwen.";

export const GPT_I2I_NOT_READY_MESSAGE =
  "GPT Image 2 — Requires Setup. Environment Reference Sheets use GPT Image 2 image-to-image only and cannot fall back to Qwen.";

export const ERS_NO_SOURCE_MESSAGE =
  "ERS requires an authoritative environment image. Attach an Atlas Shot to this Spatial Map first.";

export type ErsProviderRow = {
  id?: string;
  family?: string;
  modelId?: string;
  readiness?: string;
  source?: string;
  metadata?: { supports?: string[]; capabilities?: string[]; [key: string]: unknown };
};

function norm(value: unknown): string {
  return String(value || "").trim().toLowerCase();
}

function isReady(row: ErsProviderRow): boolean {
  return norm(row.readiness) === "ready";
}

function supportTokens(row: ErsProviderRow): string[] {
  const meta = row.metadata || {};
  const raw = [
    ...(Array.isArray(meta.supports) ? meta.supports : []),
    ...(Array.isArray(meta.capabilities) ? meta.capabilities : []),
  ];
  return raw.map((s) => norm(s));
}

function advertisesImageConditioning(tokens: string[]): boolean {
  return tokens.some((s) =>
    s.includes("reference") ||
    s === "edit" ||
    s.includes("image-to-image") ||
    s.includes("image_to_image") ||
    s.includes("image.edit")
  );
}

export function isQwenProvider(row: ErsProviderRow): boolean {
  const id = norm(row.id);
  const family = norm(row.family);
  return (
    id === ERS_QWEN_PROVIDER_ID ||
    family === ERS_QWEN_OFFICIAL_ID ||
    id.includes("qwen2512") ||
    family.includes("qwen2512") ||
    id === "qwen-image-2512-local"
  );
}

export function isGptImage2Provider(row: ErsProviderRow): boolean {
  const id = norm(row.id);
  const modelId = norm(row.modelId);
  return (
    id === ERS_GPT_HOSTED_ID ||
    id.includes("gpt-image-2") ||
    modelId.includes("gpt-image-2")
  );
}

export function isQwenReady(providers: ErsProviderRow[] | null | undefined): boolean {
  return (providers || []).some((row) => isQwenProvider(row) && isReady(row));
}

/** Qwen text-to-image availability (independent truth from I2I). */
export function isQwenT2IReady(providers: ErsProviderRow[] | null | undefined): boolean {
  return isQwenReady(providers);
}

/** Qwen image-to-image availability for ERS: the provider must be ready AND
 * advertise reference conditioning (the qwen2512.ref graph consumes the
 * source image via LoadImage + TextEncodeQwenImageEdit). */
export function isQwenI2IReady(providers: ErsProviderRow[] | null | undefined): boolean {
  return (providers || []).some((row) => {
    if (!isQwenProvider(row) || !isReady(row)) return false;
    return advertisesImageConditioning(supportTokens(row));
  });
}

export function isGptImage2Ready(providers: ErsProviderRow[] | null | undefined): boolean {
  return (providers || []).some((row) => isGptImage2Provider(row) && isReady(row));
}

/** GPT Image 2 ERS eligibility: ready AND explicit edit/reference capability. */
export function isGptImage2I2IReady(providers: ErsProviderRow[] | null | undefined): boolean {
  return (providers || []).some((row) => {
    if (!isGptImage2Provider(row) || !isReady(row)) return false;
    return advertisesImageConditioning(supportTokens(row));
  });
}

export function hasAuthoritativeEnvironmentSource(document: {
  originalEnvironmentReferenceAssetId?: string | null;
  backgroundAssetId?: string | null;
} | null | undefined): boolean {
  return Boolean(
    String(document?.originalEnvironmentReferenceAssetId || "").trim() ||
    String(document?.backgroundAssetId || "").trim(),
  );
}

export function buildErsStartContext(id: ErsGeneratorId): Record<string, unknown> {
  if (id === "gpt-image-2") {
    return {
      hostedModelId: ERS_GPT_HOSTED_ID,
      hosted_model_id: ERS_GPT_HOSTED_ID,
      kieImageModelId: ERS_GPT_OFFICIAL_ID,
      kie_image_model_id: ERS_GPT_OFFICIAL_ID,
      model: ERS_GPT_HOSTED_ID,
      source: "api",
      providerKind: "api",
      provider_kind: "api",
      // Env Creator regenerate defaults: one-pass full sheet (not component repair).
      forceFull: true,
      force_full: true,
      ers_force_full: true,
      ers_pipeline: "full_sheet",
      generationMode: "full_sheet_api",
      panel_task: "whole_sheet",
      panelTask: "whole_sheet",
      templateId: "ers.original.v1",
      collageTemplate: "ers.original.v1",
    };
  }
  return {
    model: ERS_QWEN_OFFICIAL_ID,
    modelFamilyPreference: ERS_QWEN_OFFICIAL_ID,
    model_family_preference: ERS_QWEN_OFFICIAL_ID,
    forceWorkflowKey: ERS_QWEN_WORKFLOW_KEY,
    force_workflow_key: ERS_QWEN_WORKFLOW_KEY,
    allow_force_workflow_key: true,
    lockModelFamily: true,
    source: "local",
    providerKind: "local",
    provider_kind: "local",
  };
}

export function resolveErsGeneratorFromModel(source: {
  model?: string | null;
  sourceKind?: "Local" | "API" | null;
}): ErsGeneratorId | null {
  const model = norm(source.model);
  if (
    model.includes("gpt-image-2") ||
    model === ERS_GPT_HOSTED_ID ||
    model === ERS_GPT_OFFICIAL_ID ||
    model === ERS_GPT_T2I_ID
  ) {
    return "gpt-image-2";
  }
  if (
    model === ERS_QWEN_OFFICIAL_ID ||
    model.startsWith("qwen2512") ||
    model.includes("qwen-image") ||
    model === ERS_QWEN_WORKFLOW_KEY
  ) {
    return "qwen2512";
  }
  return null;
}

export function formatErsProvenance(source: {
  model?: string | null;
  sourceKind?: "Local" | "API" | null;
}): string {
  const raw = String(source.model || "");
  if (raw.startsWith("env:")) {
    const label = raw.slice(4).trim();
    return label ? `Generating with ${label}` : "";
  }
  const resolved = resolveErsGeneratorFromModel(source);
  if (resolved === "gpt-image-2") return "Generating with GPT Image 2 · Image Edit";
  if (resolved === "qwen2512") return "Generating with Qwen Image · Reference";
  return "";
}

export function provenanceModelFromSelection(id: ErsGeneratorId): {
  model: string;
  sourceKind: "Local" | "API";
} {
  if (id === "gpt-image-2") {
    return { model: ERS_GPT_OFFICIAL_ID, sourceKind: "API" };
  }
  return { model: ERS_QWEN_WORKFLOW_KEY, sourceKind: "Local" };
}

export const ERS_PROMPT_OR_SOURCE_MESSAGE =
  "Describe the environment in the prompt, or attach a source/reference image.";

export const GPT_T2I_NOT_READY_MESSAGE =
  "GPT Image 2 — Requires Setup. Add a Kie API key in Settings to generate from a text prompt (text-to-image).";

/**
 * Block reason for ERS start.
 * - With source: GPT needs I2I readiness (gptI2IReady).
 * - Prompt-only (no source): GPT needs provider readiness (gptReady) for T2I.
 * - hasSource === false and hasPrompt !== true: ask for prompt or source.
 * - hasSource === null: do not enforce source (caller decides); still check provider.
 */
export function generatorBlockReason(
  id: ErsGeneratorId,
  qwenReady: boolean | null,
  gptReady: boolean | null,
  qwenI2IReady?: boolean | null,
  gptI2IReady?: boolean | null,
  hasSource?: boolean | null,
  hasPrompt?: boolean | null,
): string | null {
  const promptOk = hasPrompt === true;
  if (hasSource === false && !promptOk) return ERS_PROMPT_OR_SOURCE_MESSAGE;
  if (id === "qwen2512") {
    // Qwen ERS path remains I2I-only (local ref workflow).
    if (hasSource === false && promptOk) {
      return "Qwen Image cannot generate an ERS from text alone. Attach a source image or choose GPT Image 2.";
    }
    if (qwenI2IReady === false) return QWEN_I2I_NOT_READY_MESSAGE;
    if (qwenReady === false) return QWEN_NOT_READY_MESSAGE;
  }
  if (id === "gpt-image-2") {
    if (hasSource === true) {
      // Source attached → I2I readiness.
      if (gptI2IReady === false) return GPT_I2I_NOT_READY_MESSAGE;
      if (gptReady === false) return GPT_NOT_READY_MESSAGE;
    } else if (hasSource === false && promptOk) {
      // Explicit prompt-only → T2I via gptReady.
      if (gptReady === false) return GPT_T2I_NOT_READY_MESSAGE;
    } else {
      // hasSource null/undefined (legacy Spatial Map): keep I2I gate.
      if (gptI2IReady === false) return GPT_I2I_NOT_READY_MESSAGE;
      if (gptReady === false) return GPT_NOT_READY_MESSAGE;
    }
  }
  return null;
}

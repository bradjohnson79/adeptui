/** Shared Timeline generator capability helpers for Draft Mode and Video Reference. */

import { sectionsFromProductionControlModels } from "../modelRegistry/filterByModality";

export type DraftPathway = "none" | "local_live" | "cheap_preview" | "native_api_draft";

export type TimelineGeneratorOption = {
  id: string;
  label: string;
  aliases: string[];
  executable: boolean;
  capabilityLabel?: string;
  notes?: string;
  draftPathway: DraftPathway;
  supportsQueuedCancel: boolean;
  supportsRunningCancel: boolean;
  finalRequiresNewGeneration: boolean;
  supportsVideoReferences: boolean;
  supportsMultipleImageReferences: boolean;
  maximumReferenceImages: number;
  maximumReferenceVideos: number;
  supportedAspectRatios: string[];
  /** Live catalog boolean from timelineAdapters. Missing/undefined = unknown. */
  supportsTemperature?: boolean;
  supportsTextToVideo?: boolean;
  supportsImageToVideo?: boolean;
  supportsStartFrame?: boolean;
  maxDurationSec?: number | null;
  supportedDurations?: number[];
  supportedResolutions?: string[];
  draftResolution?: string | null;
  finalResolution?: string | null;
  executionType?: "local" | "api";
  locality?: string;
  adapterId?: string;
  inPaintStrategies?: string[];
};

/** PC model id → Timeline adapter id. Not a second product inventory. */
const GENERATOR_ID_ALIASES: Record<string, string> = {
  ltx: "ltx-local",
  "ltx-local": "ltx-local",
  "ltx-2.5-full": "ltx-local",
  "ltx-2.5-distilled": "ltx-local",
  "ltx-2.5-comfy": "ltx-local",
  "minimax-h3": "minimax-h3-t2v-local",
  "minimax-h3-local": "minimax-h3-t2v-local",
  "minimax-h3-t2v-local": "minimax-h3-t2v-local",
  "minimax-h3-i2v": "minimax-h3-i2v-local",
  "minimax-h3-i2v-local": "minimax-h3-i2v-local",
  "seedance-kie": "seedance-api",
  "seedance-fal": "seedance-api",
  "kling-fal": "kling-api",
  "kling-kie": "kling-api",
};

function asStringList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => String(item || "").trim()).filter(Boolean);
}

function asPathway(raw: unknown): DraftPathway {
  const v = String(raw || "none").toLowerCase();
  if (v === "local_live" || v === "cheap_preview" || v === "native_api_draft") return v;
  return "none";
}

export function generatorOptionsFromPayload(payload: Record<string, unknown>): TimelineGeneratorOption[] {
  const adapters = Array.isArray(payload?.timelineAdapters)
    ? (payload.timelineAdapters as Array<Record<string, unknown>>)
    : [];
  const out: TimelineGeneratorOption[] = [];
  for (const a of adapters) {
    const id = String(a.id || "");
    if (!id || id === "cert-stub-local") continue;
    out.push({
      id,
      label: String(a.label || id),
      aliases: asStringList(a.aliases),
      executable: a.executable !== false,
      capabilityLabel: a.capabilityLabel ? String(a.capabilityLabel) : undefined,
      notes: a.notes ? String(a.notes) : undefined,
      draftPathway: asPathway(a.draftPathway),
      supportsQueuedCancel: Boolean(a.supportsQueuedCancel),
      supportsRunningCancel: Boolean(a.supportsRunningCancel),
      finalRequiresNewGeneration: a.finalRequiresNewGeneration !== false,
      supportsVideoReferences: Boolean(a.supportsVideoReferences),
      supportsMultipleImageReferences: Boolean(a.supportsMultipleImageReferences),
      maximumReferenceImages: Number(a.maximumReferenceImages || 0),
      maximumReferenceVideos: Number(a.maximumReferenceVideos || 0),
      supportedAspectRatios: Array.isArray(a.supportedAspectRatios)
        ? a.supportedAspectRatios.map((x) => String(x))
        : [],
      // Pass through the live catalog boolean only. Do not coerce missing to true.
      supportsTemperature: typeof a.supportsTemperature === "boolean" ? a.supportsTemperature : undefined,
      maxDurationSec:
        typeof a.maxDurationSec === "number" && Number.isFinite(a.maxDurationSec)
          ? a.maxDurationSec
          : Array.isArray(a.supportedDurations)
            ? Math.max(
                ...a.supportedDurations.map((item) => Number(item)).filter((item) => Number.isFinite(item) && item > 0),
                0,
              ) || null
            : null,
      supportedDurations: Array.isArray(a.supportedDurations)
        ? a.supportedDurations.map((item) => Number(item)).filter((item) => Number.isFinite(item) && item > 0)
        : [],
      supportedResolutions: asStringList(a.supportedResolutions),
      draftResolution: a.draftResolution ? String(a.draftResolution) : null,
      finalResolution: a.finalResolution ? String(a.finalResolution) : null,
      supportsTextToVideo: typeof a.supportsTextToVideo === "boolean" ? a.supportsTextToVideo : undefined,
      supportsImageToVideo: typeof a.supportsImageToVideo === "boolean" ? a.supportsImageToVideo : undefined,
      supportsStartFrame: typeof a.supportsStartFrame === "boolean" ? a.supportsStartFrame : undefined,
      executionType: a.executionType === "api" ? "api" : "local",
      locality: a.locality ? String(a.locality) : undefined,
      adapterId: id,
      inPaintStrategies: asStringList(a.inPaintStrategies),
    });
  }
  return out;
}

function findAdapter(
  adapters: TimelineGeneratorOption[],
  modelId: string,
): TimelineGeneratorOption | undefined {
  const canonical = canonicalGeneratorId(modelId);
  return adapters.find(
    (item) =>
      item.id === modelId ||
      item.id === canonical ||
      item.aliases.includes(modelId) ||
      item.aliases.includes(canonical),
  );
}

/**
 * Production Control owns who exists and whether it is ready.
 * Timeline adapters own duration / T2V / I2V / resolution / refs.
 * Generators without a Timeline adapter are omitted (capability filter, not a second list).
 */
export function joinProductionControlVideoOptions(
  pcPayload: unknown,
  timelinePayload: Record<string, unknown>,
): TimelineGeneratorOption[] {
  const sections = sectionsFromProductionControlModels(pcPayload, "video");
  const models = [...sections.local, ...sections.api];
  const adapters = generatorOptionsFromPayload(timelinePayload);
  const gens = Array.isArray(timelinePayload.generators)
    ? (timelinePayload.generators as Array<Record<string, unknown>>)
    : [];
  const out: TimelineGeneratorOption[] = [];
  for (const model of models) {
    const adapter = findAdapter(adapters, model.id);
    if (!adapter) continue;
    const genRow = gens.find((row) => {
      const gid = String(row.id || "");
      return gid === model.id || gid === adapter.id || adapter.aliases.includes(gid);
    });
    const aliases = Array.from(new Set([adapter.id, model.id, ...adapter.aliases]));
    out.push({
      ...adapter,
      id: model.id,
      label: model.label,
      aliases,
      executable: model.executable === true,
      capabilityLabel: model.capabilityLabel,
      locality: model.locality,
      executionType: model.locality === "hosted" ? "api" : "local",
      adapterId: adapter.id,
      notes: [model.readiness, adapter.notes].filter(Boolean).join(" — ") || adapter.notes,
      inPaintStrategies: asStringList(genRow?.inPaintStrategies).length
        ? asStringList(genRow?.inPaintStrategies)
        : adapter.inPaintStrategies,
    });
  }
  return out;
}

export function canonicalGeneratorId(generatorId: string | null | undefined): string {
  const token = String(generatorId || "").trim();
  if (!token) return "";
  return GENERATOR_ID_ALIASES[token] || token;
}

export function resolveGeneratorOption(
  options: TimelineGeneratorOption[],
  ...candidateIds: Array<string | null | undefined>
): TimelineGeneratorOption | null {
  for (const raw of candidateIds) {
    const token = String(raw || "").trim();
    if (!token) continue;
    const canonical = canonicalGeneratorId(token);
    const match = options.find(
      (item) =>
        item.id === token ||
        item.id === canonical ||
        item.aliases.includes(token) ||
        item.aliases.includes(canonical),
    );
    if (match) return match;
  }
  return null;
}

export function supportsVideoMotionReferences(option: TimelineGeneratorOption | null | undefined): boolean {
  return Boolean(option?.supportsVideoReferences && (option.maximumReferenceVideos || 0) > 0);
}

export function draftPathwayCopy(pathway: DraftPathway): string {
  if (pathway === "local_live") return "Low-resolution preview. Stop before full render.";
  if (pathway === "cheap_preview") return "Generates an economical preview before the final request.";
  if (pathway === "native_api_draft") return "Uses the provider’s draft task, then a separate Final generation.";
  return "Draft unavailable — Final generation.";
}

export function promoteCopy(finalRequiresNewGeneration: boolean): string {
  return finalRequiresNewGeneration
    ? "Final starts a new generation from the same prompt and references."
    : "Promote this preview to the Timeline take.";
}

/** Shared Timeline generator capability helpers for Draft Mode and Video Reference. */

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
};

/** Mirrors studio-api director_timeline_w46 generation registry aliases. */
const GENERATOR_ID_ALIASES: Record<string, string> = {
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

/** Shared Timeline generator capability helpers for Draft Mode and Video Reference. */

export type DraftPathway = "none" | "local_live" | "cheap_preview" | "native_api_draft";

export type TimelineGeneratorOption = {
  id: string;
  label: string;
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
  supportedAspectRatios: string[];
};

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
      supportedAspectRatios: Array.isArray(a.supportedAspectRatios)
        ? a.supportedAspectRatios.map((x) => String(x))
        : [],
    });
  }
  return out;
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

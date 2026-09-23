/** Shared Timeline generator capability helpers for Draft Mode and Video Reference. */

export type DraftPathway = "none" | "local_live" | "cheap_preview" | "native_api_draft";

export type TimelineGeneratorOption = {
  id: string;
  label: string;
  aliases: string[];
  executable: boolean;
  /** True T2V (no start frame). Timeline R2V / I2V rows stay false. */
  supportsTextToVideo?: boolean;
  supportsImageToVideo?: boolean;
  supportsReferenceToVideo?: boolean;
  requiresLastFrame?: boolean;
  capabilityLabel?: string;
  notes?: string;
  disabledReason?: string;
  readiness?: string;
  draftPathway: DraftPathway;
  supportsQueuedCancel: boolean;
  supportsRunningCancel: boolean;
  supportsLivePreview?: boolean;
  supportsHonestProgress?: boolean;
  supportsIntermediateFrames?: boolean;
  remoteCancelCostNote?: string | null;
  finalRequiresNewGeneration: boolean;
  supportsVideoReferences: boolean;
  supportsMultipleImageReferences: boolean;
  maximumReferenceImages: number;
  maximumReferenceVideos: number;
  supportedAspectRatios: string[];
  /** From the Production Control / adapter join — not invented by the Timeline UI. */
  maxDurationSec?: number | null;
  supportedDurations?: number[];
  executionType?: string;
  locality?: string;
  supportsTurboLora: boolean;
  usesFastQuality: boolean;
  /** Generator produces its own synchronized audio (e.g. MiniMax H3 native audio). */
  audio_generation?: boolean;
  /** Registry-declared Inspector quality control. Never inferred from display names. */
  qualityControl?: "h3_megapixels" | "ltx_quality" | "";
  inPaintStrategies?: string[];
  supportsTimelineGeneration?: boolean;
  /** Per-surface workflow truth (t2v / i2v / multiFrame / r2v). */
  workflowCapabilities?: Record<string, {
    supported?: boolean;
    executable?: boolean;
    readiness?: string;
    reason?: string;
    runtime?: string | null;
    workflowKey?: string | null;
  }>;
};

/** Mirrors studio-api director_timeline_w46 generation registry aliases. */
const GENERATOR_ID_ALIASES: Record<string, string> = {
  "minimax-h3-local": "minimax-h3",
  "minimax-h3-t2v-local": "minimax-h3",
  "minimax-h3-i2v": "minimax-h3-i2v-local",
  "ltx-2.5": "ltx-2.5-distilled",
  "ltx-2.5-full": "ltx-2.5-full",
  "ltx-2.5-distilled": "ltx-2.5-distilled",
  "ltx-2.5-comfy": "ltx-2.5-comfy",
  "seedance-api": "seedance-2.0",
  "seedance-fal": "seedance-2.0",
  fal_seedance: "seedance-2.0",
  fal_seedance_25: "seedance-2.5",
};

function qualityControlFromUnknown(raw: unknown): TimelineGeneratorOption["qualityControl"] {
  const token = String(raw || "").trim();
  if (token === "h3_megapixels" || token === "ltx_quality") return token;
  return "";
}

function asStringList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => String(item || "").trim()).filter(Boolean);
}

function asPathway(raw: unknown): DraftPathway {
  const v = String(raw || "none").toLowerCase();
  if (v === "local_live" || v === "cheap_preview" || v === "native_api_draft") return v;
  return "none";
}

function usesFastQualityFlag(id: string, ...flags: unknown[]): boolean {
  for (const flag of flags) {
    if (flag !== undefined && flag !== null) return Boolean(flag);
  }
  return String(id).startsWith("ltx-2.5") || String(id).startsWith("minimax-h3");
}

function workflowCapsFromUnknown(
  raw: unknown,
): TimelineGeneratorOption["workflowCapabilities"] | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  return raw as TimelineGeneratorOption["workflowCapabilities"];
}

function indexPcWorkflowCapabilities(
  pc: { models?: Array<Record<string, unknown>> } | null | undefined,
): Map<string, NonNullable<TimelineGeneratorOption["workflowCapabilities"]>> {
  const map = new Map<string, NonNullable<TimelineGeneratorOption["workflowCapabilities"]>>();
  for (const model of pc?.models || []) {
    const id = String(model.id || "").trim();
    const caps = workflowCapsFromUnknown(model.workflowCapabilities);
    if (!id || !caps) continue;
    map.set(id, caps);
    const canonical = canonicalGeneratorId(id);
    if (canonical) map.set(canonical, caps);
  }
  return map;
}

export function joinProductionControlVideoOptions(
  pc: { models?: Array<Record<string, unknown>> } | null | undefined,
  timeline: Record<string, unknown>,
): TimelineGeneratorOption[] {
  /** Presenter over the backend-joined generators list. Does not invent IDs. */
  const gens = Array.isArray(timeline?.generators)
    ? (timeline.generators as Array<Record<string, unknown>>)
    : [];
  const adapters = generatorOptionsFromPayload(timeline);
  const adapterById = new Map(adapters.map((item) => [item.id, item]));
  const pcWorkflows = indexPcWorkflowCapabilities(pc);

  if (gens.length) {
    return gens
      .filter((row) => {
        const id = String(row.id || "");
        return Boolean(id) && id !== "cert-stub-local";
      })
      .map((row) => {
        const id = String(row.id || "");
        const adapterId = String(row.timelineAdapterId || canonicalGeneratorId(id) || "");
        const adapter =
          adapterById.get(adapterId) ||
          adapters.find((item) => item.aliases.includes(id) || item.id === id);
        const maxDurationSec = Number(row.maxDurationSec);
        return {
          id,
          label: String(row.label || adapter?.label || id),
          aliases: adapter?.aliases ?? [],
          executable: Boolean(row.executable),
          supportsTextToVideo: Boolean(
            row.supportsTextToVideo ?? adapter?.supportsTextToVideo,
          ),
          supportsImageToVideo: Boolean(
            row.supportsImageToVideo ?? adapter?.supportsImageToVideo,
          ),
          supportsReferenceToVideo: Boolean(
            (row as { supportsReferenceToVideo?: boolean }).supportsReferenceToVideo ??
              (adapter as { supportsReferenceToVideo?: boolean } | undefined)?.supportsReferenceToVideo,
          ),
          requiresLastFrame: Boolean(row.requiresLastFrame ?? adapter?.requiresLastFrame),
          capabilityLabel: String(row.capabilityLabel || ""),
          readiness: String(row.readiness || ""),
          disabledReason: String(row.disabledReason || ""),
          notes: String(row.disabledReason || row.notes || adapter?.notes || ""),
          maxDurationSec: Number.isFinite(maxDurationSec) && maxDurationSec > 0 ? maxDurationSec : null,
          supportedDurations: Array.isArray(row.supportedDurations)
            ? row.supportedDurations.map((item) => Number(item)).filter((n) => Number.isFinite(n) && n > 0)
            : adapter?.supportedDurations,
          executionType: String(row.executionType || adapter?.executionType || ""),
          locality: String(row.locality || adapter?.locality || ""),
          draftPathway: asPathway(row.draftPathway ?? adapter?.draftPathway),
          supportsQueuedCancel: Boolean(row.supportsQueuedCancel ?? adapter?.supportsQueuedCancel),
          supportsRunningCancel: Boolean(row.supportsRunningCancel ?? adapter?.supportsRunningCancel),
          supportsLivePreview: Boolean(row.supportsLivePreview ?? adapter?.supportsLivePreview),
          supportsHonestProgress: Boolean(row.supportsHonestProgress ?? adapter?.supportsHonestProgress),
          supportsIntermediateFrames: Boolean(
            row.supportsIntermediateFrames ?? adapter?.supportsIntermediateFrames,
          ),
          remoteCancelCostNote:
            (row.remoteCancelCostNote as string | null | undefined) ??
            (adapter?.remoteCancelCostNote as string | null | undefined) ??
            null,
          finalRequiresNewGeneration:
            row.finalRequiresNewGeneration !== undefined
              ? Boolean(row.finalRequiresNewGeneration)
              : adapter?.finalRequiresNewGeneration !== false,
          supportsVideoReferences: Boolean(
            row.supportsVideoReferences ?? adapter?.supportsVideoReferences,
          ),
          supportsMultipleImageReferences: Boolean(adapter?.supportsMultipleImageReferences),
          maximumReferenceImages: Number(adapter?.maximumReferenceImages || 0),
          maximumReferenceVideos: Number(
            row.maximumReferenceVideos ?? adapter?.maximumReferenceVideos ?? 0,
          ),
          supportedAspectRatios: Array.isArray(row.supportedAspectRatios)
            ? row.supportedAspectRatios.map((item) => String(item))
            : adapter?.supportedAspectRatios ?? [],
          supportsTurboLora: Boolean(row.supportsTurboLora ?? adapter?.supportsTurboLora),
          usesFastQuality: usesFastQualityFlag(id, row.usesFastQuality, adapter?.usesFastQuality),
          audio_generation: Boolean(
            row.audio_generation ?? row.supportsAudio ?? adapter?.audio_generation,
          ),
          qualityControl: qualityControlFromUnknown(
            row.qualityControl ?? adapter?.qualityControl,
          ),
          inPaintStrategies: asStringList(row.inPaintStrategies),
          supportsTimelineGeneration: row.supportsTimelineGeneration !== false,
          workflowCapabilities:
            workflowCapsFromUnknown(row.workflowCapabilities)
            || pcWorkflows.get(id)
            || pcWorkflows.get(canonicalGeneratorId(id))
            || (adapterId ? pcWorkflows.get(adapterId) : undefined),
        };
      });
  }
  return adapters.map((item) => ({
    ...item,
    workflowCapabilities:
      item.workflowCapabilities
      || pcWorkflows.get(item.id)
      || pcWorkflows.get(canonicalGeneratorId(item.id)),
  }));
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
      supportsTextToVideo: Boolean(a.supportsTextToVideo),
      supportsImageToVideo: Boolean(a.supportsImageToVideo),
      supportsReferenceToVideo: Boolean((a as { supportsReferenceToVideo?: boolean }).supportsReferenceToVideo),
      requiresLastFrame: Boolean(a.requiresLastFrame),
      capabilityLabel: a.capabilityLabel ? String(a.capabilityLabel) : undefined,
      notes: a.notes ? String(a.notes) : undefined,
      draftPathway: asPathway(a.draftPathway),
      supportsQueuedCancel: Boolean(a.supportsQueuedCancel),
      supportsRunningCancel: Boolean(a.supportsRunningCancel),
      supportsLivePreview: Boolean(a.supportsLivePreview),
      supportsHonestProgress: Boolean(a.supportsHonestProgress),
      supportsIntermediateFrames: Boolean(a.supportsIntermediateFrames),
      remoteCancelCostNote: a.remoteCancelCostNote ? String(a.remoteCancelCostNote) : null,
      finalRequiresNewGeneration: a.finalRequiresNewGeneration !== false,
      supportsVideoReferences: Boolean(a.supportsVideoReferences),
      supportsMultipleImageReferences: Boolean(a.supportsMultipleImageReferences),
      maximumReferenceImages: Number(a.maximumReferenceImages || 0),
      maximumReferenceVideos: Number(a.maximumReferenceVideos || 0),
      supportedAspectRatios: Array.isArray(a.supportedAspectRatios)
        ? a.supportedAspectRatios.map((x) => String(x))
        : [],
      supportsTurboLora: Boolean(a.supportsTurboLora),
      usesFastQuality: usesFastQualityFlag(id, a.usesFastQuality),
      audio_generation: Boolean(a.audio_generation ?? a.supportsAudio),
      qualityControl: qualityControlFromUnknown(a.qualityControl),
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

/** True when any named scene/batch engine can actually run. */
export function anyTimelineGeneratorExecutable(
  options: TimelineGeneratorOption[],
  ...candidateIds: Array<string | null | undefined>
): boolean {
  const seen = new Set<string>();
  for (const raw of candidateIds) {
    const token = String(raw || "").trim();
    if (!token || seen.has(token)) continue;
    seen.add(token);
    if (resolveGeneratorOption(options, token)?.executable === true) return true;
  }
  return false;
}

export function supportsVideoMotionReferences(option: TimelineGeneratorOption | null | undefined): boolean {
  return Boolean(option?.supportsVideoReferences && (option.maximumReferenceVideos || 0) > 0);
}

export function supportsTurboLora(option: TimelineGeneratorOption | null | undefined): boolean {
  return Boolean(option?.supportsTurboLora);
}

export function nextTurboLoraState(
  current: boolean | undefined,
  option: TimelineGeneratorOption | null | undefined,
): boolean {
  if (!supportsTurboLora(option)) return false;
  return Boolean(current);
}

export function usesFastQuality(option: TimelineGeneratorOption | null | undefined): boolean {
  const id = String(option?.id || "");
  return Boolean(option?.usesFastQuality || id.startsWith("ltx-2.5") || id.startsWith("minimax-h3"));
}

export function draftPathwayCopy(pathway: DraftPathway, option?: TimelineGeneratorOption | null): string {
  if (usesFastQuality(option)) {
    return "Fast finishes sooner. Quality takes longer and usually looks cleaner. Same picture size.";
  }
  if (pathway === "local_live") return "Low-resolution preview. Stop before full render.";
  if (pathway === "cheap_preview") return "Generates an economical preview before the final request.";
  if (pathway === "native_api_draft") return "Uses the provider’s draft task, then a separate Final generation.";
  return "Draft unavailable — Final generation.";
}

export function promoteCopy(
  finalRequiresNewGeneration: boolean,
  option?: TimelineGeneratorOption | null,
): string {
  if (usesFastQuality(option)) {
    return finalRequiresNewGeneration
      ? "Quality starts a new generation from the same prompt and references."
      : "Keep this Fast take on the Timeline.";
  }
  return finalRequiresNewGeneration
    ? "Final starts a new generation from the same prompt and references."
    : "Promote this preview to the Timeline take.";
}

/** Timeline generate sufficiency: R2V is enough. I2V-false is not a refuse. */
export function canTimelineGenerate(option: TimelineGeneratorOption | null | undefined): boolean {
  if (!option || option.executable === false) return false;
  if (option.supportsTimelineGeneration === false) return false;
  return Boolean(
    option.supportsReferenceToVideo || option.supportsImageToVideo || option.supportsTextToVideo,
  );
}

/** Timeline Re-Take sufficiency: same R2V-first law as generate. */
export function canTimelineRetake(option: TimelineGeneratorOption | null | undefined): boolean {
  if (!canTimelineGenerate(option)) return false;
  return true;
}

/** Image-frame / Visual-ref sufficiency: R2V or I2V, never I2V-only. */
export function timelineVisualSufficient(option: TimelineGeneratorOption | null | undefined): boolean {
  return Boolean(option?.supportsReferenceToVideo || option?.supportsImageToVideo);
}

export function generatorQualityControl(
  option: TimelineGeneratorOption | null | undefined,
): TimelineGeneratorOption["qualityControl"] {
  return option?.qualityControl || "";
}

export type NativeAudioStatus = "checking" | "supported" | "not_supported" | "offline" | "unavailable";

export type NativeAudioState = {
  status: NativeAudioStatus;
  modelSupported: boolean;
  runtimeAvailable: boolean;
  label: string;
  detail: string;
};

export function resolveNativeAudioState(
  option: TimelineGeneratorOption | null | undefined,
  loadState: "loading" | "ready" | "error",
): NativeAudioState {
  if (loadState === "loading") {
    return {
      status: "checking",
      modelSupported: false,
      runtimeAvailable: false,
      label: "Checking…",
      detail: "Reading the selected generator’s current audio capability.",
    };
  }
  if (loadState === "error" || !option) {
    return {
      status: "unavailable",
      modelSupported: false,
      runtimeAvailable: false,
      label: "UNAVAILABLE",
      detail: "Native audio cannot be confirmed until a generator is selected.",
    };
  }
  const modelSupported = Boolean(option.audio_generation);
  const readiness = String(option.readiness || "").toLowerCase();
  const runtimeAvailable = option.executable === true;
  const name = option.label || "This generator";
  if (!modelSupported) {
    return {
      status: "not_supported",
      modelSupported: false,
      runtimeAvailable,
      label: "NOT SUPPORTED",
      detail: `${name} does not provide native audio`,
    };
  }
  if (!runtimeAvailable || readiness.includes("offline")) {
    const offline = readiness.includes("offline");
    return {
      status: offline ? "offline" : "unavailable",
      modelSupported: true,
      runtimeAvailable: false,
      label: offline ? "OFFLINE" : "UNAVAILABLE",
      detail:
        option.disabledReason ||
        option.readiness ||
        `${name} supports native audio, but the current runtime is not available.`,
    };
  }
  return {
    status: "supported",
    modelSupported: true,
    runtimeAvailable: true,
    label: "SUPPORTED",
    detail: `${name} produces synchronized native audio`,
  };
}

/** Canonical generator runtime events. Mirror of studio-api video_runtime/runtime_events.py */

export const GENERATOR_EVENT_TYPES = [
  "PREPARING",
  "PROGRESS",
  "PREVIEW_FRAME",
  "PREVIEW_VIDEO",
  "FINALIZING",
  "COMPLETED",
  "CANCEL_REQUESTED",
  "CANCELLED",
  "CANCEL_REJECTED",
  "FAILED",
] as const;

export type GeneratorEventType = (typeof GENERATOR_EVENT_TYPES)[number];

export type PreviewRef = {
  url: string;
  mimeType: string;
  timestamp: string;
  sequence: number;
  width?: number | null;
  height?: number | null;
  expiresAt?: string | null;
  draft: boolean;
};

export type GeneratorRuntimeEvent = {
  executionId: string;
  jobId: string;
  provider: string;
  modelId: string;
  eventType: GeneratorEventType;
  createdAt: string;
  progressPercent?: number | null;
  stage?: string;
  preview?: PreviewRef | null;
  providerJobId?: string | null;
  outputAssetId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  cancelReason?: string | null;
  capabilities?: Record<string, unknown> | null;
};

export type RuntimeMonitorState = {
  jobId: string | null;
  eventType: GeneratorEventType | null;
  stage: string;
  progressPercent: number | null;
  previewUrl: string | null;
  previewMime: string | null;
  previewSequence: number;
  outputAssetId: string | null;
  errorMessage: string | null;
  cancelReason: string | null;
  capabilities: Record<string, unknown> | null;
};

export const EMPTY_RUNTIME_MONITOR: RuntimeMonitorState = {
  jobId: null,
  eventType: null,
  stage: "",
  progressPercent: null,
  previewUrl: null,
  previewMime: null,
  previewSequence: 0,
  outputAssetId: null,
  errorMessage: null,
  cancelReason: null,
  capabilities: null,
};

export function isPreviewEvent(event: GeneratorRuntimeEvent): boolean {
  return event.eventType === "PREVIEW_FRAME" || event.eventType === "PREVIEW_VIDEO";
}

export function isTerminalEvent(event: GeneratorRuntimeEvent): boolean {
  return (
    event.eventType === "COMPLETED" ||
    event.eventType === "CANCELLED" ||
    event.eventType === "FAILED"
  );
}

export function reduceRuntimeEvent(
  state: RuntimeMonitorState,
  event: GeneratorRuntimeEvent,
): RuntimeMonitorState {
  if (!event.jobId) return state;
  if (state.jobId && state.jobId !== event.jobId) return state;
  const seq = event.preview?.sequence ?? state.previewSequence;
  if (event.preview && seq < state.previewSequence) return state;
  return {
    jobId: event.jobId,
    eventType: event.eventType,
    stage: event.stage || state.stage,
    progressPercent: event.progressPercent ?? state.progressPercent,
    previewUrl: event.preview?.url || state.previewUrl,
    previewMime: event.preview?.mimeType || state.previewMime,
    previewSequence: event.preview ? seq : state.previewSequence,
    outputAssetId: event.outputAssetId ?? state.outputAssetId,
    errorMessage: event.errorMessage ?? state.errorMessage,
    cancelReason: event.cancelReason ?? state.cancelReason,
    capabilities: event.capabilities ?? state.capabilities,
  };
}

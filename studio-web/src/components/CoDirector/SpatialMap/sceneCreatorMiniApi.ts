import { api } from "../../../api";
import { ersGeneratorOptionDisabled } from "./ersGenerator";
import type { SpatialMapDocument } from "./types";

export const MINI_ASPECTS = ["1:1", "4:5", "3:2", "16:9", "9:16", "21:9"] as const;
export type MiniAspect = (typeof MINI_ASPECTS)[number];
export type MiniGeneratorId = "qwen2512" | "gpt-image-2";

export type MiniValidation = {
  state: "generating" | "validating" | "pass" | "continuity_failed" | "generation_failed" | "validation_unavailable";
  verdict?: string;
  fields?: Record<string, string>;
  summary?: string;
  model?: string;
  checkedAt?: string;
  reason?: string;
  pendingSince?: string;
};

export type MiniResult = {
  id: string;
  cameraId: string;
  cameraLabel: string;
  variation: string;
  jobId: string;
  assetId?: string | null;
  status: string;
  inLibrary?: boolean;
  libraryVisible?: boolean;
  error?: string | null;
  generator?: string;
  frameSize?: string;
  shotSize?: string | null;
  requiredCharacters?: string[];
  validation?: MiniValidation;
  selected?: boolean;
};

export type MiniTake = {
  id: string;
  takeNumber: number;
  generator: MiniGeneratorId;
  aspectRatio: string;
  mapVersion?: string;
  ersSheetId?: string;
  ersRevision?: string;
  cameras: Array<{ id: string; label: string }>;
  cameraPackets?: Record<string, unknown>;
  results: MiniResult[];
};

/** Product display state for a Mini result (Part 24). */
export function miniResultState(result: MiniResult): "generating" | "validating" | "pass" | "continuity_failed" | "generation_failed" | "validation_unavailable" {
  const status = String(result.status || "").toLowerCase();
  if (status === "failed" || status === "error" || status === "cancelled" || status === "canceled") {
    return "generation_failed";
  }
  if (status === "queued" || status === "generating") {
    return "generating";
  }
  const v = result.validation;
  if (!v) return "validating";
  if (v.state === "pass" || v.state === "continuity_failed" || v.state === "validation_unavailable") {
    return v.state;
  }
  return "validating";
}

/** Only PASS-validated, completed, non-library candidates are selectable. */
export function miniResultSelectable(result: MiniResult): boolean {
  if (result.inLibrary) return false;
  if (miniResultState(result) !== "pass") return false;
  return Boolean(result.assetId);
}

export function activeMiniCameras(document: SpatialMapDocument | null): Array<{
  id: string;
  label: string;
  cameraSlot: number;
}> {
  const cams = document?.cameras || [];
  return cams
    .filter((c) => c.visible !== false && (c.gridRow ?? -1) >= 0 && (c.gridColumn ?? -1) >= 0)
    .map((c) => ({
      id: c.id,
      label: c.cameraSlot >= 0 ? `C${c.cameraSlot + 1}` : c.label || "Camera",
      cameraSlot: c.cameraSlot,
    }))
    .sort((a, b) => a.cameraSlot - b.cameraSlot)
    .slice(0, 4);
}

export function miniOutputCount(cameraCount: number): number {
  return Math.max(0, Math.min(4, cameraCount)) * 2;
}

/** Prefer a generator the creator can actually run. Never keep a disabled selection. */
export function resolveReadyMiniGenerator(
  current: MiniGeneratorId,
  qwenI2IReady?: boolean | null,
  gptI2IReady?: boolean | null,
): MiniGeneratorId {
  if (!ersGeneratorOptionDisabled(current, qwenI2IReady, gptI2IReady)) return current;
  if (!ersGeneratorOptionDisabled("gpt-image-2", qwenI2IReady, gptI2IReady)) return "gpt-image-2";
  if (!ersGeneratorOptionDisabled("qwen2512", qwenI2IReady, gptI2IReady)) return "qwen2512";
  return current;
}

export const sceneCreatorMiniApi = {
  preview: (projectId: string, mapId: string) => api.spatialMap.miniTakePreview(projectId, mapId),
  create: (projectId: string, mapId: string, body: { generator: MiniGeneratorId; aspectRatio: string }) =>
    api.spatialMap.createMiniTake(projectId, mapId, body),
  get: (projectId: string, mapId: string, takeId: string) => api.spatialMap.getMiniTake(projectId, mapId, takeId),
  regenerate: (projectId: string, mapId: string, takeId: string, cameraId?: string | null) =>
    api.spatialMap.regenerateMiniTake(projectId, mapId, takeId, { cameraId }),
  sendToLibrary: (projectId: string, mapId: string, takeId: string, resultIds: string[]) =>
    api.spatialMap.sendMiniTakeToLibrary(projectId, mapId, takeId, { resultIds }),
};

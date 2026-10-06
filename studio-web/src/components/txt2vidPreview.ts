import type { Asset, Job } from "../types";

const STORAGE_PREFIX = "adept_txt2vid_preview_asset:";

export function txt2vidPreviewStorageKey(projectId: string): string {
  return `${STORAGE_PREFIX}${projectId}`;
}

export function readPersistedTxt2VidPreviewAssetId(projectId: string): string | null {
  if (!projectId) return null;
  try {
    const value = localStorage.getItem(txt2vidPreviewStorageKey(projectId));
    const trimmed = (value || "").trim();
    return trimmed || null;
  } catch {
    return null;
  }
}

export function persistTxt2VidPreviewAssetId(projectId: string, assetId: string): void {
  if (!projectId || !assetId) return;
  try {
    localStorage.setItem(txt2vidPreviewStorageKey(projectId), assetId);
  } catch {
    /* quota / private mode — in-memory state still binds the preview */
  }
}

export function clearPersistedTxt2VidPreviewAssetId(projectId: string): void {
  if (!projectId) return;
  try {
    localStorage.removeItem(txt2vidPreviewStorageKey(projectId));
  } catch {
    /* ignore */
  }
}

/** Only a successful Text to Video job may replace the page preview. */
export function extractTxt2VidOutputAssetId(job: Pick<Job, "params_json" | "status" | "kind">): string | null {
  const kind = String(job.kind || "").toLowerCase();
  if (kind && kind !== "txt2vid") return null;
  if (job.status && job.status !== "done") return null;
  try {
    const params = JSON.parse(job.params_json || "{}") as Record<string, unknown>;
    const single = params.output_asset_id || params.outputAssetId;
    if (typeof single === "string" && single.trim()) return single.trim();
    const list = params.outputAssetIds || params.output_asset_ids;
    if (Array.isArray(list)) {
      const first = list.find((item) => typeof item === "string" && item.trim());
      if (typeof first === "string") return first.trim();
    }
    return null;
  } catch {
    return null;
  }
}

export function latestSuccessfulTxt2VidAssetId(jobs: Array<Pick<Job, "params_json" | "status" | "kind" | "updated_at" | "created_at">>): string | null {
  const done = jobs
    .filter((job) => String(job.kind || "").toLowerCase() === "txt2vid" && job.status === "done")
    .sort((a, b) => String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")));
  for (const job of done) {
    const id = extractTxt2VidOutputAssetId(job);
    if (id) return id;
  }
  return null;
}

export function resolveTxt2VidPreviewAsset(
  projectId: string,
  assets: Asset[],
  assetId: string | null,
): Asset | null {
  if (!assetId) return null;
  const found = assets.find((asset) => asset.id === assetId);
  if (found) return found;
  return {
    id: assetId,
    project_id: projectId,
    tag: "txt2vid",
    kind: "video",
    filename: "text-to-video.mp4",
    path: "",
    comfy_name: "",
    created_at: "",
  };
}

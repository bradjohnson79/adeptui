import { api } from "../api";

const TERMINAL = new Set(["done", "failed", "cancelled", "canceled", "timed_out"]);

export type MagiUpscaleJobSnapshot = {
  jobId: string;
  status: string;
  progress: number;
  message: string;
  history: Record<string, unknown>;
  assetId: string | null;
  ok: boolean;
};

export function parseJobHistory(history: unknown): Record<string, unknown> {
  if (!history) return {};
  if (typeof history === "object") return history as Record<string, unknown>;
  if (typeof history === "string") {
    try {
      const parsed = JSON.parse(history);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return {};
}

export function jobAssetId(history: Record<string, unknown>): string | null {
  const id = history.assetId || history.output_asset_id || history.upscaledAssetId;
  return typeof id === "string" && id.trim() ? id.trim() : null;
}

export async function pollMagiUpscaleJob(
  projectId: string,
  jobId: string,
  opts?: {
    timeoutMs?: number;
    intervalMs?: number;
    onTick?: (snap: MagiUpscaleJobSnapshot) => void;
  },
): Promise<MagiUpscaleJobSnapshot> {
  const timeoutMs = opts?.timeoutMs ?? 30 * 60_000;
  const intervalMs = opts?.intervalMs ?? 2_000;
  const deadline = Date.now() + timeoutMs;
  let last: MagiUpscaleJobSnapshot = {
    jobId,
    status: "queued",
    progress: 0,
    message: "Queued",
    history: {},
    assetId: null,
    ok: false,
  };
  while (Date.now() < deadline) {
    const row = await api.magi.getFinishingJob(projectId, jobId);
    const history = parseJobHistory(row.history);
    const status = String(row.status || row.unifiedStatus || "");
    last = {
      jobId,
      status,
      progress: Number(row.progress || 0),
      message: String(row.message || history.message || ""),
      history,
      assetId: jobAssetId(history),
      ok: status === "done" && history.ok !== false,
    };
    opts?.onTick?.(last);
    if (TERMINAL.has(status)) {
      if (status !== "done") {
        last.ok = false;
      }
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("MAGI upscale is still working. Check Timeline again in a few minutes.");
}

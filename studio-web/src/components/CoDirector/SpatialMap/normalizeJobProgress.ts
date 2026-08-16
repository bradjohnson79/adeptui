/**
 * Generic Image Core / job progress normalizer.
 *
 * Genuine percent only when sampler N/M is present. Coarse Comfy buckets
 * (0.2 queued / 0.55 running / 1.0 done) and Kie fake +0.02/poll are NOT
 * shown as a real percent.
 */
export type NormalizedJobProgress = {
  status: string;
  progressPercent: number | null;
  stage: string;
  message: string;
  indeterminate: boolean;
  previewUrl: string | null;
  finalAssetId: string | null;
  genuineSampler: boolean;
};

const TERMINAL_DONE = new Set(["done", "completed", "succeeded"]);
const TERMINAL_FAIL = new Set(["failed", "error", "cancelled", "canceled", "interrupted", "dead"]);
const QUEUED = new Set(["queued", "pending", "waiting", "preparing"]);
const RUNNING = new Set(["running", "processing", "generating", "preview"]);
const COARSE = new Set([0, 0.2, 0.55, 1, 1.0]);

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function parsePreview(raw: unknown): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === "object") return asRecord(raw);
  if (typeof raw !== "string") return {};
  const text = raw.trim();
  if (!text) return {};
  try {
    return asRecord(JSON.parse(text));
  } catch {
    return {};
  }
}

function samplerPair(current: unknown, total: unknown): { current: number; total: number } | null {
  const c = Number(current);
  const t = Number(total);
  if (!Number.isFinite(c) || !Number.isFinite(t) || t < 4 || t > 200 || c < 0 || c > t) return null;
  return { current: c, total: t };
}

function samplerFromPreview(preview: Record<string, unknown>): { current: number; total: number } | null {
  return (
    samplerPair(preview.current_step ?? preview.currentStep, preview.total_steps ?? preview.totalSteps) ||
    samplerPair(preview.step ?? preview.steps_done, preview.steps ?? preview.max_steps)
  );
}

function samplerFromText(text: string): { current: number; total: number } | null {
  const raw = String(text || "");
  const labeled = raw.match(/(?:step|sampler|sampling)\s*(\d+)\s*\/\s*(\d+)/i);
  if (labeled) return samplerPair(labeled[1], labeled[2]);
  return null;
}

export function normalizeJobProgress(job: unknown): NormalizedJobProgress {
  const row = asRecord(job);
  const status = String(row.status || "").toLowerCase();
  const stageRaw = String(row.stage || "");
  const message = String(row.message || "");
  const progress = Number(row.progress);
  const preview = parsePreview(row.preview_json ?? row.previewJson ?? row.preview);
  const sampler = samplerFromPreview(preview) || samplerFromText(stageRaw) || samplerFromText(message);
  const asset = row.finalAssetId ?? row.final_asset_id ?? row.asset_id ?? row.assetId;
  const finalAssetId = typeof asset === "string" && asset ? asset : null;
  const previewCandidate = preview.url ?? preview.preview_url ?? preview.previewUrl ?? row.previewUrl;
  const previewUrl = typeof previewCandidate === "string" && previewCandidate ? previewCandidate : null;

  if (TERMINAL_DONE.has(status) || stageRaw.toLowerCase() === "completed") {
    return {
      status: "completed",
      progressPercent: 100,
      stage: "Complete",
      message: message || "Complete",
      indeterminate: false,
      previewUrl,
      finalAssetId,
      genuineSampler: false,
    };
  }

  if (TERMINAL_FAIL.has(status)) {
    const cancelled = status === "cancelled" || status === "canceled";
    return {
      status: cancelled ? "cancelled" : "failed",
      progressPercent: null,
      stage: cancelled ? "Cancelled" : "Failed",
      message,
      indeterminate: false,
      previewUrl,
      finalAssetId,
      genuineSampler: false,
    };
  }

  if (QUEUED.has(status) || stageRaw.toLowerCase() === "queued") {
    return {
      status: "queued",
      progressPercent: null,
      stage: "Queued",
      message: message || "Preparing…",
      indeterminate: true,
      previewUrl,
      finalAssetId,
      genuineSampler: false,
    };
  }

  if (sampler) {
    const pct = Math.max(0, Math.min(100, Math.round((sampler.current / sampler.total) * 100)));
    return {
      status: "running",
      progressPercent: pct,
      stage: `Generating · ${sampler.current}/${sampler.total}`,
      message: message || stageRaw || "Generating",
      indeterminate: false,
      previewUrl,
      finalAssetId,
      genuineSampler: true,
    };
  }

  // Coarse 0.2/0.55/1.0, Kie +0.02 drift, or any other non-sampler number:
  // never invent a percent such as 53.
  const coarse =
    (Number.isFinite(progress) && progress >= 1) || COARSE.has(progress)
      ? progress >= 1
        ? "Complete"
        : progress >= 0.55 || RUNNING.has(status)
          ? "Generating"
          : "Queued"
      : RUNNING.has(status)
        ? "Generating"
        : "Queued";

  return {
    status: RUNNING.has(status) ? "running" : status || "running",
    progressPercent: null,
    stage: coarse,
    message: message || (coarse === "Generating" ? "Generating…" : "Preparing…"),
    indeterminate: coarse !== "Complete",
    previewUrl,
    finalAssetId,
    genuineSampler: false,
  };
}

import { shortJobMessage } from "../../generators/shortJobMessage";

export type PropCandidate = {
  id: string;
  prop_id: string;
  index: number;
  job_id: string;
  asset_id?: string | null;
  status: "queued" | "generating" | "complete" | "failed";
  source: "local" | "api";
  family: string;
  model: string;
  seed?: number | null;
  provenance_label: string;
  conditioning: "reference_conditioned" | "description_guided";
  take_label: string;
  error?: string;
  /** Live Job.progress (0-1) copied by GET hydration. Absent when no job reported one. */
  progress?: number | null;
};

export type PropGeneratorPersist = {
  local_enabled?: boolean;
  api_enabled?: boolean;
  local_family?: string;
  api_model?: string;
  local?: Array<{ family: string; enabled: boolean; batchCount: number }> | null;
  api?: Array<{
    model: string;
    providerId: string;
    modelId: string;
    enabled: boolean;
    batchCount: number;
  }> | null;
  styleEngine?: { enabled: boolean; family?: string };
  stage2Enabled?: boolean;
  stage2Family?: string;
};

export type PropEntity = {
  id: string;
  project_id: string;
  tag: string;
  display_label: string;
  library_asset_id: string;
  notes: string;
  visual_style: string;
  description: string;
  reference_asset_id?: string | null;
  approved_asset_id?: string | null;
  candidates: PropCandidate[];
  generator?: PropGeneratorPersist;
  created_at?: string;
  updated_at?: string;
};

export type PropCreatorWorkspace = {
  props: PropEntity[];
  selected_prop: PropEntity | null;
  api_generation_available: boolean;
  local_families: Array<{ id: string; label: string; executable?: boolean; supportsReferences?: boolean }>;
};

/** Terminal error statuses already returned by prop GET job hydration. */
export const CANDIDATE_FAIL_STATUSES = ["failed", "error", "cancelled", "missing"] as const;

function normStatus(status?: string | null): string {
  return String(status || "").trim().toLowerCase();
}

export function candidateIsFailed(c: PropCandidate): boolean {
  return (CANDIDATE_FAIL_STATUSES as readonly string[]).includes(normStatus(c.status));
}

/** A look is finished when it succeeded or reached a terminal error. */
export function candidateIsFinished(c: PropCandidate): boolean {
  const status = normStatus(c.status);
  return status === "complete" || status === "done" || !!c.asset_id || candidateIsFailed(c);
}

export function candidateErrorMessage(c: PropCandidate): string {
  return shortJobMessage(c.error || "");
}

export function candidateProgress(candidates: PropCandidate[]): { done: number; total: number; percent: number } {
  const total = candidates.length;
  // Failed looks count as finished so a failed batch does not hang at 0 of N.
  const done = candidates.filter(candidateIsFinished).length;
  return { done, total, percent: total ? Math.round((done / total) * 100) : 0 };
}

/** Progress totals = sum of checked batches when live candidates have not arrived yet. */
export function plannedProgress(
  candidates: PropCandidate[],
  plannedTotal: number,
): { done: number; total: number; percent: number } {
  const live = candidateProgress(candidates);
  const total = live.total > 0 ? live.total : Math.max(0, plannedTotal);
  const done = live.done;
  return { done, total, percent: total ? Math.round((done / total) * 100) : 0 };
}

const LIVE_GEN_STATUSES = ["generating", "running"] as const;

/** Hide unless a live candidate status exists, or generating with at least one candidate. */
export function shouldShowPropProgress(args: {
  generating: boolean;
  candidates: PropCandidate[];
}): boolean {
  const hasLive = args.candidates.some((c) =>
    (LIVE_GEN_STATUSES as readonly string[]).includes(normStatus(c.status)),
  );
  if (hasLive) return true;
  return Boolean(args.generating && args.candidates.length);
}

/** Live Job.progress copied onto unfinished candidates. Null when none reported. */
export function surfacedJobProgress(candidates: PropCandidate[]): number | null {
  const live = candidates.filter((c) => !candidateIsFinished(c));
  const reported = live.filter((c) => typeof c.progress === "number" && Number.isFinite(c.progress));
  if (!reported.length) return null;
  return reported.reduce((sum, c) => sum + Number(c.progress), 0) / reported.length;
}

export function displayProgressPercent(candidates: PropCandidate[], plannedTotal: number): number {
  const job = surfacedJobProgress(candidates);
  if (job != null) {
    const pct = job <= 1 ? job * 100 : job;
    return Math.round(Math.max(0, Math.min(100, pct)));
  }
  return plannedProgress(candidates, plannedTotal).percent;
}

/** Queued look with no job.progress after this many ms while generating is treated as failed. */
export const PROP_QUEUED_NO_HYDRATE_MS = 30_000;

export function candidateHasHydrate(c: PropCandidate): boolean {
  return typeof c.progress === "number" && Number.isFinite(c.progress) && c.progress > 0;
}

/** generating===true + still queued + no hydrate past timeout → fail so UI never pins 0% 0 of 1. */
export function staleQueuedNoHydrate(
  c: PropCandidate,
  generating: boolean,
  elapsedMs: number,
  timeoutMs: number = PROP_QUEUED_NO_HYDRATE_MS,
): boolean {
  if (!generating) return false;
  if (normStatus(c.status) !== "queued") return false;
  if (candidateHasHydrate(c)) return false;
  return elapsedMs >= timeoutMs;
}

export function markStaleQueuedFailed(
  candidates: PropCandidate[],
  generating: boolean,
  elapsedMs: number,
  timeoutMs: number = PROP_QUEUED_NO_HYDRATE_MS,
): PropCandidate[] {
  let changed = false;
  const next = candidates.map((c) => {
    if (!staleQueuedNoHydrate(c, generating, elapsedMs, timeoutMs)) return c;
    changed = true;
    return {
      ...c,
      status: "failed" as const,
      error: c.error || "Generation stalled before progress was reported. Retry this look.",
    };
  });
  return changed ? next : candidates;
}

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
  return String(c.error || "").trim();
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

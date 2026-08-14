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
  generator?: {
    local_enabled: boolean;
    api_enabled: boolean;
    local_family: string;
    api_model: string;
  };
  created_at?: string;
  updated_at?: string;
};

export type PropCreatorWorkspace = {
  props: PropEntity[];
  selected_prop: PropEntity | null;
  api_generation_available: boolean;
  local_families: Array<{ id: string; label: string; executable?: boolean; supportsReferences?: boolean }>;
};

export function candidateProgress(candidates: PropCandidate[]): { done: number; total: number; percent: number } {
  const total = candidates.length;
  const done = candidates.filter((c) => c.status === "complete" || c.status === "failed").length;
  return { done, total, percent: total ? Math.round((done / total) * 100) : 0 };
}

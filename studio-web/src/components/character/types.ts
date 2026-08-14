/**
 * Canonical shared character types for both Character Creator surfaces
 * (Co-Director Express + standalone Character Creator). One authoritative
 * schema — do not fork per-surface types.
 */

export type CharacterProfile = {
  id: string;
  project_id?: string;
  name: string;
  role?: string;
  description?: string;
  visual_description?: string;
  visual_style?: string;
  gender_presentation?: string;
  apparent_age?: string;
  species_or_type?: string;
  body_type?: string;
  height_description?: string;
  status?: string;
  approval_status?: string;
  active_version_id?: string | null;
  active_voice_profile_id?: string | null;
  active_wardrobe_id?: string | null;
  hair?: { primary_color?: string; canonical_style?: string; length?: string };
  personality?: Record<string, unknown>;
  updated_at?: string;
  created_at?: string;
};

export type CharacterReference = {
  id: string;
  asset_id?: string | null;
  reference_role?: string;
  approval_status?: string;
  canonical?: boolean;
  source_type?: string;
  filename?: string;
};

export type CharacterViewJob = {
  jobId?: string;
  role?: string;
  viewIndex?: number;
  status?: string;
  assetId?: string | null;
  seed?: number;
  modelFamily?: string;
  workflowKey?: string;
  referenceLocked?: boolean;
};

export type CharacterCandidate = {
  assetId?: string | null;
  jobId?: string;
  label?: string;
  status?: string;
  candidateIndex?: number;
  generator?: string | null;
  provider?: string | null;
  model?: string | null;
  modelVariant?: string | null;
  workflowKey?: string | null;
  seed?: number | null;
  referenceAssetIds?: string[];
  compositionIntent?: string | null;
  referenceFidelityMode?: string | null;
  referenceLocked?: boolean;
  lowReferenceFidelity?: boolean;
  /** Composed canonical 4-view sheet asset id (creator-facing). */
  sheetAssetId?: string | null;
  /** Per-view job states (front / side / back / close-up). */
  viewJobs?: CharacterViewJob[];
  /** Error message when the candidate failed. */
  error?: string | null;
  /** local | api — never infer from a truthy Comfy provider string. */
  providerKind?: "local" | "api";
  /** PROFILE_GUIDED | REFERENCE_CONDITIONED */
  conditioningMode?: "PROFILE_GUIDED" | "REFERENCE_CONDITIONED" | null;
  selectedSource?: string | null;
  hostedModelId?: string | null;
};

/** Truthful per-candidate generation stage derived from backend state. */
export type CandidateStage =
  | "queued"
  | "generating"
  | "assembling"
  | "complete"
  | "failed";

/** Friendly label for each sheet-view role. */
export const SHEET_VIEW_LABELS: Record<string, string> = {
  hero_identity: "Front",
  full_body_side_left: "Side",
  full_body_back: "Back",
  closeup_front: "Close-Up",
};

/** Derive a truthful stage for a candidate from its backend state. */
export function candidateStage(c: CharacterCandidate): CandidateStage {
  const views = c.viewJobs || [];
  const anyFailed =
    c.status === "failed" ||
    views.some((v) => ["failed", "error", "cancelled", "missing"].includes(v.status || ""));
  if (anyFailed) return "failed";
  if (c.status === "done" || c.sheetAssetId || c.assetId) return "complete";
  if (c.status === "assembling") return "assembling";
  // All views done but no composed sheet yet → assembling.
  if (views.length && views.every((v) => v.status === "done" || v.assetId) && !c.sheetAssetId) {
    return "assembling";
  }
  const anyRunning = views.some((v) => v.status === "running");
  if (anyRunning || c.status === "generating") return "generating";
  return "queued";
}

/** Aggregate batch progress across all candidates (honest, view-based). */
export function batchProgress(candidates: CharacterCandidate[]): {
  doneViews: number;
  totalViews: number;
  doneSheets: number;
  totalSheets: number;
  percent: number;
} {
  let doneViews = 0;
  let totalViews = 0;
  let doneSheets = 0;
  const totalSheets = candidates.length;
  for (const c of candidates) {
    const views = c.viewJobs || [];
    totalViews += views.length;
    doneViews += views.filter((v) => v.status === "done" || v.assetId).length;
    if (candidateStage(c) === "complete") doneSheets += 1;
  }
  // Percent reflects real completed units: finished views + a finished sheet
  // counts its assembly. No fake smoothing.
  const units = totalViews + totalSheets; // views + one assembly step per sheet
  const done = doneViews + doneSheets;
  const percent = units > 0 ? Math.round((done / units) * 100) : 0;
  return { doneViews, totalViews, doneSheets, totalSheets, percent };
}

export type {
  GeneratorOption,
  GeneratorSourceKind,
  GeneratorSourceState,
} from "../generators/types";

export const CHARACTER_STYLE_OPTIONS = [
  { value: "", label: "Select a style…" },
  { value: "live_action", label: "Live Action" },
  { value: "anime", label: "Anime" },
  { value: "realistic_anime", label: "Realistic Anime" },
  { value: "stylized_3d_animation", label: "Stylized 3D" },
  { value: "stop_motion", label: "Stop Motion" },
  { value: "claymation", label: "Claymation" },
  { value: "graphic_novel", label: "Comic / Graphic Novel" },
  { value: "watercolor", label: "Watercolor" },
  { value: "oil_painting", label: "Oil Painting" },
  { value: "documentary_realism", label: "Photorealistic" },
  { value: "cartoon", label: "Cartoon" },
  { value: "concept_art", label: "Concept Art" },
];

export const CHARACTER_GENDER_OPTIONS = [
  { value: "", label: "Select…" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "non_binary", label: "Non-binary" },
  { value: "androgynous", label: "Androgynous" },
  { value: "other", label: "Other" },
];

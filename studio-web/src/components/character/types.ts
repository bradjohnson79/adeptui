/**
 * Canonical shared character types for both Character Creator surfaces
 * (Co-Director Express + standalone Character Creator). One authoritative
 * schema — do not fork per-surface types.
 */

import { shortJobMessage } from "../generators/shortJobMessage";

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
  /** Canonical sheet view role, e.g. front_closeup. Do not infer from tile index. */
  viewRole?: string;
  viewIndex?: number;
  status?: string;
  assetId?: string | null;
  seed?: number;
  modelFamily?: string;
  workflowKey?: string;
  referenceLocked?: boolean;
  /** Job message when this view reached a terminal error status. */
  error?: string | null;
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
  /** Optional API stamp: result is not a four-view Character Sheet. */
  layoutNoncompliant?: boolean;
  /** local | api — never infer from a truthy Comfy provider string. */
  providerKind?: "local" | "api";
  /** PROFILE_GUIDED | REFERENCE_CONDITIONED */
  conditioningMode?: "PROFILE_GUIDED" | "REFERENCE_CONDITIONED" | null;
  selectedSource?: string | null;
  hostedModelId?: string | null;
  /** Creator-facing provenance, e.g. LOCAL — Illustrious XL — Profile Guided */
  provenance?: string | null;
  /** 1-based batch index within this generator's requested count. */
  batchIndex?: number | null;
  /** Total batches requested for this generator in the originating plan. */
  batchOf?: number | null;
  providerId?: string | null;
  modelId?: string | null;
};

/** True when the API stamps this result as not a four-view Character Sheet. */
export function isLayoutNoncompliant(c: CharacterCandidate | Record<string, unknown> | null | undefined): boolean {
  if (!c || typeof c !== "object") return false;
  const rec = c as Record<string, unknown>;
  return rec.layoutNoncompliant === true || rec.layout_noncompliant === true;
}

/** Hydrate a pack candidate; map snake_case layout_noncompliant onto the typed field. */
export function normalizeCharacterCandidate(raw: unknown): CharacterCandidate {
  const rec = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const c = { ...rec } as CharacterCandidate;
  if (isLayoutNoncompliant(rec)) c.layoutNoncompliant = true;
  return c;
}

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

const LOCAL_FAMILY_PROVENANCE: Record<string, string> = {
  illustrious: "Illustrious XL",
  qwen2512: "Qwen Image 2512",
  qwen: "Qwen Image 2512",
  zimage: "Z-Image Turbo",
  flux: "FLUX.1 Kontext",
  krea2: "Local Krea 2",
};

function kreaModelNameFromCandidate(c: CharacterCandidate): string {
  const hosted = String(c.hostedModelId || c.selectedSource || c.model || "");
  const low = hosted.toLowerCase();
  if (low.includes("turbo")) return "Krea 2 Turbo";
  if (low.includes("medium")) return "Krea 2 Medium";
  if (low.includes("large")) return "Krea 2 Large";
  if (low.includes("raw")) return "Krea 2 RAW";
  return String(c.model || c.modelVariant || hosted || "Krea 2");
}

export function characterSheetBatchLabel(c: CharacterCandidate): string | null {
  const index = Number(c.batchIndex);
  const of = Number(c.batchOf);
  if (!Number.isFinite(index) || !Number.isFinite(of) || of < 1) return null;
  return `Batch ${index} of ${of}`;
}

/** Creator-facing candidate provenance. Never show a raw family id as the product label. */
export function characterSheetProvenanceLabel(c: CharacterCandidate): string {
  if (c.provenance && c.provenance.trim()) return c.provenance.trim();
  const src = `${c.generator || ""} ${c.provider || ""} ${c.hostedModelId || ""} ${c.selectedSource || ""}`.toLowerCase();
  const isKrea = src.includes("krea");
  const kind = c.providerKind || (isKrea && (c.hostedModelId || "").includes("fal") ? "api" : "");
  const mode =
    c.conditioningMode === "PROFILE_GUIDED"
      ? " — Profile Guided"
      : c.conditioningMode === "REFERENCE_CONDITIONED"
        ? " — Reference Conditioned"
        : "";
  if (
    kind === "api" ||
    src.includes("api") ||
    src.includes("cloud") ||
    (c.provider && !["comfy", "comfyui", "local"].includes(String(c.provider).toLowerCase()))
  ) {
    if (isKrea) return `API — Krea / ${kreaModelNameFromCandidate(c)}${mode}`;
    const modelName = c.model || c.modelVariant || "";
    return `API — ${[c.provider, modelName].filter(Boolean).join(" / ") || "cloud"}${mode}`;
  }
  const familyKey = String(c.selectedSource || c.model || "")
    .toLowerCase();
  const display = LOCAL_FAMILY_PROVENANCE[familyKey] || c.modelVariant || c.model || familyKey;
  return display ? `LOCAL — ${display}${mode}` : "LOCAL";
}

/** Terminal error statuses already returned by visual-sheet job hydration. */
export const VIEW_FAIL_STATUSES = ["failed", "error", "cancelled", "missing"] as const;

function normStatus(status?: string | null): string {
  return String(status || "").trim().toLowerCase();
}

export function viewIsFailed(v: CharacterViewJob): boolean {
  return (VIEW_FAIL_STATUSES as readonly string[]).includes(normStatus(v.status));
}

/** A view is finished when it succeeded or reached a terminal error. */
export function viewIsFinished(v: CharacterViewJob): boolean {
  const status = normStatus(v.status);
  return status === "done" || !!v.assetId || (VIEW_FAIL_STATUSES as readonly string[]).includes(status);
}

/** Replace raw sheet-view role keys (hero_identity) with creator labels (Front). */
function rewriteSheetViewLabels(text: string): string {
  let out = text;
  for (const [role, label] of Object.entries(SHEET_VIEW_LABELS)) {
    const re = new RegExp(`(^|[,;]\\s*)${role}(?=\\s*:|\\s*$|\\s*[,;])`, "g");
    out = out.replace(re, `$1${label}`);
  }
  return out.replace(/:\s*$/, "").trim();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Creator label for the first failed sheet view (Front / Side / Back / Close-Up). */
export function candidateFailedViewLabel(c: CharacterCandidate): string {
  const views = c.viewJobs || [];
  const firstFailed = views.find(viewIsFailed);
  if (firstFailed) {
    const key = String(firstFailed.role || firstFailed.viewRole || "").trim();
    if (SHEET_VIEW_LABELS[key]) return SHEET_VIEW_LABELS[key];
    if (key) return key;
  }
  const raw = String(c.error || "");
  for (const [role, label] of Object.entries(SHEET_VIEW_LABELS)) {
    const re = new RegExp(`(^|[,;]\\s*)${escapeRegExp(role)}(?=\\s*:|\\s*$|\\s*[,;])`);
    if (re.test(raw)) return label;
  }
  return "";
}

/** Failed-card title: "Generation failed — Front" (or without a view when unknown). */
export function candidateFailedTitle(c: CharacterCandidate): string {
  const label = candidateFailedViewLabel(c);
  return label ? `Generation failed — ${label}` : "Generation failed";
}

export function candidateErrorMessage(c: CharacterCandidate): string {
  const own = rewriteSheetViewLabels(shortJobMessage(String(c.error || "")));
  if (own) return own;
  const views = c.viewJobs || [];
  const bits = views
    .filter(viewIsFailed)
    .map((v) => rewriteSheetViewLabels(shortJobMessage(String(v.error || ""))))
    .filter(Boolean);
  return bits[0] || "";
}

/** Derive a truthful stage for a candidate from its backend state. */
export function candidateStage(c: CharacterCandidate): CandidateStage {
  const views = c.viewJobs || [];
  const status = normStatus(c.status);
  const anyFailed =
    (VIEW_FAIL_STATUSES as readonly string[]).includes(status) || views.some(viewIsFailed);
  if (anyFailed) return "failed";
  if (status === "done" || c.sheetAssetId || c.assetId) return "complete";
  if (status === "assembling") return "assembling";
  // All views done but no composed sheet yet → assembling.
  if (views.length && views.every((v) => normStatus(v.status) === "done" || v.assetId) && !c.sheetAssetId) {
    return "assembling";
  }
  const anyRunning = views.some((v) => normStatus(v.status) === "running");
  if (anyRunning || status === "generating") return "generating";
  return "queued";
}

/** Use This Look is only for a complete, layout-compliant sheet. */
export function canUseCharacterLook(c: CharacterCandidate): boolean {
  if (isLayoutNoncompliant(c)) return false;
  const assetId = c.sheetAssetId || c.assetId;
  return candidateStage(c) === "complete" && !!assetId;
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
    doneViews += views.filter(viewIsFinished).length;
    if (candidateStage(c) === "complete") doneSheets += 1;
  }
  // Percent reflects real completed units: finished views + a finished sheet
  // counts its assembly. Failed views count as finished so a failed batch
  // does not look hung at 0 of N.
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

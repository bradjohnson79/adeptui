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
};

export type GeneratorSourceKind = "local" | "api";

export type GeneratorOption = {
  id: string;
  label: string;
  family?: string;
  providerKind?: "local" | "cloud";
  /** Readiness / Certified state */
  executable: boolean;
  status?: string;
  /** Numeric credit balance only when the provider actually exposes one. */
  credits?: number | null;
  /** Human availability when no numeric balance: "Connected" | "Balance unavailable" */
  availability?: string;
};

export type GeneratorSourceState = {
  enabled: boolean;
  selectedId: string;
};

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
];

export const CHARACTER_GENDER_OPTIONS = [
  { value: "", label: "Select…" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "non_binary", label: "Non-binary" },
  { value: "androgynous", label: "Androgynous" },
  { value: "other", label: "Other" },
];

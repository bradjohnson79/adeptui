export type ReferenceIngredientRole =
  | "character"
  | "costume"
  | "prop"
  | "vehicle"
  | "environment"
  | "architecture"
  | "lighting"
  | "style"
  | "other";

export type ReferencePriority = "primary" | "supporting";

export type ReferenceMethod =
  | "none"
  | "start_frame"
  | "first_last_frame"
  | "ingredients_ic_lora"
  | "identity_id_lora";

export type StrengthPreset = "subtle" | "balanced" | "strong";

export type SheetLayout =
  | "auto"
  | "character_focus"
  | "two_characters_environment"
  | "character_props_environment"
  | "environment_focus"
  | "custom_grid";

export interface ReferenceIngredient {
  id: string;
  asset_id: string;
  role: ReferenceIngredientRole;
  subject_name?: string;
  description?: string;
  priority: ReferencePriority;
  include: boolean;
  crop_preference?: string;
  label?: string;
}

export interface ReferenceSheet {
  id: string;
  version: number;
  layout: SheetLayout;
  composite_asset_id?: string | null;
  static_video_asset_id?: string | null;
  source_ingredient_ids: string[];
  source_references: Array<{
    asset_id: string;
    role: ReferenceIngredientRole;
    subject_name?: string;
    priority: ReferencePriority;
  }>;
  preview_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ReferenceContinuityPreset {
  id: string;
  project_id: string;
  name: string;
  model_family: "ltx-2.3";
  reference_method: "ingredients_ic_lora";
  reference_sheet_asset_id?: string | null;
  sheet_id?: string | null;
  source_reference_ids: string[];
  subjects: Array<{
    name: string;
    role: ReferenceIngredientRole;
    asset_ids: string[];
  }>;
  strength_preset: StrengthPreset;
  strength_value: number;
  created_at: string;
  updated_at: string;
}

export interface ReferenceCapabilities {
  model_id: string;
  model_ready: boolean;
  model_status: string;
  model_issue_code?: string | null;
  model_message?: string | null;
  installed_filename?: string | null;
  nodes_available: boolean;
  strategy?: string | null;
  workflow_key: string;
  workflow_version: string;
  blockers: string[];
  ic_lora_option_enabled: boolean;
  identity_option_enabled: boolean;
  strength_presets: Record<StrengthPreset, number>;
  vram_warning?: string | null;
}

export interface ValidationIssue {
  level: "error" | "warning";
  code: string;
  message: string;
}

export const REFERENCE_ROLES: ReferenceIngredientRole[] = [
  "character",
  "costume",
  "prop",
  "vehicle",
  "environment",
  "architecture",
  "lighting",
  "style",
  "other",
];

export const STRENGTH_PRESET_VALUES: Record<StrengthPreset, number> = {
  subtle: 0.8,
  balanced: 1.4,
  strong: 1.8,
};

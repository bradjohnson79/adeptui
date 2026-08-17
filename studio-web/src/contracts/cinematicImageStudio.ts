/** M4.8 Cinematic Image Studio contracts */

import type { VisualContinuitySession } from "./visualContinuity";

export type GenerationMode = "best_match" | "choose_model" | "all_models";
export type ShotIntent =
  | "establishing"
  | "medium"
  | "close_up"
  | "extreme_close_up"
  | "over_shoulder"
  | "pov"
  | "insert"
  | "wide"
  | "two_shot"
  | "custom";
export type ImageCategory =
  | "storyboard"
  | "concept"
  | "keyframe"
  | "character"
  | "location"
  | "prop"
  | "mood"
  | "general";
export type ResolutionLabel = "1K" | "2K" | "4K" | "8K";
export type ResolutionOrigin = "native" | "upscaled" | "requested";
export type ProviderReadiness =
  | "ready"
  | "not_installed"
  | "needs_auth"
  | "unhealthy"
  | "disabled"
  | "incompatible"
  | "draft";

export type CinematicControls = {
  lens?: string;
  lighting?: string;
  colorTreatment?: string;
  colorGradePreset?: string;
  visualEra?: string;
  productionStyle?: string;
  aspectRatio: string;
  shotIntent: ShotIntent;
  /** Artist description when shotIntent is custom — Prompt Intelligence input. */
  customShotIntent?: string;
  category: ImageCategory;
};

export const CREATOR_IMAGE_CATEGORIES: { value: Exclude<ImageCategory, "storyboard">; label: string }[] = [
  { value: "general", label: "General" },
  { value: "keyframe", label: "Keyframe" },
  { value: "concept", label: "Concept" },
  { value: "character", label: "Character" },
  { value: "location", label: "Location" },
  { value: "prop", label: "Prop" },
  { value: "mood", label: "Mood" },
];

export const DEFAULT_IMAGE_CATEGORY: ImageCategory = "general";

export type AdvancedDiffusionControls = {
  steps?: number;
  guidance?: number;
  seed?: number;
  sampler?: string;
  scheduler?: string;
  denoise?: number;
  referenceWeights?: Record<string, number>;
};

export type ImageProviderDescriptor = {
  id: string;
  displayName: string;
  family: string;
  source: "local" | "hosted" | "docker";
  readiness: ProviderReadiness;
  imageCapable: boolean;
  licenseNote?: string;
  costHint?: string;
  requiresPaidConfirmation: boolean;
  nativeResolutions: ResolutionLabel[];
  upscaleSupported: boolean;
  providerPreference?: string;
  modelId?: string;
  metadata?: Record<string, unknown>;
};

export type CinematicGenerateRequest = {
  prompt: string;
  negativePrompt?: string;
  projectId: string;
  mode: GenerationMode;
  modelFamilyPreference?: string;
  providerId?: string;
  modelId?: string;
  batchSize: number;
  resolution: ResolutionLabel;
  controls: CinematicControls;
  advanced?: AdvancedDiffusionControls;
  referenceAssetIds: string[];
  sceneId?: string;
  continuitySessionId?: string;
  inheritContinuityFromScene?: boolean;
  panelId?: string;
  purpose?: string;
  runPromptIntelligence?: boolean;
  creativeContext?: Record<string, unknown>;
  spatialMapId?: string;
  spatialMapVersion?: string;
  spatialCameraId?: string;
};

export type ContinuityUiState = {
  mode: "off" | "inherit_from_scene";
  sceneId?: string;
  session?: VisualContinuitySession | null;
};

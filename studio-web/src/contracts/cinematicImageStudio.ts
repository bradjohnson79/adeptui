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

/**
 * Resolution product label — mirrors studio-api image_studio `_resolution_product_label`.
 * 1K → 1080p, 2K → 2K, 4K → 4K, 8K caps at 4K. This is the runtime contract
 * (aspect-independent); the actual pixel size is derived from aspect below.
 */
export function resolutionProductLabel(label: ResolutionLabel): string {
  switch (label) {
    case "1K":
      return "1080p";
    case "2K":
      return "2K";
    case "4K":
      return "4K";
    case "8K":
      return "4K"; // 8K caps at 4K
    default:
      return "1080p";
  }
}

/**
 * Pixel size for a (resolution, aspect) pair — mirrors studio-api
 * image_product/compile.py `_ASPECT` + `_RES_SCALE` + `_size` (snap to 8px).
 * Used to make the CIS UI and runtime agree transparently: the dropdown shows
 * the exact pixels that will be generated for the chosen aspect.
 */
const ASPECT_BASE: Record<string, [number, number]> = {
  "1:1": [1024, 1024],
  "16:9": [1920, 1080],
  "9:16": [1080, 1920],
  "2:3": [1024, 1536],
  "3:2": [1536, 1024],
  "21:9": [1920, 820],
  "4:3": [1440, 1080],
};
const RES_SCALE: Record<string, number> = {
  "720p": 0.67,
  "1080p": 1.0,
  "2K": 1.25,
  "4K": 2.0,
};

export function resolutionPixels(label: ResolutionLabel, aspect: string): [number, number] {
  const base = ASPECT_BASE[aspect] ?? [1024, 1024];
  const scale = RES_SCALE[resolutionProductLabel(label)] ?? 1.0;
  const snap = (n: number) => Math.max(64, Math.round((n * scale) / 8) * 8);
  return [snap(base[0]), snap(base[1])];
}
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
  /** STYLE_REGISTRY / CHARACTER_STYLE_OPTIONS key — locked creator constraint. */
  visualStyle?: string;
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
  authorityReferences?: Array<{
    key: string;
    kind: "character" | "prop" | "environment" | "posecraft" | "other";
    assetId: string;
    name: string;
    chip: string;
  }>;
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

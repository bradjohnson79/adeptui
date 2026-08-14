/**
 * Scene Creator frontend contracts.
 *
 * Mirrors the frozen backend types in studio-api/app/spatial_map/ers_contracts.py
 * (ShotRequest, SceneGenerationBatch, SceneShot) and the Scene Creator REST router
 * responses in studio-api/app/scene_creator/router.py.
 *
 * Law #16 (frozen contracts): field names must match the backend exactly.
 * Law #11 (persistence): batches are reloaded from the API on mount.
 * Amendment #3 (spatial authority): Scene Creator images never mutate spatial state.
 * Amendment #5 (entity tags): @ uses real names, # uses normalized tags.
 */
import type { EnvironmentReferenceSheetSummary } from "../../../contracts/environmentReferenceSheet";

/** One parsed shot request. Tags resolve to stable entity IDs on the backend. */
export type ShotRequest = {
  index: number;
  raw_text: string;
  characters: string[];
  prop_entities: string[];
  framing: string;
  angle: string;
  orientation: string;
  additional_instructions: string;
};

/** A batch of generated scene images from one Scene Creator run. */
export type SceneGenerationBatch = {
  id: string;
  project_id: string;
  ers_package_id: string;
  shot_requests: ShotRequest[];
  output_count: number;
  result_asset_ids: string[];
  collection_id?: string | null;
  created_at: string;
  updated_at: string;
};

/** POST /scene-creator/projects/{pid}/parse-shots response. */
export type ParseShotsResponse = {
  shots: ShotRequest[];
};

/** POST /scene-creator/projects/{pid}/batches response. */
export type CreateBatchResponse = {
  batch: SceneGenerationBatch;
  child_jobs: ChildJobSummary[];
  job_ids: string[];
  surface_type?: string;
};

/** GET /scene-creator/projects/{pid}/batches response. */
export type ListBatchesResponse = {
  batches: SceneGenerationBatch[];
};

/** GET /scene-creator/projects/{pid}/batches/{bid} response. */
export type GetBatchResponse = {
  batch: SceneGenerationBatch;
};

/** POST .../regenerate-shot response. */
export type RegenerateShotResponse = {
  batch: SceneGenerationBatch;
  job_id: string;
  status: string;
  shot_index: number;
};

/** POST .../send-to-timeline response. */
export type SendToTimelineResponse = {
  batch: SceneGenerationBatch;
  timeline: Record<string, unknown>;
  clips_sent: number;
};

/** A lightweight view of a child job (mirrors AgentWorkSurface ChildJobView). */
export type ChildJobSummary = {
  job_id: string;
  label?: string;
  status?: string;
  asset_id?: string | null;
  error?: string | null;
  progress?: number;
  stage?: string;
  child_index?: number;
};

/** A character resolved from the spatial map, available as @name. */
export type ResolvedCharacter = {
  character_id: string;
  name: string;
  position_label: string;
};

/** A prop resolved from the spatial map, available as #tag. */
export type ResolvedProp = {
  prop_id?: string | null;
  tag: string;
  display_label: string;
  position_label: string;
  approved_asset_id?: string | null;
  library_asset_id?: string | null;
  description?: string;
};

/** One shot suggestion from Co-Director. */
export type ShotSuggestion = {
  prompt: string;
  rationale?: string;
};

export type CinematicShotControls = {
  shot_size: string;
  motion: string;
  framing: string;
};

export type SceneCreatorCamera = {
  camera_id: string;
  camera_slot: number | null;
  label: string;
  orientation: string;
  fov_preset: string;
  yaw_degrees?: number | null;
  lens_mm?: number | null;
  cinematic: CinematicShotControls;
};

export type GeneratorSourceSelection = {
  local_enabled: boolean;
  api_enabled: boolean;
  local_family: string;
  api_provider: string;
  api_model: string;
};

export type SceneShotTakeMemory = {
  originalTakeIntent: Record<string, unknown>;
  sceneErsState: Record<string, unknown>;
  characterIdentity: Record<string, unknown>;
  blocking: Record<string, unknown>;
  camera: Record<string, unknown>;
  takeState: Record<string, unknown>;
  userCorrection: Record<string, unknown>;
};

export type SceneShotCandidate = {
  id: string;
  shot_id: string;
  index: number;
  job_id: string;
  asset_id?: string | null;
  status: "queued" | "generating" | "complete" | "failed";
  source: "local" | "api";
  family: string;
  model: string;
  seed?: number | null;
  provenance_label: string;
  take_label: string;
  error?: string;
  created_at?: string;
};

export type SceneShot = {
  id: string;
  project_id: string;
  scene_id: string;
  sheet_id: string;
  ers_package_id: string;
  ers_runtime: boolean;
  intent: string;
  prompt: string;
  character_ids: string[];
  prop_entity_ids: string[];
  camera: SceneCreatorCamera;
  generator: GeneratorSourceSelection;
  candidates: SceneShotCandidate[];
  approved_candidate_id?: string | null;
  take_memory: SceneShotTakeMemory;
  generation_batch_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type SceneCreatorCameraOption = {
  id: string;
  label: string;
  cameraSlot: number;
  orientation: string;
  fovPreset: string;
  yawDegrees?: number | null;
  lensMm?: number | null;
  hero?: boolean;
};

export type SceneCreatorWorkspace = {
  sheets: EnvironmentReferenceSheetSummary[];
  selected_sheet_id: string;
  sheet_name: string;
  resolved_ers: {
    sheet_id?: string;
    package_id?: string;
    runtime?: boolean;
    directional_assets?: Record<string, string | null>;
    error?: string;
  } | null;
  scenes: { id: string; name: string; index: number }[];
  selected_scene_id: string;
  shots: SceneShot[];
  selected_shot: SceneShot | null;
  cameras: SceneCreatorCameraOption[];
  characters: ResolvedCharacter[];
  props: ResolvedProp[];
  api_generation_available: boolean;
  local_families: { id: string; label: string; executable?: boolean; supportsReferences?: boolean }[];
  has_reference: boolean;
};

export const DEFAULT_CINEMATIC: CinematicShotControls = {
  shot_size: "medium_wide",
  motion: "static",
  framing: "two_shot",
};

export function candidateProgress(candidates: SceneShotCandidate[]): {
  done: number;
  total: number;
  percent: number;
} {
  const total = candidates.length;
  const done = candidates.filter((c) => c.status === "complete" || c.status === "failed").length;
  return { done, total, percent: total ? Math.round((done / total) * 100) : 0 };
}

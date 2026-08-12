/**
 * Scene Creator frontend contracts.
 *
 * Mirrors the frozen backend types in studio-api/app/spatial_map/ers_contracts.py
 * (ShotRequest, SceneGenerationBatch) and the Scene Creator REST router
 * responses in studio-api/app/scene_creator/router.py.
 *
 * Law #16 (frozen contracts): field names must match the backend exactly.
 * Law #11 (persistence): batches are reloaded from the API on mount.
 * Amendment #3 (spatial authority): Scene Creator images never mutate spatial state.
 * Amendment #5 (entity tags): @ uses real names, # uses normalized tags.
 */

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
  tag: string;
  display_label: string;
  position_label: string;
};

/** One shot suggestion from Co-Director. */
export type ShotSuggestion = {
  prompt: string;
  rationale?: string;
};

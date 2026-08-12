/**
 * Live Agent Work Surface — frontend state contracts.
 *
 * Spec §18: "The right Co-Director pane becomes a dynamic AGENT WORK SURFACE
 * during execution."
 * Spec §19: "mode = normal | agent_work"
 * Spec §20: "Do NOT implement fake animated agent behavior. Every visible
 * Generating/Processing/Saving/Completed/Failed must correspond to actual
 * backend/task state."
 *
 * FROZEN CONTRACT — Law #16. Do not change field names without primary approval.
 * These types must match the backend `ExecutionPlan` in
 * studio-api/app/codirector/execution/contracts.py.
 */

export type WorkSurfaceMode = "normal" | "agent_work";

export type SurfaceType =
  | ""
  | "image_generation"
  | "storyboard_generation"
  | "casting_candidates"
  | "voice_generation"
  | "script_operation"
  | "atlas_shot_generation"
  | "ers_generation"
  | "scene_generation";

export type ChildJobStatus =
  | "queued"
  | "running"
  | "preview"
  | "completed"
  | "failed"
  | "cancelled";

export interface ChildJobView {
  job_id: string;
  label: string;
  status: ChildJobStatus;
  asset_id?: string | null;
  error?: string | null;
  progress: number;
  stage: string;
  child_index: number;
  metadata: Record<string, unknown>;
}

export interface WorkSurfaceState {
  /** When "normal", the right pane shows the normal tab. When "agent_work",
   * the pane shows the AgentWorkSurface for this execution. */
  mode: WorkSurfaceMode;
  execution_id: string;
  capability: string;
  surface_type: SurfaceType;
  status: string;
  progress: number;
  focused_artifact_ids: string[];
  child_jobs: ChildJobView[];
  result_asset_ids: string[];
  collection_id?: string | null;
  error?: string | null;
  project_id?: string;
  character_id?: string | null;
  scene_id?: string | null;
}

/** Empty state — normal mode, no active execution. */
export const NORMAL_WORK_SURFACE: WorkSurfaceState = {
  mode: "normal",
  execution_id: "",
  capability: "",
  surface_type: "",
  status: "",
  progress: 0,
  focused_artifact_ids: [],
  child_jobs: [],
  result_asset_ids: [],
};

/** Helper: is the work surface showing active execution? */
export function isAgentWork(state: WorkSurfaceState | null | undefined): boolean {
  if (!state) return false;
  return state.mode === "agent_work" && !!state.execution_id;
}

/** Helper: is this execution terminal (completed/failed/cancelled)? */
export function isTerminal(state: WorkSurfaceState | null | undefined): boolean {
  if (!state) return true;
  return ["completed", "failed", "cancelled"].includes(state.status);
}

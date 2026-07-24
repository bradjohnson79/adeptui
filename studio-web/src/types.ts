export type EngineName =
  | "auto"
  | "ltx"
  | "wan"
  | "fal_seedance"
  | "fal_kling"
  | "fal_veo"
  | "fal_runway";
export type PresetName = "draft" | "quality";

export interface Asset {
  id: string;
  project_id: string;
  tag: string;
  kind: string;
  filename: string;
  path: string;
  comfy_name: string;
  scope?: string;
  shared_project_ids_json?: string;
  labels_json?: string;
  prompt_meta_json?: string;
  parent_asset_id?: string | null;
  created_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  index: number;
  name: string;
  engine: EngineName;
  prompt: string;
  duration_sec: number;
  start_asset_id?: string | null;
  middle_asset_id?: string | null;
  end_asset_id?: string | null;
  audio_asset_id?: string | null;
  lipsync_enabled: boolean;
  lipsync_audio_asset_id?: string | null;
  lipsync_tracks_json?: string;
  director_json?: string;
  continuity_json?: string;
  camera_note: string;
  seed: number;
  aspect_ratio?: string;
  width?: number;
  height?: number;
  fps_mode?: string;
  fps?: number;
  output_path?: string | null;
  lipsync_output_path?: string | null;
}

export interface Project {
  id: string;
  name: string;
  engine_default: EngineName;
  global_prompt: string;
  negative_prompt: string;
  width: number;
  height: number;
  fps: number;
  seed: number;
  preset: PresetName;
  vram_gb: number;
  spatial_map_json: string;
  render_safety_json?: string;
  learning_json?: string;
  learning_enabled_json?: string;
  preview_settings_json?: string;
  description?: string;
  company?: string;
  director_name?: string;
  version?: string;
  tags_json?: string;
  archived?: number;
  defaults_json?: string;
  settings_json?: string;
  created_at: string;
  updated_at: string;
  scenes: Scene[];
  assets: Asset[];
  /** Lightweight list summary (home library) */
  scene_count?: number;
  asset_count?: number;
  render_pct?: number;
  cover_asset_id?: string | null;
  status_label?: string;
}

export interface Job {
  id: string;
  project_id: string;
  scene_id?: string | null;
  kind: string;
  status: string;
  progress: number;
  message: string;
  stage?: string;
  preview_json?: string;
  params_json?: string;
  history_json?: string;
  comfy_prompt_id?: string | null;
  output_path?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SpatialPoint {
  id: string;
  kind: "camera" | "prop" | "wall" | "marker";
  x: number;
  y: number;
  label: string;
  asset_id?: string | null;
  rotation: number;
}

export interface SpatialMap {
  width: number;
  height: number;
  background_asset_id?: string | null;
  points: SpatialPoint[];
  notes: string;
}

export interface Health {
  ok: boolean;
  comfy_reachable: boolean;
  missing_models: string[];
  message: string;
}

export interface SceneSetup {
  summary?: string;
  scene_name?: string | null;
  engine?: EngineName | null;
  duration_sec?: number | null;
  media_mode?: "image" | "video" | null;
  global_prompt?: string | null;
  negative_prompt?: string | null;
  preset?: PresetName | null;
  prompt?: string | null;
  prompt_segments?: { start: number; length: number; text: string }[] | null;
  image_slots?: Record<string, string | null> | null;
  audio_ref?: string | null;
  sfx?: { ref: string; start: number; length: number; label: string }[] | null;
}

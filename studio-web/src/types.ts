export type EngineName =
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
  camera_note: string;
  seed: number;
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
  created_at: string;
  updated_at: string;
  scenes: Scene[];
  assets: Asset[];
}

export interface Job {
  id: string;
  project_id: string;
  scene_id?: string | null;
  kind: string;
  status: string;
  progress: number;
  message: string;
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

/**
 * Scene Creator API client.
 *
 * Thin facade over `api.sceneCreator` so Scene Creator components import a
 * single named module. Express and Standard share this client.
 */
import { api } from "../../../api";
import type {
  CreateBatchResponse,
  GetBatchResponse,
  ListBatchesResponse,
  ParseShotsResponse,
  RegenerateShotResponse,
  SceneCreatorWorkspace,
  SceneShot,
  SendToTimelineResponse,
} from "./types";
import type { SceneCinematographerPack } from "./cinematographer/cameraCommandEngine";

export type CreateBatchInput = {
  ers_package_id: string;
  shot_requests_raw: string;
  output_count: number;
  visual_style?: string;
  character_names?: string[];
};

export type RegenerateShotInput = {
  shot_index: number;
  new_prompt: string;
  visual_style?: string;
};

export type SendToTimelineInput = {
  scene_id: string;
  label?: string;
  batch_block_id?: string;
};

export type UpsertShotInput = {
  sheet_id: string;
  scene_id?: string;
  shot_id?: string;
  intent?: string;
  character_ids?: string[];
  prop_entity_ids?: string[];
  camera?: Record<string, unknown>;
  generator?: Record<string, unknown>;
};

export type GenerateShotInput = {
  local_enabled: boolean;
  api_enabled: boolean;
  local_family?: string;
  api_model?: string;
  candidate_count?: number;
};

export const sceneCreatorApi = {
  parseShots: (projectId: string, rawText: string): Promise<ParseShotsResponse> =>
    api.sceneCreator.parseShots(projectId, rawText),
  createBatch: (projectId: string, body: CreateBatchInput): Promise<CreateBatchResponse> =>
    api.sceneCreator.createBatch(projectId, body),
  listBatches: (projectId: string): Promise<ListBatchesResponse> =>
    api.sceneCreator.listBatches(projectId),
  getBatch: (projectId: string, batchId: string): Promise<GetBatchResponse> =>
    api.sceneCreator.getBatch(projectId, batchId),
  regenerateShot: (
    projectId: string,
    batchId: string,
    body: RegenerateShotInput,
  ): Promise<RegenerateShotResponse> => api.sceneCreator.regenerateShot(projectId, batchId, body),
  sendToTimeline: (
    projectId: string,
    batchId: string,
    body: SendToTimelineInput,
  ): Promise<SendToTimelineResponse> => api.sceneCreator.sendToTimeline(projectId, batchId, body),
  workspace: (
    projectId: string,
    query?: { sheet_id?: string; scene_id?: string; shot_id?: string; spatial_profile_id?: string },
  ): Promise<SceneCreatorWorkspace> => api.sceneCreator.workspace(projectId, query),
  productionHandoff: (
    projectId: string,
    body?: { scene_id?: string; sheet_id?: string; spatial_map_id?: string },
  ) => api.sceneCreator.productionHandoff(projectId, body),
  listSpatialProfiles: (projectId: string) => api.sceneCreator.listSpatialProfiles(projectId),
  selectSpatialProfile: (projectId: string, handoffId: string) =>
    api.sceneCreator.selectSpatialProfile(projectId, handoffId),
  resetWorkspace: (projectId: string) => api.sceneCreator.resetWorkspace(projectId),
  upsertShot: (projectId: string, body: UpsertShotInput): Promise<{ shot: SceneShot }> =>
    api.sceneCreator.upsertShot(projectId, body),
  getShot: (projectId: string, shotId: string): Promise<{ shot: SceneShot }> =>
    api.sceneCreator.getShot(projectId, shotId),
  generateShot: (projectId: string, shotId: string, body: GenerateShotInput): Promise<{ shot: SceneShot }> =>
    api.sceneCreator.generateShot(projectId, shotId, body),
  retakeShot: (
    projectId: string,
    shotId: string,
    body: { correction: string } & GenerateShotInput,
  ): Promise<{ shot: SceneShot }> => api.sceneCreator.retakeShot(projectId, shotId, body),
  approveCandidate: (projectId: string, shotId: string, candidateId: string): Promise<{ shot: SceneShot }> =>
    api.sceneCreator.approveCandidate(projectId, shotId, candidateId),
  sendShotToTimeline: (
    projectId: string,
    shotId: string,
    body?: { batch_block_id?: string },
  ): Promise<{ timeline: Record<string, unknown>; clips_sent: number }> =>
    api.sceneCreator.sendShotToTimeline(projectId, shotId, body),
  cinematographer: (projectId: string, sceneId: string) =>
    api.sceneCreator.cinematographer(projectId, sceneId),
  cinematographerCommand: (
    projectId: string,
    sceneId: string,
    body: {
      camera_id: string;
      operation_id: string;
      character_id?: string;
      prop_id?: string;
      shot_id?: string;
      orientation3d?: {
        yawDegrees?: number;
        pitchDegrees?: number;
        rollDegrees?: number;
        zoom?: number;
        enabled?: boolean;
        targetLock?: boolean;
        axisLocks?: { yaw?: boolean; pitch?: boolean; roll?: boolean; zoom?: boolean };
        snapId?: string;
        source?: "discrete" | "gizmo";
      };
    },
  ): Promise<{ cinematographer: SceneCinematographerPack }> =>
    api.sceneCreator.cinematographerCommand(projectId, sceneId, body),
  cinematographerUndo: (projectId: string, sceneId: string, body: { camera_id: string; shot_id?: string }) =>
    api.sceneCreator.cinematographerUndo(projectId, sceneId, body),
  cinematographerReset: (projectId: string, sceneId: string, body: { camera_id: string; shot_id?: string }) =>
    api.sceneCreator.cinematographerReset(projectId, sceneId, body),
  cinematographerLock: (projectId: string, sceneId: string, body: { camera_id: string; shot_id?: string }) =>
    api.sceneCreator.cinematographerLock(projectId, sceneId, body),
  cinematographerDelta: (projectId: string, sceneId: string, body: { camera_id: string; delta: string }) =>
    api.sceneCreator.cinematographerDelta(projectId, sceneId, body),
  cinematographerPreview: (
    projectId: string,
    sceneId: string,
    body: {
      camera_id: string;
      shot_id: string;
      local_enabled: boolean;
      api_enabled: boolean;
      local_family?: string;
      api_model?: string;
    },
  ) => api.sceneCreator.cinematographerPreview(projectId, sceneId, body),
  cinematographerFinal: (
    projectId: string,
    sceneId: string,
    body: {
      camera_id: string;
      shot_id: string;
      local_enabled: boolean;
      api_enabled: boolean;
      local_family?: string;
      api_model?: string;
      sourceAssetId?: string;
      finalStrategy?: string;
    },
  ) => api.sceneCreator.cinematographerFinal(projectId, sceneId, body),
  regionEdit: (
    projectId: string,
    shotId: string,
    body: {
      operation: string;
      prompt: string;
      maskAssetId: string;
      sourceAssetId?: string;
      stage?: "preview" | "final";
      local_family?: string;
      local_enabled?: boolean;
      api_enabled?: boolean;
      api_model?: string;
      expand?: string;
      feather?: string;
    },
  ): Promise<{ shot: SceneShot }> => api.sceneCreator.regionEdit(projectId, shotId, body),
};

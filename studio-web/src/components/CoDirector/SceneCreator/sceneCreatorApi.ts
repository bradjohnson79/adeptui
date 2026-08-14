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
    query?: { sheet_id?: string; scene_id?: string; shot_id?: string },
  ): Promise<SceneCreatorWorkspace> => api.sceneCreator.workspace(projectId, query),
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
};

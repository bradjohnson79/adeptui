/**
 * Scene Creator API client.
 *
 * Thin facade over `api.sceneCreator` (defined in studio-web/src/api.ts) so
 * Scene Creator components import a single named module. All endpoints map
 * 1:1 to the backend router in studio-api/app/scene_creator/router.py.
 *
 * Law #9 (every control wired): every method calls a real backend endpoint.
 * Law #14 (project isolation): every call is scoped by projectId.
 */
import { api } from "../../../api";
import type {
  CreateBatchResponse,
  GetBatchResponse,
  ListBatchesResponse,
  ParseShotsResponse,
  RegenerateShotResponse,
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
};

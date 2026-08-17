import { api } from "../../../api";
import type { PropCreatorWorkspace, PropEntity } from "./types";

export const propCreatorApi = {
  workspace: (projectId: string, propId?: string) => api.propCreator.workspace(projectId, propId) as Promise<PropCreatorWorkspace>,
  list: (projectId: string, approvedOnly = false) => api.propCreator.list(projectId, approvedOnly),
  upsert: (projectId: string, body: Parameters<typeof api.propCreator.upsert>[1]) => api.propCreator.upsert(projectId, body),
  get: (projectId: string, propId: string) => api.propCreator.get(projectId, propId) as Promise<{ prop: PropEntity }>,
  generate: (projectId: string, propId: string, body: Parameters<typeof api.propCreator.generate>[2]) =>
    api.propCreator.generate(projectId, propId, body),
  approve: (projectId: string, propId: string, candidateId: string) => api.propCreator.approve(projectId, propId, candidateId),
  retry: (projectId: string, propId: string, candidateId: string) => api.propCreator.retry(projectId, propId, candidateId),
  delete: (projectId: string, propId: string) => api.propCreator.delete(projectId, propId),
};

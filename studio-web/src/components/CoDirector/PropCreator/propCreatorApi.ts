import { api } from "../../../api";
import type { PropCreatorWorkspace, PropEntity } from "./types";

async function useAsIdentity(projectId: string, propId: string, assetId: string): Promise<PropEntity | null> {
  try {
    if (typeof api.propCreator.useAsIdentity === "function") {
      const res = await api.propCreator.useAsIdentity(projectId, propId, assetId);
      return (res as { prop?: PropEntity })?.prop || null;
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    // Backend identity route may not have landed yet; upsert already sent the pointer fields.
    if (/404|405|not found|not implemented/i.test(message)) return null;
    throw err;
  }
  return null;
}

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
  useAsIdentity,
};

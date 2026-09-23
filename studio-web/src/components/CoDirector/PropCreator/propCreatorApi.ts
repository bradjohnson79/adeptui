import { api } from "../../../api";
import type { CreatorDeletePreview } from "../../creators/creatorProfileDelete";
import type { PropCreatorWorkspace, PropEntity } from "./types";

export const propCreatorApi = {
  workspace: (projectId: string, propId?: string) => api.propCreator.workspace(projectId, propId) as Promise<PropCreatorWorkspace>,
  list: (projectId: string, approvedOnly = false) => api.propCreator.list(projectId, approvedOnly),
  upsert: (projectId: string, body: Parameters<typeof api.propCreator.upsert>[1]) => api.propCreator.upsert(projectId, body),
  get: (projectId: string, propId: string) => api.propCreator.get(projectId, propId) as Promise<{ prop: PropEntity }>,
  generate: (projectId: string, propId: string, body: Parameters<typeof api.propCreator.generate>[2]) =>
    api.propCreator.generate(projectId, propId, body),
  approve: (projectId: string, propId: string, candidateId: string) => api.propCreator.approve(projectId, propId, candidateId),
  composeReferenceSheet: (projectId: string, propId: string) => api.propCreator.composeReferenceSheet(projectId, propId),
  retry: (projectId: string, propId: string, candidateId: string) => api.propCreator.retry(projectId, propId, candidateId),
  delete: (projectId: string, propId: string, confirmCrossProject?: boolean) =>
    api.propCreator.delete(projectId, propId, confirmCrossProject),
  deletePreview: (projectId: string, propId: string) =>
    api.propCreator.deletePreview(projectId, propId) as Promise<CreatorDeletePreview>,
  advancedEngine: (projectId: string, propId: string) => api.propCreator.advancedEngine(projectId, propId),
  advancedPrimaryGenerate: (
    projectId: string,
    propId: string,
    body?: Parameters<typeof api.propCreator.advancedPrimaryGenerate>[2],
  ) => api.propCreator.advancedPrimaryGenerate(projectId, propId, body),
  advancedPrimaryApprove: (
    projectId: string,
    propId: string,
    body?: Parameters<typeof api.propCreator.advancedPrimaryApprove>[2],
  ) => api.propCreator.advancedPrimaryApprove(projectId, propId, body),
  advancedAngleGenerate: (projectId: string, propId: string, angle: string) =>
    api.propCreator.advancedAngleGenerate(projectId, propId, angle) as Promise<{ prop: PropEntity }>,
  advancedAngleRegenerate: (projectId: string, propId: string, angle: string) =>
    api.propCreator.advancedAngleRegenerate(projectId, propId, angle) as Promise<{ prop: PropEntity }>,
  advancedAngleApprove: (projectId: string, propId: string, angle: string, approved = true) =>
    api.propCreator.advancedAngleApprove(projectId, propId, angle, approved) as Promise<{ prop: PropEntity }>,
  advancedReferenceSheetGenerate: (projectId: string, propId: string) =>
    api.propCreator.advancedReferenceSheetGenerate(projectId, propId) as Promise<{ prop: PropEntity }>,
  advancedReferenceSheetCancel: (projectId: string, propId: string) =>
    api.propCreator.advancedReferenceSheetCancel(projectId, propId) as Promise<{ prop: PropEntity }>,
  advancedPrimaryUpload: (projectId: string, propId: string, file: File) =>
    api.propCreator.advancedPrimaryUpload(projectId, propId, file),
  advancedAngleUpload: (projectId: string, propId: string, angle: string, file: File) =>
    api.propCreator.advancedAngleUpload(projectId, propId, angle, file),
  advancedAngleAdopt: (
    projectId: string,
    propId: string,
    angle: string,
    body: { assetId: string; sourceType?: string },
  ) => api.propCreator.advancedAngleAdopt(projectId, propId, angle, body),
  uploadView: (projectId: string, propId: string, file: File) =>
    api.propCreator.uploadPropView(projectId, propId, file),
  adoptView: (projectId: string, propId: string, body: { assetId: string; sourceType?: string }) =>
    api.propCreator.adoptPropView(projectId, propId, body),
};

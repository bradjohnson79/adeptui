/** Bound project id used by live `api.assetUrl` when callers omit projectId. */

let boundAssetUrlProject = "";

export function bindAssetUrlProject(projectId?: string | null) {
  boundAssetUrlProject = typeof projectId === "string" ? projectId.trim() : "";
}

export function getBoundAssetUrlProject(): string {
  return boundAssetUrlProject;
}

/** @deprecated Use bindAssetUrlProject */
export const bindAssetProjectId = bindAssetUrlProject;
/** @deprecated Use getBoundAssetUrlProject */
export const getBoundAssetProjectId = getBoundAssetUrlProject;

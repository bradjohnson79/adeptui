/** Optional fallback project id for `api.assetUrl` when callers omit projectId. */

let boundAssetProjectId = "";

export function bindAssetProjectId(projectId?: string | null) {
  boundAssetProjectId = typeof projectId === "string" ? projectId.trim() : "";
}

export function getBoundAssetProjectId(): string {
  return boundAssetProjectId;
}

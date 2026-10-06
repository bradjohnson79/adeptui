/** Wave 2B — resolve completed video asset id from a done job row (params_json). */
export function resolveJobOutputVideoAssetId(job: {
  status?: string;
  scene_id?: string | null;
  params_json?: string | null;
  kind?: string;
}): string | null {
  if ((job.status || "").toLowerCase() !== "done") return null;
  let params: Record<string, unknown> = {};
  try {
    params = JSON.parse(job.params_json || "{}") as Record<string, unknown>;
  } catch {
    params = {};
  }
  const direct =
    (typeof params.output_asset_id === "string" && params.output_asset_id) ||
    (typeof params.outputAssetId === "string" && params.outputAssetId) ||
    (typeof params.libraryAssetId === "string" && params.libraryAssetId) ||
    null;
  if (direct) return String(direct);
  const ids = params.outputAssetIds;
  if (Array.isArray(ids) && ids.length && typeof ids[0] === "string") return String(ids[0]);
  const provenance = params.ic_lora_provenance;
  if (provenance && typeof provenance === "object") {
    const p = provenance as Record<string, unknown>;
    if (typeof p.output_asset_id === "string") return String(p.output_asset_id);
  }
  return null;
}

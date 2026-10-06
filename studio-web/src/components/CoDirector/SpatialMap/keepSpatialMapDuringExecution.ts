/** ERS and Atlas belong on Spatial Map. Do not unmount the panel under an overlay. */
export function keepSpatialMapDuringExecution(
  tab: string,
  execution: { capability?: string; surface_type?: string } | null | undefined,
): boolean {
  if (tab !== "spatial_map" || !execution) return false;
  const surface = String(execution.surface_type || "");
  const capability = String(execution.capability || "");
  return (
    surface === "ers_generation" ||
    surface === "atlas_shot_generation" ||
    surface === "atlas_assign" ||
    capability === "atlas.generate" ||
    capability === "atlas.assign"
  );
}

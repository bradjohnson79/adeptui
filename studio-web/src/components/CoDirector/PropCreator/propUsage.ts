import { api } from "../../../api";

export type PropUsageCounts = {
  spatial: number;
  shots: number;
};

export function countSpatialPlacementsForProp(
  documents: Array<{ props?: Array<{ propId?: string | null }> }>,
  propId: string,
): number {
  return documents.reduce(
    (n, doc) => n + (doc.props || []).filter((item) => item.propId === propId).length,
    0,
  );
}

export function countSceneShotsForProp(
  shots: Array<{
    prop_entity_ids?: string[];
    take_memory?: { blocking?: Record<string, unknown> };
  }>,
  propId: string,
): number {
  return shots.filter((shot) => {
    if ((shot.prop_entity_ids || []).includes(propId)) return true;
    const blocking = shot.take_memory?.blocking;
    const raw = blocking && typeof blocking === "object" ? (blocking as { prop_entity_ids?: unknown }).prop_entity_ids : undefined;
    const blockIds = Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : [];
    return blockIds.includes(propId);
  }).length;
}

export async function loadPropUsage(projectId: string, propId: string): Promise<PropUsageCounts> {
  const [spatial, shots] = await Promise.all([
    (async () => {
      try {
        const res = await api.spatialMap.listMaps(projectId);
        return countSpatialPlacementsForProp(res.documents || [], propId);
      } catch {
        return 0;
      }
    })(),
    (async () => {
      try {
        const ws = await api.sceneCreator.workspace(projectId);
        return countSceneShotsForProp(ws.shots || [], propId);
      } catch {
        return 0;
      }
    })(),
  ]);
  return { spatial, shots };
}

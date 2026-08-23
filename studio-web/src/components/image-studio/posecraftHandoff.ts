export const POSECRAFT_HANDOFF_PREFIX = "adept.posecraft.handoff.";

export type PoseCraftHandoff = {
  snapshotId?: string;
  imageAssetId?: string;
  name?: string;
  honestyLabel?: string;
};

export function posecraftHandoffKey(projectId: string): string {
  return `${POSECRAFT_HANDOFF_PREFIX}${projectId}`;
}

export function readPoseCraftHandoff(projectId: string, storage: Storage | null = defaultSessionStorage()): PoseCraftHandoff | null {
  if (!projectId || !storage) return null;
  try {
    const raw = storage.getItem(posecraftHandoffKey(projectId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PoseCraftHandoff;
    if (!parsed?.imageAssetId) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function consumePoseCraftHandoff(projectId: string, storage: Storage | null = defaultSessionStorage()): PoseCraftHandoff | null {
  const handoff = readPoseCraftHandoff(projectId, storage);
  if (!handoff || !storage) return handoff;
  try {
    storage.removeItem(posecraftHandoffKey(projectId));
  } catch {
    /* ignore */
  }
  return handoff;
}

function defaultSessionStorage(): Storage | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

import { api } from "../../api";

export interface CompatibleLora {
  id: string;
  name: string;
  category?: string;
  recommended_strength?: number | null;
  strength_min?: number | null;
  strength_max?: number | null;
  modality?: string;
  model_family?: string;
}

// Single-flight per (family, modality) cache - selectors never hammer the
// API (Request Stability Law): the registry is read-mostly state.
const compatibleCache = new Map<string, Promise<CompatibleLora[]> | CompatibleLora[]>();

function cacheKey(modelFamily: string, modality?: string): string {
  return `${modelFamily}|${modality || "any"}`;
}

export function fetchCompatibleLoras(
  modelFamily: string,
  modality?: string,
  fetcher: (family: string, mod?: string) => Promise<{ loras?: CompatibleLora[] }> = (family, mod) =>
    api.loras.compatible(family, mod),
): Promise<CompatibleLora[]> {
  const key = cacheKey(modelFamily, modality);
  const hit = compatibleCache.get(key);
  if (hit) return Promise.resolve(hit);
  const p = fetcher(modelFamily, modality)
    .then((r) => {
      const list: CompatibleLora[] = r.loras || [];
      compatibleCache.set(key, list);
      return list;
    })
    .catch((error: unknown) => {
      compatibleCache.delete(key);
      throw error;
    });
  compatibleCache.set(key, p);
  return p;
}

export function clearLoraSelectorCache() {
  compatibleCache.clear();
}

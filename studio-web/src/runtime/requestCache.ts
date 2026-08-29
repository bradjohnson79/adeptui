/**
 * Lightweight request cache with single-flight deduplication and TTL expiry.
 *
 * - Concurrent callers requesting the same endpoint share one network request.
 * - Successful responses are cached for a configurable TTL.
 * - Failed responses are NOT cached.
 * - Cache entries are evicted after TTL expiry.
 * - Explicitly clear entries for mutation endpoints (POST/PUT/DELETE).
 */
const cache = new Map<string, {
  promise: Promise<unknown>;
  expiresAt: number;
  settled: boolean;
}>();

const GET_TTL_MS: Record<string, number> = {
  "/api/health": 10_000,
  "/api/healthz": 5_000,
  "/api/capabilities": 15_000,
  "/api/runtime/beta": 10_000,
  "/api/runtime/local-generation": 2_500,
  "/api/gpu/stats": 5_000,
  "/api/production-control/status": 15_000,
  "/api/production-control/preferences": 30_000,
  "/api/production-control/gate": 15_000,
  "/api/production-control/models": 30_000,
  "/api/production-control/resolved": 15_000,
  "/api/production-control/queue": 10_000,
};

function cacheKey(method: string, path: string): string {
  // Query string is part of GET identity. Stripping it collapsed
  // /api/production-control/models?modality=video onto the LLM payload.
  return `${method}:${path}`;
}

function getDefaultTtl(method: string, path: string): number {
  if (method !== "GET") return 0;
  const url = path.split("?")[0];
  return GET_TTL_MS[url] ?? 0;
}

export function clearCacheEntry(method: string, path: string): void {
  const exact = `${method}:${path}`;
  cache.delete(exact);
  const base = path.split("?")[0];
  const prefix = `${method}:${base}`;
  for (const key of [...cache.keys()]) {
    if (key === prefix || key.startsWith(`${prefix}?`)) {
      cache.delete(key);
    }
  }
}

export function clearAllCache(): void {
  cache.clear();
}

export async function cachedFetch<T>(
  method: string,
  path: string,
  fetcher: () => Promise<T>,
  ttlMs?: number,
): Promise<T> {
  if (method !== "GET") {
    return fetcher();
  }
  const ttl = ttlMs ?? getDefaultTtl(method, path);
  if (ttl <= 0) {
    return fetcher();
  }

  const key = cacheKey(method, path);
  const existing = cache.get(key);

  if (existing && Date.now() < existing.expiresAt) {
    return existing.promise as Promise<T>;
  }

  if (existing && !existing.settled) {
    return existing.promise as Promise<T>;
  }

  const entry = {
    promise: fetcher()
      .then((result) => {
        entry.settled = true;
        entry.expiresAt = Date.now() + ttl;
        return result;
      })
      .catch((error) => {
        cache.delete(key);
        throw error;
      }) as Promise<unknown>,
    expiresAt: Date.now() + ttl,
    settled: false,
  };

  cache.set(key, entry);
  return entry.promise as Promise<T>;
}

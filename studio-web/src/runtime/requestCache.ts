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
  "/api/gpu/stats": 5_000,
  "/api/production-control/status": 15_000,
  "/api/production-control/preferences": 30_000,
  "/api/production-control/gate": 15_000,
  "/api/production-control/models": 30_000,
  "/api/production-control/resolved": 15_000,
  "/api/production-control/queue": 10_000,
};

function cacheKey(method: string, path: string): string {
  // Query is part of identity. /models?modality=image must not reuse the llm payload.
  return `${method}:${path}`;
}

function getDefaultTtl(method: string, path: string): number {
  if (method !== "GET") return 0;
  const url = path.split("?")[0];
  const exact = GET_TTL_MS[url];
  if (exact !== undefined) return exact;
  // Prefix-based matching for paths with variable segments (project IDs, etc.)
  if (url.startsWith("/api/codirector/conversations/")) {
    if (url.endsWith("/events")) {
      return 0; // POST body — never cache
    }
    if (url.endsWith("/revision")) {
      // /conversations/{projectId}/revision — polled every 5s;
      // cache 30s to deduplicate overlapping interval/visibility/reconnect polls.
      return 30_000;
    }
    // Full conversation GET (no trailing segment after project id) — cache 15s
    // so reconciliation doesn't fire duplicate requests within the same tick.
    return 15_000;
  }
  return 0;
}

export function clearCacheEntry(method: string, path: string): void {
  const key = cacheKey(method, path);
  cache.delete(key);
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

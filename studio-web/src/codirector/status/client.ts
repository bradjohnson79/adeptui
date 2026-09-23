import { api } from "../../api";
import type { StatusCheckRequest, StatusRegistryCheck, StatusRun } from "./types";

/**
 * Shared Co-Director status fetching with single-flight deduplication and a
 * 30-second TTL (same pattern as studio-web/runtime/requestCache and
 * studio-web/runtime/localGenerationAttention).
 *
 * Multiple components/sessions may request the latest run or history (mount
 * auto-check, Status panel open, manual Refresh, header chip). Without a shared
 * layer each caller would issue its own network request, so these helpers
 * coalesce concurrent callers onto one in-flight fetch and reuse the cached
 * result until the TTL expires.
 *
 * The cache is keyed on (projectId, sceneId) so reads for different projects
 * never collide. Failed responses are not cached. Mutation endpoints
 * (status/check / deep-diagnostic) intentionally bypass this cache and write
 * through `runStatusCheckComponent`/`requestStatusCheck`/`requestDeepDiagnostic`.
 */

const STATUS_TTL_MS = 30_000;

interface CacheEntry<T> {
  promise: Promise<T>;
  expiresAt: number;
  settled: boolean;
}

const latestCache = new Map<string, CacheEntry<StatusRun | null>>();
const historyCache = new Map<string, CacheEntry<StatusRun[]>>();

function scopeKey(projectId?: string, sceneId?: string): string {
  return `${projectId ?? ""}::${sceneId ?? ""}`;
}

/**
 * Run `fetcher` once per scope until the TTL expires; concurrent callers share
 * the same in-flight promise (single flight). Failed fetches are evicted so the
 * next caller retries instead of being handed a cached rejection.
 */
function withStatusTtl<T>(cache: Map<string, CacheEntry<T>>, key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = cache.get(key);
  if (existing) {
    if (existing.settled && Date.now() < existing.expiresAt) {
      return existing.promise;
    }
    if (!existing.settled) {
      // Another caller is already fetching this scope — coalesce onto it.
      return existing.promise;
    }
  }

  const entry: CacheEntry<T> = {
    promise: fetcher()
      .then((result) => {
        entry.settled = true;
        entry.expiresAt = Date.now() + STATUS_TTL_MS;
        return result;
      })
      .catch((error) => {
        cache.delete(key);
        throw error;
      }),
    expiresAt: Date.now() + STATUS_TTL_MS,
    settled: false,
  };
  cache.set(key, entry);
  return entry.promise;
}

export async function fetchStatusRegistry(): Promise<StatusRegistryCheck[]> {
  const payload = await api.codirectorStatusRegistry();
  return payload.checks;
}

export async function runStatusCheck(body: StatusCheckRequest): Promise<StatusRun> {
  return api.codirectorStatusCheck(body);
}

export async function runStatusCheckComponent(checkId: string, body: StatusCheckRequest): Promise<StatusRun> {
  return api.codirectorStatusCheckComponent(checkId, body);
}

export async function runDeepDiagnostic(body: StatusCheckRequest & { confirm: boolean }): Promise<StatusRun> {
  return api.codirectorDeepDiagnostic(body);
}

export async function fetchLatestStatus(projectId?: string, sceneId?: string): Promise<StatusRun | null> {
  const key = scopeKey(projectId, sceneId);
  return withStatusTtl(latestCache, key, () => {
    return api.codirectorStatusLatest({ projectId, sceneId }).then((payload) => payload.run);
  });
}

export async function fetchStatusHistory(projectId?: string, sceneId?: string, limit = 20): Promise<StatusRun[]> {
  const key = scopeKey(projectId, sceneId);
  return withStatusTtl(historyCache, key, () => {
    return api.codirectorStatusHistory({ projectId, sceneId, limit }).then((payload) => payload.runs);
  });
}

export function rememberLatestStatus(projectId?: string, sceneId?: string, run?: StatusRun | null): void {
  const key = scopeKey(projectId, sceneId);
  latestCache.set(key, {
    promise: Promise.resolve(run ?? null),
    expiresAt: Date.now() + STATUS_TTL_MS,
    settled: true,
  });
}

export function invalidateStatusCaches(projectId?: string, sceneId?: string): void {
  if (!projectId && !sceneId) {
    latestCache.clear();
    historyCache.clear();
    return;
  }
  const key = scopeKey(projectId, sceneId);
  latestCache.delete(key);
  historyCache.delete(key);
}

export function statusEventsUrl(): string {
  return "/api/codirector/status/events";
}

/** Queued Image Generator job with no hydrate after this many ms is treated as failed. */
export const CIS_QUEUED_NO_HYDRATE_MS = 30_000;

export function cisJobHasHydrate(job: { progress?: number | null; status?: string }): boolean {
  return typeof job.progress === "number" && Number.isFinite(job.progress) && job.progress > 0;
}

export function staleCisQueuedNoHydrate(
  job: { status?: string; progress?: number | null },
  startedAt: number,
  now: number = Date.now(),
  timeoutMs: number = CIS_QUEUED_NO_HYDRATE_MS,
): boolean {
  const status = String(job.status || "").toLowerCase();
  if (status !== "queued" && status !== "pending") return false;
  if (cisJobHasHydrate(job)) return false;
  return now - startedAt >= timeoutMs;
}

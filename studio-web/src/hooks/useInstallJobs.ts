import { useEffect, useRef, useState } from "react";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import {
  installJobFromDownloadOperation,
  isInstallJobActive,
  type InstallJob,
} from "../contracts/installJobs";
import { setInstallJobsSnapshot } from "../state/installJobsStore";

function dedupeJobs(jobs: InstallJob[]): InstallJob[] {
  const seen = new Map<string, InstallJob>();
  for (const job of jobs) {
    seen.set(job.id, job);
  }
  return Array.from(seen.values());
}

function applyFilter(jobs: InstallJob[], opts?: { activeOnly?: boolean; componentId?: string }) {
  return jobs.filter((job) => {
    if (opts?.componentId && job.componentId !== opts.componentId) return false;
    if (opts?.activeOnly ?? true) return isInstallJobActive(job);
    return true;
  });
}

async function fetchJobsSnapshot(
  opts?: { activeOnly?: boolean; componentId?: string },
  signal?: AbortSignal,
): Promise<InstallJob[]> {
  const [installJobs, downloads] = await Promise.all([
    api.installJobs
      .list({
        active: opts?.activeOnly ?? true,
        componentId: opts?.componentId,
        signal,
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : String(err);
        if (/404|not found/i.test(message)) return [] as InstallJob[];
        throw err;
      }),
    api
      .listDownloads({
        active: opts?.activeOnly ?? true,
        componentId: opts?.componentId,
        signal,
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : String(err);
        if (/404|not found/i.test(message)) return { operations: [] };
        throw err;
      }),
  ]);

  return dedupeJobs([
    ...(installJobs || []),
    ...((downloads.operations || []).map(installJobFromDownloadOperation)),
  ]);
}

/**
 * SSE-first install job transport with bounded polling fallback.
 * Does not invent progress from click time — only server-reported job state.
 */
export function useInstallJobs(
  enabled = true,
  intervalMs = 2500,
  opts?: { activeOnly?: boolean; componentId?: string },
) {
  const [jobs, setJobs] = useState<InstallJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [transport, setTransport] = useState<"sse" | "poll">("sse");
  const mountedRef = useRef(true);
  const delayRef = useRef(intervalMs);
  const sseOkRef = useRef(false);

  const publish = (next: InstallJob[]) => {
    const filtered = applyFilter(next, opts);
    setJobs(filtered);
    setInstallJobsSnapshot(next);
  };

  const refresh = async (signal?: AbortSignal) => {
    try {
      const merged = await fetchJobsSnapshot(opts, signal);
      if (!mountedRef.current || signal?.aborted) return;
      publish(merged);
      setError(null);
      delayRef.current = intervalMs;
    } catch (err) {
      if (isAbortError(err) || signal?.aborted || !mountedRef.current) return;
      if (isNavigationFetchFailure(err)) return;
      setError(err instanceof Error ? err.message : String(err));
      delayRef.current = Math.min(Math.round(delayRef.current * 1.6), 15000);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) return;

    let pollTimer: number | undefined;
    let es: EventSource | null = null;
    const ac = new AbortController();
    let pollActive = false;

    const stopPoll = () => {
      pollActive = false;
      if (pollTimer) {
        window.clearTimeout(pollTimer);
        pollTimer = undefined;
      }
    };

    const startPoll = () => {
      if (pollActive) return;
      pollActive = true;
      setTransport("poll");
      const tick = async () => {
        if (!mountedRef.current || document.visibilityState === "hidden") {
          pollTimer = window.setTimeout(tick, delayRef.current);
          return;
        }
        await refresh(ac.signal);
        if (!mountedRef.current || ac.signal.aborted || !pollActive) return;
        pollTimer = window.setTimeout(tick, delayRef.current);
      };
      void tick();
    };

    const upsertJob = (job: InstallJob) => {
      setJobs((prev) => {
        const map = new Map(prev.map((item) => [item.id, item]));
        map.set(job.id, job);
        const next = Array.from(map.values());
        setInstallJobsSnapshot(next);
        return applyFilter(next, opts);
      });
    };

    try {
      const params = new URLSearchParams();
      if (opts?.componentId) params.set("componentId", opts.componentId);
      const url = `/api/setup/install-jobs/events${params.toString() ? `?${params}` : ""}`;
      es = new EventSource(url);
      setTransport("sse");

      es.addEventListener("snapshot", (evt) => {
        try {
          const data = JSON.parse((evt as MessageEvent).data || "{}") as { jobs?: InstallJob[] };
          sseOkRef.current = true;
          stopPoll();
          setTransport("sse");
          publish(Array.isArray(data.jobs) ? data.jobs : []);
          setError(null);
        } catch {
          /* ignore malformed snapshot */
        }
      });

      const onJobEvent = (evt: Event) => {
        try {
          const data = JSON.parse((evt as MessageEvent).data || "{}") as { job?: InstallJob };
          if (data.job?.id) {
            sseOkRef.current = true;
            stopPoll();
            setTransport("sse");
            upsertJob(data.job);
            setError(null);
          }
        } catch {
          /* ignore */
        }
      };
      es.addEventListener("install_job", onJobEvent);
      es.onmessage = onJobEvent;

      es.onerror = () => {
        sseOkRef.current = false;
        if (es) {
          es.close();
          es = null;
        }
        startPoll();
      };
    } catch {
      startPoll();
    }

    // Initial fetch so first paint is not empty while SSE connects.
    void refresh(ac.signal);

    const onVisibility = () => {
      if (document.visibilityState === "visible" && !sseOkRef.current) {
        void refresh();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      mountedRef.current = false;
      ac.abort();
      stopPoll();
      document.removeEventListener("visibilitychange", onVisibility);
      if (es) es.close();
    };
  }, [enabled, intervalMs, opts?.activeOnly, opts?.componentId]);

  return { jobs, error, transport, refresh: () => refresh() };
}

/** @deprecated Prefer useInstallJobs — kept for existing imports. */
export function useInstallJobsPoll(
  enabled = true,
  intervalMs = 1000,
  opts?: { activeOnly?: boolean; componentId?: string },
) {
  return useInstallJobs(enabled, intervalMs, opts);
}

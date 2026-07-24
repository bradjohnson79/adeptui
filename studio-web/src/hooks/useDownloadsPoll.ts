import { useEffect, useRef, useState } from "react";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import type { DownloadOperation } from "../setup/types";

/** Shared polling for active download operations (Phase 1B). */
export function useDownloadsPoll(enabled = true, intervalMs = 1000) {
  const [operations, setOperations] = useState<DownloadOperation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const delayRef = useRef(intervalMs);

  const refresh = async (signal?: AbortSignal) => {
    try {
      const data = await api.listDownloads({ active: true, signal });
      if (!mountedRef.current || signal?.aborted) return;
      setOperations(data.operations || []);
      setError(null);
      delayRef.current = intervalMs;
    } catch (err) {
      if (isAbortError(err) || signal?.aborted || !mountedRef.current) return;
      if (isNavigationFetchFailure(err)) return;
      setError(err instanceof Error ? err.message : String(err));
      delayRef.current = Math.min(delayRef.current * 1.6, 15000);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) return;
    let timer: number | undefined;
    const ac = new AbortController();
    const tick = async () => {
      await refresh(ac.signal);
      if (!mountedRef.current || ac.signal.aborted) return;
      timer = window.setTimeout(tick, delayRef.current);
    };
    void tick();
    return () => {
      mountedRef.current = false;
      ac.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [enabled, intervalMs]);

  return { operations, error, refresh: () => refresh() };
}

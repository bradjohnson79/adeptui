import { useCallback, useEffect, useState } from "react";
import type { Health } from "../types";
import { api } from "../api";
import {
  ensureStudioApiConnectionMonitor,
  getStudioApiConnection,
  subscribeStudioApiConnection,
} from "../runtime/studioApiConnection";

export function useStudioHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<unknown>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.health();
      setHealth(data);
      setError(null);
    } catch {
      // Connection monitor handles outage state; don't override its error.
    }
  }, []);

  const reload = useCallback(async () => {
    // Phase BS — central health monitor is the single authority.
    // This hook reads from the central monitor AND fetches the actual health payload.
    const snap = getStudioApiConnection();
    if (snap.state === "OFFLINE") {
      setError(new Error("Studio API is offline"));
    } else if (snap.state === "RECONNECTING") {
      setError(new Error("Reconnecting to Studio API…"));
    } else {
      await fetchHealth();
    }
  }, [fetchHealth]);

  useEffect(() => {
    ensureStudioApiConnectionMonitor();

    // Initial health fetch — don't wait for the monitor to tell us to fetch.
    void fetchHealth();

    const unsub = subscribeStudioApiConnection(() => {
      // Rerender on central monitor state changes — and refetch health when connected.
      const snap = getStudioApiConnection();
      if (snap.state === "CONNECTED" || snap.state === "RECOVERED") {
        setError(null);
        void fetchHealth();
      } else if (snap.state === "OFFLINE") {
        setError(new Error("Studio API is offline"));
      } else if (snap.state === "RECONNECTING") {
        setError(new Error("Reconnecting to Studio API…"));
      }
    });
    return () => unsub();
  }, [fetchHealth]);

  return { health, error, reload };
}

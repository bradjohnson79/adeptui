import { useCallback, useEffect, useRef, useState } from "react";
import type { Health } from "../types";
import { api } from "../api";
import {
  ensureStudioApiConnectionMonitor,
  getStudioApiConnection,
  subscribeStudioApiConnection,
  type StudioApiConnectionState,
} from "../runtime/studioApiConnection";

export function useStudioHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<unknown>(null);
  const prevStateRef = useRef<StudioApiConnectionState | null>(null);
  const fetchInFlightRef = useRef(false);

  const fetchHealth = useCallback(async () => {
    if (fetchInFlightRef.current) return;
    fetchInFlightRef.current = true;
    try {
      const data = await api.health();
      setHealth(data);
      setError(null);
    } catch {
      // Connection monitor handles outage state; don't override its error.
    } finally {
      fetchInFlightRef.current = false;
    }
  }, []);

  const reload = useCallback(async () => {
    const snap = getStudioApiConnection();
    if (snap.state === "OFFLINE") {
      setError(new Error("Studio API is offline"));
    } else if (snap.state === "RECONNECTING") {
      setError(new Error("Reconnecting to Studio API\u2026"));
    } else {
      await fetchHealth();
    }
  }, [fetchHealth]);

  useEffect(() => {
    ensureStudioApiConnectionMonitor();

    void fetchHealth();

    const unsub = subscribeStudioApiConnection(() => {
      const snap = getStudioApiConnection();
      const prev = prevStateRef.current;
      prevStateRef.current = snap.state;

      const transitionedFrom = (from: StudioApiConnectionState[]) =>
        prev != null && from.includes(prev);

      if (snap.state === "CONNECTED" && transitionedFrom(["RECOVERED"])) {
        setError(null);
        void fetchHealth();
      } else if (snap.state === "RECOVERED") {
        setError(null);
        void fetchHealth();
      } else if (snap.state === "OFFLINE") {
        setError(new Error("Studio API is offline"));
      } else if (snap.state === "RECONNECTING") {
        setError(new Error("Reconnecting to Studio API\u2026"));
      }
    });
    return () => unsub();
  }, [fetchHealth]);

  return { health, error, reload };
}

import { useCallback, useEffect, useState } from "react";
import type { Health } from "../types";
import {
  ensureStudioApiConnectionMonitor,
  getStudioApiConnection,
  subscribeStudioApiConnection,
} from "../runtime/studioApiConnection";

export function useStudioHealth() {
  const [health] = useState<Health | null>(null);
  const [error, setError] = useState<unknown>(null);

  const reload = useCallback(async () => {
    // Phase BS — central health monitor is the single authority.
    // This hook reads from the central monitor, not from its own /api/health call.
    const snap = getStudioApiConnection();
    if (snap.state === "OFFLINE") {
      setError(new Error("Studio API is offline"));
    } else if (snap.state === "RECONNECTING") {
      setError(new Error("Reconnecting to Studio API…"));
    } else {
      setError(null);
    }
  }, []);

  useEffect(() => {
    ensureStudioApiConnectionMonitor();
    const unsub = subscribeStudioApiConnection(() => {
      // Rerender on central monitor state changes — no own polling.
      const snap = getStudioApiConnection();
      if (snap.state === "CONNECTED" || snap.state === "RECOVERED") {
        setError(null);
      } else if (snap.state === "OFFLINE") {
        setError(new Error("Studio API is offline"));
      }
    });
    return () => unsub();
  }, []);

  return { health, error, reload };
}

/**
 * Shared Studio API outage coordinator.
 * One connection state for the whole UI — panels must not independently spam retries.
 */

import { apiUrl } from "./apiBase";

export type StudioApiConnectionState =
  | "CONNECTED"
  | "RECONNECTING"
  | "DEGRADED"
  | "OFFLINE"
  | "RECOVERED";

export type StudioApiFailureCode =
  | "STUDIO_API_OFFLINE"
  | "STUDIO_API_CONNECTION_RESET"
  | "API_PROXY_UNAVAILABLE"
  | "UNKNOWN";

export type StudioApiConnectionSnapshot = {
  state: StudioApiConnectionState;
  failureCode: StudioApiFailureCode | null;
  lastError: string | null;
  consecutiveFailures: number;
  lastHealthyAt: number | null;
  lastCheckedAt: number | null;
  recoveredAt: number | null;
  pollingSuspended: boolean;
};

type Listener = (snap: StudioApiConnectionSnapshot) => void;

const INITIAL: StudioApiConnectionSnapshot = {
  state: "CONNECTED",
  failureCode: null,
  lastError: null,
  consecutiveFailures: 0,
  lastHealthyAt: null,
  lastCheckedAt: null,
  recoveredAt: null,
  pollingSuspended: false,
};

let snapshot: StudioApiConnectionSnapshot = { ...INITIAL };
const listeners = new Set<Listener>();
let healthTimer: number | null = null;
let probeInFlight: Promise<boolean> | null = null;
let recoverHandlers = new Set<() => void | Promise<void>>();

const BASE_RETRY_MS = 1_200;
const MAX_RETRY_MS = 30_000;

export function getStudioApiConnection(): StudioApiConnectionSnapshot {
  return snapshot;
}

export function subscribeStudioApiConnection(listener: Listener): () => void {
  listeners.add(listener);
  listener(snapshot);
  return () => {
    listeners.delete(listener);
  };
}

export function onStudioApiRecovered(handler: () => void | Promise<void>): () => void {
  recoverHandlers.add(handler);
  return () => {
    recoverHandlers.delete(handler);
  };
}

function emit() {
  for (const listener of listeners) {
    try {
      listener(snapshot);
    } catch {
      /* ignore subscriber errors */
    }
  }
}

function setSnapshot(patch: Partial<StudioApiConnectionSnapshot>) {
  const next = { ...snapshot, ...patch };
  const changed =
    next.state !== snapshot.state ||
    next.pollingSuspended !== snapshot.pollingSuspended ||
    next.consecutiveFailures !== snapshot.consecutiveFailures ||
    next.lastError !== snapshot.lastError ||
    next.failureCode !== snapshot.failureCode;
  snapshot = next;
  if (changed) emit();
}

export function nextStudioApiRetryMs(consecutiveFailures: number): number {
  if (consecutiveFailures <= 0) return BASE_RETRY_MS;
  const exp = Math.min(consecutiveFailures, 6);
  return Math.min(MAX_RETRY_MS, BASE_RETRY_MS * 2 ** (exp - 1));
}

export function classifyStudioApiTransportFailure(error: unknown): StudioApiFailureCode {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const lower = message.toLowerCase();
  if (/connection reset|err_connection_reset|forcibly closed|econnreset/i.test(lower)) {
    return "STUDIO_API_CONNECTION_RESET";
  }
  if (/proxy|bad gateway|502|api_proxy/i.test(lower)) {
    return "API_PROXY_UNAVAILABLE";
  }
  if (
    /failed to fetch|networkerror|err_connection_refused|connection refused|econnrefused|load failed/i.test(
      lower,
    )
  ) {
    return "STUDIO_API_OFFLINE";
  }
  return "UNKNOWN";
}

export function isStudioApiConnectivityFailure(error: unknown): boolean {
  if (!error) return false;
  if (typeof error === "object" && error !== null) {
    const code = String(
      (error as { code?: string; error_code?: string }).code
        || (error as { error_code?: string }).error_code
        || "",
    );
    if (
      code === "STUDIO_API_OFFLINE"
      || code === "STUDIO_API_CONNECTION_RESET"
      || code === "API_PROXY_UNAVAILABLE"
      || code === "BACKEND_UNAVAILABLE"
    ) {
      return true;
    }
  }
  return classifyStudioApiTransportFailure(error) !== "UNKNOWN";
}

/** True when dependent polls (PA, wiki refresh loops, revision spam) should pause. */
export function shouldSuspendDependentPolling(): boolean {
  return snapshot.pollingSuspended || snapshot.state === "OFFLINE" || snapshot.state === "RECONNECTING";
}

function scheduleHealthProbe(delayMs: number) {
  if (typeof window === "undefined") return;
  if (healthTimer != null) {
    window.clearTimeout(healthTimer);
  }
  healthTimer = window.setTimeout(() => {
    healthTimer = null;
    void probeStudioApiHealth();
  }, delayMs);
}

async function probeStudioApiHealth(): Promise<boolean> {
  if (probeInFlight) return probeInFlight;
  probeInFlight = (async () => {
    const checkedAt = Date.now();
    try {
      // Fast path: lightweight /healthz (no DB, no ComfyUI, no provider checks)
      const hzController = new AbortController();
      const hzTimeoutId = window.setTimeout(() => hzController.abort(), 5_000);
      try {
        const hz = await fetch(apiUrl("/api/healthz"), {
          method: "GET", credentials: "include", signal: hzController.signal,
        });
        if (hz.ok) {
          markStudioApiHealthy();
          setSnapshot({ lastCheckedAt: checkedAt });
          return true;
        }
      } catch {
        // healthz failed — fall through to full health check
      } finally {
        window.clearTimeout(hzTimeoutId);
      }

      // Full health check with its own timeout
      const fullController = new AbortController();
      const fullTimeoutId = window.setTimeout(() => fullController.abort(), 10_000);
      try {
        const res = await fetch(apiUrl("/api/health"), { method: "GET", credentials: "include", signal: fullController.signal });
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          let code: StudioApiFailureCode = "STUDIO_API_OFFLINE";
          try {
            const payload = JSON.parse(text) as { detail?: { error_code?: string; code?: string } };
            const c = payload?.detail?.error_code || payload?.detail?.code;
            if (c === "STUDIO_API_CONNECTION_RESET" || c === "API_PROXY_UNAVAILABLE" || c === "STUDIO_API_OFFLINE") {
              code = c;
            }
          } catch {
            /* plain body */
          }
          markStudioApiDegraded(code, `Health check returned HTTP ${res.status}`);
          return true;
        }
        markStudioApiHealthy();
        return true;
      } catch (error) {
        const code = classifyStudioApiTransportFailure(error);
        markStudioApiFailure(
          code === "UNKNOWN" ? "STUDIO_API_OFFLINE" : code,
          error instanceof Error ? error.message : String(error),
        );
        return false;
      } finally {
        window.clearTimeout(fullTimeoutId);
        setSnapshot({ lastCheckedAt: checkedAt });
      }
    } finally {
      // SINGLE cleanup point — covers healthz success, healthz failure,
      // full health success, full health failure, timeout, exception, early return.
      probeInFlight = null;
    }
  })();
  return probeInFlight;
}

export function markStudioApiFailure(code: StudioApiFailureCode, message?: string | null) {
  const failures = snapshot.consecutiveFailures + 1;
  // Hysteresis: RECONNECTING for first 4 failures, OFFLINE only on 5th+
  const state: StudioApiConnectionState = failures >= 5 ? "OFFLINE" : "RECONNECTING";
  setSnapshot({
    state,
    failureCode: code,
    lastError: message || code,
    consecutiveFailures: failures,
    pollingSuspended: failures >= 3,  // Suspend dependent polls after 3 failures
  });
  scheduleHealthProbe(nextStudioApiRetryMs(failures));
}

export function markStudioApiHealthy() {
  const wasOffline =
    snapshot.state === "OFFLINE"
    || snapshot.state === "RECONNECTING"
    || snapshot.pollingSuspended
    || snapshot.consecutiveFailures > 0;
  const now = Date.now();
  if (wasOffline) {
    setSnapshot({
      state: "RECOVERED",
      failureCode: null,
      lastError: null,
      consecutiveFailures: 0,
      lastHealthyAt: now,
      recoveredAt: now,
      pollingSuspended: false,
    });
    for (const handler of recoverHandlers) {
      void Promise.resolve(handler()).catch(() => undefined);
    }
    // Settle RECOVERED → CONNECTED after a short notice window.
    if (typeof window !== "undefined") {
      window.setTimeout(() => {
        if (snapshot.state === "RECOVERED") {
          setSnapshot({ state: "CONNECTED" });
        }
      }, 4_000);
    }
  } else {
    setSnapshot({
      state: "CONNECTED",
      failureCode: null,
      lastError: null,
      consecutiveFailures: 0,
      lastHealthyAt: now,
      pollingSuspended: false,
    });
  }
  if (healthTimer != null && typeof window !== "undefined") {
    window.clearTimeout(healthTimer);
    healthTimer = null;
  }
}

/** Mark API as reachable but degraded — liveness OK, readiness partial.
 *
 *  Transition: any state → DEGRADED.
 *  DEGRADED does NOT suspend dependent polling — chat and Co-Director remain usable.
 *  Only the degraded capability is affected.
 */
export function markStudioApiDegraded(code: string, message?: string | null) {
  const now = Date.now();
  setSnapshot({
    state: "DEGRADED",
    failureCode: code as StudioApiFailureCode,
    lastError: message || code,
    lastHealthyAt: now,
    lastCheckedAt: now,
    pollingSuspended: false,  // Do NOT suspend dependent polling — liveness is intact
  });
  // Continue health monitoring on the normal cadence
  if (healthTimer == null) {
    healthTimer = window.setTimeout(() => {
      healthTimer = null;
      void probeStudioApiHealth();
    }, 15_000);
  }
}

/** Manual retry from the outage banner. */
export async function retryStudioApiConnection(): Promise<boolean> {
  setSnapshot({
    state: "RECONNECTING",
    pollingSuspended: true,
  });
  return probeStudioApiHealth();
}

/** Call from the shared API client when a transport-level failure is observed. */
export function noteStudioApiTransportError(error: unknown) {
  if (!isStudioApiConnectivityFailure(error)) return;
  const code = (() => {
    if (typeof error === "object" && error !== null) {
      const c = String(
        (error as { code?: string; error_code?: string }).code
          || (error as { error_code?: string }).error_code
          || "",
      );
      if (c === "STUDIO_API_CONNECTION_RESET") return "STUDIO_API_CONNECTION_RESET" as const;
      if (c === "API_PROXY_UNAVAILABLE") return "API_PROXY_UNAVAILABLE" as const;
      if (c === "STUDIO_API_OFFLINE" || c === "BACKEND_UNAVAILABLE") return "STUDIO_API_OFFLINE" as const;
    }
    const classified = classifyStudioApiTransportFailure(error);
    return classified === "UNKNOWN" ? "STUDIO_API_OFFLINE" : classified;
  })();
  markStudioApiFailure(code, error instanceof Error ? error.message : String(error));
}

/** Ensure the coordinator is watching; safe to call multiple times. */
export function ensureStudioApiConnectionMonitor() {
  if (typeof window === "undefined") return;
  if (healthTimer == null && snapshot.state === "CONNECTED" && snapshot.consecutiveFailures === 0) {
    // Light heartbeat when healthy — 20s. Dependent panels must respect suspension.
    healthTimer = window.setTimeout(() => {
      healthTimer = null;
      void probeStudioApiHealth().then((ok) => {
        if (ok) scheduleHealthProbe(20_000);
      });
    }, 20_000);
  }
}

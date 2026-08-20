/** Shared timeout and creator-facing errors for CD Scene Review / Smart Select. */

export const PERCEPTION_REQUEST_MS = 45_000;

export const SCENE_REVIEW_START_FAILED = "Scene review couldn't start.";
export const SMART_SELECT_PAINT = "Paint the region.";

export function perceptionAbortSignal(ms = PERCEPTION_REQUEST_MS): AbortSignal {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

function isTimeoutOrAbort(err: unknown): boolean {
  if (!err) return false;
  if (typeof DOMException !== "undefined" && err instanceof DOMException) {
    return err.name === "AbortError" || err.name === "TimeoutError";
  }
  if (err instanceof Error) {
    return err.name === "AbortError" || err.name === "TimeoutError" || /aborted|timeout/i.test(err.message);
  }
  return false;
}

export function creatorPerceptionMessage(err: unknown, fallback: string): string {
  if (isTimeoutOrAbort(err)) return fallback;
  const raw = err instanceof Error ? err.message : String(err ?? "");
  if (!raw.trim()) return fallback;
  if (/RuntimeError|Traceback|subprocess|File "|\.py|exit code|WinError/i.test(raw)) return fallback;
  if (raw.length > 180) return fallback;
  return raw;
}

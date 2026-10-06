/** Session-only hide of terminal render-queue rows and the 1 Frame failure overlay. */

export const RENDER_QUEUE_DISMISS_EVENT = "adept-render-queue-dismissed";

function storageKey(projectId: string): string {
  return `adept_render_queue_dismissed:${projectId}`;
}

export function loadDismissedRenderJobIds(projectId: string): Set<string> {
  try {
    const raw = sessionStorage.getItem(storageKey(projectId));
    const arr = raw ? (JSON.parse(raw) as string[]) : [];
    return new Set(Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function saveDismissedRenderJobIds(projectId: string, ids: Set<string>): void {
  try {
    sessionStorage.setItem(storageKey(projectId), JSON.stringify([...ids]));
  } catch {
    /* ignore quota / private mode */
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(RENDER_QUEUE_DISMISS_EVENT, { detail: { projectId } }));
  }
}

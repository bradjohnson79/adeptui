/**
 * Double-click opens the Timed Prompt modal on pointerup. The browser then
 * sends click, often after a microtask, onto whatever is now under the
 * pointer. If that is the modal backdrop, the same gesture dismisses it and
 * the creator is back on the Timeline. Open on the next turn, and ignore
 * backdrop/Escape dismiss for a short beat so that leftover click cannot close it.
 */
export const TIMED_PROMPT_OPEN_DISMISS_GUARD_MS = 200;

export function openTimedPromptAfterGesture(open: (id: string) => void, id: string): void {
  const promptId = String(id || "").trim();
  if (!promptId) return;
  globalThis.setTimeout(() => open(promptId), 0);
}

export function timedPromptDismissGuardUntil(now = Date.now()): number {
  return now + TIMED_PROMPT_OPEN_DISMISS_GUARD_MS;
}

export function shouldIgnoreTimedPromptDismiss(now: number, guardUntil: number): boolean {
  return now < guardUntil;
}

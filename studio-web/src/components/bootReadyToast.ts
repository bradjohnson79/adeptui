/** Session lifetime of the startup readiness notice. Errors are not on this timer. */
export const BOOT_READY_TOAST_MS = 6000;
export const BOOT_READY_DISMISS_KEY = "adept-boot-ready-dismissed";

export function bootReadyToastVisible(input: {
  gaugeVisible: boolean;
  verdict?: string;
  dismissed: boolean;
  now: number;
  shownAt: number | null;
}): boolean {
  if (input.gaugeVisible || input.dismissed || input.verdict !== "GO" || input.shownAt == null) return false;
  return input.now - input.shownAt < BOOT_READY_TOAST_MS;
}

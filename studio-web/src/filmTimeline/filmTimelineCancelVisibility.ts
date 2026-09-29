/** Active Film Timeline segment statuses that own a real cancelable job / Comfy prompt. */
export const FILM_TIMELINE_ACTIVE_STATUSES = [
  "queued",
  "generating",
  "processing",
  "downloading",
] as const;

export type FilmTimelineActiveStatus = (typeof FILM_TIMELINE_ACTIVE_STATUSES)[number];

const ACTIVE = new Set<string>(FILM_TIMELINE_ACTIVE_STATUSES);

/**
 * Whether Cancel is armed (real job to cancel).
 * The V1 red Cancel pill is always mounted in Preview upper-left; this flag
 * only enables the click / clears aria-disabled. Idle / completed / failed /
 * cancelled segments leave Cancel visible but disabled (no false toast).
 */
export function filmTimelineHasCancellableJob(
  segments: Array<{ status?: string | null }> | null | undefined,
): boolean {
  return (segments || []).some((item) => ACTIVE.has(String(item.status || "")));
}

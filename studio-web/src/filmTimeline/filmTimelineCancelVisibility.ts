/** Active Film Timeline segment statuses that own a real cancelable job / Comfy prompt. */
export const FILM_TIMELINE_ACTIVE_STATUSES = [
  "queued",
  "generating",
  "processing",
  "downloading",
] as const;

export type FilmTimelineActiveStatus = (typeof FILM_TIMELINE_ACTIVE_STATUSES)[number];

const ACTIVE = new Set<string>(FILM_TIMELINE_ACTIVE_STATUSES);

export type FilmTimelineCancelSegment = {
  status?: string | null;
  generationMetadata?: { renderStatus?: { apiPhase?: string | null } | null } | null;
};

/**
 * Preview Monitor Cancel.
 * Local renders keep the button armed for the whole job.
 * API video keeps it armed only during preparation. Once the provider
 * generation starts, the button is hidden until that render finishes,
 * then the idle button returns to the same spot.
 */
export function filmTimelineCancelPresentation(
  segments: FilmTimelineCancelSegment[] | null | undefined,
): { visible: boolean; armed: boolean } {
  const active = (segments || []).find((item) => ACTIVE.has(String(item.status || "")));
  if (!active) return { visible: true, armed: false };
  if (active.generationMetadata?.renderStatus?.apiPhase === "generating") {
    return { visible: false, armed: false };
  }
  return { visible: true, armed: true };
}

/**
 * Whether Cancel is armed (real job to cancel).
 * Idle / completed / failed / cancelled segments leave Cancel visible but disabled.
 */
export function filmTimelineHasCancellableJob(
  segments: FilmTimelineCancelSegment[] | null | undefined,
): boolean {
  return filmTimelineCancelPresentation(segments).armed;
}

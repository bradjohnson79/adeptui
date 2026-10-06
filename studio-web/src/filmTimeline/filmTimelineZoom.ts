import {
  FILM_TIMELINE_ZOOM_DEFAULT,
  FILM_TIMELINE_ZOOM_MAX,
  FILM_TIMELINE_ZOOM_MIN,
  clampTimelineZoom,
} from "../timelineMaster/timelineZoom";

const STORAGE_KEY = "adept.filmTimeline.zoom";

function clampZoom(value: number): number {
  return clampTimelineZoom(value, FILM_TIMELINE_ZOOM_MIN, FILM_TIMELINE_ZOOM_MAX);
}

function readStoredZoom(): number {
  try {
    if (typeof sessionStorage === "undefined") return FILM_TIMELINE_ZOOM_DEFAULT;
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw == null || raw === "") return FILM_TIMELINE_ZOOM_DEFAULT;
    return clampZoom(Number(raw));
  } catch {
    return FILM_TIMELINE_ZOOM_DEFAULT;
  }
}

let zoom = readStoredZoom();
const listeners = new Set<() => void>();

/** Session zoom for Timeline V2. Survives scene changes in this tab. Not a project field. */
export function getFilmTimelineZoom(): number {
  return zoom;
}

export function setFilmTimelineZoom(value: number): void {
  const next = clampZoom(value);
  if (next === zoom) return;
  zoom = next;
  try {
    sessionStorage.setItem(STORAGE_KEY, String(next));
  } catch {
    /* Private mode can refuse storage. The in-memory value still holds for this session. */
  }
  listeners.forEach((listener) => listener());
}

export function subscribeFilmTimelineZoom(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

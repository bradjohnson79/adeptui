/** Same-track no-overlap law.

Hard law: no temporal intersection on the same track.
Adjacent boundaries are legal (A.end == B.start).
Epsilon ~1e-9 matches the Python twin.
Music is aliased to the Audio lane until a separate Music lane exists.
*/
export const SAME_TRACK_EPS = 1e-9;

/** Creator toast / save-error copy when a placement would overlap. */
export const USER_FACING_TRACK_OCCUPIED = "That part of the track is already occupied.";

/** Co-Director chat copy (Law #39 — no raw timing codes). */
export const CD_LAYMAN_TRACK_OCCUPIED =
  "That section of the track is already in use. Choose another time range.";

export type SameTrackClip = {
  id?: string | null;
  start?: number | null;
  length?: number | null;
};

export class SameTrackOverlapError extends Error {
  readonly code = "SAME_TRACK_OVERLAP";
  constructor(message: string) {
    super(message);
    this.name = "SameTrackOverlapError";
  }
}

export function rangesIntersect(
  aStart: number,
  aLen: number,
  bStart: number,
  bLen: number,
): boolean {
  const a0 = Number(aStart);
  const a1 = a0 + Number(aLen);
  const b0 = Number(bStart);
  const b1 = b0 + Number(bLen);
  if (![a0, a1, b0, b1].every(Number.isFinite)) return false;
  return a0 < b1 - SAME_TRACK_EPS && b0 < a1 - SAME_TRACK_EPS;
}

export function findSameTrackIntersection(
  clips: SameTrackClip[] | null | undefined,
  candidate: SameTrackClip,
): SameTrackClip | null {
  const candId = candidate?.id != null && String(candidate.id) !== "" ? String(candidate.id) : null;
  const cStart = Number(candidate?.start || 0);
  const cLen = Number(candidate?.length || 0);
  for (const clip of clips || []) {
    const id = clip?.id != null && String(clip.id) !== "" ? String(clip.id) : null;
    if (candId && id && id === candId) continue;
    if (rangesIntersect(cStart, cLen, Number(clip?.start || 0), Number(clip?.length || 0))) {
      return clip;
    }
  }
  return null;
}

export function findSameTrackOverlapPair(
  clips: SameTrackClip[] | null | undefined,
): { a: SameTrackClip; b: SameTrackClip } | null {
  const items = clips || [];
  for (let i = 0; i < items.length; i += 1) {
    const hit = findSameTrackIntersection(items.slice(i + 1), items[i]);
    if (hit) return { a: items[i], b: hit };
  }
  return null;
}

export function sameTrackOverlapError(
  clips: SameTrackClip[] | null | undefined,
  candidate: SameTrackClip,
  track = "track",
): string | null {
  const hit = findSameTrackIntersection(clips, candidate);
  if (!hit) return null;
  const cand = candidate.id || "(new)";
  const other = hit.id || "(other)";
  return `SAME_TRACK_OVERLAP: clip ${cand} intersects ${other} on the ${track} track`;
}

export function assertNoSameTrackOverlap(
  clips: SameTrackClip[] | null | undefined,
  candidate: SameTrackClip,
  track = "track",
): void {
  const message = sameTrackOverlapError(clips, candidate, track);
  if (message) throw new SameTrackOverlapError(message);
}

/** First scene time where `length` fits before `horizon` without intersecting existing clips. */
export function firstFreeSameTrackStart(
  clips: SameTrackClip[] | null | undefined,
  length: number,
  horizon: number,
): number | null {
  const need = Number(length);
  const limit = Number(horizon);
  if (!Number.isFinite(need) || need <= SAME_TRACK_EPS) return null;
  if (!Number.isFinite(limit) || need > limit + SAME_TRACK_EPS) return null;
  const sorted = [...(clips || [])].sort(
    (a, b) => Number(a.start || 0) - Number(b.start || 0),
  );
  let cursor = 0;
  for (const clip of sorted) {
    const start = Number(clip.start || 0);
    const end = start + Number(clip.length || 0);
    if (start >= cursor + need - SAME_TRACK_EPS) return cursor;
    if (end > cursor) cursor = end;
  }
  if (cursor + need <= limit + SAME_TRACK_EPS) return cursor;
  return null;
}

/** Music / ambience share the Audio lane until a dedicated Music lane exists. */
export function audioLaneKind(kind: string | null | undefined): "audio" | "sfx" {
  return kind === "sfx" ? "sfx" : "audio";
}

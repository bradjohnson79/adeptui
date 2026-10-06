import type { MagiClip, MagiSequenceDocument, MagiTrack } from "./types";

/** Picture kinds the MAGI renderer can blend. Objects stay overlays. */
export const PICTURE_TRACK_KINDS = ["video", "image"] as const;

export const TRANSITION_KINDS = ["none", "dissolve", "fade", "wipe"] as const;

export type TransitionKind = (typeof TRANSITION_KINDS)[number];

/**
 * Same window clip dragging uses to snap onto a neighbor.
 * A 2s gap is outside this window and is not a cut.
 */
export function adjacencyToleranceFrames(fps: number): number {
  return Math.max(4, Math.round(Math.max(1, fps) * 0.2));
}

export function isPictureTrack(kind: MagiTrack["kind"] | string | undefined): boolean {
  return kind === "video" || kind === "image";
}

function clipEnd(clip: MagiClip): number {
  return clip.startFrame + clip.durationFrames;
}

/** Longest blend the two clips can hold. 0 means they are too short. */
export function maxTransitionSeconds(leftFrames: number, rightFrames: number, fps: number): number {
  const rate = Math.max(1, fps);
  const raw = Math.min(3, leftFrames / rate - 0.08, rightFrames / rate - 0.08);
  const stepped = Math.floor(raw * 10 + 1e-6) / 10;
  return stepped >= 0.1 ? stepped : 0;
}

export type OutgoingCut =
  | { status: "none" }
  | { status: "not-picture" }
  | { status: "last" }
  | { status: "gap"; next: MagiClip; gapFrames: number }
  | { status: "cut"; next: MagiClip; cutFrame: number; maxSeconds: number };

/** Picture clips in timeline order. Audio and objects are not edges. */
export function orderedPictureClips(doc: MagiSequenceDocument): MagiClip[] {
  const pictureTracks = new Set(doc.tracks.filter((track) => isPictureTrack(track.kind)).map((track) => track.id));
  return doc.clips
    .filter((clip) => pictureTracks.has(clip.trackId))
    .sort((a, b) => a.startFrame - b.startFrame || a.id.localeCompare(b.id));
}

/** Whether this picture clip opens or closes the sequence. */
export function clipEdgeRole(doc: MagiSequenceDocument, clip: MagiClip | null | undefined): { first: boolean; last: boolean } {
  if (!clip) return { first: false, last: false };
  const pictures = orderedPictureClips(doc);
  return {
    first: pictures[0]?.id === clip.id,
    last: pictures.length > 0 && pictures[pictures.length - 1]?.id === clip.id,
  };
}

/** Longest fade an open head or tail can hold. */
export function maxEdgeFadeSeconds(durationFrames: number, fps: number): number {
  const rate = Math.max(1, fps);
  const raw = Math.min(3, durationFrames / rate - 0.08);
  const stepped = Math.floor(raw * 10 + 1e-6) / 10;
  return stepped >= 0.1 ? stepped : 0;
}

export type EdgeFade = { clipId: string; opacity: number };

/**
 * Timeline frame that shows a transition the moment it is applied.
 * Null when the playhead is already inside that window, so a duration
 * change does not yank a playhead the creator is already watching.
 */
export function transitionPreviewFrame(args: {
  playheadFrame: number;
  clip: MagiClip;
  durationFrames: number;
  edge: "in" | "out";
  cutFrame?: number | null;
}): number | null {
  const frames = Math.max(1, Math.round(args.durationFrames));
  const start = args.clip.startFrame;
  const end = start + args.clip.durationFrames;
  const playhead = args.playheadFrame;
  if (args.edge === "in") {
    const windowEnd = Math.min(end, start + frames);
    if (playhead >= start && playhead < windowEnd) return null;
    return Math.min(end - 1, start + Math.floor(frames / 2));
  }
  if (args.cutFrame == null) {
    const windowStart = Math.max(start, end - frames);
    if (playhead >= windowStart && playhead < end) return null;
    return Math.max(windowStart, end - Math.max(1, Math.ceil(frames / 2)));
  }
  const half = frames / 2;
  const windowStart = args.cutFrame - half;
  const windowEnd = args.cutFrame + half;
  if (playhead >= windowStart && playhead <= windowEnd) return null;
  return Math.round(args.cutFrame);
}

/**
 * Fade through black at the open start or end.
 * A fade between two meeting clips stays on the cut blend, not here.
 */
export function edgeFadeAtPlayhead(doc: MagiSequenceDocument, playheadFrame: number): EdgeFade | null {
  const pictures = orderedPictureClips(doc);
  if (!pictures.length) return null;
  const clip = pictures.find(
    (item) => playheadFrame >= item.startFrame && playheadFrame < item.startFrame + item.durationFrames,
  );
  if (!clip) return null;
  const fps = Math.max(1, doc.frameRate || 24);
  let opacity = 1;
  if (pictures[0]?.id === clip.id && clip.transitionInId === "fade") {
    const frames = Math.max(1, clip.transitionInDurationFrames || clip.transitionDurationFrames || fps);
    const local = playheadFrame - clip.startFrame;
    if (local < frames) opacity *= Math.max(0, local) / frames;
  }
  const outgoing = resolveOutgoingCut(doc, clip);
  if (pictures[pictures.length - 1]?.id === clip.id && outgoing.status === "last" && clip.transitionOutId === "fade") {
    const frames = Math.max(1, clip.transitionDurationFrames || fps);
    const remaining = clip.startFrame + clip.durationFrames - playheadFrame;
    if (remaining < frames) opacity *= Math.max(0, remaining) / frames;
  }
  if (opacity >= 0.999) return null;
  return { clipId: clip.id, opacity: Math.min(1, Math.max(0, opacity)) };
}

/** The cut that leaves `clip`, if the next picture clip on that track meets it. */
export function resolveOutgoingCut(doc: MagiSequenceDocument, clip: MagiClip | null | undefined): OutgoingCut {
  if (!clip) return { status: "none" };
  const track = doc.tracks.find((item) => item.id === clip.trackId);
  if (!isPictureTrack(track?.kind)) return { status: "not-picture" };
  const end = clipEnd(clip);
  const tolerance = adjacencyToleranceFrames(doc.frameRate || 24);
  let next: MagiClip | null = null;
  let gap = Number.POSITIVE_INFINITY;
  for (const other of doc.clips) {
    if (other.id === clip.id || other.trackId !== clip.trackId) continue;
    const start = other.startFrame;
    const delta = start - end;
    if (delta < 0 || delta > gap) continue;
    next = other;
    gap = delta;
  }
  if (!next || !Number.isFinite(gap)) return { status: "last" };
  if (gap > tolerance) return { status: "gap", next, gapFrames: gap };
  const maxSeconds = maxTransitionSeconds(clip.durationFrames, next.durationFrames, doc.frameRate || 24);
  return { status: "cut", next, cutFrame: end, maxSeconds };
}

export type CutBlend = {
  kind: "dissolve" | "fade" | "wipe";
  progress: number;
  outgoing: MagiClip;
  incoming: MagiClip;
  cutFrame: number;
  durationFrames: number;
};

function canonicalKind(value: string | null | undefined): "dissolve" | "fade" | "wipe" | null {
  if (value === "dissolve" || value === "fade" || value === "wipe") return value;
  return null;
}

/** Blend window centered on a real cut. Null everywhere else, including gaps. */
export function blendAtPlayhead(doc: MagiSequenceDocument, playheadFrame: number): CutBlend | null {
  for (const clip of doc.clips) {
    const kind = canonicalKind(clip.transitionOutId);
    if (!kind) continue;
    const cut = resolveOutgoingCut(doc, clip);
    if (cut.status !== "cut" || cut.maxSeconds <= 0) continue;
    const fps = Math.max(1, doc.frameRate || 24);
    const requested = (clip.transitionDurationFrames || fps) / fps;
    const seconds = Math.min(cut.maxSeconds, Math.max(0.1, requested));
    const durationFrames = Math.max(1, Math.round(seconds * fps));
    const half = durationFrames / 2;
    const start = cut.cutFrame - half;
    const end = cut.cutFrame + half;
    if (playheadFrame < start || playheadFrame > end) continue;
    const progress = durationFrames <= 0 ? 0 : (playheadFrame - start) / durationFrames;
    return {
      kind,
      progress: Math.min(1, Math.max(0, progress)),
      outgoing: clip,
      incoming: cut.next,
      cutFrame: cut.cutFrame,
      durationFrames,
    };
  }
  return null;
}

/** Source seconds for a clip, held on the first or last frame outside its span. */
export function blendSourceSeconds(clip: MagiClip, playheadFrame: number, fps: number): number {
  const rate = Math.max(1, fps);
  const end = clipEnd(clip);
  if (playheadFrame <= clip.startFrame) return Math.max(0, clip.inPoint) / rate;
  if (playheadFrame >= end) return Math.max(0, clip.outPoint - 1, clip.inPoint) / rate;
  return Math.max(0, clip.inPoint + (playheadFrame - clip.startFrame)) / rate;
}

export type CutLayerPresentation = {
  outgoingOpacity: number;
  incomingOpacity: number;
  incomingClipPath?: string;
};

/**
 * Preview composite that matches the duration-preserving xfade renderer.
 * Dissolve keeps the outgoing picture opaque and raises the incoming picture.
 * Fade follows ffmpeg fadeblack: the outgoing picture is gone by 20% of the
 * blend, then the incoming picture rises out of black.
 * Wipe follows wipeleft: the incoming picture is revealed from the right.
 */
export function cutLayerPresentation(kind: "dissolve" | "fade" | "wipe", progress: number): CutLayerPresentation {
  const p = Math.min(1, Math.max(0, progress));
  if (kind === "fade") {
    if (p <= 0.2) return { outgoingOpacity: 1 - p / 0.2, incomingOpacity: 0 };
    return { outgoingOpacity: 0, incomingOpacity: (p - 0.2) / 0.8 };
  }
  if (kind === "wipe") {
    const hidden = (1 - p) * 100;
    return {
      outgoingOpacity: 1,
      incomingOpacity: 1,
      incomingClipPath: `inset(0 0 0 ${hidden}%)`,
    };
  }
  return { outgoingOpacity: 1, incomingOpacity: p };
}

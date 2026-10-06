import type { MagiOverlayElement } from "../components/magi/overlays/types";
import { overlayDisplayName, overlayObjectsTrack } from "../components/magi/overlays/types";
import {
  createObjectsTrack,
  findObjectsTrack,
  normalizeObjectsTrack,
} from "./tracks";
import type { MagiClip, MagiObjectsSlot, MagiSequenceDocument, MagiTrack } from "./types";

export const GRAPHICS_CLIP_PREFIX = "gfx_";

export function isGraphicsClipId(clipId: string | null | undefined): boolean {
  return String(clipId || "").startsWith(GRAPHICS_CLIP_PREFIX);
}

export function overlayIdFromGraphicsClip(clipId: string): string {
  return clipId.startsWith(GRAPHICS_CLIP_PREFIX) ? clipId.slice(GRAPHICS_CLIP_PREFIX.length) : clipId;
}

export function persistableSequenceClips(clips: MagiClip[]): MagiClip[] {
  return clips.filter((clip) => !isGraphicsClipId(clip.id) && clip.ingestRole !== "graphic");
}

export function ensureObjectsTrack(doc: MagiSequenceDocument, slot: MagiObjectsSlot): MagiTrack {
  const found = findObjectsTrack(doc.tracks, slot);
  if (found) return normalizeObjectsTrack(found, slot);
  return createObjectsTrack(slot, slot === 2 ? 0 : 1);
}

/** @deprecated GRAPHICS is a migration alias. Use ensureObjectsTrack(doc, 1). */
export function ensureGraphicsTrack(doc: MagiSequenceDocument): MagiTrack {
  return ensureObjectsTrack(doc, 1);
}

export function overlayToGraphicsClip(
  el: MagiOverlayElement,
  trackId: string,
  fallbackDuration: number,
): MagiClip {
  const start = el.startFrame ?? 0;
  const end = el.endFrame ?? start + Math.max(1, fallbackDuration);
  const duration = Math.max(1, end - start);
  return {
    id: `${GRAPHICS_CLIP_PREFIX}${el.id}`,
    trackId,
    assetId: el.type === "image" ? el.assetId : `overlay:${el.id}`,
    name: overlayDisplayName(el),
    startFrame: start,
    durationFrames: duration,
    inPoint: 0,
    outPoint: duration,
    ingestRole: "graphic",
    overlayId: el.id,
  };
}

export function mergeGraphicsIntoSequence(
  doc: MagiSequenceDocument,
  overlays: MagiOverlayElement[],
): MagiSequenceDocument {
  const needSlot2 = overlays.some((el) => overlayObjectsTrack(el) === 2) || Boolean(findObjectsTrack(doc.tracks, 2));
  const objects1 = ensureObjectsTrack(doc, 1);
  const objects2 = needSlot2 ? ensureObjectsTrack(doc, 2) : undefined;

  const replaced = new Map<string, MagiTrack>();
  replaced.set(objects1.id, objects1);
  if (objects2) replaced.set(objects2.id, objects2);

  const nextTracks: MagiTrack[] = [];
  if (objects2 && !doc.tracks.some((track) => track.id === objects2.id)) {
    nextTracks.push(objects2);
  }
  for (const track of doc.tracks) {
    const replacement = replaced.get(track.id);
    if (replacement) {
      nextTracks.push(replacement);
      continue;
    }
    if (track.id === objects1.id) {
      nextTracks.push(objects1);
      continue;
    }
    nextTracks.push(track);
  }
  if (!nextTracks.some((track) => track.id === objects1.id)) {
    const videoIndex = nextTracks.findIndex((track) => track.kind === "video");
    if (videoIndex >= 0) nextTracks.splice(videoIndex, 0, objects1);
    else nextTracks.unshift(objects1);
  }

  const trackIdBySlot: Record<MagiObjectsSlot, string> = {
    1: objects1.id,
    2: objects2?.id || objects1.id,
  };
  const fallback = Math.max(1, Math.round(doc.frameRate * 5));
  const projected = overlays.map((el) =>
    overlayToGraphicsClip(el, trackIdBySlot[overlayObjectsTrack(el)], fallback),
  );
  const clips = [...persistableSequenceClips(doc.clips), ...projected];
  return { ...doc, tracks: nextTracks, clips };
}

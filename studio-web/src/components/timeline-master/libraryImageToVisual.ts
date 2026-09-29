/** Library image -> Visual track planner (Timeline UX/state only).

Click Timeline on an image:
  - Mark In/Out set -> Image-Frame placeVisualImageRange (Hop 6, unchanged)
  - Visual empty (no video_clips AND no playable visual) -> full-span image clip
  - Visual occupied -> do not auto-add; caller keeps references-only + notice

Drag Library image onto Visual:
  - Mark In/Out set -> placeVisualImageRange
  - video_clips empty -> full-span image clip (explicit place)
  - video_clips present -> append/place at drop time (do not smash A|imgclip_|B)
*/
import { findSameTrackIntersection } from '../../timelineMaster/sameTrackNoOverlap';

export const LIBRARY_IMAGE_VISUAL_NOTICE_OCCUPIED =
  'Visual already has a clip. Image added to References. Drag onto Visual to place, or set Mark In/Out for Image-Frame.';

export const LIBRARY_IMAGE_VISUAL_NOTICE_NO_ROOM =
  'Cannot drop image — that time is already occupied on the Visual track.';

export type LibraryImageAsset = {
  id: string;
  tag?: string | null;
  filename?: string | null;
  kind?: string | null;
};

export type VisualLaneClip = {
  id?: string;
  start?: number;
  length?: number;
};

export type ImageVisualClip = {
  id: string;
  start: number;
  length: number;
  label: string;
  asset_id: string;
  trim_start: number;
  mediaType: 'image';
  media_type: 'image';
  metadata: { role: 'image_frame'; referenceImageAssetId: string };
};

export function visualTrackOccupied(args: {
  videoClips?: VisualLaneClip[] | null;
  playableTakes?: VisualLaneClip[] | null;
}): boolean {
  if ((args.videoClips || []).length > 0) return true;
  return (args.playableTakes || []).length > 0;
}

export function newImageVisualClipId(seed?: string): string {
  const token =
    seed ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 10)
      : Math.random().toString(36).slice(2, 12));
  return `imgclip_${token}`;
}

export function buildImageVisualClip(args: {
  asset: LibraryImageAsset;
  start: number;
  length: number;
  id?: string;
}): ImageVisualClip {
  const label = String(args.asset.tag || args.asset.filename || 'Image').trim() || 'Image';
  return {
    id: args.id || newImageVisualClipId(),
    start: Math.max(0, Number(args.start) || 0),
    length: Math.max(0.15, Number(args.length) || 0.15),
    label,
    asset_id: args.asset.id,
    trim_start: 0,
    mediaType: 'image',
    media_type: 'image',
    metadata: { role: 'image_frame', referenceImageAssetId: args.asset.id },
  };
}

export type LibraryImageClickPlan =
  | { action: 'place-marks' }
  | { action: 'add-full-span'; clip: ImageVisualClip }
  | { action: 'occupied-safe'; notice: string };

export function planLibraryImageClick(args: {
  marksOk: boolean;
  videoClips?: VisualLaneClip[] | null;
  playableTakes?: VisualLaneClip[] | null;
  durationSec: number;
  asset: LibraryImageAsset;
  clipId?: string;
}): LibraryImageClickPlan {
  if (args.marksOk) return { action: 'place-marks' };
  if (visualTrackOccupied({ videoClips: args.videoClips, playableTakes: args.playableTakes })) {
    return { action: 'occupied-safe', notice: LIBRARY_IMAGE_VISUAL_NOTICE_OCCUPIED };
  }
  const duration = Math.max(0.15, Number(args.durationSec) || 5);
  return {
    action: 'add-full-span',
    clip: buildImageVisualClip({ asset: args.asset, start: 0, length: duration, id: args.clipId }),
  };
}

export type LibraryImageDropPlan =
  | { action: 'place-marks' }
  | { action: 'add-full-span'; clip: ImageVisualClip }
  | { action: 'add-at-time'; clip: ImageVisualClip }
  | { action: 'no-room'; notice: string };

function placeInVisualGap(
  clips: VisualLaneClip[],
  dropTime: number,
  duration: number,
): { start: number; length: number } | null {
  const wanted = Math.min(2, Math.max(0.15, duration));
  const start0 = Math.max(0, Math.min(duration, Number(dropTime) || 0));
  if (start0 >= duration - 1e-9) {
    const lastEnd = clips.reduce((m, c) => Math.max(m, Number(c.start || 0) + Number(c.length || 0)), 0);
    if (lastEnd < duration - 0.15) return { start: lastEnd, length: Math.min(wanted, duration - lastEnd) };
    return null;
  }
  const first = { id: '__drop__', start: start0, length: Math.min(wanted, Math.max(0.15, duration - start0)) };
  if (!findSameTrackIntersection(clips, first) && first.length >= 0.15) {
    return { start: first.start, length: first.length };
  }
  const next = clips
    .map((c) => ({ s: Number(c.start || 0), e: Number(c.start || 0) + Number(c.length || 0) }))
    .filter((c) => c.e > start0 + 1e-9)
    .sort((a, b) => a.s - b.s)[0];
  if (next && next.s > start0 + 0.15) {
    const gap = { start: start0, length: Math.min(wanted, next.s - start0) };
    if (!findSameTrackIntersection(clips, { id: '__drop__', ...gap })) return gap;
  }
  const lastEnd = clips.reduce((m, c) => Math.max(m, Number(c.start || 0) + Number(c.length || 0)), 0);
  if (lastEnd < duration - 0.15) {
    return { start: lastEnd, length: Math.min(wanted, duration - lastEnd) };
  }
  return null;
}

export function planLibraryImageDrop(args: {
  marksOk: boolean;
  videoClips?: VisualLaneClip[] | null;
  durationSec: number;
  dropTime: number;
  asset: LibraryImageAsset;
  clipId?: string;
}): LibraryImageDropPlan {
  if (args.marksOk) return { action: 'place-marks' };
  const duration = Math.max(0.15, Number(args.durationSec) || 5);
  const existing = [...(args.videoClips || [])];
  if (existing.length === 0) {
    return {
      action: 'add-full-span',
      clip: buildImageVisualClip({ asset: args.asset, start: 0, length: duration, id: args.clipId }),
    };
  }
  const placed = placeInVisualGap(existing, args.dropTime, duration);
  if (!placed) return { action: 'no-room', notice: LIBRARY_IMAGE_VISUAL_NOTICE_NO_ROOM };
  return {
    action: 'add-at-time',
    clip: buildImageVisualClip({
      asset: args.asset,
      start: placed.start,
      length: placed.length,
      id: args.clipId,
    }),
  };
}

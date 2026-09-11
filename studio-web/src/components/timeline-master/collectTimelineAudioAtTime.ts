/** Collect every audible Timeline layer at a playhead time.

The visual resolver keeps a single activeSfx for preview inspection.
Playback needs every overlapping dialogue and footstep clip.
*/
import type { DirectorTimeline, LipSyncTrack, TimelineClip } from "../DirectorTracks";
import type { BatchBlock, BatchClip } from "../../timelineMaster/contracts";
import { resolveBatchAtTime } from "./resolveTimelineAtTime";

export type TimelineAudioKind = "dialogue" | "audio" | "sfx";

export type TimelineAudioLayer = {
  clipId: string;
  assetId: string;
  label: string;
  kind: TimelineAudioKind;
  localTime: number;
  volume: number;
};

function intersects(start: number, length: number, t: number): boolean {
  return t >= start && t < start + length;
}

function pushClip(
  out: TimelineAudioLayer[],
  args: {
    clipId: string;
    assetId?: string | null;
    label?: string | null;
    kind: TimelineAudioKind;
    start: number;
    length: number;
    volume?: number | null;
    muted?: boolean | null;
    t: number;
  },
) {
  const assetId = String(args.assetId || "").trim();
  if (!assetId || !intersects(args.start, args.length, args.t)) return;
  const fallbackVolume = args.kind === "sfx" ? 0.32 : 1;
  const storedVolume = Math.max(0, Math.min(1, Number(args.volume ?? fallbackVolume)));
  out.push({
    clipId: args.clipId,
    assetId,
    label: String(args.label || args.kind),
    kind: args.kind,
    localTime: Math.max(0, args.t - args.start),
    volume: args.muted ? 0 : storedVolume,
  });
}

function addDirectorClips(
  out: TimelineAudioLayer[],
  clips: TimelineClip[] | undefined,
  kind: TimelineAudioKind,
  t: number,
) {
  for (const clip of clips || []) {
    pushClip(out, {
      clipId: clip.id,
      assetId: clip.asset_id,
      label: clip.label,
      kind,
      start: Number(clip.start || 0),
      length: Number(clip.length || 0),
      volume: clip.volume,
      muted: clip.muted,
      t,
    });
  }
}

function addBatchClips(
  out: TimelineAudioLayer[],
  clips: BatchClip[] | undefined,
  kind: TimelineAudioKind,
  t: number,
  batchStart: number,
) {
  for (const clip of clips || []) {
    pushClip(out, {
      clipId: clip.id,
      assetId: clip.assetId,
      label: clip.label,
      kind,
      start: batchStart + Number(clip.start || 0),
      length: Number(clip.length || 0),
      volume: clip.volume,
      muted: clip.muted,
      t,
    });
  }
}

function addLipSync(
  out: TimelineAudioLayer[],
  tracks: LipSyncTrack[] | undefined,
  t: number,
) {
  for (const track of tracks || []) {
    for (const clip of track.clips || []) {
      pushClip(out, {
        clipId: clip.id,
        assetId: clip.audio_asset_id || track.audio_asset_id,
        label: clip.label || track.label,
        kind: "dialogue",
        start: Number(clip.start || 0),
        length: Number(clip.length || 0),
        volume: 1,
        t,
      });
    }
  }
}

export function collectTimelineAudioAtTime(
  timeline: DirectorTimeline | null,
  master: { batchBlocks?: BatchBlock[] } | null,
  playheadSec: number,
): TimelineAudioLayer[] {
  const t = Math.max(0, playheadSec || 0);
  const out: TimelineAudioLayer[] = [];
  const batchHit = resolveBatchAtTime(master?.batchBlocks || [], t);
  const batch = batchHit?.batch || null;
  const batchStart = batchHit ? t - batchHit.localTime : 0;

  addLipSync(out, timeline?.lipsync?.tracks, t);

  // WYSIWYG: when any batch owns Music/SFX clips, only play clips that exist on
  // the active batch (no silent fall-through to stale scene-global tracks).
  const batches = master?.batchBlocks || [];
  const anyBatchAudio = batches.some((b) => (b.audioClips || []).length > 0);
  const anyBatchSfx = batches.some((b) => (b.sfxClips || []).length > 0);

  const batchAudio = batch?.audioClips || [];
  if (anyBatchAudio) addBatchClips(out, batchAudio, "audio", t, batchStart);
  else addDirectorClips(out, timeline?.audio_clips, "audio", t);

  const batchSfx = batch?.sfxClips || [];
  if (anyBatchSfx) addBatchClips(out, batchSfx, "sfx", t, batchStart);
  else addDirectorClips(out, timeline?.sfx_clips, "sfx", t);

  return out;
}

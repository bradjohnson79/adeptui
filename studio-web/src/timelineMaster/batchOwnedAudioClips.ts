/** Batch-owned Music/SFX -> scene-absolute Timeline clips (WYSIWYG with playback).

BATCH_OWNED_CLIPS: each batch stores audioClips/sfxClips in batch-local time.
Playback (collectTimelineAudioAtTime) already offsets by batch window start.
The Music/SFX tracks must paint the same clips at those scene offsets — otherwise
later batches audibly play with no visible clip (ghost playback).
*/
import type { BatchBlock, BatchClip, SceneTimelineMaster } from "./contracts";

export type BatchOwnedAudioKind = "audio" | "sfx";

export type DisplayBatchAudioClip = {
  id: string;
  asset_id: string | null;
  start: number;
  length: number;
  trim_start: number;
  label: string;
  volume: number;
  muted?: boolean;
  fade_in?: number;
  fade_out?: number;
  /** Owning batch — present when the clip was flattened from master. */
  batchId: string;
  /** Batch-local start before scene offset. */
  batchLocalStart: number;
};

function batchWindows(master: SceneTimelineMaster | null | undefined): Array<{
  batch: BatchBlock;
  start: number;
  length: number;
}> {
  const batches = [...(master?.batchBlocks || [])].sort((a, b) => a.order - b.order);
  const out: Array<{ batch: BatchBlock; start: number; length: number }> = [];
  let cursor = 0;
  for (const batch of batches) {
    const length = Math.max(0.1, Number(batch.duration?.plannedDuration || 0));
    out.push({ batch, start: cursor, length });
    cursor += length;
  }
  return out;
}

function clipsForKind(batch: BatchBlock, kind: BatchOwnedAudioKind): BatchClip[] {
  return kind === "audio" ? batch.audioClips || [] : batch.sfxClips || [];
}

/** True when any batch owns at least one clip of this kind (batch track authority). */
export function masterHasBatchOwnedAudio(
  master: SceneTimelineMaster | null | undefined,
  kind: BatchOwnedAudioKind,
): boolean {
  return (master?.batchBlocks || []).some((batch) => clipsForKind(batch, kind).length > 0);
}

/** Flatten per-batch audio/SFX clips to scene-absolute starts (batchStart + localStart). */
export function sceneAbsoluteBatchAudioClips(
  master: SceneTimelineMaster | null | undefined,
  kind: BatchOwnedAudioKind,
): DisplayBatchAudioClip[] {
  const out: DisplayBatchAudioClip[] = [];
  for (const { batch, start: batchStart } of batchWindows(master)) {
    for (const clip of clipsForKind(batch, kind)) {
      const assetId = String(clip.assetId || "").trim();
      if (!assetId) continue;
      const localStart = Number(clip.start || 0);
      const length = Math.max(0.05, Number(clip.length || 0));
      out.push({
        id: clip.id,
        asset_id: assetId,
        start: batchStart + localStart,
        length,
        trim_start: Number(clip.trimStart || 0),
        label: clip.label || (kind === "sfx" ? "SFX" : "Music"),
        volume: Number(clip.volume ?? (kind === "sfx" ? 0.32 : 1)),
        muted: Boolean(clip.muted),
        fade_in: Number(clip.fade_in || 0),
        fade_out: Number(clip.fade_out || 0),
        batchId: batch.id,
        batchLocalStart: localStart,
      });
    }
  }
  return out;
}

/**
 * Display source for Music/SFX tracks.
 * When any batch owns clips of this kind, batch clips are authoritative (match playback).
 * Otherwise fall back to legacy scene-global timeline clips.
 */
export function resolveDisplayAudioClips<T extends { id: string }>(
  timelineClips: T[] | null | undefined,
  master: SceneTimelineMaster | null | undefined,
  kind: BatchOwnedAudioKind,
): Array<T | DisplayBatchAudioClip> {
  if (masterHasBatchOwnedAudio(master, kind)) {
    return sceneAbsoluteBatchAudioClips(master, kind);
  }
  return timelineClips || [];
}

export function findBatchOwnedAudioClip(
  master: SceneTimelineMaster | null | undefined,
  kind: BatchOwnedAudioKind,
  clipId: string,
): { batch: BatchBlock; windowStart: number; windowLength: number; clip: BatchClip } | null {
  for (const { batch, start, length } of batchWindows(master)) {
    const clip = clipsForKind(batch, kind).find((c) => c.id === clipId);
    if (clip) return { batch, windowStart: start, windowLength: length, clip };
  }
  return null;
}

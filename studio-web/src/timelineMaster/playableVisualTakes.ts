import type { BatchBlock, SceneTake, SceneTimelineMaster } from "./contracts";
import { sceneTakeDisplayLabel } from "./sceneTakes";

/** Retake / range metadata written by Generation on A|Retake|B clips. */
export type VisualTakeMetadata = {
  role?: string;
  retakeId?: string;
  sourceBatchId?: string;
  sourceAssetId?: string;
  replacementAssetId?: string;
  markIn?: number;
  markOut?: number;
  createdAt?: string;
  [key: string]: unknown;
};

export type PlayableVisualClip = {
  id: string;
  asset_id: string;
  start: number;
  length: number;
  label: string;
  /** Source-local offset (TimelineClip.trim_start). Pass through — never invent sourceIn. */
  trim_start: number;
  metadata?: VisualTakeMetadata;
};

export function playableAssetIdForBatch(batch: BatchBlock): string | null {
  if (batch.approvedClip?.assetId) return batch.approvedClip.assetId;
  const latest = [...(batch.candidateVersions || [])]
    .filter((candidate) => candidate.assetId)
    .sort((a, b) => String(a.createdAt || "").localeCompare(String(b.createdAt || "")))
    .at(-1);
  return latest?.assetId || null;
}

export function playableLengthForBatch(batch: BatchBlock): number {
  const latest = [...(batch.candidateVersions || [])]
    .filter((candidate) => candidate.assetId)
    .sort((a, b) => String(a.createdAt || "").localeCompare(String(b.createdAt || "")))
    .at(-1);
  return Math.max(
    0.15,
    Number(
      batch.duration?.timelineVisibleDuration ||
        batch.duration?.generatedDuration ||
        latest?.generatedDuration ||
        batch.duration?.plannedDuration ||
        5,
    ),
  );
}

function metadataFromManagedClip(clip: {
  role?: string | null;
  metadata?: Record<string, unknown>;
}): VisualTakeMetadata | undefined {
  const meta = { ...(clip.metadata || {}) } as VisualTakeMetadata;
  if (clip.role && meta.role == null) meta.role = clip.role;
  return Object.keys(meta).length ? meta : undefined;
}

export function filterVideoClipsForSceneTake<T extends { asset_id?: string; metadata?: Record<string, unknown> }>(
  clips: T[] | null | undefined,
  take: SceneTake | null | undefined,
): T[] {
  const list = clips || [];
  if (!take) return list;
  const assets = new Set(
    [...(take.batches || []).map((member) => member.assetId), take.resultAssetId]
      .map((id) => String(id || "").trim())
      .filter(Boolean),
  );
  const retakes = new Set((take.retakeIds || []).map((id) => String(id || "").trim()).filter(Boolean));
  if (assets.size === 0 && retakes.size === 0) return list;
  return list.filter((clip) => {
    const assetId = String(clip.asset_id || "").trim();
    if (assetId && assets.has(assetId)) return true;
    const retakeId = String(clip.metadata?.retakeId || "").trim();
    return Boolean(retakeId && retakes.has(retakeId));
  });
}

export function resolveSceneTake(
  master: SceneTimelineMaster | null | undefined,
  takeId?: string | null,
): SceneTake | null {
  const takes = master?.sceneTakes || [];
  if (takeId) return takes.find((take) => take.id === takeId) || null;
  if (master?.currentSceneTakeId) {
    return takes.find((take) => take.id === master.currentSceneTakeId) || null;
  }
  return takes[0] || null;
}

function clipsFromSceneTake(master: SceneTimelineMaster, take: SceneTake): PlayableVisualClip[] {
  const batches = [...(master.batchBlocks || [])];
  const clips: PlayableVisualClip[] = [];
  let cursor = 0;
  for (const member of [...(take.batches || [])].sort((a, b) => (a.order || 0) - (b.order || 0))) {
    const batch = batches.find((item) => item.id === member.batchId);
    const assetId = String(member.assetId || "").trim();
    const length = Math.max(
      0.15,
      Number(member.durationSec || batch?.duration?.timelineVisibleDuration || batch?.duration?.plannedDuration || 5),
    );
    if (assetId && String(batch?.dismissedVisualAssetId || "") !== assetId) {
      clips.push({
        id: `bbclip_${member.batchId}_${take.id}`,
        asset_id: assetId,
        start: cursor,
        length,
        label: sceneTakeDisplayLabel(take.label),
        trim_start: 0,
      });
    }
    cursor += length;
  }
  return clips;
}

function masterHasManagedVisuals(master: SceneTimelineMaster | null | undefined): boolean {
  return (master?.batchBlocks || []).some((batch) =>
    (batch.visualClips || []).some((clip) => (clip.kind === "video" || clip.kind === "image") && clip.assetId),
  );
}

/** Scene-absolute Visual clips from playable batch takes (approved, else latest candidate).
 *  When a batch already owns managed visualClips (e.g. A|Retake|B), flatten those and
 *  pass through trimStart → trim_start so Preview/playable Visual keep source offsets.
 *  Whole-scene Takes: Preview of another Take uses that Take's membership so the
 *  current Take stays on the monitor while a new Take renders.
 */
export function playableVisualClipsFromMaster(
  master: SceneTimelineMaster | null | undefined,
  options?: { takeId?: string | null },
): PlayableVisualClip[] {
  const previewTakeId = options?.takeId || null;
  const take = resolveSceneTake(master, previewTakeId);
  const previewingOther = Boolean(previewTakeId && previewTakeId !== master?.currentSceneTakeId);
  if (master && take && (take.batches || []).some((member) => member.assetId)) {
    if (previewingOther || !masterHasManagedVisuals(master)) {
      return clipsFromSceneTake(master, take);
    }
  }
  const batches = [...(master?.batchBlocks || [])].sort((a, b) => a.order - b.order);
  const clips: PlayableVisualClip[] = [];
  let cursor = 0;
  for (const batch of batches) {
    const managed = (batch.visualClips || []).filter(
      (c) => (c.kind === "video" || c.kind === "image") && c.assetId,
    );
    if (managed.length > 0) {
      for (const clip of managed) {
        const assetId = String(clip.assetId || "").trim();
        if (!assetId) continue;
        clips.push({
          id: clip.id,
          asset_id: assetId,
          start: cursor + Number(clip.start || 0),
          length: Math.max(0.05, Number(clip.length || 0)),
          label: clip.label || batch.label || "Take",
          // Pass through managed trim — do not hardcode 0 (B needs markOut / prior).
          trim_start: Number(clip.trimStart || 0),
          metadata: metadataFromManagedClip(clip),
        });
      }
    } else {
      const assetId = playableAssetIdForBatch(batch);
      const length = playableLengthForBatch(batch);
      if (assetId && String(batch.dismissedVisualAssetId || "") !== assetId) {
        clips.push({
          id: `bbclip_${batch.id}`,
          asset_id: assetId,
          start: cursor,
          length,
          label: batch.label || "Take",
          // Full synthetic take starts at source origin (no A|B split yet).
          trim_start: 0,
        });
      }
    }
    cursor += playableLengthForBatch(batch);
  }
  return clips;
}

/**
 * Visual track display source.
 * Prefer explicit timeline video_clips (Generation A|Retake|B). When those are empty,
 * fall back to master playable takes — except once media_mode is "video", empty
 * video_clips are authoritative (user cleared the track). Without that gate,
 * removeClip writing video_clips=[] immediately resurrected bbclip_* takes and
 * the X looked like a no-op.
 *
 * video_clips are returned as-is so trim_start / metadata.role survive into Preview.
 */
export function resolveVisualVideoClips<T extends { id: string }>(
  videoClips: T[] | null | undefined,
  playableTakes: T[],
  mediaMode: "image" | "video" | null | undefined,
): T[] {
  const clips = videoClips || [];
  if (clips.length > 0) return clips;
  if (mediaMode === "video") return [];
  return playableTakes;
}

/** Visual-track list the creator sees. Director clips (optionally take-filtered)
 *  go through resolveVisualVideoClips so media_mode=video empty stays empty. */
export function displayedVisualVideoClips<
  T extends { id: string; asset_id?: string | null; metadata?: Record<string, unknown> },
>(
  videoClips: T[] | null | undefined,
  playableTakes: T[],
  mediaMode: "image" | "video" | null | undefined,
  sceneTake?: SceneTake | null,
): T[] {
  return resolveVisualVideoClips(
    filterVideoClipsForSceneTake(videoClips, sceneTake),
    playableTakes,
    mediaMode,
  );
}

/** Detach one placed Visual clip. Does not touch Takes, candidates, assets, or the Batch. */
export function removePlacedVisualClip<T extends { id: string }>(args: {
  clipId: string;
  displayedClips: T[] | null | undefined;
}): { video_clips: T[]; media_mode: "video" } {
  return {
    video_clips: (args.displayedClips || []).filter((clip) => clip.id !== args.clipId),
    media_mode: "video",
  };
}

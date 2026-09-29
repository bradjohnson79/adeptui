import type { DirectorSelection } from "../directorSelection";
import type { BatchBlock, SceneTimelineMaster } from "./contracts";

const COMPLETED_STATUSES = new Set([
  "Approved",
  "ApprovedConfigurationChanged",
  "RegenerationRecommended",
]);

export function completedApprovedBatches(master: SceneTimelineMaster | null | undefined): BatchBlock[] {
  return [...(master?.batchBlocks || [])]
    .filter((batch) => {
      const assetId = String(batch.approvedClip?.assetId || "").trim();
      return Boolean(assetId) && COMPLETED_STATUSES.has(String(batch.status || ""));
    })
    .sort((a, b) => (a.order || 0) - (b.order || 0));
}

export function sceneStitchCoveredEndSec(master: SceneTimelineMaster | null | undefined): number {
  const stitch = master?.sceneStitch;
  if (!stitch?.assetId) return 0;
  const ids = new Set(stitch.sourceBatchIds || []);
  const fromBatches = (master?.batchBlocks || [])
    .filter((batch) => (ids.size ? ids.has(batch.id) : false))
    .reduce((sum, batch) => sum + Math.max(0, Number(batch.duration?.plannedDuration || 0)), 0);
  if (fromBatches > 0) return fromBatches;
  const recorded = Number(stitch.durationSec || 0);
  if (recorded > 0) return recorded;
  return completedApprovedBatches(master).reduce(
    (sum, batch) => sum + Math.max(0, Number(batch.duration?.plannedDuration || 0)),
    0,
  );
}

/** True when master batches own at least one Music or SFX stem with an asset. */
export function masterHasMusicOrSfxStems(master: SceneTimelineMaster | null | undefined): boolean {
  for (const batch of master?.batchBlocks || []) {
    for (const clip of batch.audioClips || []) {
      if (String(clip.assetId || "").trim()) return true;
    }
    for (const clip of batch.sfxClips || []) {
      if (String(clip.assetId || "").trim()) return true;
    }
  }
  return false;
}

/**
 * Prefer scene stitch as the Play visual only when there are no Timeline Music/SFX
 * stems. Stitch files are Visual (+ baked LTX dialogue) — they do not carry separate
 * AUDIO/SFX buses. When stems exist, Preview uses per-batch Visual +
 * useTimelineAudioPlayback layered mix instead.
 */
export function shouldPreviewSceneStitch(args: {
  master: SceneTimelineMaster | null | undefined;
  selection: DirectorSelection;
  playheadSec: number;
  timelinePlaying?: boolean;
}): boolean {
  const stitch = args.master?.sceneStitch;
  if (!stitch?.assetId) return false;
  // STEM_MIX_OVER_STITCH: Music/SFX live on batch buses; stitch is Visual-only.
  if (masterHasMusicOrSfxStems(args.master)) return false;
  if (args.selection.kind === "batch" && !args.timelinePlaying) return false;
  const end = sceneStitchCoveredEndSec(args.master);
  if (end <= 0) return false;
  return args.playheadSec <= end + 1e-6;
}

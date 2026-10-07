/**
 * Timeline Publish + MAGI Upscale — FE readiness / dirty / chrome helpers.
 * Consumes Final Check lifecycle; does not fork QC authority.
 */

import type { SceneFinalCheck, ScenePublishState, SceneStitch, SceneTimelineMaster } from "./contracts";

export const PUBLISH_READY_LIFECYCLES = new Set([
  "SCENE_FINISHED",
  "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
]);

export type PublishChrome = {
  publishReady: boolean;
  changesPending: boolean;
  hasPublished: boolean;
  showPublish: boolean;
  showUpdatePublished: boolean;
  showUpscaleWithMagi: boolean;
  changesPendingLabel: string | null;
  scenePublish: ScenePublishState | null;
  contentFingerprint: string;
};

function stitchAssetId(stitch: SceneStitch | null | undefined): string {
  return String(stitch?.assetId || "").trim();
}

/** True only after Final Check PASS / accepted-issues AND a scene stitch exists. */
export function isPublishReady(master: SceneTimelineMaster | null | undefined): boolean {
  if (!master) return false;
  const life = String(master.sceneFinalCheck?.lifecycleStatus || "");
  if (!PUBLISH_READY_LIFECYCLES.has(life)) return false;
  return Boolean(stitchAssetId(master.sceneStitch));
}

/**
 * Stable fingerprint of current stitch identity for Changes Pending.
 * Prefer BE `scenePublish.contentFingerprint` after reload; this FE mirror is for chrome before round-trip.
 */
export function contentFingerprint(master: SceneTimelineMaster | null | undefined): string {
  const stitch = master?.sceneStitch;
  const assetId = stitchAssetId(stitch);
  if (!assetId || !stitch) return "";
  const sources = (stitch.sourceAssetIds || []).map((x) => String(x).trim()).filter(Boolean).join(",");
  const batches = (stitch.sourceBatchIds || []).map((x) => String(x).trim()).filter(Boolean).join(",");
  return `${assetId}::${sources}::${batches}`;
}

/** Dirty when last published stitch identity differs from current stitch. */
export function resolveChangesPending(master: SceneTimelineMaster | null | undefined): boolean {
  const pub = master?.scenePublish;
  if (!pub?.publishedAssetId) return false;
  const stitch = master?.sceneStitch;
  if (!stitch?.assetId) return false;
  if (pub.contentFingerprint) {
    // BE stores sha256 hex; compare via locked sourceSceneStitchAssetId + current stitch asset.
    // Also treat as dirty when BE fingerprint was set and stitch asset moved.
    if (String(stitch.assetId).trim() !== String(pub.sourceSceneStitchAssetId || "").trim()) {
      return true;
    }
    // Same stitch asset id but FE fingerprint string differs from what we last showed — use source lists via currentFp vs published lock.
    // When publish just happened, BE fingerprint is sha; we only mark dirty on stitch asset id change (authoritative rebuild).
    return false;
  }
  return String(stitch.assetId).trim() !== String(pub.sourceSceneStitchAssetId || "").trim();
}

/**
 * Mark dirty when stitch asset changed OR when caller provides BE status.changesPending.
 * Primary chrome path: stitch.assetId !== published.sourceSceneStitchAssetId.
 */
export function isPublishDirty(master: SceneTimelineMaster | null | undefined): boolean {
  return resolveChangesPending(master);
}

/**
 * Full chrome resolution for Preview Monitor CTAs.
 * Hidden before PASS/accepted-issues; Update only when dirty vs last published.
 */
export function resolvePublishChrome(master: SceneTimelineMaster | null | undefined): PublishChrome {
  const ready = isPublishReady(master);
  const pub = (master?.scenePublish as ScenePublishState | null | undefined) || null;
  const hasPublished = Boolean(String(pub?.publishedAssetId || "").trim());
  const stitchPending = ready && hasPublished ? resolveChangesPending(master) : false;
  const upscalePending = Boolean(hasPublished && pub?.upscalePendingPublish);
  const pending = stitchPending || upscalePending;
  return {
    publishReady: ready,
    changesPending: pending,
    hasPublished,
    showPublish: ready && !hasPublished,
    showUpdatePublished: ready && hasPublished && pending,
    showUpscaleWithMagi: ready,
    changesPendingLabel: pending ? "Changes Pending" : null,
    scenePublish: pub,
    contentFingerprint: contentFingerprint(master),
  };
}

/** Allowed MAGI asset ids from this Timeline entry (full stitch / published / upscaled only). */
export function allowedMagiUpscaleAssetIds(master: SceneTimelineMaster | null | undefined): string[] {
  const out: string[] = [];
  const stitch = stitchAssetId(master?.sceneStitch);
  if (stitch) out.push(stitch);
  const pub = master?.scenePublish;
  if (pub?.publishedAssetId) out.push(String(pub.publishedAssetId).trim());
  if (pub?.upscaledAssetId) out.push(String(pub.upscaledAssetId).trim());
  return [...new Set(out.filter(Boolean))];
}

export function isFullStitchMagiAsset(
  master: SceneTimelineMaster | null | undefined,
  assetId: string | null | undefined,
): boolean {
  const id = String(assetId || "").trim();
  if (!id) return false;
  return allowedMagiUpscaleAssetIds(master).includes(id);
}

/** Honest accepted-issues flag from Final Check (for display / provenance). */
export function publishAcceptedIssues(fc: SceneFinalCheck | null | undefined): boolean {
  return String(fc?.lifecycleStatus || "") === "SCENE_FINISHED_WITH_ACCEPTED_ISSUES";
}

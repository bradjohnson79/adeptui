/**
 * The picture Publish and MAGI use for a Film Timeline shot.
 *
 * A ready stitch is the finished multi-clip scene. One completed, untrimmed
 * clip is already the finished scene, so it does not need a second file.
 */

type PublishableSegment = {
  status?: string | null;
  assetId?: string | null;
  trimInSec?: number | null;
  trimOutSec?: number | null;
};

type PublishableShot = {
  segments?: PublishableSegment[] | null;
  state?: {
    stitchAssetId?: string | null;
    stitchStatus?: string | null;
  } | null;
};

function untrimmed(segment: PublishableSegment): boolean {
  return Number(segment.trimInSec || 0) <= 0.02 && segment.trimOutSec == null;
}

export function publishableSceneAsset(shot: PublishableShot | null | undefined): string {
  const status = String(shot?.state?.stitchStatus || "").trim().toLowerCase();
  const stitchId = String(shot?.state?.stitchAssetId || "").trim();
  if (status === "ready" && stitchId) return stitchId;
  const completed = (shot?.segments || []).filter(
    (segment) => String(segment.status || "") === "completed" && String(segment.assetId || "").trim() && untrimmed(segment),
  );
  if (completed.length === 1) return String(completed[0].assetId);
  return "";
}

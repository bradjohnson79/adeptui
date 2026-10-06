/** One scene clock. A current stitch is the file. Otherwise the ordered clips are the scene. */

export function stitchCoversClips(
  status: string | null | undefined,
  assetId: string | null | undefined,
  recorded: string[] | null | undefined,
  clipIds: string[],
): boolean {
  if (String(status || "").trim().toLowerCase() !== "ready" || !assetId) return false;
  const ids = recorded || [];
  return ids.length > 0 && ids.join("\n") === clipIds.join("\n");
}

export function fileTimeForWindow(trimInSec: number, sceneLocal: number): number {
  return Math.max(0, (Number(trimInSec) || 0) + Math.max(0, sceneLocal));
}

export function sceneLocalFromFile(trimInSec: number, fileTime: number): number {
  return Math.max(0, (Number(fileTime) || 0) - (Number(trimInSec) || 0));
}

/** A trimmed window ends before the source file does. */
export function windowReachedEnd(trimInSec: number, trimOutSec: number | null, durationSec: number, fileTime: number): boolean {
  const start = Math.max(0, Number(trimInSec) || 0);
  const end = trimOutSec == null ? start + Math.max(0, Number(durationSec) || 0) : Number(trimOutSec);
  return fileTime >= end - 0.05;
}

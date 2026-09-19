import { api } from "../../api";

/** Build a playable take/compare `<audio>` src. Empty only when there is no asset. */
export function voiceTakeAudioSrc(
  projectId: string,
  audioAssetId?: string | null,
  rev?: string | number | null,
): string {
  if (!audioAssetId) return "";
  return api.assetUrl(audioAssetId, rev, projectId);
}

/** One dialogue authority on Timeline preview (Re-Take-only).

Lip Sync tracks and scene.lipsync_output_path are demoted for Timeline Preview.
Composed Visual (video_clips / rtclip_* A|Retake|B) owns the AV window — including
baked retake AAC. Do NOT mute Visual soundtrack for leftover lipsync_output_path
or for legacy lipsync dialogue clips (those must not layer under Retake).

MAGI may revive LatentSync/Qwen lipsync later; Timeline must not depend on it.
*/
export type LipsyncClipLike = {
  start?: number;
  length?: number;
  audio_asset_id?: string | null;
};

export type LipsyncTrackLike = {
  enabled?: boolean;
  audio_asset_id?: string | null;
  clips?: LipsyncClipLike[];
};

export const RETAKE_VISUAL_CLIP_PREFIX = "rtclip_";

export function parseSceneLipsyncTracks(
  scene?: { lipsync_tracks_json?: string } | null,
): LipsyncTrackLike[] {
  const raw = scene?.lipsync_tracks_json;
  if (!raw || typeof raw !== "string") return [];
  try {
    const parsed = JSON.parse(raw);
    const tracks = parsed?.tracks ?? parsed;
    if (Array.isArray(tracks)) return tracks;
  } catch {
    /* ignore malformed scene JSON */
  }
  return [];
}

export function lipsyncDialogueActiveAt(
  tracks: LipsyncTrackLike[] | undefined,
  playheadSec: number,
): boolean {
  const t = Math.max(0, playheadSec || 0);
  for (const track of tracks || []) {
    if (track.enabled === false) continue;
    for (const clip of track.clips || []) {
      const start = Number(clip.start || 0);
      const length = Number(clip.length || 0);
      if (!(t >= start && t < start + length)) continue;
      const asset = String(clip.audio_asset_id || track.audio_asset_id || "").trim();
      if (asset) return true;
    }
  }
  return false;
}

export function isRetakeVisualClipId(clipId?: string | null): boolean {
  return Boolean(clipId && String(clipId).startsWith(RETAKE_VISUAL_CLIP_PREFIX));
}

export function shouldMutePreviewVideoSoundtrack(args: {
  /** @deprecated Ignored. lipsync_output_path is not Preview Visual/dialogue authority. */
  lipsyncOutputPath?: string | null;
  /** @deprecated Legacy Lip Sync tracks are not Timeline dialogue authority (MAGI shelf). */
  tracks?: LipsyncTrackLike[];
  playheadSec: number;
  libraryPreview?: boolean;
  /** When playhead sits on rtclip_*, retake media owns AV — never mute. */
  activeVisualClipId?: string | null;
}): boolean {
  if (args.libraryPreview) return false;
  // Re-Take AV window owns [markIn,markOut) audio — never suppress retake AAC.
  if (isRetakeVisualClipId(args.activeVisualClipId)) return false;
  // Lip Sync track demotion: do not mute Visual AAC for legacy lipsync dialogue.
  // (Previously muted while lipsyncDialogueActiveAt; that layered obsolete wavs.)
  void args.tracks;
  void args.playheadSec;
  void args.lipsyncOutputPath;
  return false;
}

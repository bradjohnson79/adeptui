export type DirectorSelectionKind =
  | "scene"
  | "promptSeg"
  | "imageClip"
  | "videoClip"
  | "camera"
  | "audio"
  | "sfx"
  | "lipsync"
  | "lipsyncTrack"
  | "lipsyncClip"
  | "batch"
  | "repair"
  | "job"
  | null;

export type DirectorSelection = {
  kind: DirectorSelectionKind;
  id?: string;
  trackIndex?: number;
  trackId?: string;
};

/**
 * Single authoritative Timeline selection contract (TIMELINE_OWNS_SELECTION).
 * The Inspector observes this; it never becomes the source of truth.
 * One discriminated union per selectable Timeline object so routing is
 * exhaustive and no object silently falls back to Scene Inspector.
 */
export type TimelineSelection =
  | { type: "SCENE"; sceneId: string }
  | { type: "PROMPT_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "IMAGE_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "VIDEO_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "AUDIO_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "SFX_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "LIPSYNC_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | { type: "CAMERA_CLIP"; sceneId: string; trackId?: string; clipId: string }
  | null;

export type WorkspaceTab = "timeline" | "prompt" | "lipsync" | "settings";

export const CONTINUITY_KEYS = [
  "identity",
  "wardrobe",
  "environment",
  "lighting",
  "camera",
  "props",
  "audio_bed",
  "motion_style",
] as const;

export type ContinuityKey = (typeof CONTINUITY_KEYS)[number];
export type ContinuityLock = "locked" | "unlocked" | "inherit_project" | "inherit_previous";

export function parseContinuity(raw?: string | null): Record<ContinuityKey, ContinuityLock> {
  const base = Object.fromEntries(CONTINUITY_KEYS.map((k) => [k, "inherit_project"])) as Record<
    ContinuityKey,
    ContinuityLock
  >;
  if (!raw?.trim()) return base;
  try {
    const data = JSON.parse(raw) as Record<string, string>;
    for (const k of CONTINUITY_KEYS) {
      const v = data[k];
      if (v === "locked" || v === "unlocked" || v === "inherit_project" || v === "inherit_previous") {
        base[k] = v;
      }
    }
  } catch {
    /* ignore */
  }
  return base;
}

export function continuityLockedCount(raw?: string | null) {
  const c = parseContinuity(raw);
  return {
    locked: CONTINUITY_KEYS.filter((k) => c[k] === "locked").length,
    total: CONTINUITY_KEYS.length,
    keys: c,
  };
}

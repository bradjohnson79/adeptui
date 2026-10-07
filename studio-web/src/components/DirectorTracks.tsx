import type { TimelineWorkspaceLayout } from "../timelineMaster/workspaceLayout";
import type { TimelinePromptSegment as MasterTimelinePromptSegment } from "../timelineMaster/contracts";
import { getBoundShellTimeline } from "./timeline-master/timelineMutateBridge";

export type RegionBox = { x: number; y: number; w: number; h: number };
export type TimelineClip = {
  id: string;
  asset_id?: string | null;
  start: number;
  length: number;
  trim_start?: number;
  label?: string;
  title?: string | null;
  description?: string | null;
  role?: "start" | "middle" | "end" | "guide";
  /** Generation A|Retake|B metadata (role, retakeId, markIn/Out, asset ids). */
  metadata?: {
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
  /** Stable timeline tag e.g. @Image1 â€” never renumbered on delete/move. */
  display_tag?: string | null;
  volume?: number;
  muted?: boolean;
  fade_in?: number;
  fade_out?: number;
  reference_binding_id?: string | null;
  /** Omni Wave 3A: image=reference, video=playable take. */
  mediaType?: "image" | "video" | null;
  media_type?: "image" | "video" | null;
};
export type PromptSegment = {
  id: string;
  start: number;
  length: number;
  text: string;
  weight?: number;
  region?: RegionBox | null;
  /** Foley / ambience / music cues for Audio Studio / Editor (intent only). */
  audio_intent?: string[];
  script_segment_id?: string | null;
  storyboard_panel_id?: string | null;
  scene_state_id?: string | null;
  model_prompt?: string | null;
  negative_prompt?: string | null;
  bound_image_clip_id?: string | null;
  reference_binding_ids?: string[];
  reference_name_bindings?: Array<{
    binding_id: string;
    prompt_name: string;
    type: "character" | "prop" | "environment" | "video" | "audio";
    tag: string;
    asset_id?: string;
    identity_id?: string;
    reference_sheet_id?: string;
  }>;
  user_direction?: string | null;
  production_prompt?: string | null;
  dialogue?: string | null;
  movement_segment_ref?: { id: string; segmentNumber: number; alias: string } | null;
  movement_segment_revision?: number | null;
  temperature?: number;
};

/**
 * SINGLE-STORE: Master batch.promptSegments rows (camelCase contract) projected
 * into the view PromptSegment shape (snake_case). The Timed Prompt modal,
 * Inspector, and track all consume this — never the retired
 * TimelineBoardView.promptSegments legacy array.
 */
export function masterPromptSegmentToView(seg: MasterTimelinePromptSegment): PromptSegment {
  const nameBindings = (seg.referenceNameBindings || []).map((row) => ({
    binding_id: String(row.binding_id ?? row.bindingId ?? ""),
    prompt_name: String(row.prompt_name ?? row.promptName ?? ""),
    type: (row.type || "character") as "character" | "prop" | "environment" | "video" | "audio",
    tag: String(row.tag || ""),
  }));
  return {
    id: seg.id,
    start: Number(seg.start) || 0,
    length: Number(seg.length) || 0,
    text: seg.text || "",
    weight: Number(seg.strength) || 1,
    reference_binding_ids: [...(seg.referenceBindingIds || [])],
    reference_name_bindings: nameBindings,
    production_prompt: seg.productionPrompt ?? null,
    dialogue: seg.dialogue ?? null,
    movement_segment_ref: seg.movementSegmentRef ?? null,
    movement_segment_revision: seg.movementSegmentRevision ?? null,
    temperature: seg.temperature,
  };
}
export type CameraClip = {
  id: string;
  start: number;
  length: number;
  motion_type: string;
  motion_id?: string | null;
  speed?: number;
  distance?: number;
  ease?: string;
  shake?: number;
  blend?: number;
  intensity?: number | null;
  subject_lock?: number | null;
  stabilization?: string | null;
  rig: string;
  rig_id?: string | null;
  custom_motion_label?: string | null;
  custom_rig_label?: string | null;
  execution_strategy?: string | null;
  label?: string;
  preset_id?: string | null;
  text?: string;
  reference_binding_ids?: string[];
  shot_id?: string | null;
  lens_id?: string | null;
  focus_id?: string | null;
  focus_name?: string | null;
  lighting_id?: string | null;
};
export type LipSyncClip = {
  id: string;
  start: number;
  length: number;
  label?: string;
  title?: string | null;
  description?: string | null;
  line?: string | null;
  status?: string;
  character_id?: string | null;
  character_name?: string | null;
  speaker_binding_id?: string | null;
  audio_asset_id?: string | null;
  follow_policy?: string | null;
};
export type LipSyncTrack = {
  id: string;
  slot: number;
  label: string;
  enabled: boolean;
  audio_asset_id?: string | null;
  character_id?: string | null;
  character_name?: string | null;
  clips?: LipSyncClip[];
  roi?: RegionBox | null;
  track_path?: Array<{ frame: number; x: number; y: number; w: number; h: number; visible?: boolean; mode?: string }>;
  notes?: string;
};
export type TimelineBoardView = {
  media_mode: "image" | "video";
  duration_sec: number;
  imageClips: TimelineClip[];
  videoClips: TimelineClip[];
  /** Motion/performance reference â€” independent of the output Video track. One clip this milestone. */
  video_reference_clips?: TimelineClip[];
  /** Image / entity reference â€” distinct from VISUAL playback images. */
  image_reference_clips?: TimelineClip[];
  promptSegments: PromptSegment[];
  cameraClips?: CameraClip[];
  audioClips: TimelineClip[];
  sfxClips: TimelineClip[];
  lipsync: { tracks: LipSyncTrack[] };
  playhead: number;
  /** Monotonic allocator for @ImageN tags (per scene timeline). */
  next_image_tag_number?: number;
  /** How visual / prompt / camera guidance is weighted at compile time. */
  guidance_priority?: TimelineWorkspaceLayout["guidancePriority"];
  prompt_refs_migrated?: boolean;
  /** Timeline Library pane staging â€” not generation input. */
  library_asset_ids?: string[] | null;
};

function nid() {
  return Math.random().toString(36).slice(2, 10);
}

/** Deleted Timed Prompt ids that GET/overlay must not treat as pending drafts. */
const deletedPromptIds = new Set<string>();

export function tombstonePromptId(id: string) {
  if (id) deletedPromptIds.add(id);
}

export function forgetPromptTombstone(id: string) {
  if (id) deletedPromptIds.delete(id);
}

export function isPromptTombstoned(id: string | null | undefined): boolean {
  return Boolean(id && deletedPromptIds.has(id));
}

export function dropTombstonedPrompts<
  T extends { id?: string | null; legacyPromptSegmentId?: string | null },
>(segments: T[] | null | undefined): T[] {
  const seen = new Set<string>();
  const next: T[] = [];
  for (const seg of segments || []) {
    if (seg.id && deletedPromptIds.has(seg.id)) continue;
    if (seg.legacyPromptSegmentId && deletedPromptIds.has(seg.legacyPromptSegmentId)) continue;
    if (seg.id) {
      if (seen.has(seg.id)) continue;
      seen.add(seg.id);
    }
    next.push(seg);
  }
  return next;
}

/** Prefer saved GET prose over a stale empty snapshot; do not resurrect memory after a real clear. */
export function firstNonemptyPromptText(
  shared: string | null | undefined,
  live: string | null | undefined,
  memory: string | null | undefined,
): string {
  if (typeof shared === "string" && shared.length > 0) return shared;
  if (typeof live === "string" && live.length > 0) return live;
  if (typeof live === "string") return live;
  if (typeof shared === "string") return shared;
  return typeof memory === "string" ? memory : "";
}

/** Overlay GET director with in-memory drafts. Deleted prompt ids are never pending drafts. */
export function overlayLiveTimeline(live: TimelineBoardView, memory: TimelineBoardView | null): TimelineBoardView {
  if (!memory) {
    return { ...live, promptSegments: dropTombstonedPrompts(live.promptSegments || []) };
  }
  const memPromptList = memory.promptSegments || [];
  const memPrompts = new Map(memPromptList.filter((row) => row.id).map((row) => [row.id, row]));
  const livePrompts = live.promptSegments || [];
  const promptSegments = dropTombstonedPrompts([
    ...livePrompts.map((row) => {
      if (!row.id || !memPrompts.has(row.id)) return row;
      const mem = memPrompts.get(row.id);
      if (!mem) return row;
      const shared = getBoundShellTimeline()?.promptSegments.find((item) => item.id === row.id);
      return {
        ...row,
        ...mem,
        // Shared shell snapshot is the same clip Inspect and the modal write.
        // A late GET must not restore stale track memory over those bindings.
        reference_binding_ids:
          shared?.reference_binding_ids ??
          (Array.isArray(row.reference_binding_ids) ? row.reference_binding_ids : mem.reference_binding_ids),
        reference_name_bindings:
          shared?.reference_name_bindings ??
          (Array.isArray(row.reference_name_bindings) ? row.reference_name_bindings : mem.reference_name_bindings),
        text: firstNonemptyPromptText(shared?.text, row.text, undefined), // A11: fetched GET must not be hidden by stale local memory overlay
      };
    }),
    ...memPromptList.filter((row) => !row.id),
  ]);
  return {
    ...live,
    promptSegments,
    // Master reload rebuilds the view from batch clips and drops tray membership
    // and reference-lane drafts. Those live on this view; keep the in-memory copy.
    library_asset_ids:
      memory.library_asset_ids !== undefined ? memory.library_asset_ids : live.library_asset_ids,
    video_reference_clips:
      memory.video_reference_clips !== undefined ? memory.video_reference_clips : live.video_reference_clips,
    image_reference_clips:
      memory.image_reference_clips !== undefined ? memory.image_reference_clips : live.image_reference_clips,
  };
}

export function syncPromptTombstones(before: TimelineBoardView, after: TimelineBoardView) {
  const beforeIds = new Set((before.promptSegments || []).map((seg) => seg.id).filter(Boolean));
  const afterIds = new Set((after.promptSegments || []).map((seg) => seg.id).filter(Boolean));
  for (const id of beforeIds) {
    if (!afterIds.has(id)) tombstonePromptId(id);
  }
  for (const id of afterIds) {
    if (!beforeIds.has(id)) forgetPromptTombstone(id);
  }
}

export function promptIdsOf(timeline: TimelineBoardView | null | undefined): Set<string> {
  return new Set((timeline?.promptSegments || []).map((seg) => seg.id).filter(Boolean));
}

export function createLipSyncTrack(slot: number): LipSyncTrack {
  return {
    id: nid(),
    slot,
    label: `Lip Sync ${slot}`,
    enabled: false,
    audio_asset_id: null,
    character_id: null,
    character_name: null,
    clips: [],
    roi: {
      x: Math.min(0.72, 0.35 + ((slot - 1) % 2) * 0.2),
      y: 0.55,
      w: 0.18,
      h: 0.12,
    },
    track_path: [],
    notes: "",
  };
}

function normalizeLipSyncClip(raw: Partial<LipSyncClip> | null | undefined): LipSyncClip {
  return {
    id: raw?.id || nid(),
    start: Math.max(0, Number(raw?.start || 0)),
    length: Math.max(0.1, Number(raw?.length || 2)),
    label: (raw?.label || "").trim() || "Lip Sync Clip",
    title: (raw?.title || "").trim() || null,
    description: (raw?.description || "").trim() || null,
    line: typeof raw?.line === "string" ? raw.line : "",
    status: (raw?.status || "").trim() || "draft",
    character_id: raw?.character_id || null,
    character_name: raw?.character_name || null,
    speaker_binding_id: raw?.speaker_binding_id || null,
    audio_asset_id: raw?.audio_asset_id || null,
    follow_policy: (raw?.follow_policy || "").trim() || "follow_audio",
  };
}

export function normalizeLipSyncTracks(rawTracks: Array<Partial<LipSyncTrack>> | null | undefined): LipSyncTrack[] {
  const source = (rawTracks || []).length ? rawTracks || [] : [createLipSyncTrack(1)];
  return source.map((rawTrack, index) => {
    const base = createLipSyncTrack(index + 1);
    const clips = (rawTrack?.clips || []).map((clip) => normalizeLipSyncClip(clip));
    const firstClipWithAudio = clips.find((clip) => clip.audio_asset_id);
    const firstClipWithCharacterId = clips.find((clip) => clip.character_id);
    const firstClipWithCharacterName = clips.find((clip) => clip.character_name);
    return {
      ...base,
      ...rawTrack,
      id: rawTrack?.id || base.id,
      slot: index + 1,
      label: (rawTrack?.label || "").trim() || `Lip Sync ${index + 1}`,
      enabled: Boolean(rawTrack?.enabled),
      audio_asset_id: rawTrack?.audio_asset_id || firstClipWithAudio?.audio_asset_id || null,
      character_id: rawTrack?.character_id || firstClipWithCharacterId?.character_id || null,
      character_name: rawTrack?.character_name || firstClipWithCharacterName?.character_name || null,
      clips: clips.sort((a, b) => a.start - b.start),
      roi: rawTrack?.roi
        ? {
            x: Number(rawTrack.roi.x ?? base.roi!.x),
            y: Number(rawTrack.roi.y ?? base.roi!.y),
            w: Number(rawTrack.roi.w ?? base.roi!.w),
            h: Number(rawTrack.roi.h ?? base.roi!.h),
          }
        : base.roi,
      track_path: rawTrack?.track_path || [],
      notes: rawTrack?.notes || "",
    };
  });
}

export function lipSyncTrackHasContent(track: LipSyncTrack | null | undefined) {
  if (!track) return false;
  return Boolean(
    track.enabled ||
      track.audio_asset_id ||
      track.character_id ||
      (track.character_name || "").trim() ||
      (track.notes || "").trim() ||
      (track.track_path || []).length ||
      (track.clips || []).length,
  );
}


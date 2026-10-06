import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { ActionWithHelp, PanelHeading } from "./HelpTip";
import { useDirectorSelectionOptional } from "./DirectorSelectionContext";
import { VisualReferencesPanel } from "./VisualReferencesPanel";
import { TimelineReferencesPanel } from "./TimelineReferencesPanel";
import {
  TIMELINE_LAYOUT_EVENT,
  loadTimelineWorkspaceLayout,
  saveTimelineWorkspaceLayout,
  type TimelineWorkspaceLayout,
} from "../timelineMaster/workspaceLayout";
import { getTimelineHelp } from "../timelineMaster/helpCatalog";
import {
  TimelineSettingsDrawer,
  formatTimelineTime,
} from "./timeline-master/TimelineSettingsDrawer";
import { TrackClipInteractive, type ClipDragMode, type ClipGeometry } from "./timeline-master/TrackClipInteractive";
import { TimedPromptEditorModal } from "./timeline-master/TimedPromptEditorModal";
import {
  openTimedPromptAfterGesture,
  shouldIgnoreTimedPromptDismiss,
  timedPromptDismissGuardUntil,
} from "./timedPromptOpen";
/* Phase 0: CameraSettingsModal unmounted â€” Timed Prompt is sole camera authority */
import { buildMagneticSnapTargets } from "../timelineMaster/magneticSnap";
import { pixelsPerSecond, sliderToZoom, stepTimelineZoom, zoomToSlider } from "../timelineMaster/timelineZoom";
import { TimelineTrackLabel } from "./timeline-master/TimelineTrackLabel";
import { TrackVolumeControl } from "./timeline-master/TrackVolumeControl";
import { laneTimeFromPointer } from "../timelineMaster/audioClipModal";
import type { SceneTimelineMaster, TimelinePromptSegment as MasterTimelinePromptSegment } from "../timelineMaster/contracts";
import {
  flattenMasterPrompts,
  patchMasterPrompt,
  projectMasterPreviewClips,
  removableVisualClipIds,
  removeMasterPrompts,
  syncMasterClips,
} from "../timelineMaster/masterTimelineMutate";
import {
  displayedVisualVideoClips,
  playableVisualClipsFromMaster,
  removePlacedVisualClip,
  resolveSceneTake,
} from "../timelineMaster/playableVisualTakes";
import {
  findBatchOwnedAudioClip,
  masterHasBatchOwnedAudio,
  resolveDisplayAudioClips,
  type DisplayBatchAudioClip,
} from "../timelineMaster/batchOwnedAudioClips";
import { findSameTrackIntersection, rangesIntersect, USER_FACING_TRACK_OCCUPIED } from "../timelineMaster/sameTrackNoOverlap";
import { runTimelineCommand } from "../timelineMaster/timelineHotkeys";
import {
  applyShellPromptSnapshot,
  getBoundShellTimeline,
  getBoundShellTimelineMutate,
  bindInspectingPrompt,
  subscribeShellTimelineSnapshot,
} from "./timeline-master/timelineMutateBridge";
import { ReferenceTokenAutocomplete } from "./sceneReferences/ReferenceTokenAutocomplete";
// TS6133 unblock: JSX usage removed by in-progress refactor; keep symbol for re-wire.
void ReferenceTokenAutocomplete;
import {
  assetDurationSec,
  displayToken,
  normalizePromptTags,
  tokenSummary,
  type ReferenceBindingView,
} from "../sceneReferences/referenceTokens";
import { labelCharacterBindingFromIdentity } from "../timelineMaster/timedPromptNameBindings";
import {
  collectPromptBindingIds,
  loadTimelineReferenceCatalog,
} from "../timelineMaster/loadTimelineReferenceCatalog";
import { resolveMediaClipLabels } from "../timelineMaster/mediaClipLabels";
import { planLibraryImageDrop } from "./timeline-master/libraryImageToVisual";
import {
  decideTimedPromptRange,
  liveSceneClockSec,
} from "../timelineMaster/sceneDurationAuthority";
import { persistCanonicalSceneDuration } from "../timelineMaster/persistSceneDuration";
import { rematerializeSceneExecutionWindows } from "../timelineMaster/rematerializeThenGenerate";
import {
  nextTimelineScaleExtraSec,
  timelineRulerTickStepSec,
  timelineRulerTicks,
  timelineScaleShouldGrow,
  timelineSequenceSec,
  timelineViewportSec,
  timelineVisibleScaleSec,
} from "../timelineMaster/timelineVisibleScale";


function mediaClipFaceLabel(
  kind: "audio" | "sfx" | "lipsync",
  clip: {
    title?: string | null;
    description?: string | null;
    label?: string | null;
    line?: string | null;
    character_name?: string | null;
    audio_asset_id?: string | null;
    asset_id?: string | null;
    id?: string | null;
  },
  asset?: { tag?: string | null; filename?: string | null } | null,
  promptTexts?: string[] | null,
  clipStart?: number,
  clipLength?: number,
): { face: string; fullTitle: string | null; description: string | null } {
  const resolved = resolveMediaClipLabels({
    kind: kind === "lipsync" ? "lipsync" : kind,
    clip: {
      title: clip.title,
      description: clip.description,
      label: clip.label,
      line: clip.line,
      character_name: clip.character_name,
      audio_asset_id: clip.audio_asset_id,
      asset_id: clip.asset_id,
      id: clip.id,
    },
    asset: asset || null,
    promptContext: promptTexts?.length
      ? { prompts: promptTexts, clipStart, clipLength }
      : null,
  });
  const fallback = kind === "audio" ? "Audio" : kind === "sfx" ? "SFX" : "Lip Sync Clip";
  const ownLabel = (clip.label || "").trim();
  const genericFace = !ownLabel || /^(audio|sfx|music|sound effect)$/i.test(ownLabel);
  return {
    face: genericFace ? resolved.label || fallback : ownLabel,
    fullTitle: resolved.title || ownLabel || null,
    description: clip.description ?? resolved.description,
  };
}

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
    type: "character" | "prop" | "environment";
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
    type: (row.type || "character") as "character" | "prop" | "environment",
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

function pct(start: number, length: number, duration: number) {
  const d = Math.max(0.1, duration);
  return {
    left: `${(start / d) * 100}%`,
    width: `${(Math.max(0.15, length) / d) * 100}%`,
  };
}

function snapTime(t: number, snap: boolean, step = 0.25) {
  if (!snap) return Math.max(0, t);
  return Math.max(0, Math.round(t / step) * step);
}


function dropTimeFromLane(e: React.DragEvent, boardDuration: number, snap: boolean, sceneFps: number): number {
  const row = e.currentTarget as HTMLElement;
  const content = (row.querySelector("[class*='track-content']") as HTMLElement | null) || row;
  const rect = content.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / Math.max(1, rect.width)));
  return snapTime(ratio * boardDuration, snap, snap ? 1 / sceneFps : 0.01);
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

function trackRowClass(shellMode: boolean, extra = "") {
  const base = shellMode ? "timeline-v2__track-row" : "track-row";
  return extra ? `${base} ${extra}` : base;
}

function trackContentClass(shellMode: boolean, extra = "") {
  const base = shellMode ? "timeline-v2__track-content" : "track-lane";
  return extra ? `${base} ${extra}` : base;
}

function firstLaneMuted(
  master: SceneTimelineMaster | null | undefined,
  tl: TimelineBoardView | null,
  kind: "audio" | "sfx",
): boolean | undefined {
  if (masterHasBatchOwnedAudio(master, kind) && master) {
    for (const batch of master.batchBlocks || []) {
      const clips = kind === "audio" ? batch.audioClips || [] : batch.sfxClips || [];
      if (clips.length) return Boolean(clips[0]?.muted);
    }
  }
  const clips = kind === "audio" ? tl?.audioClips || [] : tl?.sfxClips || [];
  if (clips.length) return Boolean(clips[0]?.muted);
  return undefined;
}

function TrackHeader({
  label,
  labelKey,
  testId,
  shellMode,
  controls = ["eye", "lock"],
  pressedControls,
  headerExtra,
  actionLabel,
  onAction,
  onControlToggle,
}: {
  label: string;
  labelKey?: string;
  testId?: string;
  shellMode: boolean;
  controls?: Array<"eye" | "lock" | "mute" | "solo">;
  pressedControls?: Array<"eye" | "lock" | "mute" | "solo">;
  headerExtra?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  onControlToggle?: (control: "eye" | "lock" | "mute" | "solo") => void;
}) {
  if (shellMode) {
    return (
      <TimelineTrackLabel
        label={label}
        labelKey={labelKey}
        testId={testId}
        controls={controls}
        pressedControls={pressedControls}
        headerExtra={headerExtra}
        onAction={onAction}
        onControlToggle={onControlToggle}
      />
    );
  }
  return (
    <div className="track-label">
      {label}
      {onAction ? (
        <button className="ghost" style={{ padding: "0.15rem 0.45rem", marginTop: 4 }} onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

/** Normalize legacy start/middle/end roles into free guide clips for Director Timeline Generation.
 * Preserves stable display_tag; never overwrites tags with index-based Image N.
 */
function freeImageClips(tl: TimelineBoardView): TimelineClip[] {
  const clips = tl.imageClips || [];
  if (!clips.length) return [];
  return clips.map((c, i) => {
    const resolvedLabel = c.display_tag
      ? c.display_tag
      : c.label && !["Start", "Middle", "End"].includes(c.label)
        ? c.label
        : `Image ${i + 1}`;
    return {
      ...c,
      role: "guide" as const,
      label: resolvedLabel,
    };
  });
}


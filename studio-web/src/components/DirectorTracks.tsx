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
import { findSameTrackIntersection, rangesIntersect } from "../timelineMaster/sameTrackNoOverlap";
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

export function DirectorTracks({
  project,
  scene,
  onChange,
  viewMode = "tracks",
  onGoEditor,
  hideEmbeddedStage = false,
  externalPlayhead,
  onPlayheadChange,
  reloadKey = 0,
  master = null,
  shellMode = false,
  mutateTimeline,
  retakeMode = false,
  retakeRange = null,
  onRetakeRangeDraft,
  onRetakeRangeCommit,
  repairMarkMode = false,
  repairRange = null,
  onRepairRangeDraft,
  onRepairRangeCommit,
  onStartRepairMark,
  previewSceneTakeId = null,
  onOpenAudioClip,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
  viewMode?: "tracks" | "prompt" | "full";
  onGoEditor?: () => void;
  /** When Preview Monitor is stacked above tracks (W46 SA26). */
  hideEmbeddedStage?: boolean;
  externalPlayhead?: number;
  onPlayheadChange?: (t: number) => void;
  reloadKey?: number;
  master?: SceneTimelineMaster | null;
  shellMode?: boolean;
  mutateTimeline?: (
    mutator: (timeline: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
  retakeMode?: boolean;
  retakeRange?: { start: number; length: number } | null;
  onRetakeRangeDraft?: (range: { start: number; length: number } | null) => void;
  onRetakeRangeCommit?: (range: { start: number; length: number }) => void;
  repairMarkMode?: boolean;
  repairRange?: { start: number; length: number } | null;
  onRepairRangeDraft?: (range: { start: number; length: number } | null) => void;
  onRepairRangeCommit?: (range: { start: number; length: number }) => void;
  onStartRepairMark?: () => void;
  previewSceneTakeId?: string | null;
  onOpenAudioClip?: (request: { kind: "audio" | "sfx"; clipId: string | null; start: number }) => void;
}) {
  const { t } = useTranslation("timeline");
  void t;
  void repairMarkMode;
  void repairRange;
  void onRepairRangeDraft;
  void onRepairRangeCommit;
  void onStartRepairMark;
  void onRetakeRangeDraft;
  void onRetakeRangeCommit;
  const sel = useDirectorSelectionOptional();
  const [tl, setTl] = useState<TimelineBoardView | null>(null);  const [selectedSeg, setSelectedSeg] = useState<string>();
  const [selectedClip, setSelectedClip] = useState<string>();
  const [timelineRefsEnabled, setTimelineRefsEnabled] = useState(false);
  const [selectedClipKind, setSelectedClipKind] = useState<
    "imageClip" | "videoClip" | "videoReferenceClip" | "imageReferenceClip" | "camera" | "audio" | "sfx" | null
  >(null);
  const [refsCounts, setRefsCounts] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [tagWarnings, setTagWarnings] = useState<string[]>([]);
  const [sendMsg, setSendMsg] = useState<string | null>(null);
  const [sendBusy, setSendBusy] = useState(false);
  const [bindings, setBindings] = useState<ReferenceBindingView[]>([]);
  const [tokenDraft, setTokenDraft] = useState<Record<string, string>>({});
  void tokenDraft;
  void setTokenDraft;
  const [tokenError, setTokenError] = useState<string | null>(null);
  // Consolidated, non-spammy save error state. A failed save preserves local
  // drafts (tl is set before the API call) and surfaces a single status; it
  // does not trigger repeated retries (API_ERROR_CONSOLIDATED_NO_SPAM).
  const [saveError, setSaveError] = useState<string | null>(null);
  const [laneMuteOverride, setLaneMuteOverride] = useState<Partial<Record<"audio" | "sfx", boolean>>>({});
  const [soloLane, setSoloLane] = useState<"audio" | "sfx" | null>(null);
  const [includeAudio, setIncludeAudio] = useState(true);
  const [proxyFlag, setProxyFlag] = useState(false);
  const [audioIntentDraft, setAudioIntentDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workspaceLayout, setWorkspaceLayout] = useState(() => loadTimelineWorkspaceLayout());
  const [rulerHoverSec, setRulerHoverSec] = useState<number | null>(null);
  const [undoSnapshot, setUndoSnapshot] = useState<TimelineBoardView | null>(null);
  const [removeNotice, setRemoveNotice] = useState(false);
  const [editingPromptId, setEditingPromptId] = useState<string | null>(null);
  /* Phase 0: editingCameraId removed with CAMERA lane */
  const boardScrollRef = useRef<HTMLDivElement>(null);
  // Scroll-aware batch windowing (100+ batches): the render window tracks the
  // visible scroll range in addition to playhead/selection, so scrolling to a
  // distant batch never renders a blank lane (audit UI-D9).
  const [boardScroll, setBoardScroll] = useState({ left: 0, width: 0 });
  const [scaleExtraSec, setScaleExtraSec] = useState(0);
  const playheadRef = useRef<HTMLDivElement>(null);
  const undoTimerRef = useRef<number | null>(null);
  // NO_STALE_RELOAD: generation token so only the latest getDirector response
  // is applied to local state. A late response from a previous load (e.g.
  // batch-add then image-save racing) is discarded instead of clobbering
  // newer local/PUT state.
  const loadTokenRef = useRef(0);

  // Sync local highlight from the authoritative global selection so the
  // highlighted clip and the Inspector never diverge (TIMELINE_OWNS_SELECTION).
  // When global selection is cleared/reset to scene, local highlight clears
  // too â€” no more brown clip staying active while the Inspector shows Scene.
  useEffect(() => {
    const s = sel?.selection;
    if (!s) {
      setSelectedSeg(undefined);
      setSelectedClip(undefined);
      setSelectedClipKind(null);
      return;
    }
    if (s.kind === "promptSeg") {
      setSelectedSeg(s.id);
      setSelectedClip(undefined);
      setSelectedClipKind(null);
    } else if (s.kind === "camera") {
      /* Phase 0: CAMERA lane unmounted â€” clear legacy camera selection */
      setSelectedSeg(undefined);
      setSelectedClip(undefined);
      setSelectedClipKind(null);
      if (scene) sel?.setSelection({ kind: "scene", id: scene.id });
    } else if (
      s.kind === "imageClip" ||
      s.kind === "videoClip" ||
      s.kind === "videoReferenceClip" ||
      s.kind === "imageReferenceClip" ||
      s.kind === "audio" ||
      s.kind === "sfx"
    ) {
      setSelectedClip(s.id);
      setSelectedClipKind(s.kind);
      setSelectedSeg(undefined);
    } else {
      setSelectedSeg(undefined);
      setSelectedClip(undefined);
      setSelectedClipKind(null);
    }
  }, [sel?.selection]);
  const zoom = sel?.zoom ?? 1;
  const setZoom = sel?.setZoom ?? (() => undefined);
  const snap = sel?.snap ?? workspaceLayout.snapEnabled;
  const setSnap = sel?.setSnap ?? (() => undefined);

  useEffect(() => {
    api
      .health()
      .then((h: any) => setTimelineRefsEnabled(Boolean(h?.operator?.timelineReferencesEnabled)))
      .catch(() => setTimelineRefsEnabled(false));
  }, []);

  useEffect(() => {
    const onLayout = (event: Event) => {
      const detail = (event as CustomEvent<TimelineWorkspaceLayout>).detail;
      const next = detail || loadTimelineWorkspaceLayout();
      setWorkspaceLayout((prev) => {
        if (
          prev.zoom === next.zoom &&
          prev.trackDensity === next.trackDensity &&
          prev.displayMode === next.displayMode &&
          prev.snapEnabled === next.snapEnabled &&
          prev.playheadFollow === next.playheadFollow &&
          prev.guidancePriority === next.guidancePriority &&
          prev.showFilenames === next.showFilenames &&
          prev.showThumbnails === next.showThumbnails
        ) {
          return prev;
        }
        return next;
      });
    };
    window.addEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
    return () => window.removeEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
  }, []);

  const storedPromptBindingKey = useMemo(
    () => collectPromptBindingIds(tl?.promptSegments).sort().join(","),
    [tl?.promptSegments],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      loadTimelineReferenceCatalog({
        projectId: project.id,
        sceneId: scene?.id,
        bindingIds: storedPromptBindingKey ? storedPromptBindingKey.split(",") : [],
      }),
      api.listCharacterProfiles(project.id).catch(() => ({ items: [] })),
    ])
      .then(([catalog, characters]) => {
        if (cancelled) return;
        const profiles = new Map(
          (characters.items || []).map((profile: { id: string; name?: string }) => [
            profile.id,
            String(profile.name || "").trim(),
          ]),
        );
        const items = catalog.map((binding) => {
          const asset = project.assets.find((a) => a.id === binding.asset_id);
          const labeled = labelCharacterBindingFromIdentity(binding, profiles.get(binding.identity_id || ""));
          return { ...labeled, duration_sec: assetDurationSec(asset) };
        });
        const boundIdentities = new Set(items.map((item) => item.identity_id).filter(Boolean));
        const extra: ReferenceBindingView[] = [];
        for (const profile of characters.items || []) {
          if (boundIdentities.has(profile.id)) continue;
          const name = String(profile.name || "").trim();
          if (!name) continue;
          const asset =
            project.assets.find((a) => (a.tag || "").toLowerCase() === name.toLowerCase() && a.kind === "image") ||
            project.assets.find((a) => a.kind === "image");
          extra.push({
            id: `character:${profile.id}`,
            asset_id: asset?.id || "",
            identity_id: profile.id,
            alias: name.replace(/\s+/g, ""),
            media_kind: "entity",
            reference_type: "character",
            display_token: `@${name.replace(/\s+/g, "")}`,
            asset_name: name,
          });
        }
        setBindings([...items, ...extra]);
      })
      .catch(() => {
        if (!cancelled) setBindings([]);
      });
    return () => {
      cancelled = true;
    };
  }, [project.assets, project.id, reloadKey, scene?.id, storedPromptBindingKey]);

  useEffect(() => {
    return subscribeShellTimelineSnapshot((snapshot) => {
      if (!snapshot) return;
      setTl((prev) => (prev ? applyShellPromptSnapshot(prev, snapshot) : snapshot));
    });
  }, []);

  const directorSceneIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!scene) return;
    const token = ++loadTokenRef.current;
    const sceneChanged = directorSceneIdRef.current !== scene.id;
    directorSceneIdRef.current = scene.id;
    if (sceneChanged) setTl(null);
    let cancelled = false;
    Promise.resolve()
      .then(() => {
        if (cancelled || token !== loadTokenRef.current) return;
        const clips = projectMasterPreviewClips(master);
        const incoming = {
          media_mode: clips.videoClips.length ? "video" : "image",
          duration_sec: scene.duration_sec || 5,
          ...clips,
          imageClips: freeImageClips({ imageClips: clips.imageClips } as TimelineBoardView),
          video_reference_clips: [],
          image_reference_clips: [],
          cameraClips: [],
          // SINGLE-STORE: prompt view projects from Master, never from a
          // legacy director blob.
          promptSegments: flattenMasterPrompts(master).map(masterPromptSegmentToView),
          lipsync: { tracks: normalizeLipSyncTracks([]) },
          playhead: 0,
          guidance_priority: "visual_first",
        } as TimelineBoardView;
        let next: TimelineBoardView = incoming;
        setTl((prev) => {
          next = overlayLiveTimeline(incoming, sceneChanged ? null : prev);
          return next;
        });
        const masterPromptIds = new Set(flattenMasterPrompts(master).map((s) => s.id));
        setSelectedSeg((prev) => {
          if (prev && masterPromptIds.has(prev)) return prev;
          if (
            sel?.selection?.kind === "promptSeg" &&
            sel.selection.id &&
            masterPromptIds.has(sel.selection.id)
          ) {
            return sel.selection.id;
          }
          return undefined;
        });
        if (externalPlayhead == null) {
          onPlayheadChange?.(next.playhead || 0);
        }
        const layout = loadTimelineWorkspaceLayout();
        setWorkspaceLayout(layout);
        if (layout.guidancePriority) {
          setTl({ ...next, guidance_priority: layout.guidancePriority });
        }
      })
      .catch(() => {
        if (cancelled || token !== loadTokenRef.current) return;
        // True-empty fallback so shell mode never sticks on a perpetual loader.
        setTl({
          media_mode: "image",
          duration_sec: scene.duration_sec || 5,
          imageClips: [],
          videoClips: [],
          video_reference_clips: [],
          image_reference_clips: [],
          promptSegments: [],
          cameraClips: [],
          audioClips: [],
          sfxClips: [],
          lipsync: { tracks: normalizeLipSyncTracks([]) },
          playhead: 0,
          guidance_priority: "visual_first",
        } as unknown as TimelineBoardView);
      });
    return () => {
      cancelled = true;
    };
    // Intentionally omit onPlayheadChange â€” parent setter identity must not retrigger reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, scene?.id, scene?.director_json, reloadKey, master]);

  useEffect(() => {
    setScaleExtraSec(0);
  }, [scene?.id]);

  useLayoutEffect(() => {
    const el = boardScrollRef.current;
    if (!el) return;
    const measure = () => setBoardScroll({ left: el.scrollLeft, width: el.clientWidth });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [scene?.id, shellMode]);

  // Prefetch per-clip Refs counts so track chrome is honest before a clip is selected.
  // Debounced: `tl` changes on every drag/trim commit, and without a settle
  // window each commit fired N parallel requests (audit D11).
  useEffect(() => {
    if (!scene || !tl || !timelineRefsEnabled) return;
    const clips = tl.imageClips || [];
    if (!clips.length) {
      setRefsCounts({});
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (document.visibilityState === "hidden") return;
      void Promise.all(
        clips.map(async (clip) => {
          try {
            const data = await api.getTimelineReferences(project.id, scene.id, clip.id);
            return [clip.id, Number(data?.count ?? (data?.bindings || []).length ?? 0)] as const;
          } catch {
            return [clip.id, 0] as const;
          }
        }),
      ).then((pairs) => {
        if (cancelled) return;
        const next: Record<string, number> = {};
        for (const [id, count] of pairs) next[id] = count;
        setRefsCounts(next);
      });
    }, 600);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [project.id, scene?.id, tl, timelineRefsEnabled]);

  const assetsById = useMemo(() => {
    const m = new Map<string, Asset>();
    project.assets.forEach((a) => m.set(a.id, a));
    return m;
  }, [project.assets]);

  // RULES OF HOOKS: these must stay above the scene/tl early returns.
  // Refs keep persist/commit implementations without changing hook count when tl hydrates.
  const editingPromptIdRef = useRef(editingPromptId);
  editingPromptIdRef.current = editingPromptId;
  const persistPromptEditRef = useRef<
    (id: string, patch: Partial<PromptSegment>, opts?: { close?: boolean }) => void | Promise<void>
  >(async () => undefined);
  const commitPromptEditRef = useRef<
    (id: string, patch: Partial<PromptSegment>) => void | Promise<void>
  >(async () => undefined);
  // Serialize Timed Prompt writes. A meta patch built from an older snapshot
  // must not replace prompt text that OK or blur already queued.
  const promptWriteTail = useRef(Promise.resolve());
  const promptWriteSegs = useRef<PromptSegment[] | null>(null);
  const promptDismissGuardUntil = useRef(0);
  const closeTimedPromptModal = useCallback(() => {
    if (shouldIgnoreTimedPromptDismiss(Date.now(), promptDismissGuardUntil.current)) return;
    setEditingPromptId(null);
  }, []);
  const persistTimedPromptPatch = useCallback((patch: Partial<PromptSegment>) => {
    const id = editingPromptIdRef.current;
    if (!id) return;
    void persistPromptEditRef.current(id, patch);
  }, []);
  const commitTimedPromptPatch = useCallback((patch: Partial<PromptSegment>) => {
    const id = editingPromptIdRef.current;
    if (!id) return;
    void commitPromptEditRef.current(id, patch);
  }, []);

  const trackLabelWidthPx = shellMode ? 132 : 88;
  const scalePxPerSec = pixelsPerSecond(zoom);
  const scaleViewportSec = timelineViewportSec(
    Math.max(0, boardScroll.width - trackLabelWidthPx),
    scalePxPerSec,
  );
  const scaleSequenceSec = timelineSequenceSec(
    liveSceneClockSec(scene, tl) || 5,
    (master?.batchBlocks || []).reduce((sum, batch) => sum + Math.max(0, Number(batch.duration?.plannedDuration || 0)), 0),
  );
  const scaleBoardDuration = timelineVisibleScaleSec({
    sequenceSec: scaleSequenceSec,
    viewportSec: scaleViewportSec,
    extraSec: scaleExtraSec,
  });
  const scaleBoardWidth = scalePxPerSec * scaleBoardDuration;

  useEffect(() => {
    if (
      !timelineScaleShouldGrow({
        scrollLeftPx: boardScroll.left,
        viewportPx: boardScroll.width,
        boardWidthPx: trackLabelWidthPx + scaleBoardWidth,
      })
    ) {
      return;
    }
    setScaleExtraSec((prev) => nextTimelineScaleExtraSec(prev, scaleViewportSec));
  }, [boardScroll.left, boardScroll.width, scaleBoardWidth, scaleViewportSec]);

  useEffect(() => {
    setLaneMuteOverride((prev) => {
      if (prev.audio === undefined && prev.sfx === undefined) return prev;
      const next = { ...prev };
      if (prev.audio !== undefined && prev.audio === firstLaneMuted(master, tl, "audio")) delete next.audio;
      if (prev.sfx !== undefined && prev.sfx === firstLaneMuted(master, tl, "sfx")) delete next.sfx;
      return next;
    });
  }, [master, tl]);

  // SINGLE-STORE: Timed Prompt track reads Master batch.promptSegments (view
  // projection) — never the retired legacy TimelineBoardView.promptSegments.
  const masterPrompts = useMemo(
    () => flattenMasterPrompts(master).map(masterPromptSegmentToView),
    [master],
  );
  const masterPromptsRef = useRef(masterPrompts);
  masterPromptsRef.current = masterPrompts;
  /** Fresh Master for writers after empty-window bootstrap (prop may lag one frame). */
  const masterLiveRef = useRef(master);
  masterLiveRef.current = master;
  const emptyWindowBootstrapSceneRef = useRef<string | null>(null);
  useEffect(() => {
    const local = promptWriteSegs.current;
    if (!local) return;
    const caughtUp =
      local.length === masterPrompts.length &&
      local.every((seg) => {
        const live = masterPrompts.find((row) => row.id === seg.id);
        return (
          !!live &&
          live.text === seg.text &&
          JSON.stringify(live.reference_name_bindings || []) ===
            JSON.stringify(seg.reference_name_bindings || [])
        );
      });
    if (caughtUp) promptWriteSegs.current = null;
  }, [masterPrompts]);

  // Recover empty masters on open: GET bootstraps from Scene.engine so locked
  // toolbar writers see a window without waiting for Add.
  useEffect(() => {
    if (!scene || !master) return;
    if ((master.batchBlocks || []).length > 0) {
      emptyWindowBootstrapSceneRef.current = null;
      return;
    }
    if (emptyWindowBootstrapSceneRef.current === scene.id) return;
    emptyWindowBootstrapSceneRef.current = scene.id;
    let cancelled = false;
    void (async () => {
      try {
        const loaded = await api.directorTimelineMaster(project.id, scene.id);
        if (cancelled) return;
        if (loaded?.ok && loaded.master && (loaded.master.batchBlocks || []).length > 0) {
          masterLiveRef.current = loaded.master;
          await onChange();
          return;
        }
        const durationSec = Number(scene.duration_sec) || 0;
        const generatorId = String(
          loaded?.master?.sceneGeneratorId || master.sceneGeneratorId || scene.engine || "",
        ).trim();
        if (!(durationSec > 0) || !generatorId) return;
        const remat = await rematerializeSceneExecutionWindows({
          projectId: project.id,
          sceneId: scene.id,
          generatorId,
          durationSeconds: durationSec,
        });
        if (cancelled || remat.ok === false) return;
        const nextMaster = remat.master as SceneTimelineMaster | undefined;
        if (nextMaster && (nextMaster.batchBlocks || []).length > 0) {
          masterLiveRef.current = nextMaster;
          await onChange();
        }
      } catch {
        /* Add/drop surfaces a creator-language error if still empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [project.id, scene?.id, scene?.duration_sec, scene?.engine, master, onChange]);

  if (!scene) {
    return (
      <div className={shellMode ? "timeline-v2__canvas" : "panel"} data-testid="timeline-track-board">
        <p className="empty">{shellMode ? "Select a Scene in the left rail." : "Select a scene"}</p>
      </div>
    );
  }
  if (!tl) {
    return (
      <div className={shellMode ? "timeline-v2__canvas" : "panel"} data-testid="timeline-track-board">
        <p className="scene-meta">{shellMode ? "Loading Timeline tracksâ€¦" : "Loadingâ€¦"}</p>
      </div>
    );
  }

  const hasOutput = !!(scene.output_path || tl.videoClips[0]?.asset_id);

  const sendToEditor = async (mode: "shot" | "sequence" | "selected") => {
    if (!scene) return;
    setSendBusy(true);
    setSendMsg(null);
    try {
      const segmentIds =
        mode === "selected" && selectedSeg
          ? [selectedSeg]
          : mode === "selected"
            ? tl.promptSegments.map((s) => s.id)
            : undefined;
      const seq = await api.directorSequenceFromScene(project.id, {
        scene_id: scene.id,
        name: `${scene.name} Â· ${mode === "shot" ? "Shot" : mode === "selected" ? "Segments" : "Sequence"}`,
        status: hasOutput ? "approved" : "draft",
        include_audio: includeAudio,
        proxy: proxyFlag,
        segment_ids: segmentIds,
      });
      if (hasOutput || mode === "sequence") {
        await api.patchDirectorSequence(project.id, seq.id, { approve: true });
      }
      await api.sendDirectorToEditor(project.id, seq.id, {
        track: "video",
        include_audio: includeAudio,
        proxy: proxyFlag,
        label: seq.name,
      });
      setSendMsg(`Sent to Editor (${mode}${proxyFlag ? ", proxy" : ""}${includeAudio ? "" : ", video only"}).`);
      onGoEditor?.();
    } catch (e) {
      setSendMsg(e instanceof Error ? e.message : "Send to Editor failed");
    } finally {
      setSendBusy(false);
    }
  };

  const save = async (next: TimelineBoardView) => {
    // SINGLE-STORE: PUT /director is retired (410 Gone). SceneTimelineMaster is
    // the sole Timeline authority. Legacy track edits are applied to local
    // state for immediate UI feedback and persisted via Master batch clip
    // arrays where a Master mapping exists. Prompt edits route through
    // persistViaMutate → Master patchBatch only.
    const normalized = {
      ...next,
      lipsync: { tracks: normalizeLipSyncTracks(next.lipsync?.tracks) },
    } as TimelineBoardView;
    setTl(normalized);
    setSaving(true);
    try {
      const liveMaster = masterLiveRef.current || master;
      if (liveMaster && scene) {
        // SINGLE-STORE removal diff: view clip arrays are Master projections,
        // so an id present before but absent now is a creator removal and must
        // be deleted from the Master clip array (not just hidden in the view).
        const removedVisualViewIds = [
          ...(tl?.imageClips || []).filter((c) => !(next.imageClips || []).some((n) => n.id === c.id)),
          ...(tl?.videoClips || []).filter((c) => !(next.videoClips || []).some((n) => n.id === c.id)),
        ].map((c) => c.id);
        const removedVisual = removableVisualClipIds(liveMaster, removedVisualViewIds);
        const removedAudio = new Set(
          (tl?.audioClips || [])
            .filter((c) => !(next.audioClips || []).some((n) => n.id === c.id))
            .map((c) => c.id),
        );
        const removedSfx = new Set(
          (tl?.sfxClips || [])
            .filter((c) => !(next.sfxClips || []).some((n) => n.id === c.id))
            .map((c) => c.id),
        );
        if (next.imageClips !== tl?.imageClips || next.videoClips !== tl?.videoClips || removedVisual.size) {
          await syncMasterClips(project.id, scene.id, liveMaster, {
            attr: "visualClips",
            removeIds: removedVisual,
            upserts: [
              ...(next.imageClips || []).map((c) => ({
                id: c.id,
                kind: "image" as const,
                assetId: c.asset_id ?? null,
                start: Number(c.start) || 0,
                length: Number(c.length) || 0,
                label: c.label || "Image clip",
                role: c.role,
              })),
              ...(next.videoClips || []).map((c) => ({
                id: c.id,
                kind: "video" as const,
                assetId: c.asset_id ?? null,
                start: Number(c.start) || 0,
                length: Number(c.length) || 0,
                label: c.label || "Video clip",
              })),
            ],
          });
        }
        if (next.audioClips !== tl?.audioClips || removedAudio.size) {
          await syncMasterClips(project.id, scene.id, liveMaster, {
            attr: "audioClips",
            removeIds: removedAudio,
            upserts: (next.audioClips || []).map((c) => ({
              id: c.id,
              kind: "audio" as const,
              assetId: c.asset_id ?? null,
              start: Number(c.start) || 0,
              length: Number(c.length) || 0,
              label: c.label || "Audio clip",
            })),
          });
        }
        if (next.sfxClips !== tl?.sfxClips || removedSfx.size) {
          await syncMasterClips(project.id, scene.id, liveMaster, {
            attr: "sfxClips",
            removeIds: removedSfx,
            upserts: (next.sfxClips || []).map((c) => ({
              id: c.id,
              kind: "sfx" as const,
              assetId: c.asset_id ?? null,
              start: Number(c.start) || 0,
              length: Number(c.length) || 0,
              label: c.label || "SFX clip",
            })),
          });
        }
      }
      setSaveError(null);
      onChange();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed — your edits are preserved locally.");
    } finally {
      setSaving(false);
    }
  };

  const persistMasterPromptRemoval = async (removedIds: Iterable<string>) => {
    const liveMaster = masterLiveRef.current || master;
    if (!liveMaster || !scene) return;
    await removeMasterPrompts(project.id, scene.id, liveMaster, removedIds);
  };

  const persistMasterPromptUpserts = async (
    prevSegs: PromptSegment[],
    nextSegs: PromptSegment[],
  ) => {
    const liveMaster = masterLiveRef.current || master;
    if (!liveMaster || !scene) return;
    for (const seg of nextSegs) {
      const prev = prevSegs.find((s) => s.id === seg.id);
      const changed =
        !prev ||
        prev.text !== seg.text ||
        Number(prev.start) !== Number(seg.start) ||
        Number(prev.length) !== Number(seg.length) ||
        JSON.stringify(prev.reference_binding_ids || []) !== JSON.stringify(seg.reference_binding_ids || []);
      if (!changed) continue;
      await patchMasterPrompt(project.id, scene.id, liveMaster, {
        id: seg.id,
        start: Number(seg.start) || 0,
        length: Number(seg.length) || 0,
        text: seg.text || "",
        referenceBindingIds: seg.reference_binding_ids || [],
      });
    }
  };


  const persistViaMutate = async (
    mutator: (current: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => {
    if (!tl) return null;
    const bound = mutateTimeline || getBoundShellTimelineMutate();
    const next = mutator(tl);
    const removedPromptIds = [...promptIdsOf(tl)].filter((id) => !promptIdsOf(next).has(id));
    syncPromptTombstones(tl, next);
    setTl(next);
    if (bound) {
      await bound(mutator, opts);
    } else {
      // SINGLE-STORE: Master is sole SoT. Patch Master batch.promptSegments
      // directly (start-containment). No putDirector, no midpoint mirror.
      await persistMasterPromptRemoval(removedPromptIds);
      await persistMasterPromptUpserts(tl?.promptSegments || [], next.promptSegments || []);
    }
    return next;
  };

  /**
   * SINGLE-STORE Timed Prompt write path. When a Master is present, prompt
   * mutations diff the Master-derived view list (masterPrompts) and persist
   * straight to Master batch.promptSegments via patchMasterPrompt /
   * removeMasterPrompts — never through the retired legacy promptSegments
   * view array (which is empty under single-store and silently dropped
   * edits). Falls back to persistViaMutate only when no Master exists.
   */
  const persistPrompts = (
    mutator: (segments: PromptSegment[]) => PromptSegment[],
  ): Promise<void> => {
    const run = promptWriteTail.current.then(async () => {
      try {
        const liveMaster = masterLiveRef.current || master;
        if (liveMaster && scene) {
          const prevSegs = promptWriteSegs.current ?? masterPromptsRef.current;
          const nextSegs = mutator(prevSegs.map((seg) => ({ ...seg })));
          const nextIds = new Set(nextSegs.map((seg) => seg.id));
          const removedIds = prevSegs.filter((seg) => !nextIds.has(seg.id)).map((seg) => seg.id);
          if (removedIds.length) {
            await removeMasterPrompts(project.id, scene.id, liveMaster, removedIds);
          }
          for (const seg of nextSegs) {
            const prev = prevSegs.find((row) => row.id === seg.id);
            const changed =
              !prev ||
              prev.text !== seg.text ||
              Number(prev.start) !== Number(seg.start) ||
              Number(prev.length) !== Number(seg.length) ||
              JSON.stringify(prev.reference_binding_ids || []) !==
                JSON.stringify(seg.reference_binding_ids || []) ||
              JSON.stringify(prev.reference_name_bindings || []) !==
                JSON.stringify(seg.reference_name_bindings || []) ||
              JSON.stringify(prev.movement_segment_ref ?? null) !==
                JSON.stringify(seg.movement_segment_ref ?? null) ||
              (prev.movement_segment_revision ?? null) !== (seg.movement_segment_revision ?? null) ||
              (prev.production_prompt ?? null) !== (seg.production_prompt ?? null) ||
              (prev.dialogue ?? null) !== (seg.dialogue ?? null);
            if (!changed) continue;
            await patchMasterPrompt(project.id, scene.id, liveMaster, {
              id: seg.id,
              start: Number(seg.start) || 0,
              length: Number(seg.length) || 0,
              text: seg.text || "",
              referenceBindingIds: seg.reference_binding_ids || [],
              referenceNameBindings: seg.reference_name_bindings || [],
              productionPrompt: seg.production_prompt !== undefined ? seg.production_prompt : undefined,
              dialogue: seg.dialogue !== undefined ? seg.dialogue : undefined,
              movementSegmentRef:
                seg.movement_segment_ref !== undefined ? seg.movement_segment_ref : undefined,
              movementSegmentRevision:
                seg.movement_segment_revision !== undefined ? seg.movement_segment_revision : undefined,
            });
          }
          promptWriteSegs.current = nextSegs;
          onChange();
          return;
        }
        await persistViaMutate((current) => ({
          ...current,
          promptSegments: mutator(current.promptSegments || []),
        }));
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : "Could not save Timed Prompt changes.");
        throw e;
      }
    });
    promptWriteTail.current = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  };

  /**
   * Empty new scenes have no execution windows until rematerialize/bootstrap.
   * Locked writers (patchMasterPrompt / syncMasterClips) no-op without a window.
   * Prefer GET (server bootstraps from Scene.engine) then rematerialize if needed.
   */
  const ensureMasterWindows = async (): Promise<SceneTimelineMaster | null> => {
    if (!scene) return null;
    const current = masterLiveRef.current || master;
    if (current && (current.batchBlocks || []).length > 0) return current;
    try {
      const loaded = await api.directorTimelineMaster(project.id, scene.id);
      if (loaded?.ok && loaded.master && (loaded.master.batchBlocks || []).length > 0) {
        masterLiveRef.current = loaded.master;
        await onChange();
        return loaded.master;
      }
      const durationSec = Number(scene.duration_sec) || 0;
      const generatorId = String(
        loaded?.master?.sceneGeneratorId || current?.sceneGeneratorId || scene.engine || "",
      ).trim();
      if (!(durationSec > 0)) {
        setSaveError("This scene needs a length before you can add clips. Set the scene duration, then try again.");
        return null;
      }
      if (!generatorId) {
        setSaveError("This scene needs a video engine before you can add clips. Choose an engine, then try again.");
        return null;
      }
      const remat = await rematerializeSceneExecutionWindows({
        projectId: project.id,
        sceneId: scene.id,
        generatorId,
        durationSeconds: durationSec,
      });
      if (remat.ok === false) {
        setSaveError(
          String(remat.message || remat.error || "Could not prepare the timeline for clips. Try again."),
        );
        return null;
      }
      const nextMaster = (remat.master as SceneTimelineMaster | undefined) || null;
      if (nextMaster && (nextMaster.batchBlocks || []).length > 0) {
        masterLiveRef.current = nextMaster;
        await onChange();
        return nextMaster;
      }
      const again = await api.directorTimelineMaster(project.id, scene.id);
      if (again?.ok && again.master && (again.master.batchBlocks || []).length > 0) {
        masterLiveRef.current = again.master;
        await onChange();
        return again.master;
      }
      setSaveError("Could not prepare the timeline for clips. Try again.");
      return null;
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not prepare the timeline for clips.");
      return null;
    }
  };

  const persistPromptEdit = async (
    id: string,
    patch: Partial<PromptSegment>,
    opts?: { close?: boolean },
  ) => {
    if (opts?.close) setEditingPromptId(null);
    let nextPatch: Partial<PromptSegment> =
      patch.text !== undefined ? { ...patch, production_prompt: null } : patch;
    if (nextPatch.start !== undefined || nextPatch.length !== undefined) {
      const current = masterPrompts.find((seg) => seg.id === id);
      const start = Number(nextPatch.start ?? current?.start ?? 0);
      const length = Number(nextPatch.length ?? current?.length ?? 0);
      const decision = decideTimedPromptRange(
        start,
        length,
        liveSceneClockSec(scene, tl),
        scene.name || "Scene 1",
      );
      if (!decision.ok) {
        const { start: _start, length: _length, ...safe } = nextPatch;
        nextPatch = safe;
        if (Object.keys(nextPatch).length === 0) return;
      }
    }
    await persistPrompts((segments) =>
      segments.map((seg) => (seg.id === id ? { ...seg, ...nextPatch } : seg)),
    );
  };

  const commitPromptEdit = async (id: string, patch: Partial<PromptSegment>) => {
    await persistPromptEdit(id, patch, { close: true });
  };

  /* Phase 0: commitCameraEdit removed with CAMERA lane */

  const duration = liveSceneClockSec(scene, tl) || 5;
  const sceneFps =
    scene.fps_mode && scene.fps_mode !== "auto" && scene.fps ? scene.fps : project.fps || 24;
  const playhead = externalPlayhead ?? tl.playhead ?? 0;
  const activeSeg =
    (masterPrompts.find((s) => s.id === selectedSeg) as unknown as PromptSegment | undefined) ||
    (masterPrompts[0] as unknown as PromptSegment | undefined);
  const editingPrompt =
    (masterPrompts.find((s) => s.id === editingPromptId) as unknown as PromptSegment | null) || null;
  persistPromptEditRef.current = persistPromptEdit;
  commitPromptEditRef.current = commitPromptEdit;

  /* Phase 0: editingCamera removed with CAMERA lane */
  const editorGeneratorId = (() => {
    const mid = editingPrompt ? editingPrompt.start + editingPrompt.length / 2 : playhead;
    let cursor = 0;
    const batches = [...(master?.batchBlocks || [])].sort((a, b) => a.order - b.order);
    for (const batch of batches) {
      const span = Math.max(0.1, Number(batch.duration?.plannedDuration || 0));
      if (mid >= cursor && mid < cursor + span) return batch.generatorId || scene.engine;
      cursor += span;
    }
    return batches[0]?.generatorId || scene.engine;
  })();
  const images = project.assets.filter((a) => a.kind === "image");
  const videos = project.assets.filter((a) => a.kind === "video");
  const audios = project.assets.filter((a) => a.kind === "audio");
  const imageClips = freeImageClips(tl);
  const selectedImageClip =
    selectedClipKind === "imageClip"
      ? imageClips.find((c) => c.id === selectedClip)
      : undefined;
  const playableTakes = playableVisualClipsFromMaster(master, { takeId: previewSceneTakeId });
  const sceneTake = resolveSceneTake(master, previewSceneTakeId);
  const visualVideoClips = displayedVisualVideoClips(
    tl.videoClips,
    playableTakes,
    tl.media_mode,
    sceneTake,
  );
  const displayAudioClips = resolveDisplayAudioClips(tl.audioClips, master, "audio") as Array<
    TimelineClip | DisplayBatchAudioClip
  >;
  const displaySfxClips = resolveDisplayAudioClips(tl.sfxClips, master, "sfx") as Array<
    TimelineClip | DisplayBatchAudioClip
  >;
  const showVideoVisual =
    tl.media_mode === "video" || ((tl.imageClips || []).length === 0 && visualVideoClips.length > 0);
  const batchWindows = (master?.batchBlocks || [])
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((batch, index, items) => {
      const start = items
        .slice(0, index)
        .reduce((sum, item) => sum + Math.max(0.1, item.duration.plannedDuration || 0), 0);
      return {
        batch,
        start,
        length: Math.max(0.1, batch.duration.plannedDuration || 0),
      };
    });
  const sequenceSec = scaleSequenceSec;
  const pxPerSec = scalePxPerSec;
  const boardDuration = scaleBoardDuration;
  const boardWidth = scaleBoardWidth;
  const rulerTickStep = timelineRulerTickStepSec(pxPerSec);
  const rulerTicks = timelineRulerTicks(boardDuration, rulerTickStep);
  const snapTargets = buildMagneticSnapTargets({
    sceneEnd: sequenceSec,
    batches: batchWindows.map((entry) => ({
      id: entry.batch.id,
      start: entry.start,
      length: entry.length,
      label: entry.batch.label,
    })),
    clips: [
      ...imageClips,
      ...visualVideoClips,
      ...(tl.promptSegments || []),
      /* Phase 0: cameraClips omitted from snap â€” lane unmounted; schema retained */
      ...displayAudioClips,
      ...displaySfxClips,
    ],
    playhead,
  });

  const laneClipsFor = (kind: "image" | "video" | "videoReference" | "imageReference" | "prompt" | "audio" | "sfx" | "camera") => {
    if (!tl) return [] as Array<{ id: string; start: number; length: number }>;
    if (kind === "image") return tl.imageClips || [];
    if (kind === "video") return visualVideoClips;
    if (kind === "videoReference") return tl.video_reference_clips || [];
    if (kind === "imageReference") return tl.image_reference_clips || [];
    if (kind === "prompt") return masterPrompts;
    if (kind === "audio") return displayAudioClips;
    if (kind === "sfx") return displaySfxClips;
    /* Phase 0: camera lane unmounted â€” no interactive clips */
    return [];
  };

  // CLIP_OVERLAP_GUARD: clips on the same lane may not overlap. Moves clamp
  // flush against the neighbor; trims clamp at the neighbor boundary.
  const clampToLane = (
    kind: "image" | "video" | "videoReference" | "imageReference" | "prompt" | "audio" | "sfx" | "camera",
    id: string,
    start: number,
    length: number,
    mode: ClipDragMode,
  ): { start: number; length: number } => {
    const others = laneClipsFor(kind)
      .filter((c) => c.id !== id)
      .map((c) => ({ s: c.start, e: c.start + c.length }))
      .sort((a, b) => a.s - b.s);
    let s = Math.max(0, start);
    let l = length;
    const fitPromptToScene = (nextStart: number, nextLength: number) => {
      if (kind !== "prompt") return { start: nextStart, length: nextLength };
      const sceneDur = liveSceneClockSec(scene, tl);
      if (sceneDur <= 0) return { start: nextStart, length: nextLength };
      const clampedStart = Math.max(0, Math.min(nextStart, Math.max(0, sceneDur - 0.15)));
      const end = Math.min(clampedStart + nextLength, sceneDur);
      return { start: clampedStart, length: Math.max(0.15, end - clampedStart) };
    };
    if (mode === "trim-left") {
      const end = s + l;
      for (const n of others) {
        if (n.e > s && n.s < end) s = Math.min(Math.max(s, n.e), end - 0.15);
      }
      return fitPromptToScene(s, Math.max(0.15, end - s));
    }
    if (mode === "trim-right") {
      for (const n of others) {
        if (n.s >= s - 1e-9 && n.s < s + l) l = Math.max(0.15, n.s - s);
      }
      return fitPromptToScene(s, l);
    }
    for (let pass = 0; pass < 2; pass++) {
      for (const n of others) {
        if (rangesIntersect(s, l, n.s, n.e - n.s)) {
          const leftFit = n.s - l;
          s = leftFit >= 0 && s <= n.s ? leftFit : n.e;
        }
      }
    }
    return fitPromptToScene(s, l);
  };

  const commitClipGeometry = (
    kind: "image" | "video" | "videoReference" | "imageReference" | "prompt" | "audio" | "sfx" | "camera",
    id: string,
    next: ClipGeometry,
    mode: ClipDragMode,
  ) => {
    const clamped = clampToLane(kind, id, next.start, Math.max(0.15, next.length), mode);
    const start = clamped.start;
    const length = clamped.length;
    // Snapshot the pre-drag timeline so the creator can undo a move/trim via
    // the local toast (PERSIST_DURATION_ON_COMMIT + undo for move/trim).
    if (tl) setUndoSnapshot({ ...tl });
    scheduleUndoClear();
    if (kind === "image") {
      void save({
        ...tl,
        imageClips: (tl.imageClips || []).map((c) => (c.id === id ? { ...c, start, length } : c)),
      });
      return;
    }
    if (kind === "video") {
      void save({
        ...tl,
        media_mode: "video",
        videoClips: visualVideoClips.map((c) => {
          if (c.id !== id) return c;
          const delta = start - c.start;
          const trim_start =
            mode === "trim-left" ? Math.max(0, (c.trim_start || 0) + delta) : c.trim_start;
          return { ...c, start, length, trim_start };
        }),
      });
      return;
    }
    if (kind === "videoReference") {
      void save({
        ...tl,
        video_reference_clips: (tl.video_reference_clips || []).map((c) => {
          if (c.id !== id) return c;
          const delta = start - c.start;
          const trim_start =
            mode === "trim-left" ? Math.max(0, (c.trim_start || 0) + delta) : c.trim_start;
          return { ...c, start, length, trim_start };
        }),
      });
      return;
    }
    if (kind === "imageReference") {
      void save({
        ...tl,
        image_reference_clips: (tl.image_reference_clips || []).map((c) => {
          if (c.id !== id) return c;
          const delta = start - c.start;
          const trim_start =
            mode === "trim-left" ? Math.max(0, (c.trim_start || 0) + delta) : c.trim_start;
          return { ...c, start, length, trim_start };
        }),
      });
      return;
    }
    if (kind === "prompt") {
      // SINGLE-STORE: prompt geometry persists to Master batch.promptSegments.
      void persistPrompts((segments) =>
        segments.map((s) => (s.id === id ? { ...s, start, length } : s)),
      );
      return;
    }
    if (kind === "audio" || kind === "sfx") {
      const owned = findBatchOwnedAudioClip(master, kind, id);
      if (owned && masterHasBatchOwnedAudio(master, kind)) {
        const localStart = Math.max(0, Math.min(start - owned.windowStart, Math.max(0.05, owned.windowLength - 0.05)));
        const localLength = Math.max(0.05, Math.min(length, owned.windowLength - localStart));
        const field = kind === "audio" ? "audioClips" : "sfxClips";
        const nextClips = (kind === "audio" ? owned.batch.audioClips : owned.batch.sfxClips).map((c) =>
          c.id === id ? { ...c, start: localStart, length: localLength } : c,
        );
        void api
          .directorTimelinePatchBatch(project.id, scene.id, owned.batch.id, { [field]: nextClips })
          .then(() => onChange())
          .catch((e) => setSaveError(e instanceof Error ? e.message : "Batch audio update failed"));
        return;
      }
      const key = kind === "audio" ? "audioClips" : "sfxClips";
      void save({
        ...tl,
        [key]: (tl[key] || []).map((c) => (c.id === id ? { ...c, start, length } : c)),
      });
      return;
    }
    /* Phase 0: camera geometry edits disabled â€” lane unmounted */
    return;
  };

  const selectSeg = (id: string) => {
    setSelectedSeg(id);
    sel?.setSelection({ kind: "promptSeg", id });
  };
  const selectClip = (kind: "imageClip" | "videoClip" | "videoReferenceClip" | "imageReferenceClip" | "camera" | "audio" | "sfx", id: string) => {
    setSelectedClip(id);
    setSelectedClipKind(kind);
    sel?.setSelection({ kind, id });
  };

  const addImageFromLibrary = async (assetId: string, dropTime = 0) => {
    if (!assetId || !tl) return;
    const ensured = await ensureMasterWindows();
    if (!ensured) return;
    const asset = assetsById.get(assetId) || { id: assetId, kind: "image" as const, tag: "", filename: "" };
    const marksOk = Boolean(retakeMode && retakeRange && Number(retakeRange.length) > 0 && scene);
    if (marksOk && scene && retakeRange) {
      const placementId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
          : Math.random().toString(36).slice(2, 14);
      try {
        const placed = await api.placeVisualImageRange(project.id, scene.id, {
          markIn: retakeRange.start,
          markOut: retakeRange.start + retakeRange.length,
          imageAssetId: assetId,
          placementId,
          label: asset.tag || asset.filename || "Image frame",
        });
        if (placed && placed.ok === false) {
          setSaveError(String(placed.message || placed.error || "Could not place image on Visual."));
          return;
        }
        await onChange();
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : "Add image failed");
      }
      return;
    }
    const plan = planLibraryImageDrop({
      marksOk: false,
      videoClips: [...(tl.imageClips || []), ...(tl.videoClips || [])],
      durationSec: duration,
      dropTime,
      asset,
    });
    if (plan.action === "no-room") {
      setSaveError(plan.notice);
      return;
    }
    if (plan.action === "add-full-span" || plan.action === "add-at-time") {
      const clip = plan.clip;
      const mutator = (current: TimelineBoardView) => {
        const images = current.imageClips || [];
        const nextImages =
          plan.action === "add-full-span" && images.length === 0
            ? [clip]
            : [...images.filter((row) => row.id !== clip.id), clip];
        return { ...current, imageClips: nextImages };
      };
      try {
        if (mutateTimeline || getBoundShellTimelineMutate()) {
          await persistViaMutate(mutator);
        } else {
          await save(mutator(tl));
        }
        setSaveError(null);
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : "Could not add that image to Visual.");
      }
    }
  };

  const addVideoReferenceFromLibrary = async (assetId: string, binding?: ReferenceBindingView) => {
    if (!assetId && !binding) return;
    const resolved = binding || bindings.find((item) => item.asset_id === assetId);
    if (resolved && resolved.media_kind && resolved.media_kind !== "video") {
      setTokenError("Video Reference only accepts * video tokens.");
      return;
    }
    const clip: TimelineClip = {
      id: nid(),
      start: 0,
      length: Math.min(duration, 5),
      label: resolved ? displayToken(resolved.alias || resolved.asset_name, "video") : "Video Reference",
      asset_id: resolved?.asset_id || assetId,
      reference_binding_id: resolved?.id || null,
      trim_start: 0,
    };
    await save({ ...tl, video_reference_clips: [clip] });
    selectClip("videoReferenceClip", clip.id);
  };

  const addImageReferenceFromLibrary = async (assetId: string, binding?: ReferenceBindingView) => {
    if (!assetId && !binding) return;
    const resolved = binding || bindings.find((item) => item.asset_id === assetId);
    if (resolved && resolved.media_kind === "video") {
      setTokenError("Image Reference only accepts # image or @ character/prop tokens.");
      return;
    }
    const imageClips = tl.image_reference_clips || [];
    const clip: TimelineClip = {
      id: nid(),
      start: 0,
      length: Math.min(duration, 5),
      label: resolved
        ? displayToken(resolved.alias || resolved.asset_name, resolved.media_kind || "image")
        : "Image Reference",
      asset_id: resolved?.asset_id || assetId,
      reference_binding_id: resolved?.id || null,
    };
    await save({ ...tl, image_reference_clips: [...imageClips, clip] });
    selectClip("imageReferenceClip", clip.id);
  };

  const assignBindingToClip = async (
    track: "imageReference" | "videoReference",
    clipId: string,
    binding: ReferenceBindingView,
  ) => {
    setTokenError(null);
    let resolved = binding;
    if (binding.id.startsWith("character:")) {
      if (!binding.asset_id) {
        setTokenError("Broken Reference â€” this character needs an approved picture in the Library.");
        return;
      }
      const created = (await api.sceneReferences.attach(project.id, {
        asset_id: binding.asset_id,
        scope_type: "project",
        scope_id: project.id,
        reference_type: "character",
        media_kind: "entity",
        identity_id: binding.identity_id,
        alias: binding.alias,
        usage_modes: ["identity", "appearance"],
        reference_roles: ["character"],
      })) as ReferenceBindingView;
      resolved = { ...binding, ...created, id: String(created.id) };
    }
    if (track === "videoReference") {
      await save({
        ...tl,
        video_reference_clips: (tl.video_reference_clips || []).map((c) =>
          c.id === clipId
            ? {
                ...c,
                asset_id: resolved.asset_id,
                reference_binding_id: resolved.id,
                label: displayToken(resolved.alias || resolved.asset_name, "video"),
              }
            : c,
        ),
      });
      return;
    }
    await save({
      ...tl,
      image_reference_clips: (tl.image_reference_clips || []).map((c) =>
        c.id === clipId
          ? {
              ...c,
              asset_id: resolved.asset_id,
              reference_binding_id: resolved.id,
              label: displayToken(resolved.alias || resolved.asset_name, resolved.media_kind || "image"),
            }
          : c,
      ),
    });
  };
  void assignBindingToClip;

  const onDropAsset = async (e: React.DragEvent, kind: "image" | "audio" | "sfx" | "videoReference" | "imageReference") => {
    e.preventDefault();
    const assetId = e.dataTransfer.getData("application/x-adept-asset");
    if (!assetId) return;
    if (kind === "image") {
      const dropTime = dropTimeFromLane(e, boardDuration, snap, sceneFps);
      await addImageFromLibrary(assetId, dropTime);
    }
    else if (kind === "videoReference") await addVideoReferenceFromLibrary(assetId);
    else if (kind === "imageReference") await addImageReferenceFromLibrary(assetId);
    else if (kind === "audio") {
      const next = { id: nid(), start: 0, length: duration, label: "Audio", asset_id: assetId, volume: 1 };
      const lane = masterHasBatchOwnedAudio(master, "audio") ? displayAudioClips : tl.audioClips;
      if (findSameTrackIntersection(lane, next)) {
        setSaveError("Cannot drop Audio â€” that time is already occupied on the Audio track.");
        return;
      }
      await save({
        ...tl,
        audioClips: [...tl.audioClips, next],
      });
    } else {
      const next = { id: nid(), start: snapTime(1, snap), length: 1, label: "SFX", asset_id: assetId, volume: 1 };
      const lane = masterHasBatchOwnedAudio(master, "sfx") ? displaySfxClips : tl.sfxClips;
      if (findSameTrackIntersection(lane, next)) {
        setSaveError("Cannot drop SFX â€” that time is already occupied on the SFX track.");
        return;
      }
      await save({
        ...tl,
        sfxClips: [...tl.sfxClips, next],
      });
    }
  };

  const switchToVideo = async () => {
    await save({
      ...tl,
      media_mode: "video",
      videoClips: tl.videoClips.length
        ? tl.videoClips
        : [{ id: nid(), start: 0, length: duration, label: "Video", asset_id: null, trim_start: 0 }],
    });
  };

  const switchToImage = async () => {
    await save({ ...tl, media_mode: "image", imageClips: imageClips });
  };

  const addPromptSegment = async () => {
    try {
      const wasEmpty = !((masterLiveRef.current || master)?.batchBlocks || []).length;
      const ensured = await ensureMasterWindows();
      if (!ensured) return;
      const existing = flattenMasterPrompts(ensured);
      // First open of an empty scene: rematerialize leaves one blank planning
      // segment — select it instead of stacking a duplicate overlapping clip.
      if (wasEmpty && existing.length >= 1) {
        const first = existing[0];
        promptWriteSegs.current = existing.map(masterPromptSegmentToView);
        selectSeg(first.id);
        setSaveError(null);
        return;
      }
      const seg: PromptSegment = {
        id: nid(),
        start: snapTime(Math.min(duration - 1, activeSeg ? activeSeg.start + activeSeg.length : 0), snap),
        length: Math.min(2, duration),
        text: "",
        weight: 1,
        region: null,
        reference_binding_ids: [],
        reference_name_bindings: [],
      };
      // SINGLE-STORE: persists to Master batch.promptSegments when Master exists.
      await persistPrompts((segments) => [...segments, seg]);
      selectSeg(seg.id);
      setSaveError(null);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not add a Timed Prompt clip.");
    }
  };

  const duplicateSeg = async () => {
    if (!activeSeg) return;
    const seg: PromptSegment = {
      ...activeSeg,
      id: nid(),
      start: snapTime(Math.min(duration - 0.2, activeSeg.start + activeSeg.length), snap),
    };
    await persistPrompts((segments) => [...segments, seg]);
    selectSeg(seg.id);
  };

  const splitSeg = async () => {
    if (!activeSeg || activeSeg.length < 0.5) return;
    const mid = activeSeg.length / 2;
    const a = { ...activeSeg, length: mid };
    const b: PromptSegment = {
      ...activeSeg,
      id: nid(),
      start: snapTime(activeSeg.start + mid, snap),
      length: mid,
    };
    await persistPrompts((segments) =>
      segments.flatMap((s) => (s.id === activeSeg.id ? [a, b] : [s])),
    );
    selectSeg(b.id);
  };

  const deleteSeg = async () => {
    if (!activeSeg) return;
    let remainingFirstId: string | undefined;
    await persistPrompts((segments) => {
      const next = segments.filter((s) => s.id !== activeSeg.id);
      remainingFirstId = next[0]?.id;
      return next;
    });
    if (remainingFirstId) selectSeg(remainingFirstId);
  };

  const previewMedia =
    showVideoVisual && visualVideoClips[0]?.asset_id
      ? api.assetUrl(visualVideoClips[0].asset_id)
      : imageClips.find((c) => c.asset_id)?.asset_id
        ? api.assetUrl(imageClips.find((c) => c.asset_id)!.asset_id!)
        : scene.output_path
          ? api.mediaUrl(scene.output_path)
          : "";

  const videoClip = visualVideoClips[0];
  const showTracks = viewMode === "tracks" || viewMode === "full";
  const showPromptEditor = !shellMode && (viewMode === "prompt" || viewMode === "full");
  const showStage = !shellMode && viewMode !== "prompt" && !hideEmbeddedStage;

  const seekPlayhead = (clientX: number, laneEl: HTMLElement | null) => {
    if (!laneEl || !tl) return;
    const rect = laneEl.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / Math.max(1, rect.width)));
    const t = snapTime(ratio * boardDuration, snap, snap ? 1 / sceneFps : 0.01);
    onPlayheadChange?.(t);
    void save({ ...tl, playhead: t });
    if (workspaceLayout.playheadFollow && boardScrollRef.current) {
      const scroll = boardScrollRef.current;
      const gutter = shellMode ? 132 : 88;
      const needleLeft = gutter + (t / Math.max(0.1, boardDuration)) * laneEl.offsetWidth;
      const viewLeft = scroll.scrollLeft;
      const viewRight = viewLeft + scroll.clientWidth;
      if (needleLeft < viewLeft + 40 || needleLeft > viewRight - 40) {
        scroll.scrollLeft = Math.max(0, needleLeft - scroll.clientWidth / 2);
      }
    }
  };

  const onPlayheadKey = (e: ReactKeyboardEvent) => {
    if (!tl) return;
    const frame = 1 / sceneFps;
    const large = 0.5;
    let next = playhead;
    if (e.key === "ArrowLeft") next -= e.shiftKey ? large : frame;
    if (e.key === "ArrowRight") next += e.shiftKey ? large : frame;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = duration;
    if (next !== playhead) {
      e.preventDefault();
      const t = snapTime(Math.min(boardDuration, next), snap, frame);
      onPlayheadChange?.(t);
      void save({ ...tl, playhead: t });
    }
  };

  const scheduleUndoClear = () => {
    if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);
    undoTimerRef.current = window.setTimeout(() => {
      setUndoSnapshot(null);
      setRemoveNotice(false);
    }, 8000);
  };

  const removeClip = async (
    kind: "image" | "video" | "videoReference" | "imageReference" | "audio" | "sfx" | "prompt" | "camera",
    id: string,
    persisted: boolean,
  ) => {
    if (!tl) return;
    if (persisted) {
      const ok = window.confirm(
        "Remove this item from the Timeline?\n\nSource assets remain in Project Library.",
      );
      if (!ok) return;
    }
    if ((kind === "audio" || kind === "sfx") && masterHasBatchOwnedAudio(master, kind)) {
      const owned = findBatchOwnedAudioClip(master, kind, id);
      if (owned) {
        const field = kind === "audio" ? "audioClips" : "sfxClips";
        const nextClips = (kind === "audio" ? owned.batch.audioClips : owned.batch.sfxClips).filter(
          (c) => c.id !== id,
        );
        try {
          await api.directorTimelinePatchBatch(project.id, scene.id, owned.batch.id, { [field]: nextClips });
          await onChange();
        } catch (e) {
          setSaveError(e instanceof Error ? e.message : "Remove batch audio failed");
        }
        return;
      }
    }
    const prev = tl;
    const bound = Boolean(mutateTimeline || getBoundShellTimelineMutate());
    const selectedThisPrompt =
      kind === "prompt" &&
      ((sel?.selection?.kind === "promptSeg" && sel.selection.id === id) || selectedSeg === id);
    if (kind === "prompt" && master && scene) {
      // SINGLE-STORE: prompt removal persists to Master batch.promptSegments.
      await persistPrompts((segments) => segments.filter((seg) => seg.id !== id));
      bindInspectingPrompt(null);
      if (selectedThisPrompt) {
        setSelectedSeg(undefined);
        sel?.setSelection({ kind: "scene", id: scene.id });
      }
      setRemoveNotice(true);
      scheduleUndoClear();
      return;
    }
    const next = await persistViaMutate((current) => {
      const updated = { ...current };
      if (kind === "image") updated.imageClips = (current.imageClips || []).filter((c) => c.id !== id);
      if (kind === "video") {
        const detached = removePlacedVisualClip({
          clipId: id,
          displayedClips: displayedVisualVideoClips(
            current.videoClips,
            playableTakes,
            current.media_mode,
            sceneTake,
          ),
        });
        updated.videoClips = detached.video_clips as TimelineClip[];
        updated.media_mode = detached.media_mode;
      }
      if (kind === "videoReference") {
        updated.video_reference_clips = (current.video_reference_clips || []).filter((c) => c.id !== id);
      }
      if (kind === "imageReference") {
        updated.image_reference_clips = (current.image_reference_clips || []).filter((c) => c.id !== id);
      }
      if (kind === "audio") updated.audioClips = (current.audioClips || []).filter((c) => c.id !== id);
      if (kind === "sfx") updated.sfxClips = (current.sfxClips || []).filter((c) => c.id !== id);
      if (kind === "prompt") {
        updated.promptSegments = (current.promptSegments || []).filter((c) => c.id !== id);
      }
      /* Phase 0: allow data-level camera clip removal; lane UI gone */
      if (kind === "camera") updated.cameraClips = (current.cameraClips || []).filter((c) => c.id !== id);
      return updated;
    });
    if (kind === "prompt") {
      bindInspectingPrompt(null);
      if (selectedThisPrompt && scene) {
        setSelectedSeg(undefined);
        sel?.setSelection({ kind: "scene", id: scene.id });
      }
      if (next && !(next.promptSegments || []).some((seg) => seg.id === id)) {
        if (!bound) setUndoSnapshot(prev);
        setRemoveNotice(true);
        scheduleUndoClear();
      } else {
        setRemoveNotice(false);
      }
    } else if (next) {
      if (!bound) setUndoSnapshot(prev);
      setRemoveNotice(true);
      scheduleUndoClear();
    }
  };

  const undoRemove = async () => {
    if (!undoSnapshot) return;
    await save(undoSnapshot);
    setUndoSnapshot(null);
    setRemoveNotice(false);
    if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);
  };

  const addAttachedPrompt = async () => {
    if (!selectedImageClip) return;
    const seg: PromptSegment = {
      id: nid(),
      start: selectedImageClip.start,
      length: selectedImageClip.length,
      text: "",
      weight: 1,
      region: null,
      bound_image_clip_id: selectedImageClip.id,
    };
    await persistViaMutate((current) => ({
      ...current,
      promptSegments: [...(current.promptSegments || []), seg],
    })); /* PHASE23_PROMPT_SAVE_VIA_MUTATE */
    selectSeg(seg.id);
  };

  const onGuidancePriorityChange = (value: TimelineWorkspaceLayout["guidancePriority"]) => {
    saveTimelineWorkspaceLayout({ guidancePriority: value });
    setWorkspaceLayout((prev) => ({ ...prev, guidancePriority: value }));
    if (tl) void save({ ...tl, guidance_priority: value });
  };

  const helpFrom = (id: string) => {
    const h = getTimelineHelp(id);
    return { label: h.title, content: h.body, text: h.title };
  };

  const clipIsPersisted = (clip: { asset_id?: string | null; text?: string }) =>
    Boolean(clip.asset_id || (clip.text && clip.text.trim()));

  const shownLaneMuted = (kind: "audio" | "sfx") => {
    if (laneMuteOverride[kind] !== undefined) return Boolean(laneMuteOverride[kind]);
    const clips = kind === "audio" ? displayAudioClips : displaySfxClips;
    return Boolean(clips[0]?.muted);
  };

  const laneSoloOn = (kind: "audio" | "sfx") => soloLane === kind;

  const setLaneMuted = async (kind: "audio" | "sfx", muted: boolean) => {
    const field = kind === "audio" ? "audioClips" : "sfxClips";
    if (masterHasBatchOwnedAudio(master, kind) && master) {
      for (const batch of master.batchBlocks || []) {
        const clips = batch[field] || [];
        if (!clips.length) continue;
        await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, {
          [field]: clips.map((clip) => ({ ...clip, muted })),
        });
      }
      await onChange();
      return;
    }
    await save({
      ...tl,
      [field]: (tl[field] || []).map((clip) => ({ ...clip, muted })),
    });
  };

  const toggleLaneMute = (kind: "audio" | "sfx") => {
    const nextMuted = !shownLaneMuted(kind);
    setSoloLane((current) => (current === kind ? null : current));
    setLaneMuteOverride((prev) => ({ ...prev, [kind]: nextMuted }));
    void setLaneMuted(kind, nextMuted).catch((error) => {
      setLaneMuteOverride((prev) => {
        const next = { ...prev };
        delete next[kind];
        return next;
      });
      setSaveError(error instanceof Error ? error.message : kind === "audio" ? "Music mute update failed" : "SFX mute update failed");
    });
  };

  const toggleLaneSolo = (kind: "audio" | "sfx") => {
    const other = kind === "audio" ? "sfx" : "audio";
    const turningOff = soloLane === kind;
    setSoloLane(turningOff ? null : kind);
    setLaneMuteOverride((prev) => ({
      ...prev,
      [kind]: false,
      [other]: !turningOff,
    }));
    void (async () => {
      await setLaneMuted(kind, false);
      await setLaneMuted(other, !turningOff);
    })().catch((error) => {
      setLaneMuteOverride((prev) => {
        const next = { ...prev };
        delete next[kind];
        delete next[other];
        return next;
      });
      setSaveError(error instanceof Error ? error.message : "Solo update failed");
    });
  };

  const lanePressedControls = (kind: "audio" | "sfx") => {
    const pressed: Array<"mute" | "solo"> = [];
    if (shownLaneMuted(kind)) pressed.push("mute");
    if (laneSoloOn(kind)) pressed.push("solo");
    return pressed;
  };

  const onLaneControlToggle = (kind: "audio" | "sfx", control: "eye" | "lock" | "mute" | "solo") => {
    if (control === "mute") toggleLaneMute(kind);
    if (control === "solo") toggleLaneSolo(kind);
  };

  return (
    <div className={shellMode ? "timeline-v2__canvas" : "panel director-tracks"}>
      {!shellMode ? (
        <>
          <p className="scene-meta" style={{ margin: "0 0 0.35rem", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: "0.7rem" }}>
            Prompt Timeline
          </p>
          <PanelHeading
            title="Director Â· Prompt Timeline"
            tip="Director creates the shots: timed prompts (including camera direction) and model-ready sequences. Assemble the film in Editor."
          >
            <span className="scene-meta">
              {duration.toFixed(1)}s Â· {saving ? "Savingâ€¦" : tl.media_mode === "image" ? "Image timeline" : "Video timeline"}
            </span>
          </PanelHeading>
        </>
      ) : null}

      {!shellMode && scene && (
        <VisualReferencesPanel
          project={project}
          scene={scene}
          assets={project.assets || []}
          onChange={onChange}
        />
      )}

      {!shellMode && scene && timelineRefsEnabled && selectedImageClip && (
        <TimelineReferencesPanel
          project={project}
          scene={scene}
          clip={selectedImageClip}
          timelineImages={imageClips}
          enabled={timelineRefsEnabled}
          onRefsCount={(itemId, count) =>
            setRefsCounts((prev) => ({ ...prev, [itemId]: count }))
          }
        />
      )}

      {!shellMode && (showTracks || hasOutput) && (
        <div className="director-toolbar send-to-editor-bar" style={{ marginBottom: 8, flexWrap: "wrap" }}>
          <span className="scene-meta">Send to Editor</span>
          <label className="scene-meta">
            <input type="checkbox" checked={includeAudio} onChange={(e) => setIncludeAudio(e.target.checked)} /> Video+audio
          </label>
          <label className="scene-meta">
            <input type="checkbox" checked={!includeAudio} onChange={(e) => setIncludeAudio(!e.target.checked)} /> Video only
          </label>
          <label className="scene-meta">
            <input type="checkbox" checked={proxyFlag} onChange={(e) => setProxyFlag(e.target.checked)} /> Proxy
          </label>
          <button type="button" disabled={sendBusy || !hasOutput} onClick={() => sendToEditor("shot")} title="Current generated shot">
            Current shot
          </button>
          <button type="button" disabled={sendBusy} onClick={() => sendToEditor("sequence")}>
            Full sequence
          </button>
          <button type="button" disabled={sendBusy || !selectedSeg} onClick={() => sendToEditor("selected")}>
            Selected segments
          </button>
          {sendMsg && <span className="pill">{sendMsg}</span>}
          {saveError && (
            <span
              className="pill warn"
              data-testid="timeline-save-error"
              title={saveError}
            >
              Save paused: {saveError}
            </span>
          )}
        </div>
      )}

      {showStage && (
        <div className="director-stage">
          {(() => {
            // Playback authority: Visual/output only â€” never legacy lipsync_output_path.
            const renderSrc = scene.output_path ? api.mediaUrl(scene.output_path) : "";
            const stageSrc = renderSrc || previewMedia;
            const isVideo =
              !!renderSrc ||
              tl.media_mode === "video" ||
              /\.(mp4|webm|mov)(\?|$)/i.test(stageSrc || "");

            if (!stageSrc) {
              return (
                <div className="director-stage-empty">
                  <strong>Prompt Timeline preview</strong>
                  <span>Add images or switch to video to preview here</span>
                </div>
              );
            }

            return (
              <>
                {isVideo ? (
                  <video key={stageSrc} src={stageSrc} controls playsInline muted={false} />
                ) : (
                  <img src={stageSrc} alt="Director preview" />
                )}
                {activeSeg?.region && (
                  <div
                    className="region-box"
                    style={{
                      left: `${activeSeg.region.x * 100}%`,
                      top: `${activeSeg.region.y * 100}%`,
                      width: `${activeSeg.region.w * 100}%`,
                      height: `${activeSeg.region.h * 100}%`,
                    }}
                    title="Segment prompt region"
                  />
                )}
              </>
            );
          })()}
        </div>
      )}

      {showTracks && (
        <>
          {tokenError ? (
            <p className="scene-meta" role="alert" data-testid="timeline-reference-type-error">
              {tokenError}
            </p>
          ) : null}
          {!shellMode ? (
            <>
              <div className="director-toolbar">
                {tl.media_mode === "image" ? (
                  images.length > 0 ? (
                    <select
                      defaultValue=""
                      aria-label="Library Image"
                      onChange={(e) => {
                        addImageFromLibrary(e.target.value);
                        e.target.value = "";
                      }}
                    >
                      <option value="">Library Imageâ€¦</option>
                      {images.map((a) => (
                        <option key={a.id} value={a.id}>
                          @{a.tag || a.filename}
                        </option>
                      ))}
                    </select>
                  ) : null
                ) : videos.length > 0 ? (
                  <select
                    defaultValue=""
                    aria-label="Library Video"
                    onChange={(e) => {
                      const assetId = e.target.value;
                      e.currentTarget.value = "";
                      if (!assetId) return;
                      void save({
                        ...tl,
                        media_mode: "video",
                        videoClips: [
                          {
                            id: nid(),
                            start: 0,
                            length: duration,
                            label: "Video",
                            asset_id: assetId,
                            trim_start: 0,
                          },
                        ],
                      });
                    }}
                  >
                    <option value="">{videoClip?.asset_id ? "Replace from Libraryâ€¦" : "Library Videoâ€¦"}</option>
                    {videos.map((a) => (
                      <option key={a.id} value={a.id}>
                        @{a.tag || a.filename}
                      </option>
                    ))}
                  </select>
                ) : null}

                {selectedImageClip && (
                  <button type="button" onClick={() => void addAttachedPrompt()}>
                    Add Attached Prompt
                  </button>
                )}

                {tl.media_mode === "image" ? (
                  <button type="button" onClick={switchToVideo}>
                    Switch to Video
                  </button>
                ) : (
                  <button type="button" onClick={switchToImage}>
                    Switch to Image Planning
                  </button>
                )}

                <label className="scene-meta director-duration">
                  Duration
                  <input
                    style={{ width: 64 }}
                    type="number"
                    min={0.1}
                    step={0.5}
                    data-testid="timeline-scene-duration"
                    value={duration}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      if (!Number.isFinite(next) || next <= 0) return;
                      void persistCanonicalSceneDuration({
                        projectId: project.id,
                        sceneId: scene.id,
                        durationSec: next,
                        generatorId: editorGeneratorId || master?.sceneGeneratorId || scene.engine,
                        mutateTimeline: async (mutator, opts) => {
                          await persistViaMutate(mutator, opts);
                        },
                      }).then(() => onChange());
                    }}
                  />
                  s
                </label>
              </div>

              <div className="director-zoom">
                <span className="scene-meta">Track zoom</span>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setZoom(stepTimelineZoom(zoom, -1))}
                >
                  Ã¢Ë†â€™
                </button>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.001}
                  value={zoomToSlider(zoom)}
                  onChange={(e) => setZoom(sliderToZoom(Number(e.target.value)))}
                  aria-label="Zoom timeline tracks"
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setZoom(stepTimelineZoom(zoom, 1))}
                >
                  +
                </button>
                <span className="scene-meta">{zoom.toFixed(2)}Ã—</span>
                <label
                  className="scene-meta"
                  style={{ display: "inline-flex", gap: 6, alignItems: "center", marginLeft: 8 }}
                >
                  <input
                    type="checkbox"
                    checked={snap}
                    onChange={(e) => setSnap(e.target.checked)}
                    style={{ width: "auto" }}
                  />
                  Snap
                </label>
                <ActionWithHelp help={helpFrom("timeline_settings")}>
                  <button
                    type="button"
                    className="ghost"
                    data-testid="timeline-settings-gear"
                    aria-label="Timeline Settings"
                    title="Timeline Settings"
                    aria-expanded={settingsOpen}
                    onClick={() => setSettingsOpen((v) => !v)}
                  >
                    Ã¢Å¡â„¢
                  </button>
                </ActionWithHelp>
                <TimelineSettingsDrawer
                  open={settingsOpen}
                  onClose={() => setSettingsOpen(false)}
                  onGuidancePriorityChange={onGuidancePriorityChange}
                  onLayoutChange={(layout) => {
                    setWorkspaceLayout(layout);
                    if (layout.snapEnabled !== snap) setSnap(layout.snapEnabled);
                  }}
                />
                <span
                  className="scene-meta"
                  data-testid="timeline-playhead-time"
                  data-playhead={String(playhead)}
                >
                  {formatTimelineTime(playhead, workspaceLayout.displayMode, sceneFps)} Â· playhead
                </span>
              </div>
            </>
          ) : null}

          {(undoSnapshot || removeNotice) && (
            <div className="timeline-undo-toast" role="status" data-testid="timeline-undo-toast">
              <span>Removed from Timeline</span>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  if (undoSnapshot) {
                    void undoRemove();
                    return;
                  }
                  setRemoveNotice(false);
                  runTimelineCommand("undo");
                }}
              >
                Undo
              </button>
            </div>
          )}

          <div
            className={shellMode ? "timeline-v2__canvas-scroll" : "track-board-scroll"}
            ref={boardScrollRef}
            data-testid="timeline-track-scroll"
            onScroll={(e) =>
              setBoardScroll({ left: e.currentTarget.scrollLeft, width: e.currentTarget.clientWidth })
            }
          >
            <div
              className={shellMode ? "timeline-v2__board" : `track-board track-board--${workspaceLayout.trackDensity}`}
              style={{
                width: trackLabelWidthPx + boardWidth,
                ["--timeline-lane-width" as string]: `${boardWidth}px`,
                position: "relative",
              }}
              tabIndex={0}
              onKeyDown={onPlayheadKey}
              data-testid="timeline-track-board"
              data-retake-mode={retakeMode ? "true" : "false"}
              onWheel={(e) => {
                if (!(e.ctrlKey || e.metaKey)) return;
                e.preventDefault();
                setZoom?.(stepTimelineZoom(zoom, e.deltaY > 0 ? -1 : 1));
              }}
              data-zoom={String(zoom)}
              data-board-width={String(boardWidth)}
              data-board-duration={String(boardDuration)}
              data-sequence-sec={String(sequenceSec)}
              data-scale-sec={String(boardDuration)}
            >
              <div className={shellMode ? "timeline-v2__ruler" : "track-ruler"} data-testid="timeline-ruler">
                <div className={shellMode ? "timeline-v2__ruler-gutter" : "track-ruler__gutter"} aria-hidden />
                <div
                  className={shellMode ? "timeline-v2__ruler-lane" : "track-ruler__lane"}
                  onClick={(e) => seekPlayhead(e.clientX, e.currentTarget)}
                  onPointerDown={(e) => {
                    const lane = e.currentTarget;
                    const move = (ev: PointerEvent) => seekPlayhead(ev.clientX, lane);
                    const up = () => {
                      window.removeEventListener("pointermove", move);
                      window.removeEventListener("pointerup", up);
                    };
                    window.addEventListener("pointermove", move);
                    window.addEventListener("pointerup", up);
                  }}
                  onMouseMove={(e) => {
                    const lane = e.currentTarget;
                    const rect = lane.getBoundingClientRect();
                    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / Math.max(1, rect.width)));
                    setRulerHoverSec(ratio * boardDuration);
                  }}
                  onMouseLeave={() => setRulerHoverSec(null)}
                >
                  {rulerTicks.map((tickSec) => (
                    <span
                      key={tickSec}
                      className={
                        shellMode
                          ? tickSec === 0
                            ? "timeline-v2__ruler-tick timeline-v2__ruler-tick--origin"
                            : "timeline-v2__ruler-tick"
                          : tickSec === 0
                            ? "track-ruler__tick track-ruler__tick--origin"
                            : "track-ruler__tick"
                      }
                      style={{ left: `${(tickSec / Math.max(0.1, boardDuration)) * 100}%` }}
                    >
                      {formatTimelineTime(tickSec, workspaceLayout.displayMode, sceneFps)}
                    </span>
                  ))}
                  {rulerHoverSec != null && (
                    <span
                      className={shellMode ? "timeline-v2__ruler-hover" : "track-ruler__hover"}
                      style={{ left: `${(rulerHoverSec / Math.max(0.1, boardDuration)) * 100}%` }}
                    >
                      {formatTimelineTime(rulerHoverSec, workspaceLayout.displayMode, sceneFps)}
                    </span>
                  )}
                </div>
              </div>
              <div className={shellMode ? "timeline-v2__playhead-rail" : "track-playhead-rail"} aria-hidden={false}>
                <div className={shellMode ? "timeline-v2__playhead-gutter" : "track-playhead-rail__gutter"} aria-hidden />
                <div className={shellMode ? "timeline-v2__playhead-lane" : "track-playhead-rail__lane"}>
                  <div
                    className={shellMode ? "timeline-v2__sequence-end" : "track-sequence-end"}
                    data-testid="timeline-sequence-end"
                    style={{ left: `${(sequenceSec / Math.max(0.1, boardDuration)) * 100}%` }}
                    title={`Scene ends at ${formatTimelineTime(sequenceSec, workspaceLayout.displayMode, sceneFps)}`}
                  />
                  <div
                    ref={playheadRef}
                    className="track-playhead"
                    style={{ left: `${(playhead / Math.max(0.1, boardDuration)) * 100}%` }}
                    id="timeline-playhead"
                    data-testid="timeline-playhead"
                    data-playhead={String(playhead)}
                  >
                    <span className="track-playhead__head" aria-hidden />
                  </div>
                </div>
              </div>


                            {!showVideoVisual ? (
                <div
                  className={trackRowClass(shellMode)}
                  data-testid="timeline-visual-drop"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDropAsset(e, "image")}
                >
                  <TrackHeader label="VISUAL" labelKey="tracks.visual" shellMode={shellMode} />
                  <div className={trackContentClass(shellMode)}>
                    {imageClips.length === 0 && workspaceLayout.showEmptyHelp && (
                      <div className="track-empty">Add an image clip or drop an image here.</div>
                    )}
                    {imageClips.map((clip) => {
                      const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                      return (
                        <TrackClipInteractive
                          key={clip.id}
                          clipId={clip.id}
                          start={clip.start}
                          length={clip.length}
                          boardDuration={boardDuration}
                          dragMaxSec={sequenceSec}
                          boardWidthPx={boardWidth}
                          snapEnabled={snap}
                          snapTargets={snapTargets}
                          selected={selectedClip === clip.id}
                          className="media"
                          domId={`timeline-track-item-imageClip-${clip.id}`}
                          testId={`track-clip-image-${clip.id}`}
                          onSelect={() => selectClip("imageClip", clip.id)}
                          onCommit={(next, mode) => commitClipGeometry("image", clip.id, next, mode)}
                        >
                          <button
                            type="button"
                            className="track-clip__remove"
                            aria-label="Remove from Timeline"
                            title="Remove from Timeline"
                            onClick={(e) => {
                              e.stopPropagation();
                              void removeClip("image", clip.id, Boolean(clip.asset_id));
                            }}
                          >
                            Ã—
                          </button>
                          {workspaceLayout.showThumbnails && asset ? (
                            <img className="track-clip__thumb" src={api.assetUrl(asset.id)} alt="" />
                          ) : null}
                          <strong>{clip.display_tag || clip.label || "Image"}</strong>
                          <span>
                            {asset ? `@${asset.tag || asset.filename}` : "empty"} Â· {clip.start.toFixed(1)}â€“
                            {(clip.start + clip.length).toFixed(1)}s
                          </span>
                          {timelineRefsEnabled && (
                            <span className="scene-meta">
                              Primary Â· Supporting refs: {refsCounts[clip.id] ?? 0}
                            </span>
                          )}
                          {!shellMode ? (
                            <select
                              value={clip.asset_id || ""}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) =>
                                save({
                                  ...tl,
                                  imageClips: imageClips.map((c) =>
                                    c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                                  ),
                                })
                              }
                            >
                              <option value="">Assetâ€¦</option>
                              {images.map((a) => (
                                <option key={a.id} value={a.id}>
                                  @{a.tag || a.filename}
                                </option>
                              ))}
                            </select>
                          ) : null}
                        </TrackClipInteractive>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div
                  className={trackRowClass(shellMode)}
                  data-testid="timeline-visual-drop"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDropAsset(e, "image")}
                >
                  <TrackHeader label="VISUAL" labelKey="tracks.visual" shellMode={shellMode} controls={["eye", "lock"]} />
                  <div className={trackContentClass(shellMode)}>
                    {visualVideoClips.length === 0 && workspaceLayout.showEmptyHelp && (
                      <div className="track-empty">Add a video clip or switch back to image planning.</div>
                    )}
                    {visualVideoClips.map((clip) => {
                      const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                      return (
                        <TrackClipInteractive
                          key={clip.id}
                          clipId={clip.id}
                          start={clip.start}
                          length={clip.length}
                          boardDuration={boardDuration}
                          dragMaxSec={sequenceSec}
                          boardWidthPx={boardWidth}
                          snapEnabled={snap}
                          snapTargets={snapTargets}
                          selected={selectedClip === clip.id}
                          className="media video"
                          domId={`timeline-track-item-videoClip-${clip.id}`}
                          testId={`track-clip-video-${clip.id}`}
                          onSelect={() => selectClip("videoClip", clip.id)}
                          onCommit={(next, mode) => commitClipGeometry("video", clip.id, next, mode)}
                        >
                          <button
                            type="button"
                            className="track-clip__remove"
                            aria-label="Remove from Timeline"
                            title="Remove from Timeline"
                            onClick={(e) => {
                              e.stopPropagation();
                              void removeClip("video", clip.id, Boolean(clip.asset_id));
                            }}
                          >
                            Ã—
                          </button>
                          {workspaceLayout.showThumbnails && asset ? (
                            <video
                              className="track-clip__thumb track-clip__filmstrip"
                              src={api.assetUrl(asset.id)}
                              muted
                              playsInline
                              preload="metadata"
                            />
                          ) : null}
                          <strong>Video</strong>
                          <span>
                            {asset
                              ? workspaceLayout.showFilenames
                                ? `@${asset.tag || asset.filename}`
                                : "Video clip"
                              : "Upload a video"}
                          </span>
                          {!shellMode && videos.length > 0 && (
                            <select
                              value={clip.asset_id || ""}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) =>
                                save({
                                  ...tl,
                                  media_mode: "video",
                                  videoClips: visualVideoClips.map((c) =>
                                    c.id === clip.id
                                      ? { ...c, asset_id: e.target.value || null }
                                      : c,
                                  ),
                                })
                              }
                            >
                              <option value="">Libraryâ€¦</option>
                              {videos.map((a) => (
                                <option key={a.id} value={a.id}>
                                  @{a.tag || a.filename}
                                </option>
                              ))}
                            </select>
                          )}
                        </TrackClipInteractive>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Image/Video Reference lanes retired: bindings live on Prompt clips. */}

              <div
                className={trackRowClass(shellMode, "timeline-v2__track-row--prompt")}
                data-testid="timeline-timed-prompt-track"
              >
                <TrackHeader
                  label="TIMED PROMPT"
                  labelKey="tracks.timedPrompt"
                  testId="timeline-v2-label-timed-prompt"
                  shellMode={shellMode}
                  onAction={addPromptSegment}
                  actionLabel="+ Prompt"
                />
                <div className={trackContentClass(shellMode)} data-testid="timeline-timed-prompt-lane">
                  {masterPrompts.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">{t("emptyTimedPrompt")}</div>
                  )}
                  {masterPrompts.map((seg) => (
                    <TrackClipInteractive
                      key={seg.id}
                      clipId={seg.id}
                      start={seg.start}
                      length={seg.length}
                      boardDuration={boardDuration}
                      dragMaxSec={sequenceSec}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapTargets={snapTargets}
                      selected={selectedSeg === seg.id}
                      className="prompt"
                      domId={`timeline-track-item-promptSeg-${seg.id}`}
                      testId={`track-clip-prompt-${seg.id}`}
                      ariaLabel={`Timed Prompt ${seg.start.toFixed(1)}s`}
                      onSelect={() => selectSeg(seg.id)}
                      onCommit={(next, mode) => commitClipGeometry("prompt", seg.id, next, mode)}
                      onActivate={() => {
                        selectSeg(seg.id);
                        promptDismissGuardUntil.current = timedPromptDismissGuardUntil();
                        openTimedPromptAfterGesture(setEditingPromptId, seg.id);
                      }}
                    >
                      <button
                        type="button"
                        className="track-clip__remove"
                        aria-label={t("removeInstruction")}
                        title={t("removeInstruction")}
                        onClick={(e) => {
                          e.stopPropagation();
                          void removeClip("prompt", seg.id, clipIsPersisted(seg));
                        }}
                      >
                        Ã—
                      </button>
                      {seg.movement_segment_ref?.alias ? (
                        <span className="timeline-v2__movement-chip" data-testid={`prompt-movement-${seg.id}`}>
                          ~{seg.movement_segment_ref.alias}
                        </span>
                      ) : null}
                      <span className="timeline-v2__clip-tokens" data-testid={`prompt-token-summary-${seg.id}`}>
                        {tokenSummary(seg.reference_binding_ids, bindings) ||
                          (seg.region ? t("timedPromptRegion") : null) ||
                          (seg.text ? normalizePromptTags(seg.text.slice(0, 36), bindings) : t("emptyPromptClip"))}
                      </span>
                      {tokenSummary(seg.reference_binding_ids, bindings) && seg.text ? (
                        <span className="timeline-v2__clip-instruction">{normalizePromptTags(seg.text.slice(0, 40), bindings)}</span>
                      ) : null}
                    </TrackClipInteractive>
                  ))}
                </div>
              </div>

              {/* Phase 0: CAMERA lane unmounted â€” Timed Prompt is sole camera authority.
                  Lane order: VISUAL -> TIMED PROMPT -> AUDIO -> SFX. (Batch track removed P3.)
                  Legacy cameraClips retained in schema/provenance; not mounted. */}

              <div
                className={trackRowClass(shellMode, "timeline-v2__track-row--audio")}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropAsset(e, "audio")}
              >
                <TrackHeader
                  label="AUDIO"
                  labelKey="tracks.audio"
                  shellMode={shellMode}
                  controls={["mute", "solo"]}
                  pressedControls={lanePressedControls("audio")}
                  onControlToggle={(control) => onLaneControlToggle("audio", control)}
                  headerExtra={
                    <TrackVolumeControl
                      trackLabel={t("musicTrackName", { defaultValue: "Music" })}
                      volumePercent={Math.round((displayAudioClips[0]?.volume ?? 1) * 100)}
                      muted={shownLaneMuted("audio")}
                      disabled={displayAudioClips.length === 0}
                      onChange={(pct) => {
                        setLaneMuteOverride((prev) => ({ ...prev, audio: false }));
                        if (masterHasBatchOwnedAudio(master, "audio") && master) {
                          void (async () => {
                            for (const batch of master.batchBlocks || []) {
                              if (!(batch.audioClips || []).length) continue;
                              const next = (batch.audioClips || []).map((c) => ({
                                ...c,
                                volume: pct / 100,
                                muted: false,
                              }));
                              await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, {
                                audioClips: next,
                              });
                            }
                            await onChange();
                          })().catch((e) =>
                            setSaveError(e instanceof Error ? e.message : "Music volume update failed"),
                          );
                          return;
                        }
                        save({
                          ...tl,
                          audioClips: tl.audioClips.map((c) => ({ ...c, volume: pct / 100, muted: false })),
                        });
                      }}
                      onToggleMute={() => toggleLaneMute("audio")}
                    />
                  }
                />
                <div
                  className={trackContentClass(shellMode)}
                  data-testid="timeline-audio-lane"
                  onDoubleClick={(event) => {
                    if (!onOpenAudioClip) return;
                    if ((event.target as HTMLElement).closest(".track-clip, button, input, select")) return;
                    const rect = event.currentTarget.getBoundingClientRect();
                    onOpenAudioClip({
                      kind: "audio",
                      clipId: null,
                      start: laneTimeFromPointer(event.clientX, { left: rect.left, width: rect.width }, boardDuration),
                    });
                  }}
                >
                  {displayAudioClips.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">Add ambience, score, or dialogue stems for this scene.</div>
                  )}
                  {displayAudioClips.map((clip) => (
                    <TrackClipInteractive
                      key={clip.id}
                      clipId={clip.id}
                      start={clip.start}
                      length={clip.length}
                      boardDuration={boardDuration}
                      dragMaxSec={sequenceSec}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapTargets={snapTargets}
                      selected={selectedClip === clip.id}
                      className="audio"
                      domId={`timeline-track-item-audio-${clip.id}`}
                      testId={`track-clip-audio-${clip.id}`}
                      onSelect={() => selectClip("audio", clip.id)}
                      onCommit={(next, mode) => commitClipGeometry("audio", clip.id, next, mode)}
                      onActivate={() => {
                        selectClip("audio", clip.id);
                        onOpenAudioClip?.({ kind: "audio", clipId: clip.id, start: clip.start });
                      }}
                    >
                      <button
                        type="button"
                        className="track-clip__remove"
                        aria-label="Remove from Timeline"
                        title="Remove from Timeline"
                        onClick={(e) => {
                          e.stopPropagation();
                          void removeClip("audio", clip.id, Boolean(clip.asset_id));
                        }}
                      >
                        Ã—
                      </button>
                      {(() => {
                        const asset = audios.find((a) => a.id === clip.asset_id);
                        const face = mediaClipFaceLabel("audio", clip, asset);
                        return <strong title={face.fullTitle || undefined}>{face.face}</strong>;
                      })()}
                      {!shellMode ? (
                        <select
                          value={clip.asset_id || ""}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const assetId = e.target.value || null;
                            const owned = findBatchOwnedAudioClip(master, "audio", clip.id);
                            if (owned && masterHasBatchOwnedAudio(master, "audio")) {
                              const next = (owned.batch.audioClips || []).map((c) =>
                                c.id === clip.id ? { ...c, assetId } : c,
                              );
                              void api
                                .directorTimelinePatchBatch(project.id, scene.id, owned.batch.id, {
                                  audioClips: next,
                                })
                                .then(() => onChange())
                                .catch((err) =>
                                  setSaveError(err instanceof Error ? err.message : "Music asset update failed"),
                                );
                              return;
                            }
                            save({
                              ...tl,
                              audioClips: tl.audioClips.map((c) =>
                                c.id === clip.id ? { ...c, asset_id: assetId } : c
                              ),
                            });
                          }}
                        >
                          <option value="">Selectâ€¦</option>
                          {audios.map((a) => (
                            <option key={a.id} value={a.id}>
                              @{a.tag || a.filename}
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </TrackClipInteractive>
                  ))}
                </div>
              </div>

              <div
                className={trackRowClass(shellMode, "timeline-v2__track-row--audio")}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropAsset(e, "sfx")}
              >
                <TrackHeader
                  label="SFX"
                  labelKey="tracks.sfx"
                  shellMode={shellMode}
                  controls={["mute", "solo"]}
                  pressedControls={lanePressedControls("sfx")}
                  onControlToggle={(control) => onLaneControlToggle("sfx", control)}
                  headerExtra={
                    <TrackVolumeControl
                      trackLabel={t("sfxTrackName", { defaultValue: "SFX" })}
                      volumePercent={Math.round((displaySfxClips[0]?.volume ?? 1) * 100)}
                      muted={shownLaneMuted("sfx")}
                      disabled={displaySfxClips.length === 0}
                      onChange={(pct) => {
                        setLaneMuteOverride((prev) => ({ ...prev, sfx: false }));
                        if (masterHasBatchOwnedAudio(master, "sfx") && master) {
                          void (async () => {
                            for (const batch of master.batchBlocks || []) {
                              if (!(batch.sfxClips || []).length) continue;
                              const next = (batch.sfxClips || []).map((c) => ({
                                ...c,
                                volume: pct / 100,
                                muted: false,
                              }));
                              await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, {
                                sfxClips: next,
                              });
                            }
                            await onChange();
                          })().catch((e) =>
                            setSaveError(e instanceof Error ? e.message : "SFX volume update failed"),
                          );
                          return;
                        }
                        save({
                          ...tl,
                          sfxClips: tl.sfxClips.map((c) => ({ ...c, volume: pct / 100, muted: false })),
                        });
                      }}
                      onToggleMute={() => toggleLaneMute("sfx")}
                    />
                  }
                />
                <div
                  className={trackContentClass(shellMode)}
                  data-testid="timeline-sfx-lane"
                  onDoubleClick={(event) => {
                    if (!onOpenAudioClip) return;
                    if ((event.target as HTMLElement).closest(".track-clip, button, input, select")) return;
                    const rect = event.currentTarget.getBoundingClientRect();
                    onOpenAudioClip({
                      kind: "sfx",
                      clipId: null,
                      start: laneTimeFromPointer(event.clientX, { left: rect.left, width: rect.width }, boardDuration),
                    });
                  }}
                >
                  {displaySfxClips.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">Drop quick impact or spot effects here.</div>
                  )}
                  {displaySfxClips.map((clip) => (
                    <TrackClipInteractive
                      key={clip.id}
                      clipId={clip.id}
                      start={clip.start}
                      length={clip.length}
                      boardDuration={boardDuration}
                      dragMaxSec={sequenceSec}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapTargets={snapTargets}
                      selected={selectedClip === clip.id}
                      className="sfx"
                      domId={`timeline-track-item-sfx-${clip.id}`}
                      testId={`track-clip-sfx-${clip.id}`}
                      onSelect={() => selectClip("sfx", clip.id)}
                      onCommit={(next, mode) => commitClipGeometry("sfx", clip.id, next, mode)}
                      onActivate={() => {
                        selectClip("sfx", clip.id);
                        onOpenAudioClip?.({ kind: "sfx", clipId: clip.id, start: clip.start });
                      }}
                    >
                      <button
                        type="button"
                        className="track-clip__remove"
                        aria-label="Remove from Timeline"
                        title="Remove from Timeline"
                        onClick={(e) => {
                          e.stopPropagation();
                          void removeClip("sfx", clip.id, Boolean(clip.asset_id));
                        }}
                      >
                        Ã—
                      </button>
                      {(() => {
                        const asset = audios.find((a) => a.id === clip.asset_id);
                        const face = mediaClipFaceLabel("sfx", clip, asset);
                        return <strong title={face.fullTitle || undefined}>{face.face}</strong>;
                      })()}
                      {!shellMode ? (
                        <select
                          value={clip.asset_id || ""}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const assetId = e.target.value || null;
                            const owned = findBatchOwnedAudioClip(master, "sfx", clip.id);
                            if (owned && masterHasBatchOwnedAudio(master, "sfx")) {
                              const next = (owned.batch.sfxClips || []).map((c) =>
                                c.id === clip.id ? { ...c, assetId } : c,
                              );
                              void api
                                .directorTimelinePatchBatch(project.id, scene.id, owned.batch.id, {
                                  sfxClips: next,
                                })
                                .then(() => onChange())
                                .catch((err) =>
                                  setSaveError(err instanceof Error ? err.message : "SFX asset update failed"),
                                );
                              return;
                            }
                            save({
                              ...tl,
                              sfxClips: tl.sfxClips.map((c) =>
                                c.id === clip.id ? { ...c, asset_id: assetId } : c
                              ),
                            });
                          }}
                        >
                          <option value="">Selectâ€¦</option>
                          {audios.map((a) => (
                            <option key={a.id} value={a.id}>
                              @{a.tag || a.filename}
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </TrackClipInteractive>
                  ))}
                </div>
              </div>


              {retakeMode && retakeRange ? (
                <div
                  className="timeline-v2__retake-layer"
                  data-testid="timeline-retake-range-layer"
                  aria-hidden
                  style={{ left: trackLabelWidthPx, width: boardWidth, pointerEvents: "none" }}
                >
                  <div
                    className="timeline-v2__retake-mark"
                    data-testid="timeline-retake-mark"
                    style={pct(retakeRange.start, retakeRange.length, boardDuration)}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </>
      )}

      {showPromptEditor && tl.media_mode === "video" && videoClip && (
        <div className="segment-editor">
          <div className="section-label">Video segment for prompt edit</div>
          <div className="row-actions">
            <label className="scene-meta">
              In-point (s)
              <input
                style={{ width: 72 }}
                type="number"
                min={0}
                max={duration}
                step={0.1}
                value={videoClip.trim_start || 0}
                onChange={(e) =>
                  save({
                    ...tl,
                    videoClips: tl.videoClips.map((c) =>
                      c.id === videoClip.id ? { ...c, trim_start: Number(e.target.value) || 0 } : c
                    ),
                  })
                }
              />
            </label>
            <button type="button" onClick={addPromptSegment}>
              New prompt segment
            </button>
          </div>
        </div>
      )}

      {showPromptEditor && activeSeg && (
        <div className="segment-editor">
          <div className="section-label">Selected prompt segment</div>
          <div className="row-actions" style={{ marginBottom: 8 }}>
            <label className="scene-meta">
              Start
              <input
                style={{ width: 72 }}
                type="number"
                min={0}
                max={duration}
                step={0.1}
                value={activeSeg.start}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    promptSegments: tl.promptSegments.map((s) =>
                      s.id === activeSeg.id
                        ? { ...s, start: snapTime(Number(e.target.value) || 0, snap) }
                        : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
            <label className="scene-meta">
              Length
              <input
                style={{ width: 72 }}
                type="number"
                min={0.2}
                max={duration}
                step={0.1}
                value={activeSeg.length}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    promptSegments: tl.promptSegments.map((s) =>
                      s.id === activeSeg.id ? { ...s, length: Number(e.target.value) || 1 } : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
            <label className="scene-meta">
              Weight
              <input
                style={{ width: 72 }}
                type="number"
                min={0.1}
                max={2}
                step={0.1}
                value={activeSeg.weight ?? 1}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    promptSegments: tl.promptSegments.map((s) =>
                      s.id === activeSeg.id ? { ...s, weight: Number(e.target.value) || 1 } : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
          </div>
          <div className="field">
            <label>Segment prompt</label>
            <textarea
              value={activeSeg.text}
              onChange={(e) =>
                setTl({
                  ...tl,
                  promptSegments: tl.promptSegments.map((s) =>
                    s.id === activeSeg.id ? { ...s, text: e.target.value } : s
                  ),
                })
              }
              onBlur={async () => {
                await save(tl);
                try {
                  const v = await api.validateMotionTags(activeSeg.text || "");
                  setTagWarnings(v.warnings || []);
                } catch {
                  setTagWarnings([]);
                }
              }}
            />
          </div>
          <div className="field">
            <label>Audio Intent</label>
            <p className="muted" style={{ margin: "0 0 0.35rem" }}>
              Foley / ambience / music cues for Editor &amp; Audio Studio (labels only â€” no synthesis yet).
            </p>
            <div className="row-actions" style={{ flexWrap: "wrap", marginBottom: 6 }}>
              {(activeSeg.audio_intent || []).map((intent) => (
                <button
                  key={intent}
                  type="button"
                  className="pill"
                  title="Remove"
                  onClick={() =>
                    save({
                      ...tl,
                      promptSegments: tl.promptSegments.map((s) =>
                        s.id === activeSeg.id
                          ? { ...s, audio_intent: (s.audio_intent || []).filter((x) => x !== intent) }
                          : s
                      ),
                    })
                  }
                >
                  {intent} Ã—
                </button>
              ))}
            </div>
            <div className="row-actions">
              <input
                style={{ flex: 1, minWidth: 160 }}
                placeholder="e.g. hydraulic door, corridor ambience"
                value={audioIntentDraft}
                onChange={(e) => setAudioIntentDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const v = audioIntentDraft.trim();
                    if (!v) return;
                    const next = Array.from(new Set([...(activeSeg.audio_intent || []), v]));
                    setAudioIntentDraft("");
                    save({
                      ...tl,
                      promptSegments: tl.promptSegments.map((s) =>
                        s.id === activeSeg.id ? { ...s, audio_intent: next } : s
                      ),
                    });
                  }
                }}
              />
              <button
                type="button"
                onClick={() => {
                  const v = audioIntentDraft.trim();
                  if (!v) return;
                  const next = Array.from(new Set([...(activeSeg.audio_intent || []), v]));
                  setAudioIntentDraft("");
                  save({
                    ...tl,
                    promptSegments: tl.promptSegments.map((s) =>
                      s.id === activeSeg.id ? { ...s, audio_intent: next } : s
                    ),
                  });
                }}
              >
                Add intent
              </button>
            </div>
          </div>
          {tagWarnings.length > 0 && (
            <div className="pill warn" style={{ marginBottom: 8 }}>
              {tagWarnings.join(" Â· ")}
            </div>
          )}
          <div className="row-actions">
            <button
              onClick={() =>
                save({
                  ...tl,
                  promptSegments: tl.promptSegments.map((s) =>
                    s.id === activeSeg.id
                      ? { ...s, region: s.region || { x: 0.25, y: 0.25, w: 0.5, h: 0.5 } }
                      : s
                  ),
                })
              }
            >
              {activeSeg.region ? "Region on" : "Add region highlight"}
            </button>
            {activeSeg.region && (
              <button
                onClick={() =>
                  save({
                    ...tl,
                    promptSegments: tl.promptSegments.map((s) =>
                      s.id === activeSeg.id ? { ...s, region: null } : s
                    ),
                  })
                }
              >
                Clear region
              </button>
            )}
            <button type="button" onClick={duplicateSeg}>
              Duplicate
            </button>
            <button type="button" onClick={splitSeg}>
              Split
            </button>
            <button type="button" className="danger" onClick={deleteSeg}>
              Delete
            </button>
          </div>
        </div>
      )}

      {editingPrompt ? (
        <TimedPromptEditorModal
          segment={editingPrompt}
          bindings={bindings}
          projectId={project.id}
          generatorId={editorGeneratorId}
          sourceSceneId={scene?.id}
          suggestedName={scene?.name}
          sceneDurationSec={liveSceneClockSec(scene, tl)}
          sceneLabel={scene.name || "Scene 1"}
          onExtendScene={async (neededSceneSec) => {
            await persistCanonicalSceneDuration({
              projectId: project.id,
              sceneId: scene.id,
              durationSec: neededSceneSec,
              generatorId: editorGeneratorId || master?.sceneGeneratorId || scene.engine,
              mutateTimeline: async (mutator, opts) => {
                await persistViaMutate(mutator, opts);
              },
            });
            onChange();
          }}
          onCancel={closeTimedPromptModal}
          onPersist={persistTimedPromptPatch}
          onCommit={commitTimedPromptPatch}
        />
      ) : null}
      {/* Phase 0: CameraSettingsModal unmounted */}
    </div>
  );
}



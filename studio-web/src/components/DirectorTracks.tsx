import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { LipSyncTracksPanel } from "./LipSyncTracks";
import { PanelHeading, HelpTip } from "./HelpTip";
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
import { TimelineTrackLabel } from "./timeline-master/TimelineTrackLabel";
import type { SceneTimelineMaster } from "../timelineMaster/contracts";
import { formatBatchStatus } from "../timelineMaster/contracts";
import { ReferenceTokenAutocomplete } from "./sceneReferences/ReferenceTokenAutocomplete";
// TS6133 unblock: JSX usage removed by in-progress refactor; keep symbol for re-wire.
void ReferenceTokenAutocomplete;
import {
  assetDurationSec,
  displayToken,
  tokenSummary,
  type ReferenceBindingView,
} from "../sceneReferences/referenceTokens";

function continuityChipLabel(status: string | undefined, stale?: boolean) {
  if (stale) return "Needs update";
  if (status === "Failed") return "Match failed";
  if (status === "Waiting" || status === "Analyzing") return "Matching…";
  if (status === "Ready" || status === "Applied") return "Matched";
  return null;
}

export type RegionBox = { x: number; y: number; w: number; h: number };
export type TimelineClip = {
  id: string;
  asset_id?: string | null;
  start: number;
  length: number;
  trim_start?: number;
  label?: string;
  role?: "start" | "middle" | "end" | "guide";
  /** Stable timeline tag e.g. @Image1 — never renumbered on delete/move. */
  display_tag?: string | null;
  volume?: number;
  fade_in?: number;
  fade_out?: number;
  reference_binding_id?: string | null;
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
  user_direction?: string | null;
  production_prompt?: string | null;
  dialogue?: string | null;
  movement_segment_ref?: { id: string; segmentNumber: number; alias: string } | null;
  movement_segment_revision?: number | null;
};
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
};
export type LipSyncClip = {
  id: string;
  start: number;
  length: number;
  label?: string;
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
export type DirectorTimeline = {
  media_mode: "image" | "video";
  duration_sec: number;
  image_clips: TimelineClip[];
  video_clips: TimelineClip[];
  /** Motion/performance reference — independent of the output Video track. One clip this milestone. */
  video_reference_clips?: TimelineClip[];
  /** Image / entity reference — distinct from VISUAL playback images. */
  image_reference_clips?: TimelineClip[];
  prompt_segments: PromptSegment[];
  camera_clips?: CameraClip[];
  audio_clips: TimelineClip[];
  sfx_clips: TimelineClip[];
  lipsync: { tracks: LipSyncTrack[] };
  playhead: number;
  /** Monotonic allocator for @ImageN tags (per scene timeline). */
  next_image_tag_number?: number;
  /** How visual / prompt / camera guidance is weighted at compile time. */
  guidance_priority?: TimelineWorkspaceLayout["guidancePriority"];
  prompt_refs_migrated?: boolean;
};

function nid() {
  return Math.random().toString(36).slice(2, 10);
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

function TrackHeader({
  label,
  labelKey,
  testId,
  shellMode,
  controls = ["eye", "lock"],
  actionLabel,
  onAction,
}: {
  label: string;
  labelKey?: string;
  testId?: string;
  shellMode: boolean;
  controls?: Array<"eye" | "lock" | "mute" | "solo">;
  actionLabel?: string;
  onAction?: () => void;
}) {
  if (shellMode) {
    return (
      <TimelineTrackLabel
        label={label}
        labelKey={labelKey}
        testId={testId}
        controls={controls}
        onAction={onAction}
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
function freeImageClips(tl: DirectorTimeline): TimelineClip[] {
  const clips = tl.image_clips || [];
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
}) {
  const { t } = useTranslation("timeline");
  void t;
  const sel = useDirectorSelectionOptional();
  const [tl, setTl] = useState<DirectorTimeline | null>(null);  const [selectedSeg, setSelectedSeg] = useState<string>();
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
  const [includeAudio, setIncludeAudio] = useState(true);
  const [proxyFlag, setProxyFlag] = useState(false);
  const [audioIntentDraft, setAudioIntentDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workspaceLayout, setWorkspaceLayout] = useState(() => loadTimelineWorkspaceLayout());
  const [rulerHoverSec, setRulerHoverSec] = useState<number | null>(null);
  const [undoSnapshot, setUndoSnapshot] = useState<DirectorTimeline | null>(null);
  const boardScrollRef = useRef<HTMLDivElement>(null);
  // Scroll-aware batch windowing (100+ batches): the render window tracks the
  // visible scroll range in addition to playhead/selection, so scrolling to a
  // distant batch never renders a blank lane (audit UI-D9).
  const [boardScroll, setBoardScroll] = useState({ left: 0, width: 0 });
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
  // too — no more brown clip staying active while the Inspector shows Scene.
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
    } else if (
      s.kind === "imageClip" ||
      s.kind === "videoClip" ||
      s.kind === "videoReferenceClip" ||
      s.kind === "imageReferenceClip" ||
      s.kind === "camera" ||
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

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.sceneReferences.list(project.id, { scopeType: "project", scopeId: project.id }),
      api.listCharacterProfiles(project.id).catch(() => ({ items: [] })),
    ])
      .then(([res, characters]) => {
        if (cancelled) return;
        const items = ((res.items || []) as ReferenceBindingView[]).map((binding) => {
          const asset = project.assets.find((a) => a.id === binding.asset_id);
          return { ...binding, duration_sec: assetDurationSec(asset) };
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
  }, [project.assets, project.id, reloadKey]);

  useEffect(() => {
    if (!scene) return;
    const token = ++loadTokenRef.current;
    let cancelled = false;
    api
      .getDirector(project.id, scene.id)
      .then((d) => {
        if (cancelled || token !== loadTokenRef.current) return;
        const next = {
          ...d,
          image_clips: freeImageClips(d as DirectorTimeline),
          video_reference_clips: (d as DirectorTimeline).video_reference_clips || [],
          image_reference_clips: (d as DirectorTimeline).image_reference_clips || [],
          lipsync: { tracks: normalizeLipSyncTracks((d as DirectorTimeline).lipsync?.tracks) },
        } as DirectorTimeline;
        setTl(next);
        setSelectedSeg((prev) => {
          if (prev && next.prompt_segments.some((s) => s.id === prev)) return prev;
          return next.prompt_segments[0]?.id;
        });
        onPlayheadChange?.(next.playhead || 0);
        const layout = loadTimelineWorkspaceLayout();
        setWorkspaceLayout(layout);
        if (layout.guidancePriority && d.guidance_priority !== layout.guidancePriority) {
          setTl({ ...next, guidance_priority: layout.guidancePriority });
        }
      })
      .catch(() => {
        if (cancelled || token !== loadTokenRef.current) return;
        // True-empty fallback so shell mode never sticks on a perpetual loader.
        setTl({
          media_mode: "image",
          duration_sec: scene.duration_sec || 5,
          image_clips: [],
          video_clips: [],
          video_reference_clips: [],
          image_reference_clips: [],
          prompt_segments: [],
          camera_clips: [],
          audio_clips: [],
          sfx_clips: [],
          lipsync: { tracks: normalizeLipSyncTracks([]) },
          playhead: 0,
          guidance_priority: "visual_first",
        } as unknown as DirectorTimeline);
      });
    return () => {
      cancelled = true;
    };
    // Intentionally omit onPlayheadChange — parent setter identity must not retrigger reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, scene?.id, scene?.director_json, reloadKey]);

  // Prefetch per-clip Refs counts so track chrome is honest before a clip is selected.
  // Debounced: `tl` changes on every drag/trim commit, and without a settle
  // window each commit fired N parallel requests (audit D11).
  useEffect(() => {
    if (!scene || !tl || !timelineRefsEnabled) return;
    const clips = tl.image_clips || [];
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
        <p className="scene-meta">{shellMode ? "Loading Timeline tracks…" : "Loading…"}</p>
      </div>
    );
  }

  const hasOutput = !!(scene.output_path || scene.lipsync_output_path || tl.video_clips[0]?.asset_id);

  const sendToEditor = async (mode: "shot" | "sequence" | "selected") => {
    if (!scene) return;
    setSendBusy(true);
    setSendMsg(null);
    try {
      const segmentIds =
        mode === "selected" && selectedSeg
          ? [selectedSeg]
          : mode === "selected"
            ? tl.prompt_segments.map((s) => s.id)
            : undefined;
      const seq = await api.directorSequenceFromScene(project.id, {
        scene_id: scene.id,
        name: `${scene.name} · ${mode === "shot" ? "Shot" : mode === "selected" ? "Segments" : "Sequence"}`,
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

  const save = async (next: DirectorTimeline) => {
    const normalized = {
      ...next,
      lipsync: { tracks: normalizeLipSyncTracks(next.lipsync?.tracks) },
    } as DirectorTimeline;
    // Preserve local drafts immediately so a failed save never loses edits.
    setTl(normalized);
    setSaving(true);
    try {
      await api.putDirector(project.id, scene.id, normalized);
      setSaveError(null);
      onChange();
    } catch (e) {
      // Consolidated, non-spammy: one status line, no toast storm. Drafts
      // remain in local state; dependent edits continue to mutate locally.
      setSaveError(e instanceof Error ? e.message : "Save failed — your edits are preserved locally.");
    } finally {
      setSaving(false);
    }
  };

  const duration = tl.duration_sec || scene.duration_sec || 5;
  const sceneFps =
    scene.fps_mode && scene.fps_mode !== "auto" && scene.fps ? scene.fps : project.fps || 24;
  const playhead = externalPlayhead ?? tl.playhead ?? 0;
  const activeSeg = tl.prompt_segments.find((s) => s.id === selectedSeg) || tl.prompt_segments[0];
  const images = project.assets.filter((a) => a.kind === "image");
  const videos = project.assets.filter((a) => a.kind === "video");
  const audios = project.assets.filter((a) => a.kind === "audio");
  const imageClips = freeImageClips(tl);
  const lipSyncTracks = normalizeLipSyncTracks(tl.lipsync?.tracks);
  const selectedImageClip =
    selectedClipKind === "imageClip"
      ? imageClips.find((c) => c.id === selectedClip)
      : undefined;
  const selectedLipSyncTrack =
    sel?.selection?.kind === "lipsyncTrack"
      ? lipSyncTracks.find((track) => track.id === sel.selection.id)
      : sel?.selection?.kind === "lipsyncClip"
        ? lipSyncTracks.find(
            (track) => track.id === sel.selection.trackId || (track.clips || []).some((clip) => clip.id === sel.selection.id),
          )
        : sel?.selection?.kind === "lipsync"
          ? lipSyncTracks[sel.selection.trackIndex ?? Number(sel.selection.id || 0)] || lipSyncTracks[0]
          : null;
  const selectedLipSyncClip =
    sel?.selection?.kind === "lipsyncClip"
      ? selectedLipSyncTrack?.clips?.find((clip) => clip.id === sel.selection.id)
      : null;
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
  const boardDuration = Math.max(
    duration,
    batchWindows.reduce((max, entry) => Math.max(max, entry.start + entry.length), 0),
  );
  const repairWindows = batchWindows.flatMap(({ batch, start }) =>
    (batch.repairRanges || []).map((repair) => ({
      id: repair.id,
      label: repair.label,
      status: repair.status,
      start: start + repair.start,
      length: repair.length,
    })),
  );
  const boardWidth = Math.max(480, boardDuration * 90 * zoom);

  const laneClipsFor = (kind: "image" | "video" | "videoReference" | "imageReference" | "prompt" | "audio" | "sfx" | "camera") => {
    if (!tl) return [] as Array<{ id: string; start: number; length: number }>;
    if (kind === "image") return tl.image_clips || [];
    if (kind === "video") return tl.video_clips || [];
    if (kind === "videoReference") return tl.video_reference_clips || [];
    if (kind === "imageReference") return tl.image_reference_clips || [];
    if (kind === "prompt") return tl.prompt_segments || [];
    if (kind === "audio") return tl.audio_clips || [];
    if (kind === "sfx") return tl.sfx_clips || [];
    return tl.camera_clips || [];
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
    if (mode === "trim-left") {
      const end = s + l;
      for (const n of others) {
        if (n.e > s && n.s < end) s = Math.min(Math.max(s, n.e), end - 0.15);
      }
      return { start: s, length: Math.max(0.15, end - s) };
    }
    if (mode === "trim-right") {
      for (const n of others) {
        if (n.s >= s - 1e-9 && n.s < s + l) l = Math.max(0.15, n.s - s);
      }
      return { start: s, length: l };
    }
    for (let pass = 0; pass < 2; pass++) {
      for (const n of others) {
        if (s < n.e && s + l > n.s) {
          const leftFit = n.s - l;
          s = leftFit >= 0 && s <= n.s ? leftFit : n.e;
        }
      }
    }
    return { start: s, length: l };
  };

  const commitClipGeometry = (
    kind: "image" | "video" | "videoReference" | "imageReference" | "prompt" | "audio" | "sfx" | "camera",
    id: string,
    next: ClipGeometry,
    mode: ClipDragMode,
  ) => {
    const snapped = snapTime(next.start, snap, snap ? 1 / sceneFps : 0.01);
    const clamped = clampToLane(kind, id, snapped, Math.max(0.15, next.length), mode);
    const start = clamped.start;
    const length = clamped.length;
    // Snapshot the pre-drag timeline so the creator can undo a move/trim via
    // the local toast (PERSIST_DURATION_ON_COMMIT + undo for move/trim).
    if (tl) setUndoSnapshot({ ...tl });
    scheduleUndoClear();
    if (kind === "image") {
      void save({
        ...tl,
        image_clips: (tl.image_clips || []).map((c) => (c.id === id ? { ...c, start, length } : c)),
      });
      return;
    }
    if (kind === "video") {
      void save({
        ...tl,
        video_clips: (tl.video_clips || []).map((c) => {
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
      void save({
        ...tl,
        prompt_segments: (tl.prompt_segments || []).map((s) => (s.id === id ? { ...s, start, length } : s)),
      });
      return;
    }
    if (kind === "audio" || kind === "sfx") {
      const key = kind === "audio" ? "audio_clips" : "sfx_clips";
      void save({
        ...tl,
        [key]: (tl[key] || []).map((c) => (c.id === id ? { ...c, start, length } : c)),
      });
      return;
    }
    void save({
      ...tl,
      camera_clips: (tl.camera_clips || []).map((c) => (c.id === id ? { ...c, start, length } : c)),
    });
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

  const addImageFromLibrary = async (assetId: string) => {
    if (!assetId) return;
    // BATCH_OWNED_CLIPS: when a batch is selected, add the image to that
    // batch's visualClips via the per-batch API so no other batch's clips are
    // touched. Only fall back to the legacy scene-global path when no batch is
    // selected (preserves the classic single-batch workflow).
    const selectedBatchId =
      sel?.selection?.kind === "batch" ? sel.selection.id : undefined;
    if (selectedBatchId && master) {
      const batch = (master.batchBlocks || []).find((b) => b.id === selectedBatchId);
      if (batch) {
        const batchStart = (master.batchBlocks || [])
          .slice()
          .sort((a, b) => a.order - b.order)
          .reduce((acc, b) => (b.id === selectedBatchId ? acc : acc + Math.max(0.1, b.duration.plannedDuration || 0)), 0);
        const planned = Math.max(0.1, batch.duration.plannedDuration || 0);
        try {
          await api.directorTimelineAddClipToBatch(project.id, scene.id, batch.id, {
            kind: "image",
            assetId,
            start: batchStart,
            length: Math.min(2, planned),
            label: `Image ${(batch.visualClips || []).length + 1}`,
            role: "guide",
          });
          await onChange();
        } catch (e) {
          setSaveError(e instanceof Error ? e.message : "Add image failed");
        }
        return;
      }
    }
    const start = imageClips.reduce((m, c) => Math.max(m, c.start + c.length), 0);
    const clip: TimelineClip = {
      id: nid(),
      start: snapTime(Math.min(start, Math.max(0, duration - 1)), snap),
      length: Math.min(2, duration),
      label: `Image ${imageClips.length + 1}`,
      role: "guide",
      display_tag: null,
      asset_id: assetId,
    };
    await save({ ...tl, media_mode: "image", image_clips: [...imageClips, clip] });
    selectClip("imageClip", clip.id);
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
        setTokenError("Broken Reference — this character needs an approved picture in the Library.");
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
    if (kind === "image") await addImageFromLibrary(assetId);
    else if (kind === "videoReference") await addVideoReferenceFromLibrary(assetId);
    else if (kind === "imageReference") await addImageReferenceFromLibrary(assetId);
    else if (kind === "audio") {
      await save({
        ...tl,
        audio_clips: [
          ...tl.audio_clips,
          { id: nid(), start: 0, length: duration, label: "Audio", asset_id: assetId, volume: 1 },
        ],
      });
    } else {
      await save({
        ...tl,
        sfx_clips: [
          ...tl.sfx_clips,
          { id: nid(), start: snapTime(1, snap), length: 1, label: "SFX", asset_id: assetId, volume: 1 },
        ],
      });
    }
  };

  const switchToVideo = async () => {
    await save({
      ...tl,
      media_mode: "video",
      video_clips: tl.video_clips.length
        ? tl.video_clips
        : [{ id: nid(), start: 0, length: duration, label: "Video", asset_id: null, trim_start: 0 }],
    });
  };

  const switchToImage = async () => {
    await save({ ...tl, media_mode: "image", image_clips: imageClips });
  };

  const addPromptSegment = async () => {
    const seg: PromptSegment = {
      id: nid(),
      start: snapTime(Math.min(duration - 1, activeSeg ? activeSeg.start + activeSeg.length : 0), snap),
      length: Math.min(2, duration),
      text: "",
      weight: 1,
      region: null,
      reference_binding_ids: [],
    };
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
    selectSeg(seg.id);
  };

  const duplicateSeg = async () => {
    if (!activeSeg) return;
    const seg: PromptSegment = {
      ...activeSeg,
      id: nid(),
      start: snapTime(Math.min(duration - 0.2, activeSeg.start + activeSeg.length), snap),
    };
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
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
    await save({
      ...tl,
      prompt_segments: tl.prompt_segments.flatMap((s) => (s.id === activeSeg.id ? [a, b] : [s])),
    });
    selectSeg(b.id);
  };

  const deleteSeg = async () => {
    if (!activeSeg) return;
    const next = tl.prompt_segments.filter((s) => s.id !== activeSeg.id);
    await save({ ...tl, prompt_segments: next });
    if (next[0]) selectSeg(next[0].id);
  };

  const previewMedia =
    tl.media_mode === "video" && tl.video_clips[0]?.asset_id
      ? api.assetUrl(tl.video_clips[0].asset_id)
      : imageClips.find((c) => c.asset_id)?.asset_id
        ? api.assetUrl(imageClips.find((c) => c.asset_id)!.asset_id!)
        : scene.output_path
          ? api.mediaUrl(scene.output_path)
          : "";

  const videoClip = tl.video_clips[0];
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
      const needleLeft = gutter + (t / Math.max(0.1, duration)) * laneEl.offsetWidth;
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
    undoTimerRef.current = window.setTimeout(() => setUndoSnapshot(null), 8000);
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
    const prev = { ...tl };
    const next = { ...tl };
    if (kind === "image") next.image_clips = tl.image_clips.filter((c) => c.id !== id);
    if (kind === "video") next.video_clips = tl.video_clips.filter((c) => c.id !== id);
    if (kind === "videoReference") next.video_reference_clips = (tl.video_reference_clips || []).filter((c) => c.id !== id);
    if (kind === "imageReference") next.image_reference_clips = (tl.image_reference_clips || []).filter((c) => c.id !== id);
    if (kind === "audio") next.audio_clips = tl.audio_clips.filter((c) => c.id !== id);
    if (kind === "sfx") next.sfx_clips = tl.sfx_clips.filter((c) => c.id !== id);
    if (kind === "prompt") next.prompt_segments = tl.prompt_segments.filter((c) => c.id !== id);
    if (kind === "camera") next.camera_clips = (tl.camera_clips || []).filter((c) => c.id !== id);
    setUndoSnapshot(prev);
    scheduleUndoClear();
    await save(next);
    if (kind === "prompt" && next.prompt_segments.length) selectSeg(next.prompt_segments[0].id);
  };

  const undoRemove = async () => {
    if (!undoSnapshot) return;
    await save(undoSnapshot);
    setUndoSnapshot(null);
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
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
    selectSeg(seg.id);
  };

  const onGuidancePriorityChange = (value: TimelineWorkspaceLayout["guidancePriority"]) => {
    saveTimelineWorkspaceLayout({ guidancePriority: value });
    setWorkspaceLayout((prev) => ({ ...prev, guidancePriority: value }));
    if (tl) void save({ ...tl, guidance_priority: value });
  };

  const HelpBtn = ({ id }: { id: string }) => {
    const h = getTimelineHelp(id);
    return <HelpTip label={h.title} content={h.body} text={h.title} />;
  };

  const clipIsPersisted = (clip: { asset_id?: string | null; text?: string }) =>
    Boolean(clip.asset_id || (clip.text && clip.text.trim()));

  return (
    <div className={shellMode ? "timeline-v2__canvas" : "panel director-tracks"}>
      {!shellMode ? (
        <>
          <p className="scene-meta" style={{ margin: "0 0 0.35rem", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: "0.7rem" }}>
            Prompt Timeline
          </p>
          <PanelHeading
            title="Director · Prompt Timeline"
            tip="Director creates the shots: timed prompts, camera direction, and model-ready sequences. Assemble the film in Editor."
          >
            <span className="scene-meta">
              {duration.toFixed(1)}s · {saving ? "Saving…" : tl.media_mode === "image" ? "Image timeline" : "Video timeline"}
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
            const renderSrc = scene.lipsync_output_path
              ? api.mediaUrl(scene.lipsync_output_path)
              : scene.output_path
                ? api.mediaUrl(scene.output_path)
                : "";
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
                <button
                  type="button"
                  className="primary"
                  data-testid="timeline-toolbar-add-batch"
                  title="Add Batch"
                  onClick={() => {
                    if (!scene) return;
                    void api.directorTimelineAddBatch(project.id, scene.id, { plannedDuration: duration }).then(onChange);
                  }}
                >
                  Add Batch <HelpBtn id="add_batch" />
                </button>

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
                      <option value="">Library Image…</option>
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
                        video_clips: [
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
                    <option value="">{videoClip?.asset_id ? "Replace from Library…" : "Library Video…"}</option>
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

                <button
                  type="button"
                  data-testid="timeline-toolbar-preflight"
                  title="Co-Director Preflight"
                  onClick={() => {
                    if (!scene) return;
                    void api.directorTimelinePreflight(project.id, scene.id).then((pf) => {
                      window.alert(
                        `Preflight: ${(pf.findings || []).length} finding(s)\n` +
                          (pf.findings || [])
                            .slice(0, 5)
                            .map((f) => `• ${f.severity}: ${f.message}`)
                            .join("\n"),
                      );
                      onChange();
                    });
                  }}
                >
                  Preflight <HelpBtn id="preflight" />
                </button>

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
                    min={1}
                    max={30}
                    step={0.5}
                    value={duration}
                    onChange={(e) => save({ ...tl, duration_sec: Number(e.target.value) || 5 })}
                  />
                  s
                </label>
              </div>

              <div className="director-zoom">
                <span className="scene-meta">Track zoom</span>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setZoom(Math.max(0.5, +(zoom - 0.25).toFixed(2)))}
                >
                  −
                </button>
                <input
                  type="range"
                  min={0.5}
                  max={3}
                  step={0.05}
                  value={zoom}
                  onChange={(e) => setZoom(Number(e.target.value))}
                  aria-label="Zoom timeline tracks"
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setZoom(Math.min(3, +(zoom + 0.25).toFixed(2)))}
                >
                  +
                </button>
                <span className="scene-meta">{zoom.toFixed(2)}×</span>
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
                <button
                  type="button"
                  className="ghost"
                  data-testid="timeline-settings-gear"
                  aria-label="Timeline Settings"
                  title="Timeline Settings"
                  aria-expanded={settingsOpen}
                  onClick={() => setSettingsOpen((v) => !v)}
                >
                  ⚙ <HelpBtn id="timeline_settings" />
                </button>
                <TimelineSettingsDrawer
                  open={settingsOpen}
                  onClose={() => setSettingsOpen(false)}
                  onGuidancePriorityChange={onGuidancePriorityChange}
                  onLayoutChange={(layout) => {
                    setWorkspaceLayout(layout);
                    if (layout.snapEnabled !== snap) setSnap(layout.snapEnabled);
                  }}
                />
                <span className="scene-meta" data-testid="timeline-playhead-time">
                  {formatTimelineTime(playhead, workspaceLayout.displayMode, sceneFps)} · playhead
                </span>
              </div>
            </>
          ) : null}

          {undoSnapshot && (
            <div className="timeline-undo-toast" role="status" data-testid="timeline-undo-toast">
              <span>Removed from Timeline</span>
              <button type="button" className="primary" onClick={() => void undoRemove()}>
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
              style={{ width: boardWidth, minWidth: "100%", position: "relative" }}
              tabIndex={0}
              onKeyDown={onPlayheadKey}
              data-testid="timeline-track-board"
              onWheel={(e) => {
                if (!(e.ctrlKey || e.metaKey)) return;
                e.preventDefault();
                const delta = e.deltaY > 0 ? -0.1 : 0.1;
                setZoom?.(Math.min(3, Math.max(0.5, +(zoom + delta).toFixed(2))));
              }}
              data-zoom={String(zoom)}
              data-board-width={String(boardWidth)}
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
                  {Array.from({ length: Math.floor(boardDuration) + 1 }).map((_, i) => (
                    <span
                      key={i}
                      className={
                        shellMode
                          ? i === 0
                            ? "timeline-v2__ruler-tick timeline-v2__ruler-tick--origin"
                            : "timeline-v2__ruler-tick"
                          : i === 0
                            ? "track-ruler__tick track-ruler__tick--origin"
                            : "track-ruler__tick"
                      }
                      style={{ left: `${(i / Math.max(0.1, boardDuration)) * 100}%` }}
                    >
                      {formatTimelineTime(i, workspaceLayout.displayMode, sceneFps)}
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
                    ref={playheadRef}
                    className="track-playhead"
                    style={{ left: `${(playhead / Math.max(0.1, boardDuration)) * 100}%` }}
                    id="timeline-playhead"
                    data-testid="timeline-playhead"
                  >
                    <span className="track-playhead__head" aria-hidden />
                  </div>
                </div>
              </div>

              {shellMode && (
                <div className={trackRowClass(shellMode, "timeline-v2__track-row--batch")}>
                  <TrackHeader
                    label="BATCHES"
                    labelKey="tracks.batches"
                    shellMode={shellMode}
                    onAction={() => {
                      if (!scene) return;
                      void api.directorTimelineAddBatch(project.id, scene.id, { plannedDuration: duration }).then(onChange);
                    }}
                    actionLabel="+ Batch"
                  />
                  <div className={trackContentClass(shellMode)} data-testid="timeline-batch-lane">
                    {batchWindows.length === 0 ? (
                      <div className="track-empty">Create a batch to plan how this scene renders over time.</div>
                    ) : (
                      // UNBOUNDED_BATCH_POLICY: no product-defined batch cap.
                      // Virtualize rendered DOM: only mount batches within a
                      // generous window around the playhead/selection so
                      // thousands of batches stay performant without an
                      // arbitrary MAX_BATCHES limit on the data model.
                      (() => {
                        const WIN = 80;
                        const playheadIdx = (() => {
                          let cursor = 0;
                          for (let i = 0; i < batchWindows.length; i++) {
                            const bw = batchWindows[i];
                            if (playhead >= cursor && playhead < cursor + bw.length) return i;
                            cursor += bw.length;
                          }
                          return 0;
                        })();
                        const selIdx = sel?.selection?.kind === "batch"
                          ? batchWindows.findIndex((bw) => bw.batch.id === sel.selection!.id)
                          : -1;
                        const center = selIdx >= 0 ? selIdx : playheadIdx;
                        let lo = Math.max(0, center - Math.floor(WIN / 2));
                        let hi = Math.min(batchWindows.length, lo + WIN);
                        // Union with the visible scroll range so batches the
                        // creator scrolled to are rendered even when neither
                        // playhead nor selection is near them.
                        if (boardScroll.width > 0 && boardWidth > 0 && boardDuration > 0) {
                          const t0 = (boardScroll.left / boardWidth) * boardDuration;
                          const t1 = ((boardScroll.left + boardScroll.width) / boardWidth) * boardDuration;
                          let cursor = 0;
                          let sLo = -1;
                          let sHi = batchWindows.length - 1;
                          for (let i = 0; i < batchWindows.length; i++) {
                            const bw = batchWindows[i];
                            if (sLo < 0 && cursor + bw.length > t0) sLo = i;
                            cursor += bw.length;
                            if (cursor >= t1) {
                              sHi = i;
                              break;
                            }
                          }
                          if (sLo >= 0) {
                            lo = Math.min(lo, sLo);
                            hi = Math.max(hi, sHi + 1);
                          }
                        }
                        return batchWindows.slice(lo, hi).map(({ batch, start, length }) => (
                          <button
                            key={batch.id}
                            type="button"
                            id={`timeline-track-item-batch-${batch.id}`}
                            data-testid={`timeline-batch-${batch.id}`}
                            className={`track-clip track-clip--batch ${sel?.selection?.kind === "batch" && sel.selection.id === batch.id ? "active" : ""}`}
                            style={pct(start, length, boardDuration)}
                            onClick={() => sel?.setSelection({ kind: "batch", id: batch.id })}
                          >
                            <strong>{batch.label}</strong>
                            <span>
                              {formatTimelineTime(start, workspaceLayout.displayMode, sceneFps)} - {formatTimelineTime(start + length, workspaceLayout.displayMode, sceneFps)}
                            </span>
                            {batch.status && batch.status !== "Ready" && batch.status !== "Draft" ? (
                              <span
                                className={`track-clip__badge ${batch.status === "Failed" ? "bad" : batch.status === "Approved" ? "good" : "warn"}`}
                                data-testid={`timeline-batch-status-${batch.id}`}
                              >
                                {formatBatchStatus(batch.status)}
                              </span>
                            ) : null}
                            {(() => {
                              const incoming = (master?.continuityBridges || []).find(
                                (bridge) => bridge.targetBatchId === batch.id && bridge.status !== "Superseded",
                              );
                              const label = continuityChipLabel(incoming?.status, batch.downstreamStale);
                              if (!label) return null;
                              return (
                                <span
                                  className={`track-clip__continuity ${batch.downstreamStale || incoming?.status === "Failed" ? "warn" : ""}`}
                                  data-testid={`timeline-continuity-chip-${batch.id}`}
                                >
                                  {label}
                                </span>
                              );
                            })()}
                          </button>
                        ));
                      })()
                    )}
                  </div>
                </div>
              )}

              {tl.media_mode === "image" ? (
                <div
                  className={trackRowClass(shellMode)}
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
                          boardWidthPx={boardWidth}
                          snapEnabled={snap}
                          snapStep={snap ? 1 / sceneFps : 0.01}
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
                            ×
                          </button>
                          {workspaceLayout.showThumbnails && asset ? (
                            <img className="track-clip__thumb" src={api.assetUrl(asset.id)} alt="" />
                          ) : null}
                          <strong>{clip.display_tag || clip.label || "Image"}</strong>
                          <span>
                            {asset ? `@${asset.tag || asset.filename}` : "empty"} · {clip.start.toFixed(1)}–
                            {(clip.start + clip.length).toFixed(1)}s
                          </span>
                          {timelineRefsEnabled && (
                            <span className="scene-meta">
                              Primary · Supporting refs: {refsCounts[clip.id] ?? 0}
                            </span>
                          )}
                          {!shellMode ? (
                            <select
                              value={clip.asset_id || ""}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) =>
                                save({
                                  ...tl,
                                  image_clips: imageClips.map((c) =>
                                    c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                                  ),
                                })
                              }
                            >
                              <option value="">Asset…</option>
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
                <div className={trackRowClass(shellMode)}>
                  <TrackHeader label="VISUAL" labelKey="tracks.visual" shellMode={shellMode} controls={["eye", "lock"]} />
                  <div className={trackContentClass(shellMode)}>
                    {tl.video_clips.length === 0 && workspaceLayout.showEmptyHelp && (
                      <div className="track-empty">Add a video clip or switch back to image planning.</div>
                    )}
                    {tl.video_clips.map((clip) => {
                      const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                      return (
                        <TrackClipInteractive
                          key={clip.id}
                          clipId={clip.id}
                          start={clip.start}
                          length={clip.length}
                          boardDuration={boardDuration}
                          boardWidthPx={boardWidth}
                          snapEnabled={snap}
                          snapStep={snap ? 1 / sceneFps : 0.01}
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
                            ×
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
                                  video_clips: tl.video_clips.map((c) =>
                                    c.id === clip.id
                                      ? { ...c, asset_id: e.target.value || null }
                                      : c,
                                  ),
                                })
                              }
                            >
                              <option value="">Library…</option>
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
                  {tl.prompt_segments.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">{t("emptyTimedPrompt")}</div>
                  )}
                  {tl.prompt_segments.map((seg) => (
                    <TrackClipInteractive
                      key={seg.id}
                      clipId={seg.id}
                      start={seg.start}
                      length={seg.length}
                      boardDuration={boardDuration}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapStep={snap ? 1 / sceneFps : 0.01}
                      selected={selectedSeg === seg.id}
                      className="prompt"
                      domId={`timeline-track-item-promptSeg-${seg.id}`}
                      testId={`track-clip-prompt-${seg.id}`}
                      onSelect={() => selectSeg(seg.id)}
                      onCommit={(next, mode) => commitClipGeometry("prompt", seg.id, next, mode)}
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
                        ×
                      </button>
                      {seg.movement_segment_ref?.alias ? (
                        <span className="timeline-v2__movement-chip" data-testid={`prompt-movement-${seg.id}`}>
                          ~{seg.movement_segment_ref.alias}
                        </span>
                      ) : null}
                      <span className="timeline-v2__clip-tokens" data-testid={`prompt-token-summary-${seg.id}`}>
                        {tokenSummary(seg.reference_binding_ids, bindings) ||
                          (seg.region ? t("timedPromptRegion") : null) ||
                          (seg.text ? seg.text.slice(0, 36) : t("emptyPromptClip"))}
                      </span>
                      {tokenSummary(seg.reference_binding_ids, bindings) && seg.text ? (
                        <span className="timeline-v2__clip-instruction">{seg.text.slice(0, 40)}</span>
                      ) : null}
                    </TrackClipInteractive>
                  ))}
                </div>
              </div>

              <div className={trackRowClass(shellMode, "timeline-v2__track-row--camera")} data-testid="timeline-camera-track">
                <TrackHeader
                  label="CAMERA"
                  labelKey="tracks.camera"
                  testId="timeline-v2-label-camera"
                  shellMode={shellMode}
                  onAction={() => {
                    const clip: CameraClip = {
                      id: nid(),
                      start: 0,
                      length: Math.min(2, duration),
                      motion_type: "dolly_in",
                      speed: 1,
                      distance: 1,
                      ease: "ease_in_out",
                      shake: 0,
                      blend: 0.5,
                      rig: "dolly",
                      label: "Dolly In",
                      text: "",
                      reference_binding_ids: [],
                    };
                    save({ ...tl, camera_clips: [...(tl.camera_clips || []), clip] });
                  }}
                  actionLabel="+ Camera"
                />
                <div
                  className={trackContentClass(shellMode)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const presetKind = e.dataTransfer.getData("application/x-adept-profile-kind");
                    if (presetKind !== "camera_preset" && presetKind !== "motion_preset") return;
                    const tag = e.dataTransfer.getData("application/x-adept-profile-tag");
                    const clip: CameraClip = {
                      id: nid(),
                      start: 0,
                      length: Math.min(2, duration),
                      motion_type: "dolly_in",
                      speed: 0.8,
                      distance: 1,
                      ease: "ease_in_out",
                      shake: 0,
                      blend: 0.5,
                      rig: "dolly",
                      label: tag || "Preset",
                      preset_id: e.dataTransfer.getData("application/x-adept-profile"),
                      text: "",
                      reference_binding_ids: [],
                    };
                    save({ ...tl, camera_clips: [...(tl.camera_clips || []), clip] });
                  }}
                >
                  {(tl.camera_clips || []).length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">{t("emptyCamera")}</div>
                  )}
                  {(tl.camera_clips || []).map((clip) => (
                    <TrackClipInteractive
                      key={clip.id}
                      clipId={clip.id}
                      start={clip.start}
                      length={clip.length}
                      boardDuration={boardDuration}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapStep={snap ? 1 / sceneFps : 0.01}
                      selected={selectedClip === clip.id}
                      className="camera"
                      domId={`timeline-track-item-camera-${clip.id}`}
                      testId={`track-clip-camera-${clip.id}`}
                      onSelect={() => selectClip("camera", clip.id)}
                      onCommit={(next, mode) => commitClipGeometry("camera", clip.id, next, mode)}
                    >
                      <button
                        type="button"
                        className="track-clip__remove"
                        aria-label="Remove from Timeline"
                        title="Remove from Timeline"
                        onClick={(e) => {
                          e.stopPropagation();
                          void removeClip("camera", clip.id, true);
                        }}
                      >
                        ×
                      </button>
                      {shellMode ? (
                        <>
                          <span className="timeline-v2__clip-tokens" data-testid={`camera-token-summary-${clip.id}`}>
                            {tokenSummary(clip.reference_binding_ids, bindings) ||
                              clip.motion_type.replace(/_/g, " ")}
                          </span>
                          {tokenSummary(clip.reference_binding_ids, bindings) && (clip.text || "").trim() ? (
                            <span className="timeline-v2__clip-instruction">{(clip.text || "").slice(0, 40)}</span>
                          ) : null}
                        </>
                      ) : (
                        <>
                          <strong>{clip.motion_type.replace(/_/g, " ")}</strong>
                          <span>{clip.rig}</span>
                        </>
                      )}
                      {!shellMode ? (
                        <>
                          <select
                            value={clip.motion_type}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) =>
                              save({
                                ...tl,
                                camera_clips: (tl.camera_clips || []).map((c) =>
                                  c.id === clip.id ? { ...c, motion_type: e.target.value } : c
                                ),
                              })
                            }
                          >
                            {[
                              "static",
                              "dolly_in",
                              "dolly_out",
                              "push",
                              "pull",
                              "pan",
                              "tilt",
                              "orbit",
                              "crane",
                              "rail",
                              "handheld",
                              "drone",
                            ].map((m) => (
                              <option key={m} value={m}>
                                {m}
                              </option>
                            ))}
                          </select>
                          <select
                            value={clip.rig}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) =>
                              save({
                                ...tl,
                                camera_clips: (tl.camera_clips || []).map((c) =>
                                  c.id === clip.id ? { ...c, rig: e.target.value } : c
                                ),
                              })
                            }
                          >
                            {[
                              "tripod",
                              "dolly",
                              "crane",
                              "steadicam",
                              "handheld",
                              "drone",
                              "rail",
                              "gimbal",
                              "virtual",
                            ].map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </select>
                        </>
                      ) : null}
                    </TrackClipInteractive>
                  ))}
                </div>
              </div>

              <div
                className={trackRowClass(shellMode, "timeline-v2__track-row--audio")}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropAsset(e, "audio")}
              >
                <TrackHeader label="AUDIO" labelKey="tracks.audio" shellMode={shellMode} controls={["mute", "solo"]} />
                <div className={trackContentClass(shellMode)}>
                  {tl.audio_clips.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">Add ambience, score, or dialogue stems for this scene.</div>
                  )}
                  {tl.audio_clips.map((clip) => (
                    <TrackClipInteractive
                      key={clip.id}
                      clipId={clip.id}
                      start={clip.start}
                      length={clip.length}
                      boardDuration={boardDuration}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapStep={snap ? 1 / sceneFps : 0.01}
                      selected={selectedClip === clip.id}
                      className="audio"
                      domId={`timeline-track-item-audio-${clip.id}`}
                      testId={`track-clip-audio-${clip.id}`}
                      onSelect={() => selectClip("audio", clip.id)}
                      onCommit={(next, mode) => commitClipGeometry("audio", clip.id, next, mode)}
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
                        ×
                      </button>
                      <strong>Audio</strong>
                      {!shellMode ? (
                        <select
                          value={clip.asset_id || ""}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) =>
                            save({
                              ...tl,
                              audio_clips: tl.audio_clips.map((c) =>
                                c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                              ),
                            })
                          }
                        >
                          <option value="">Select…</option>
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
                <TrackHeader label="SFX" labelKey="tracks.sfx" shellMode={shellMode} controls={["mute", "solo"]} />
                <div className={trackContentClass(shellMode)}>
                  {tl.sfx_clips.length === 0 && workspaceLayout.showEmptyHelp && (
                    <div className="track-empty">Drop quick impact or spot effects here.</div>
                  )}
                  {tl.sfx_clips.map((clip) => (
                    <TrackClipInteractive
                      key={clip.id}
                      clipId={clip.id}
                      start={clip.start}
                      length={clip.length}
                      boardDuration={boardDuration}
                      boardWidthPx={boardWidth}
                      snapEnabled={snap}
                      snapStep={snap ? 1 / sceneFps : 0.01}
                      selected={selectedClip === clip.id}
                      className="sfx"
                      domId={`timeline-track-item-sfx-${clip.id}`}
                      testId={`track-clip-sfx-${clip.id}`}
                      onSelect={() => selectClip("sfx", clip.id)}
                      onCommit={(next, mode) => commitClipGeometry("sfx", clip.id, next, mode)}
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
                        ×
                      </button>
                      <strong>SFX</strong>
                      {!shellMode ? (
                        <select
                          value={clip.asset_id || ""}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) =>
                            save({
                              ...tl,
                              sfx_clips: tl.sfx_clips.map((c) =>
                                c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                              ),
                            })
                          }
                        >
                          <option value="">Select…</option>
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

              {lipSyncTracks.map((track, index) => {
                const trackSelected =
                  sel?.selection?.kind === "lipsyncTrack" && sel.selection.id === track.id;
                return (
                  <div
                    key={track.id}
                    className={trackRowClass(
                      shellMode,
                      `${trackSelected ? "is-selected " : ""}timeline-v2__track-row--lipsync`.trim(),
                    )}
                  >
                    <TrackHeader
                      label={shellMode ? (index === 0 ? "LIP SYNC" : `LIP SYNC ${index + 1}`) : track.label || `Lip Sync ${index + 1}`}
                      labelKey={index === 0 ? "tracks.lipSync" : undefined}
                      shellMode={shellMode}
                      controls={["eye", "lock"]}
                    />
                    <div
                      id={`timeline-track-item-lipsyncTrack-${track.id}`}
                      className={trackContentClass(shellMode, trackSelected ? "is-selected" : "")}
                      tabIndex={-1}
                      onClick={() =>
                        sel?.setSelection({
                          kind: "lipsyncTrack",
                          id: track.id,
                          trackId: track.id,
                          trackIndex: index,
                        })
                      }
                    >
                      {(track.clips || []).length === 0 ? (
                        <div className="track-empty">
                          {index === 0
                            ? "Drop dialogue audio onto this Lip Sync track to time character speech."
                            : "Select this track to inspect clips, or use Lip Sync − to remove an additional track."}
                        </div>
                      ) : (
                        (track.clips || []).map((clip) => {
                          const clipSelected =
                            selectedLipSyncClip?.id === clip.id ||
                            (sel?.selection?.kind === "lipsyncClip" && sel.selection.id === clip.id);
                          return (
                            <button
                              key={clip.id}
                              type="button"
                              id={`timeline-track-item-lipsyncClip-${clip.id}`}
                              className={`track-clip lipsync lipsync-clip ${clipSelected ? "active" : ""}`}
                              data-testid={`track-clip-lipsync-${clip.id}`}
                              style={pct(clip.start, clip.length, boardDuration)}
                              onClick={(event) => {
                                event.stopPropagation();
                                sel?.setSelection({
                                  kind: "lipsyncClip",
                                  id: clip.id,
                                  trackId: track.id,
                                  trackIndex: index,
                                });
                              }}
                            >
                              <strong className="timeline-v2__clip-tokens">
                                {(() => {
                                  const speaker = bindings.find((item) => item.id === clip.speaker_binding_id);
                                  return speaker
                                    ? displayToken(speaker.alias || speaker.asset_name, speaker.media_kind || "entity")
                                    : clip.character_name
                                      ? `@${clip.character_name.replace(/\s+/g, "")}`
                                      : clip.label || "Lip Sync Clip";
                                })()}
                              </strong>
                              <span className="timeline-v2__clip-instruction">
                                {(() => {
                                  const asset = project.assets.find((item) => item.id === clip.audio_asset_id);
                                  return asset?.filename || asset?.tag || clip.audio_asset_id || "No audio";
                                })()}
                              </span>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}

              {shellMode && (
                <div className={trackRowClass(shellMode)}>
                  <TrackHeader label="MASK · REPAIR" labelKey="tracks.maskRepair" shellMode={shellMode} controls={["eye", "lock"]} />
                  <div className={trackContentClass(shellMode)}>
                    {repairWindows.length === 0 ? (
                      <div className="track-empty">Repair ranges will appear here when a batch needs a focused fix.</div>
                    ) : (
                      repairWindows.map((repair) => (
                        <button
                          key={repair.id}
                          type="button"
                          id={`timeline-track-item-repair-${repair.id}`}
                          className={`track-clip track-clip--repair ${sel?.selection?.kind === "repair" && sel.selection.id === repair.id ? "active" : ""}`}
                          style={pct(repair.start, repair.length, boardDuration)}
                          onClick={() => sel?.setSelection({ kind: "repair", id: repair.id })}
                        >
                          <strong>{repair.label}</strong>
                          <span>{repair.status}</span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
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
                    video_clips: tl.video_clips.map((c) =>
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
                    prompt_segments: tl.prompt_segments.map((s) =>
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
                    prompt_segments: tl.prompt_segments.map((s) =>
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
                    prompt_segments: tl.prompt_segments.map((s) =>
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
                  prompt_segments: tl.prompt_segments.map((s) =>
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
              Foley / ambience / music cues for Editor &amp; Audio Studio (labels only — no synthesis yet).
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
                      prompt_segments: tl.prompt_segments.map((s) =>
                        s.id === activeSeg.id
                          ? { ...s, audio_intent: (s.audio_intent || []).filter((x) => x !== intent) }
                          : s
                      ),
                    })
                  }
                >
                  {intent} ×
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
                      prompt_segments: tl.prompt_segments.map((s) =>
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
                    prompt_segments: tl.prompt_segments.map((s) =>
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
              {tagWarnings.join(" · ")}
            </div>
          )}
          <div className="row-actions">
            <button
              onClick={() =>
                save({
                  ...tl,
                  prompt_segments: tl.prompt_segments.map((s) =>
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
                    prompt_segments: tl.prompt_segments.map((s) =>
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

      {viewMode === "full" && <LipSyncTracksPanel project={project} scene={scene} onChange={onChange} />}
    </div>
  );
}

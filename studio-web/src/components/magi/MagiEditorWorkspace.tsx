import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { buildProjectWorkspaceLocation } from "../../navigation/projectWorkspaceNavigation";
import { describeMagiError } from "../../magiSequence/errors";
import type { Asset, Project } from "../../types";
import {
  applyEditCommand,
  clipSourceFrame,
  clipUnderPlayhead,
  createEmptySequence,
  frameToTimecode,
  recomputeDuration,
  type MagiClip,
  type MagiEditCommand,
  type MagiFinishingState,
  type MagiSequenceDocument,
  type MagiTrack,
  migrateToPostProductionTracks,
  mergeGraphicsIntoSequence,
  isGraphicsClipId,
  overlayIdFromGraphicsClip,
  persistableSequenceClips,
  visibleMagiTracks,
  addOptionalObjectsTrack,
  removeOptionalObjectsTrack,
  canAddObjectsTrack,
  objectsSlotOf,
  isObjectsTrackKind,
} from "../../magiSequence";
import { fetchMagiSequence, MagiSaveConflictError, saveMagiSequence } from "../../magiSequence/api";
import { MagiFocusProvider, useMagiFocus } from "../../magiSequence";
import { useMagiKeyboard } from "../../magiSequence/useMagiKeyboard";
import { stepMagiZoom } from "./magiTimelineScale";
import { TimelineGpuPane } from "../timeline-master/TimelineGpuPane";
import { TimelineHotKeysPane } from "../timeline-master/TimelineHotKeysPane";
import { JobPanel } from "../JobPanel";
import { MagiSequenceTimeline, type MagiTimelineMedia } from "./MagiSequenceTimeline";
import { MagiCutPreview } from "./MagiCutPreview";
import { blendAtPlayhead, blendSourceSeconds, clipEdgeRole, edgeFadeAtPlayhead, maxEdgeFadeSeconds, resolveOutgoingCut, transitionPreviewFrame } from "../../magiSequence/transitions";
import { MagiWorkspaceStack } from "./MagiWorkspaceStack";
import { MagiAccordion } from "./layout/MagiAccordion";
import { MagiWorkspaceLayoutProvider, useMagiLayout } from "./layout/MagiWorkspaceLayoutProvider";
import { nextDualDrawerCollapsed, type MagiPaneId, type MagiPreset } from "./layout/MagiLayoutPersistence";
import { MagiOverlayLayer } from "./overlays/MagiOverlayLayer";
import { MagiOverlayInspector } from "./overlays/MagiOverlayInspector";
import { MagiEditorCommandStack } from "./overlays/MagiEditorCommandStack";
import { MagiCompareFitMedia, MagiPreviewFitFrame } from "./MagiPreviewFitFrame";
import { MagiVideoStage } from "./MagiVideoStage";
import { MagiSplitView } from "./MagiSplitView";
import { MagiPreviewMixer, audioLaneOwnsPlayback } from "./MagiPreviewMixer";
import {
  advanceTimelineFrame,
  bindMagiPlaybackStats,
  timelineFrameFromMediaSeconds,
} from "./magiPlaybackClock";
import { AddFromProjectLibraryModal } from "../timeline-master/AddFromProjectLibraryModal";
import { MagiPreviewTransport } from "./MagiPreviewTransport";
import {
  aspectLabel,
  defaultTargetId,
  meaningfulTargets,
  normalizeUpscaleTargetId,
  resolveUpscaleTarget,
} from "../../timelineMaster/magiUpscaleTargets";
import { libraryThumbKind, libraryThumbUrl } from "../library/libraryThumb";
import { composeLiveGrade, liveGradeCssFilter, MAGI_LIGHTING_PRESETS } from "../../magiSequence/liveGrade";
import {
  applyFinalRenderJob,
  buildFinalRenderConfirm,
  emptyFinalRenderSession,
  monitorPreviewAssetId,
  type FinalRenderSession,
} from "../../magiSequence/finalRenderConfirm";
import { finalVideoNameMessage, normalizeFinalVideoName, suggestedFinalVideoName } from "../../magiSequence/finalRenderName";
import { MagiFinalRenderDialog } from "./MagiFinalRenderDialog";
import { ingestMasterAssetId, resolveSplitOriginalAssetId, resolveSplitProcessed } from "../../magiSequence/splitViewSource";
import { useMagiOverlayState } from "./overlays/useMagiOverlayState";
import type { MagiOverlayComposition } from "./overlays/types";
import { flattenOverlayIds, overlayObjectsTrack } from "./overlays/types";
import {
  WorkspaceFullscreenBanner,
  WorkspaceFullscreenControls,
  useWorkspaceFullscreen,
  type WorkspaceViewportMode,
} from "../../workspace/fullscreen";
import { proposeFromCommand } from "./magiCommandParse";
import "../../styles/timeline-master/timeline-v2-shell.css";
import "../../styles/film-timeline.css";
import "./magi-editor.css";

const MAGI_SIDE_TAB_KEY = "adept_magi_side_tab";
type MagiSideTab = "inspector" | "hotkeys" | "gpu";

function loadMagiSideTab(): MagiSideTab {
  try {
    const saved = localStorage.getItem(MAGI_SIDE_TAB_KEY);
    if (saved === "hotkeys" || saved === "gpu" || saved === "inspector") return saved;
  } catch {
    /* keep inspector */
  }
  return "inspector";
}

const PRODUCTION_CORRECTION_RE = /\b(re-?take|inpaint|mask\s*repair|timed\s*prompt)\b/;
const PRODUCTION_CORRECTION_COPY =
  "That is a production correction. Return to Timeline for Re-Take — MAGI only finishes completed takes.";

type ViewerMode = "viewer" | "compare" | "split" | "histogram" | "vectorscope";

/** Fit, Histogram, and Vectorscope stay in this file for a later MAGI update. */
const SHOW_SHELVED_MONITOR_CHROME = false;

type ProposalKind =
  | "trim"
  | "replace_clip"
  | "add_dissolve"
  | "stabilize"
  | "brighten"
  | "remove_silence"
  | "add_ambience"
  | "extend_reaction"
  | "overlay_text"
  | "overlay_lower_third"
  | "overlay_shape";

type PendingProposal = {
  kind: ProposalKind;
  title: string;
  summary: string;
  approveLabel: string;
};

/** Placebo finishing actions: no real dissolve/stabilize/brighten/silence engines. */
type UnsupportedPlaceboKind = "add_dissolve" | "stabilize" | "brighten" | "remove_silence";

const UNSUPPORTED_PLACEBO_KINDS = new Set<ProposalKind>([
  "add_dissolve",
  "stabilize",
  "brighten",
  "remove_silence",
]);

const UNSUPPORTED_PLACEBO_COPY: Record<
  UnsupportedPlaceboKind,
  { title: string; summary: string; refuseMessage: string; chipLabel: string }
> = {
  add_dissolve: {
    title: "Dissolve unavailable",
    summary:
      "MAGI has no dissolve/xfade engine yet. This will not change media or export — delivery still uses hard cuts.",
    refuseMessage:
      "Dissolve refused: no dissolve engine in MAGI. Sequence and export stay hard-cut. Use Color / Upscale for real finishing.",
    chipLabel: "Dissolve (unavailable)",
  },
  stabilize: {
    title: "Stabilize unavailable",
    summary:
      "MAGI has no stabilize engine yet. Approving will not add FX or change export pixels.",
    refuseMessage:
      "Stabilize refused: no stabilize engine in MAGI. No FX marker or bake will be created.",
    chipLabel: "Stabilize (unavailable)",
  },
  brighten: {
    title: "Brighten pass unavailable",
    summary:
      "MAGI has no dedicated brighten engine. Use Color grade (Exposure) for real brightness changes.",
    refuseMessage:
      "Brighten refused: no brighten engine. Use Inspector Color → Exposure instead.",
    chipLabel: "Brighten (unavailable)",
  },
  remove_silence: {
    title: "Remove silence unavailable",
    summary:
      "MAGI has no silence-detection engine. Approving will not analyze or trim audio for silence.",
    refuseMessage:
      "Remove silence refused: no silence analysis in MAGI. Use Trim manually or Audio Studio tools when available.",
    chipLabel: "Remove Silence (unavailable)",
  },
};

function isUnsupportedPlacebo(kind: ProposalKind): kind is UnsupportedPlaceboKind {
  return UNSUPPORTED_PLACEBO_KINDS.has(kind);
}

type HistorySnapshot = {
  sequence: MagiSequenceDocument;
  selection: string[];
  viewerAssetId: string | null;
  compareAssetId: string;
  overlayAssetId: string | null;
  overlayComposition: MagiOverlayComposition;
  overlaySelectedId: string | null;
};

const RECIPE_PRESETS = [
  { id: "music-video", name: "Music Video", detail: "Fast cuts with snapping on and open FX lanes." },
  { id: "commercial", name: "Commercial", detail: "Tight brand timing with brighter finishing cues." },
  { id: "interview", name: "Interview", detail: "Dialogue-first layout with steady viewer focus." },
  { id: "podcast", name: "Podcast", detail: "Audio-first layout with safe text lanes ready." },
  { id: "narrative", name: "Narrative", detail: "Story-first assembly with balanced track defaults." },
  { id: "trailer", name: "Trailer", detail: "Aggressive pacing, markers, and transition-ready tracks." },
  { id: "documentary", name: "Documentary", detail: "Reference-heavy cut with calm snap behavior." },
  { id: "anime", name: "Anime", detail: "Strong Objects lane and fast reaction coverage." },
  { id: "cinematic", name: "Cinematic", detail: "Wide pacing with overlay and adjustment headroom." },
  { id: "social", name: "Social", detail: "Punchy short-form setup with quick insert defaults." },
] as const;

function StatusBadge({ status }: { status: string }) {
  return <span className={`magi-status-badge ${status}`}>{status}</span>;
}

function MagiNotice({
  children,
  onClose,
  testId,
  trailing,
}: {
  children: ReactNode;
  onClose: () => void;
  testId?: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="magi-msg magi-msg--action" role="status" data-testid={testId}>
      <span className="magi-msg__text">{children}</span>
      {trailing}
      <button type="button" className="magi-msg__close" aria-label="Close notice" onClick={onClose}>
        ×
      </button>
    </div>
  );
}

function assetKindGroup(asset?: Asset | null): "video" | "image" | "audio" {
  if (!asset) return "image";
  if (asset.kind === "video") return "video";
  if (asset.kind === "audio" || asset.kind === "music" || asset.kind === "sfx") return "audio";
  return "image";
}

function clipForTrackKind(track: MagiTrack, asset: Asset) {
  if (asset.kind === "music") return track.kind === "music";
  if (asset.kind === "sfx") return track.kind === "sfx";
  if (asset.kind === "audio") return track.kind === "audio";
  if (asset.kind === "video" || asset.kind === "image") return track.kind === "video";
  return track.kind === "video";
}

function defaultTrackForAsset(sequence: MagiSequenceDocument, asset: Asset): MagiTrack | undefined {
  return sequence.tracks.find((track) => clipForTrackKind(track, asset)) || sequence.tracks[0];
}

function defaultDurationFrames(sequence: MagiSequenceDocument, asset: Asset): number {
  const fps = Math.max(1, sequence.frameRate);
  if (asset.kind === "video") return fps * 5;
  if (asset.kind === "audio" || asset.kind === "music" || asset.kind === "sfx") return fps * 4;
  return fps * 3;
}

function overlayTimingFromPlayhead(sequence: MagiSequenceDocument, durationSec = 5) {
  const startFrame = Math.max(0, sequence.playheadFrame);
  const endFrame = startFrame + Math.max(1, Math.round(sequence.frameRate * durationSec));
  return { startFrame, endFrame };
}

function recipeTracks(sequence: MagiSequenceDocument, recipeId: string): MagiTrack[] {
  return sequence.tracks.map((track) => {
    if (recipeId === "podcast") {
      return {
        ...track,
        muted: track.kind === "video",
        solo: track.kind === "audio",
        locked: false,
      };
    }
    if (recipeId === "trailer" || recipeId === "anime" || recipeId === "music-video") {
      return {
        ...track,
        muted: false,
        solo: false,
        locked: false,
      };
    }
    if (recipeId === "interview" || recipeId === "documentary") {
      return {
        ...track,
        muted: track.kind === "sfx",
        solo: false,
        locked: false,
      };
    }
    return { ...track, muted: false, solo: false, locked: false };
  });
}

function recipeSnapEnabled(recipeId: string): boolean {
  return recipeId !== "podcast" && recipeId !== "documentary";
}

function commandProposal(command: string): PendingProposal | null {
  const text = command.trim().toLowerCase();
  if (!text) return null;
  if (PRODUCTION_CORRECTION_RE.test(text)) {
    return null;
  }
  if (text.includes("lower third")) {
    return {
      kind: "overlay_lower_third",
      title: "Add lower third",
      summary: "Create a lower-third graphic on the current preview asset after approval.",
      approveLabel: "Approve lower third",
    };
  }
  if (text.includes("title") || text.includes("headline") || text.includes("add text")) {
    return {
      kind: "overlay_text",
      title: "Add text overlay",
      summary: "Create a text overlay on the current preview asset after approval.",
      approveLabel: "Approve text",
    };
  }
  if (text.includes("shape") || text.includes("box")) {
    return {
      kind: "overlay_shape",
      title: "Add shape overlay",
      summary: "Create a graphic shape overlay on the current preview asset after approval.",
      approveLabel: "Approve shape",
    };
  }
  if (text.includes("dissolve") || text.includes("wipe") || text.includes("brighten") || text.includes("stabilize")) {
    return null;
  }
  if (text.includes("silence")) {
    const copy = UNSUPPORTED_PLACEBO_COPY.remove_silence;
    return {
      kind: "remove_silence",
      title: copy.title,
      summary: copy.summary,
      approveLabel: "Acknowledge",
    };
  }
  if (text.includes("ambience")) {
    return {
      kind: "add_ambience",
      title: "Add ambience bed",
      summary: "Insert ambience on the lower audio lane after approval.",
      approveLabel: "Approve ambience",
    };
  }
  if (text.includes("reaction") || text.includes("extend")) {
    return {
      kind: "extend_reaction",
      title: "Extend reaction",
      summary: "Duplicate the selected picture beat to give the reaction more room.",
      approveLabel: "Approve extension",
    };
  }
  if (text.includes("replace")) {
    return {
      kind: "replace_clip",
      title: "Replace selected clip",
      summary: "Swap the selected timeline clip to the highlighted Library asset after approval.",
      approveLabel: "Approve replacement",
    };
  }
  if (text.includes("trim") || text.includes("tighten")) {
    return {
      kind: "trim",
      title: "Trim selected clip",
      summary: "Trim the selected clip by half a second from the tail after approval.",
      approveLabel: "Approve trim",
    };
  }
  return null;
}

function MagiEditorInner({
  project,
  onChange,
}: {
  project: Project;
  onChange: () => Promise<void>;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const handoffAssetId = String(searchParams.get("assetId") || "").trim();
  const handoffSceneId = String(searchParams.get("sceneId") || "").trim();
  const timelineImportKeyRef = useRef("");
  const {
    layout,
    setAccordion,
    setLeftWidth,
    setRightWidth,
    toggleLeftDock,
    toggleRightDock,
    setBothDocksCollapsed,
    movePane,
    reorderPane,
    applyWorkspacePreset,
    resetWorkspace,
    setRenderQueueOpen,
    compactNotice,
  } = useMagiLayout();
  const { bindRegionProps, focusRegion, setFocusRegion } = useMagiFocus();
  const [viewportMode, setViewportMode] = useState<WorkspaceViewportMode>("STANDARD");
  const workspaceFs = useWorkspaceFullscreen({
    workspaceId: "magi",
    viewMode: viewportMode,
    onRestoreViewMode: (mode) => setViewportMode(mode),
  });

  const images = useMemo(() => project.assets.filter((asset) => assetKindGroup(asset) === "image"), [project.assets]);
  const videos = useMemo(() => project.assets.filter((asset) => assetKindGroup(asset) === "video"), [project.assets]);
  const audioAssets = useMemo(() => project.assets.filter((asset) => assetKindGroup(asset) === "audio"), [project.assets]);
  const mediaAssets = useMemo(() => [...videos, ...images, ...audioAssets], [audioAssets, images, videos]);
  const timelineMedia = useMemo(() => {
    const out: Record<string, MagiTimelineMedia> = {};
    for (const asset of mediaAssets) {
      const kind = assetKindGroup(asset);
      out[asset.id] = {
        kind,
        thumbUrl: libraryThumbUrl(project.id, asset.id, asset.kind),
        mediaUrl: api.assetUrl(asset.id),
      };
    }
    return out;
  }, [mediaAssets, project.id]);

  const [sequence, setSequence] = useState<MagiSequenceDocument | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [selectedObjectsSlot, setSelectedObjectsSlot] = useState<1 | 2>(1);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [viewerMode, setViewerMode] = useState<ViewerMode>("viewer");
  const [sideTab, setSideTab] = useState<MagiSideTab>(loadMagiSideTab);
  useEffect(() => {
    try {
      localStorage.setItem(MAGI_SIDE_TAB_KEY, sideTab);
    } catch {
      /* tab still works for this visit */
    }
  }, [sideTab]);
  const [viewerAssetId, setViewerAssetId] = useState<string | null>(null);
  const [previewPinAssetId, setPreviewPinAssetId] = useState<string | null>(null);
  const [libraryFocusId, setLibraryFocusId] = useState<string | null>(null);
  const [queueFocusJobId, setQueueFocusJobId] = useState<string | null>(null);
  const [compareAssetId, setCompareAssetId] = useState("");
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [imageOverlayPickerOpen, setImageOverlayPickerOpen] = useState(false);
  const [previewMuted, setPreviewMuted] = useState(false);
  const [previewVolume, setPreviewVolume] = useState(1);
  const [volumeOpen, setVolumeOpen] = useState(false);
  const [failedThumbs, setFailedThumbs] = useState<Record<string, boolean>>({});
  const [publishedMasterId, setPublishedMasterId] = useState<string | null>(null);
  const [assetFilter, setAssetFilter] = useState<"all" | "video" | "image" | "audio">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [hideUnpublishedNotice, setHideUnpublishedNotice] = useState(false);
  const [hideCompactNotice, setHideCompactNotice] = useState(false);
  const [unpublishedSceneId, setUnpublishedSceneId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [seekGeneration, setSeekGeneration] = useState(0);
  const [command, setCommand] = useState("");
  const [pendingProposal, setPendingProposal] = useState<PendingProposal | null>(null);
  const [, setHistoryTick] = useState(0);
  const [editVersion, setEditVersion] = useState(0);
  const [lastSavedEditVersion, setLastSavedEditVersion] = useState(0);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [serverRevision, setServerRevision] = useState<number>(0);
  const [overlayPersist, setOverlayPersist] = useState({ dirty: false, saving: false, error: null as string | null });
  const [pendingOverlayRestore, setPendingOverlayRestore] = useState<HistorySnapshot | null>(null);
  const clipboardRef = useRef<string[]>([]);
  const historyRef = useRef(new MagiEditorCommandStack<HistorySnapshot>());
  const sequenceRef = useRef<MagiSequenceDocument | null>(null);
  const selectionRef = useRef<string[]>([]);
  const viewerAssetRef = useRef<string | null>(null);
  const compareAssetRef = useRef("");
  const overlayAssetRef = useRef<string | null>(null);
  const overlayCompositionRef = useRef<MagiOverlayComposition | null>(null);
  const overlaySelectionRef = useRef<string | null>(null);
  const editVersionRef = useRef(0);
  const lastSavedEditVersionRef = useRef(0);
  const serverRevisionRef = useRef(0);
  const saveNonceRef = useRef(0);
  const overlayDirtyRef = useRef(false);
  const overlayPersistNowRef = useRef<() => Promise<unknown>>(() => Promise.resolve());
  const playingRef = useRef(false);
  const dragRef = useRef<{ side: "left" | "right"; start: number; size: number } | null>(null);

  const overlays = useMagiOverlayState(project.id, publishedMasterId || viewerAssetId || "", {
    onHistoryCommit: (entry) => {
      if (!sequenceRef.current) return;
      const before = captureSnapshot({
        overlayAssetId: viewerAssetRef.current,
        overlayComposition: entry.before,
        overlaySelectedId: entry.selectedOverlayId,
      });
      const after = captureSnapshot({
        overlayAssetId: viewerAssetRef.current,
        overlayComposition: entry.after,
        overlaySelectedId: overlaySelectionRef.current,
      });
      historyRef.current.push(entry.type, entry.label, before, after);
      setHistoryTick((tick) => tick + 1);
    },
    onPersistStateChange: setOverlayPersist,
  });

  sequenceRef.current = sequence;
  playingRef.current = playing;
  selectionRef.current = selection;
  viewerAssetRef.current = viewerAssetId;
  compareAssetRef.current = compareAssetId;
  overlayAssetRef.current = publishedMasterId || viewerAssetId;
  overlayCompositionRef.current = overlays.composition;
  overlaySelectionRef.current = overlays.selectedOverlayId;
  editVersionRef.current = editVersion;
  overlayDirtyRef.current = overlayPersist.dirty;
  overlayPersistNowRef.current = overlays.persistNow;

  const currentAsset = useMemo(
    () => mediaAssets.find((asset) => asset.id === viewerAssetId) || null,
    [mediaAssets, viewerAssetId],
  );
  const compareAsset = useMemo(
    () => mediaAssets.find((asset) => asset.id === compareAssetId) || null,
    [compareAssetId, mediaAssets],
  );
  const sequenceForTimeline = useMemo(
    () => (sequence ? mergeGraphicsIntoSequence(sequence, overlays.composition.overlays) : null),
    [overlays.composition.overlays, sequence],
  );
  const selectedClips = useMemo(() => {
    const doc = sequenceForTimeline || sequence;
    if (!doc) return [] as MagiClip[];
    const ids = new Set(selection);
    return doc.clips.filter((clip) => ids.has(clip.id));
  }, [selection, sequence, sequenceForTimeline]);
  const selectedClip = selectedClips[0] || null;

  // m3: frame-synced preview — the clip under the playhead drives which asset
  // is previewed and at which source time (video), so What-You-See tracks the
  // playhead instead of a free-running loop.
  const playheadClip = useMemo(() => {
    if (!sequence) return null;
    const picture =
      clipUnderPlayhead(sequence, sequence.playheadFrame, "video") ||
      clipUnderPlayhead(sequence, sequence.playheadFrame, "image");
    if (!picture) return null;
    const track = sequence.tracks.find((item) => item.id === picture.trackId);
    if (track?.hidden) return null;
    return picture;
  }, [sequence]);
  const pictureTrackHidden = useMemo(() => {
    if (!sequence) return false;
    const picture =
      clipUnderPlayhead(sequence, sequence.playheadFrame, "video") ||
      clipUnderPlayhead(sequence, sequence.playheadFrame, "image");
    if (!picture) return false;
    return Boolean(sequence.tracks.find((item) => item.id === picture.trackId)?.hidden);
  }, [sequence]);
  const hiddenObjectsSlots = useMemo(() => {
    const slots = new Set<number>();
    for (const track of sequence?.tracks || []) {
      if (!track.hidden) continue;
      const slot = objectsSlotOf(track);
      if (slot) slots.add(slot);
    }
    return slots;
  }, [sequence]);
  const previewAssetId = monitorPreviewAssetId(
    previewPinAssetId,
    pictureTrackHidden ? null : playheadClip?.assetId,
    viewerAssetId,
  );
  const previewAsset = useMemo(
    () => mediaAssets.find((asset) => asset.id === previewAssetId) || null,
    [mediaAssets, previewAssetId],
  );
  useEffect(() => {
    if (!libraryFocusId) return;
    const node = document.querySelector(`[data-testid="magi-media-${CSS.escape(libraryFocusId)}"]`);
    if (!(node instanceof HTMLElement)) return;
    node.scrollIntoView({ block: "nearest", inline: "nearest" });
    setLibraryFocusId(null);
  }, [assetFilter, layout.accordionState, layout.leftDockCollapsed, layout.rightDockCollapsed, libraryFocusId, mediaAssets]);

  const previewVideoTime = useMemo(() => {
    if (!sequence || !playheadClip) return null;
    const sourceFrame = clipSourceFrame(playheadClip, sequence.playheadFrame);
    if (sourceFrame == null) return null;
    return sourceFrame / Math.max(1, sequence.frameRate);
  }, [playheadClip, sequence]);
  const [previewSourceSize, setPreviewSourceSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    setPreviewSourceSize({ w: 0, h: 0 });
  }, [previewAsset?.id]);

  // m2: failed-media tracking — a broken <img>/<video> marks its asset so the
  // viewer + timeline show a recovery badge and the editor stays usable.
  const [failedMedia, setFailedMedia] = useState<Record<string, boolean>>({});
  const markMediaFailed = useCallback((assetId: string) => {
    setFailedMedia((prev) => (prev[assetId] ? prev : { ...prev, [assetId]: true }));
  }, []);
  const failedMediaIds = useMemo(
    () => new Set(Object.keys(failedMedia).filter((id) => failedMedia[id])),
    [failedMedia],
  );

  const libraryAssets = useMemo(() => {
    const pinned = new Set(
      [publishedMasterId, ingestMasterAssetId(sequence?.clips, handoffSceneId)].filter(Boolean) as string[],
    );
    const rows = [...mediaAssets];
    rows.sort((a, b) => {
      const ap = pinned.has(a.id) ? 0 : 1;
      const bp = pinned.has(b.id) ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return (a.tag || a.filename).localeCompare(b.tag || b.filename);
    });
    return rows;
  }, [handoffSceneId, mediaAssets, publishedMasterId, sequence?.clips]);

  const filteredAssets = useMemo(() => {
    if (assetFilter === "all") return libraryAssets;
    return libraryAssets.filter((asset) => assetKindGroup(asset) === assetFilter);
  }, [assetFilter, libraryAssets]);

  const captureSnapshot = useCallback(
    (overrides?: Partial<HistorySnapshot>): HistorySnapshot => {
      if (!sequenceRef.current || !overlayCompositionRef.current) {
        throw new Error("MAGI snapshot requested before editor was ready");
      }
      return {
        sequence: structuredClone(sequenceRef.current),
        selection: [...selectionRef.current],
        viewerAssetId: viewerAssetRef.current,
        compareAssetId: compareAssetRef.current,
        overlayAssetId: overlayAssetRef.current,
        overlayComposition: structuredClone(overlayCompositionRef.current),
        overlaySelectedId: overlaySelectionRef.current,
        ...overrides,
      };
    },
    [],
  );

  const sequenceDirty = editVersion !== lastSavedEditVersion;
  const editorDirty = sequenceDirty || overlayPersist.dirty;

  const syncSelectionViewer = useCallback(
    (nextSelection: string[], nextSequence: MagiSequenceDocument) => {
      setSelection(nextSelection);
      const clip = nextSelection.length ? nextSequence.clips.find((item) => item.id === nextSelection[0]) : null;
      if (clip?.assetId) {
        setViewerAssetId(clip.assetId);
      }
    },
    [],
  );

  // m7 stale-selection-after-delete guard: the authoritative selection must only
  // ever reference clips that still exist, so the inspector can never show a
  // removed entity.
  const existingClipIds = useMemo(() => new Set((sequence?.clips || []).map((clip) => clip.id)), [sequence]);
  useEffect(() => {
    if (selection.some((id) => !existingClipIds.has(id))) {
      const pruned = selection.filter((id) => existingClipIds.has(id));
      selectionRef.current = pruned;
      setSelection(pruned);
    }
  }, [selection, existingClipIds]);

  const bootstrapAssetsRef = useRef({ mediaAssets, images, videos, audioAssets });
  bootstrapAssetsRef.current = { mediaAssets, images, videos, audioAssets };

  useEffect(() => {
    let cancelled = false;
    setSequence(null);
    setSelection([]);
    setPendingProposal(null);
    setCommand("");
    setMessage(null);
    setSaveError(null);
    setSaveState("idle");
    setEditVersion(0);
    setLastSavedEditVersion(0);
    setServerRevision(0);
    (async () => {
      try {
        const raw = await fetchMagiSequence(project.id);
        const loaded = migrateToPostProductionTracks(raw);
        if (cancelled) return;
        setSequence(loaded);
        if (loaded !== raw) {
          setEditVersion(1);
        }
        setServerRevision(loaded.revision);
        serverRevisionRef.current = loaded.revision;
        lastSavedEditVersionRef.current = 0;
        const assets = bootstrapAssetsRef.current;
        const published =
          loaded.clips.find((clip) => clip.ingestRole === "published_master")?.assetId || null;
        if (published) setPublishedMasterId(published);
        const firstAssetId =
          published ||
          loaded.clips[0]?.assetId ||
          assets.mediaAssets[0]?.id ||
          assets.images[0]?.id ||
          assets.videos[0]?.id ||
          assets.audioAssets[0]?.id ||
          null;
        setViewerAssetId(firstAssetId);
      } catch {
        if (cancelled) return;
        const fallback = migrateToPostProductionTracks(createEmptySequence(project.id, project.fps || 24));
        setSequence(fallback);
        setViewerAssetId(bootstrapAssetsRef.current.mediaAssets[0]?.id || null);
        setMessage("Started a fresh MAGI sequence locally because no saved sequence was available.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // Asset list refreshes (Render Queue onDone) must not tear the editor down.
  }, [project.fps, project.id]);

  const saveSequence = useCallback(async () => {
    if (!sequenceRef.current) return;
    const snapshot = structuredClone(sequenceRef.current);
    snapshot.clips = persistableSequenceClips(snapshot.clips);
    const capturedEditVersion = editVersionRef.current;
    const nonce = ++saveNonceRef.current;
    setSaveState("saving");
    setSaveError(null);
    try {
      // m1 A3: optimistic concurrency — send the revision the editor last
      // observed; the server refuses a stale write with 409.
      const expectedRevision = serverRevisionRef.current || undefined;
      const saved = await saveMagiSequence(project.id, snapshot, expectedRevision);
      setServerRevision(saved.revision);
      serverRevisionRef.current = saved.revision;
      if (capturedEditVersion === editVersionRef.current) {
        setSequence(saved);
        setLastSavedEditVersion(capturedEditVersion);
        lastSavedEditVersionRef.current = capturedEditVersion;
      }
      if (nonce === saveNonceRef.current) {
        setSaveState("saved");
      }
    } catch (error: unknown) {
      if (nonce !== saveNonceRef.current) return;
      if (error instanceof MagiSaveConflictError && error.currentRevision > 0) {
        serverRevisionRef.current = error.currentRevision;
        setServerRevision(error.currentRevision);
      }
      setSaveState("error");
      setSaveError(error instanceof Error ? error.message : "MAGI sequence save failed");
    }
  }, [project.id]);

  useEffect(() => {
    if (!sequence) return;
    if (!sequenceDirty) return;
    const timer = window.setTimeout(() => {
      void saveSequence();
    }, 500);
    return () => window.clearTimeout(timer);
  }, [saveSequence, sequence, sequenceDirty]);

  // m1 P1/A5: never drop a pending autosave on unmount/route-change/unload.
  // Single flush path covers both the sequence and the overlay store: the
  // debounce timers are each cleared before the flush fires, so a pending PUT
  // is delivered instead of silently dropped.
  useEffect(() => {
    const flush = () => {
      if (sequenceRef.current && editVersionRef.current !== lastSavedEditVersionRef.current) {
        void saveSequence();
      }
      if (overlayDirtyRef.current) {
        void overlayPersistNowRef.current().catch(() => undefined);
      }
    };
    window.addEventListener("beforeunload", flush);
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", flush);
    return () => {
      window.removeEventListener("beforeunload", flush);
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", flush);
      flush();
    };
  }, [saveSequence]);

  const gapClockRef = useRef<{ wallMs: number; frame: number } | null>(null);
  const followMediaClock = useCallback((seconds: number) => {
    const current = sequenceRef.current;
    if (!current || !playingRef.current) {
      gapClockRef.current = null;
      return;
    }
    const fps = Math.max(1, current.frameRate);
    const duration = recomputeDuration(current);
    const picture =
      clipUnderPlayhead(current, current.playheadFrame, "video") ||
      clipUnderPlayhead(current, current.playheadFrame, "image");
    const commit = (frame: number) => {
      if (frame >= duration) {
        setPlaying(false);
        gapClockRef.current = null;
        const last = Math.max(0, duration - 1);
        setSequence((prev) => (prev && prev.playheadFrame !== last ? { ...prev, playheadFrame: last } : prev));
        return;
      }
      if (current.playheadFrame === frame) return;
      setSequence((prev) => {
        if (!prev || prev.playheadFrame === frame) return prev;
        return { ...prev, playheadFrame: frame };
      });
    };
    if (picture && picture.durationFrames > 0) {
      const end = picture.startFrame + picture.durationFrames;
      // Once the playhead is on the clip's exclusive end, that clip is finished.
      // The viewer still resolves the last frame there; the clock must not.
      if (current.playheadFrame < end) {
        const mapped = timelineFrameFromMediaSeconds(picture, seconds, fps);
        gapClockRef.current = null;
        commit(mapped === "past-out" ? end : mapped);
        return;
      }
    }
    // No picture owns this frame (the trimmed chunk, or the clip just ended).
    // Keep timeline time. Do not read the file's later timecode as the playhead.
    const now = performance.now();
    const anchor = gapClockRef.current;
    if (!anchor || anchor.frame !== current.playheadFrame) {
      gapClockRef.current = { wallMs: now, frame: current.playheadFrame };
      return;
    }
    const next = advanceTimelineFrame(current.playheadFrame, (now - anchor.wallMs) / 1000, fps, duration);
    if (next === current.playheadFrame) return;
    gapClockRef.current = { wallMs: now, frame: next };
    commit(next);
  }, []);

  const stopAtMediaEnd = useCallback(() => {
    setPlaying(false);
    const current = sequenceRef.current;
    if (!current) return;
    const last = Math.max(0, recomputeDuration(current) - 1);
    setSequence((prev) => (prev ? { ...prev, playheadFrame: last } : prev));
  }, []);

  useEffect(() => {
    if (!pendingOverlayRestore || pendingOverlayRestore.overlayAssetId !== viewerAssetId) return;
    overlays.replaceComposition(pendingOverlayRestore.overlayComposition, pendingOverlayRestore.overlaySelectedId);
    setPendingOverlayRestore(null);
  }, [overlays, pendingOverlayRestore, viewerAssetId]);

  const bumpEditVersion = () => setEditVersion((value) => value + 1);

  // m1 P5 fix: transport seeks (scrub, frame-step, J/L jog, Home/End) update the
  // playhead WITHOUT pushing a history entry or bumping editVersion, so seeking
  // never marks the document dirty and never triggers autosave.
  const seekPlayhead = useCallback(
    (frame: number) => {
      if (!sequenceRef.current) return;
      const result = applyEditCommand(
        sequenceRef.current,
        { kind: "SetPlayhead", payload: { frame } },
        selectionRef.current,
      );
      setSequence(result.doc);
      setSeekGeneration((value) => value + 1);
    },
    [],
  );

  const pushSequenceCommand = useCallback(
    (label: string, command: MagiEditCommand) => {
      if (!sequenceRef.current) return;
      const before = captureSnapshot();
      const result = applyEditCommand(sequenceRef.current, command, selectionRef.current);
      setSequence(result.doc);
      syncSelectionViewer(result.selection, result.doc);
      historyRef.current.push(command.kind, label, before, {
        ...before,
        sequence: structuredClone(result.doc),
        selection: [...result.selection],
        viewerAssetId:
          result.selection[0]
            ? result.doc.clips.find((clip) => clip.id === result.selection[0])?.assetId || before.viewerAssetId
            : before.viewerAssetId,
      });
      setHistoryTick((tick) => tick + 1);
      bumpEditVersion();
    },
    [captureSnapshot, syncSelectionViewer],
  );

  const mutateSequence = useCallback(
    (type: string, label: string, mutator: (current: MagiSequenceDocument) => { doc: MagiSequenceDocument; selection?: string[] }) => {
      if (!sequenceRef.current) return;
      const before = captureSnapshot();
      const result = mutator(structuredClone(sequenceRef.current));
      setSequence(result.doc);
      const nextSelection = result.selection ?? selectionRef.current;
      syncSelectionViewer(nextSelection, result.doc);
      historyRef.current.push(type, label, before, {
        ...before,
        sequence: structuredClone(result.doc),
        selection: [...nextSelection],
        viewerAssetId:
          nextSelection[0]
            ? result.doc.clips.find((clip) => clip.id === nextSelection[0])?.assetId || before.viewerAssetId
            : before.viewerAssetId,
      });
      setHistoryTick((tick) => tick + 1);
      bumpEditVersion();
    },
    [captureSnapshot, syncSelectionViewer],
  );

  const toggleTrackControl = useCallback(
    (trackId: string, control: "mute" | "eye") => {
      mutateSequence(control, control === "mute" ? "Mute track" : "Show or hide track", (current) => ({
        doc: {
          ...current,
          tracks: current.tracks.map((track) => {
            if (track.id !== trackId) return track;
            if (control === "mute") return { ...track, muted: !track.muted };
            return { ...track, hidden: !track.hidden };
          }),
        },
      }));
    },
    [mutateSequence],
  );

  const snapFrame = useCallback(
    (trackId: string, frame: number, ignoreClipId?: string) => {
      const current = sequenceRef.current;
      if (!current || !current.snapEnabled) return Math.max(0, frame);
      const threshold = Math.max(4, Math.round(current.frameRate * 0.2));
      const candidates = [
        current.playheadFrame,
        ...current.clips
          .filter((clip) => clip.trackId === trackId && clip.id !== ignoreClipId)
          .flatMap((clip) => [clip.startFrame, clip.startFrame + clip.durationFrames]),
      ];
      const target = candidates.find((candidate) => Math.abs(candidate - frame) <= threshold);
      return Math.max(0, target ?? frame);
    },
    [],
  );

  const saveAll = useCallback(async () => {
    await Promise.all([saveSequence(), overlays.persistNow()]);
    setMessage("Saved MAGI sequence and overlay state.");
  }, [overlays, saveSequence]);

  const [finishingJobId, setFinishingJobId] = useState<string | null>(null);
  const [finishingJob, setFinishingJob] = useState<{ status: string; stage: string; message: string; kind: string } | null>(null);
  const [finalRenderSession, setFinalRenderSession] = useState<FinalRenderSession | null>(null);
  const [finalOutputName, setFinalOutputName] = useState("");
  const finalRenderJobRef = useRef<string | null>(null);
  const finalRenderLock = useRef(false);
  const [gpuReady, setGpuReady] = useState(false);
  const [gpuMessage, setGpuMessage] = useState("GPU Upscaling unavailable. FFmpeg upscale remains available.");
  const [soundAnalysis, setSoundAnalysis] = useState<{ hasAudio?: boolean; infoLine?: string } | null>(null);
  const [soundRecommendation, setSoundRecommendation] = useState<{ profile?: string; reason?: string; label?: string } | null>(null);
  const [soundProfiles, setSoundProfiles] = useState<Array<{ id: string; label: string; available: boolean; unavailableReason?: string }>>([]);

  useEffect(() => {
    const assetId = currentAsset?.id;
    if (!project?.id || !assetId) {
      setSoundAnalysis(null);
      setSoundRecommendation(null);
      setSoundProfiles([]);
      return;
    }
    let cancelled = false;
    api.magi.analyzeUpscaleSound(project.id, assetId).then((result) => {
      if (cancelled) return;
      setSoundAnalysis(result.analysis || null);
      setSoundRecommendation(result.recommendation || null);
      setSoundProfiles(result.profiles || []);
    }).catch(() => {
      if (cancelled) return;
      setSoundAnalysis(null);
      setSoundRecommendation(null);
    });
    return () => {
      cancelled = true;
    };
  }, [currentAsset?.id, project.id]);

  const finishing: MagiFinishingState = sequence?.finishing || {};
  const activeClipId = selectedClip?.id || playheadClip?.id || "";
  const activeGrade = (activeClipId && finishing.clipGrades?.[activeClipId]) || {};
  const gradePreset = activeGrade.presetId || "";
  const gradeParams = activeGrade.params || {};
  const composedGrade = composeLiveGrade(gradePreset, gradeParams);
  const sliderValue = (key: string) => {
    const raw = Math.round(Number(composedGrade[key] ?? 0) * 100);
    if (!Number.isFinite(raw)) return 0;
    return Math.max(-50, Math.min(50, raw));
  };
  const audioRange = finishing.audio?.range || "entire";
  const upscaleEngine = finishing.upscale?.engine || "ffmpeg-scale";
  const upscaleModel = finishing.upscale?.model || (upscaleEngine === "ffmpeg-scale" ? "lanczos" : "realesrgan-x4plus");
  const upscaleTarget = finishing.upscale?.target || "";
  const upscaleChoices = previewSourceSize.w > 0 && previewSourceSize.h > 0
    ? meaningfulTargets(previewSourceSize.w, previewSourceSize.h)
    : meaningfulTargets(2, 1).map((row) => ({ ...row, width: 0, height: 0, aspect: "" }));
  const normalizedUpscaleTarget = normalizeUpscaleTargetId(upscaleTarget);
  const activeUpscaleTarget = upscaleChoices.some((row) => row.id === normalizedUpscaleTarget)
    ? normalizedUpscaleTarget
    : (previewSourceSize.w > 0 ? defaultTargetId(previewSourceSize.w, previewSourceSize.h) : normalizedUpscaleTarget || "1440p");
  const resolvedUpscale = previewSourceSize.w > 0 && previewSourceSize.h > 0 && activeUpscaleTarget
    ? resolveUpscaleTarget(previewSourceSize.w, previewSourceSize.h, activeUpscaleTarget)
    : null;
  const recommendedSound = soundRecommendation?.profile || "preserve_original";
  const rememberedSound = finishing.upscale?.soundSourceAssetId && finishing.upscale.soundSourceAssetId === currentAsset?.id
    ? finishing.upscale.soundProfile || ""
    : "";
  const selectedSound = rememberedSound || recommendedSound;
  const soundHasAudio = soundAnalysis?.hasAudio !== false && Boolean(soundAnalysis);
  const soundChoices = soundProfiles.length
    ? soundProfiles
    : [
        { id: "preserve_original", label: "Preserve Original", available: true },
        { id: "cinematic_stereo", label: "Cinematic Stereo", available: true },
        { id: "dialogue_enhance", label: "Dialogue Enhance", available: true },
        { id: "wide_stereo", label: "Wide Stereo", available: true },
        { id: "clean_restore", label: "Clean & Restore", available: true },
        { id: "cinema_51", label: "5.1 Cinema Upmix", available: true },
        { id: "cinema_71", label: "7.1 Cinema Upmix", available: true },
        { id: "headphone_spatial", label: "Headphone Spatial", available: true },
      ];
  const splitOriginalId = useMemo(
    () =>
      resolveSplitOriginalAssetId({
        publishedAssetId: publishedMasterId,
        ingestMasterAssetId: ingestMasterAssetId(sequence?.clips, handoffSceneId),
        currentAssetId: previewAssetId,
        assets: mediaAssets,
      }),
    [handoffSceneId, mediaAssets, previewAssetId, publishedMasterId, sequence?.clips],
  );
  const splitProcessed = useMemo(
    () =>
      resolveSplitProcessed({
        originalAssetId: splitOriginalId,
        visualResultAssetId: finishing.visualResultAssetId,
        playheadClip,
        finishing,
        assets: mediaAssets,
        liveGradeActive: true,
      }),
    [finishing, mediaAssets, playheadClip, splitOriginalId],
  );
  const liveFilter = liveGradeCssFilter(gradeParams, gradePreset);
  const viewerLiveFilter = liveFilter;
  const splitRightFilter = liveFilter;
  const pictureMuted =
    previewMuted || audioLaneOwnsPlayback(sequence, sequence?.playheadFrame || 0);
  const splitProcessedKind =
    assetKindGroup(mediaAssets.find((asset) => asset.id === (splitProcessed.assetId || splitOriginalId)) || previewAsset) ===
    "video"
      ? "video"
      : "image";
  const reloadSequence = useCallback(async () => {
    const raw = await fetchMagiSequence(project.id);
    const loaded = migrateToPostProductionTracks(raw);
    const captured = editVersionRef.current;
    saveNonceRef.current += 1;
    setServerRevision(loaded.revision);
    serverRevisionRef.current = loaded.revision;
    sequenceRef.current = loaded;
    setSequence(loaded);
    setSaveError(null);
    if (captured === editVersionRef.current) {
      setLastSavedEditVersion(captured);
      lastSavedEditVersionRef.current = captured;
      setSaveState("saved");
    } else {
      setSaveState((state) => (state === "error" ? "idle" : state));
    }
  }, [project.id]);

  const mergeRemoteClipGrades = useCallback(async () => {
    try {
      const raw = await fetchMagiSequence(project.id);
      const remoteGrades = raw.finishing?.clipGrades || {};
      setSequence((current) => {
        if (!current) return current;
        if (JSON.stringify(current.finishing?.clipGrades || {}) === JSON.stringify(remoteGrades)) {
          return current;
        }
        const next = {
          ...current,
          finishing: {
            ...(current.finishing || {}),
            clipGrades: remoteGrades,
          },
        };
        sequenceRef.current = next;
        return next;
      });
    } catch {
      /* keep the in-memory finishing.clipGrades already driving Split View */
    }
  }, [project.id]);

  useEffect(() => {
    const onMutated = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId?: string; toolId?: string }>).detail;
      if (!detail?.projectId || detail.projectId !== project.id) return;
      const tool = String(detail.toolId || "");
      if (tool && !/color|grade|graphics|overlay|magi\./i.test(tool)) return;
      void mergeRemoteClipGrades();
      void overlays.reloadFromServer();
    };
    window.addEventListener("adept:codirector-project-mutated", onMutated as EventListener);
    return () => window.removeEventListener("adept:codirector-project-mutated", onMutated as EventListener);
  }, [mergeRemoteClipGrades, overlays.reloadFromServer, project.id]);

  const patchFinishing = useCallback(
    (patch: MagiFinishingState) => {
      mutateSequence("finishing", "Update finishing", (current) => ({
        doc: {
          ...current,
          finishing: {
            ...(current.finishing || {}),
            ...patch,
            clipGrades: { ...(current.finishing?.clipGrades || {}), ...(patch.clipGrades || {}) },
            upscale: { ...(current.finishing?.upscale || {}), ...(patch.upscale || {}) },
            audio: { ...(current.finishing?.audio || {}), ...(patch.audio || {}) },
            render: { ...(current.finishing?.render || {}), ...(patch.render || {}) },
          },
        },
      }));
    },
    [mutateSequence],
  );

  const patchFinishingLive = useCallback((patch: MagiFinishingState) => {
    setSequence((current) => {
      if (!current) return current;
      const next = {
        ...current,
        finishing: {
          ...(current.finishing || {}),
          ...patch,
          clipGrades: { ...(current.finishing?.clipGrades || {}), ...(patch.clipGrades || {}) },
          upscale: { ...(current.finishing?.upscale || {}), ...(patch.upscale || {}) },
          audio: { ...(current.finishing?.audio || {}), ...(patch.audio || {}) },
          render: { ...(current.finishing?.render || {}), ...(patch.render || {}) },
        },
      };
      sequenceRef.current = next;
      return next;
    });
    bumpEditVersion();
  }, []);

  const setGradeParam = useCallback(
    (key: string, slider: number) => {
      if (!activeClipId) return;
      const next = { ...gradeParams, [key]: slider / 100 };
      patchFinishingLive({
        clipGrades: {
          [activeClipId]: {
            presetId: gradePreset,
            lightingPresetId: activeGrade.lightingPresetId,
            params: next,
          },
        },
      });
    },
    [activeClipId, activeGrade.lightingPresetId, gradeParams, gradePreset, patchFinishingLive],
  );

  const applyLightingPreset = useCallback(
    (presetId: string) => {
      if (!activeClipId) return;
      const preset = MAGI_LIGHTING_PRESETS[presetId] || {};
      const next = { ...gradeParams };
      for (const key of ["brightness", "highlights", "shadows", "temperature"]) {
        delete next[key];
      }
      Object.assign(next, preset);
      patchFinishingLive({
        clipGrades: {
          [activeClipId]: {
            presetId: gradePreset,
            lightingPresetId: presetId === "none" ? "" : presetId,
            params: next,
          },
        },
      });
    },
    [activeClipId, gradeParams, gradePreset, patchFinishingLive],
  );

  const setBoundaryTransition = useCallback(
    (kind: string, seconds: number) => {
      const doc = sequenceRef.current;
      const clipId = selectionRef.current[0];
      const clip = doc?.clips.find((item) => item.id === clipId);
      if (!doc || !clip) return;
      const cut = resolveOutgoingCut(doc, clip);
      const edge = clipEdgeRole(doc, clip);
      const opening = edge.last && cut.status === "last" && (kind === "fade" || kind === "none");
      if (kind !== "none" && !opening && (cut.status !== "cut" || cut.maxSeconds < 0.1)) return;
      const fps = Math.max(1, doc.frameRate || 24);
      const limit = cut.status === "cut" ? cut.maxSeconds : maxEdgeFadeSeconds(clip.durationFrames, fps) || 0.1;
      const clamped = Math.min(limit, Math.max(0.1, seconds));
      const durationFrames = Math.max(1, Math.round(clamped * fps));
      const edgeLast = opening;
      let jumped = false;
      mutateSequence("ApplyTransition", "Set transition", (current) => {
        const edited = applyEditCommand(
          current,
          {
            kind: "ApplyTransition",
            payload: {
              clipId: clip.id,
              transitionId: kind,
              edge: "out",
              durationFrames,
            },
          },
          [clip.id],
        );
        const preview =
          kind === "none"
            ? null
            : transitionPreviewFrame({
                playheadFrame: current.playheadFrame,
                clip,
                durationFrames,
                edge: "out",
                cutFrame: edgeLast || cut.status !== "cut" ? null : cut.cutFrame,
              });
        if (preview == null) return edited;
        jumped = true;
        return { doc: { ...edited.doc, playheadFrame: preview }, selection: edited.selection };
      });
      if (jumped) setSeekGeneration((value) => value + 1);
    },
    [mutateSequence],
  );

  const setOpeningFade = useCallback(
    (kind: string, seconds: number) => {
      const doc = sequenceRef.current;
      const clipId = selectionRef.current[0];
      const clip = doc?.clips.find((item) => item.id === clipId);
      if (!doc || !clip || !clipEdgeRole(doc, clip).first) return;
      if (kind !== "none" && kind !== "fade") return;
      const fps = Math.max(1, doc.frameRate || 24);
      const limit = maxEdgeFadeSeconds(clip.durationFrames, fps) || 0.1;
      const clamped = Math.min(limit, Math.max(0.1, seconds));
      const durationFrames = Math.max(1, Math.round(clamped * fps));
      let jumped = false;
      mutateSequence("ApplyTransition", "Set fade in", (current) => {
        const edited = applyEditCommand(
          current,
          {
            kind: "ApplyTransition",
            payload: {
              clipId: clip.id,
              transitionId: kind,
              edge: "in",
              durationFrames,
            },
          },
          [clip.id],
        );
        const preview =
          kind === "none"
            ? null
            : transitionPreviewFrame({
                playheadFrame: current.playheadFrame,
                clip,
                durationFrames,
                edge: "in",
              });
        if (preview == null) return edited;
        jumped = true;
        return { doc: { ...edited.doc, playheadFrame: preview }, selection: edited.selection };
      });
      if (jumped) setSeekGeneration((value) => value + 1);
    },
    [mutateSequence],
  );

  useEffect(() => {
    const savedId = sequence?.finishing?.compareAssetId;
    const savedMode = sequence?.finishing?.viewerMode;
    if (savedId) setCompareAssetId(savedId);
    if (savedMode === "viewer" || savedMode === "compare" || savedMode === "split") setViewerMode(savedMode);
  }, [sequence?.finishing?.compareAssetId, sequence?.finishing?.viewerMode]);

  useEffect(() => {
    void api.magi.upscaleCapabilities().then((caps) => {
      setGpuReady(Boolean(caps.realesrganReady));
      if (typeof caps.creatorMessage === "string" && caps.creatorMessage) {
        setGpuMessage(caps.creatorMessage);
      }
    }).catch(() => setGpuReady(false));
  }, []);

  useEffect(() => {
    if (!finishingJobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const job = await api.magi.getFinishingJob(project.id, finishingJobId);
        if (cancelled) return;
        setFinishingJob({
          status: String(job.status || ""),
          stage: String(job.stage || ""),
          message: String(job.message || ""),
          kind: String(job.kind || ""),
        });
        if (finalRenderJobRef.current && finalRenderJobRef.current === finishingJobId) {
          setFinalRenderSession((current) => (current ? applyFinalRenderJob(current, job) : current));
        }
        const status = String(job.status || "");
        if (["done", "failed", "cancelled", "canceled", "timed_out"].includes(status)) {
          setFinishingJobId(null);
          if (status === "done") {
            await reloadSequence();
            if (finalRenderJobRef.current === finishingJobId) {
              const finishing = sequenceRef.current?.finishing;
              const finishedAssetId = String(finishing?.render?.assetId || finishing?.visualResultAssetId || "").trim();
              if (finishedAssetId) {
                setFinalRenderSession((current) =>
                  current
                    ? { ...current, assetId: current.assetId || finishedAssetId, jobId: current.jobId || finishingJobId }
                    : current,
                );
              }
            }
          }
          await onChange();
        }
      } catch {
        /* keep polling */
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [finishingJobId, onChange, project.id, reloadSequence]);

  const waitAccepted = (result: Record<string, unknown>, kind: string) => {
    const jobId = String(result.jobId || (Array.isArray(result.jobIds) ? result.jobIds[0] : "") || "");
    if (!jobId) {
      setMessage(String(result.message || "The studio did not accept this job."));
      return;
    }
    setFinishingJob({ status: String(result.status || "queued"), stage: String(result.stage || "Queued"), message: String(result.message || "Queued"), kind });
    setFinishingJobId(jobId);
    setMessage(String(result.message || "Queued."));
  };
  const applySnapshot = useCallback((snapshot: HistorySnapshot) => {
    setSequence(structuredClone(snapshot.sequence));
    setSelection([...snapshot.selection]);
    setViewerAssetId(snapshot.viewerAssetId);
    setCompareAssetId(snapshot.compareAssetId);
    setPendingOverlayRestore(snapshot);
    bumpEditVersion();
  }, []);

  const undo = useCallback(() => {
    if (!sequenceRef.current || !overlayCompositionRef.current) return;
    const next = historyRef.current.undo(captureSnapshot());
    if (!next) return;
    applySnapshot(next);
    setHistoryTick((tick) => tick + 1);
  }, [applySnapshot, captureSnapshot]);

  const redo = useCallback(() => {
    if (!sequenceRef.current || !overlayCompositionRef.current) return;
    const next = historyRef.current.redo(captureSnapshot());
    if (!next) return;
    applySnapshot(next);
    setHistoryTick((tick) => tick + 1);
  }, [applySnapshot, captureSnapshot]);

  useMagiKeyboard({
    focusRegion,
    hasSelection: selection.length > 0,
    onDeleteSelection: () => {
      const gfxIds = selectionRef.current.filter((id) => isGraphicsClipId(id));
      const overlayId = overlays.selectedOverlayId || (gfxIds[0] ? overlayIdFromGraphicsClip(gfxIds[0]) : null);
      if (overlayId) {
        overlays.deleteOverlay(overlayId);
        setSelection((current) => current.filter((id) => !isGraphicsClipId(id)));
        return;
      }
      pushSequenceCommand("Delete selection", { kind: "RippleDelete" });
    },
    onTogglePlay: () => setPlaying((value) => !value),
    onJog: (dir) => {
      if (!sequenceRef.current) return;
      const extent = recomputeDuration(sequenceRef.current);
      seekPlayhead(Math.max(0, Math.min(extent, sequenceRef.current.playheadFrame + dir * sequenceRef.current.frameRate)));
    },
    onShuttle: () => undefined,
    onFrameStep: (delta) => {
      if (!sequenceRef.current) return;
      seekPlayhead(Math.max(0, Math.min(recomputeDuration(sequenceRef.current), sequenceRef.current.playheadFrame + delta)));
    },
    onHome: () => seekPlayhead(0),
    onEnd: () => {
      if (!sequenceRef.current) return;
      seekPlayhead(recomputeDuration(sequenceRef.current));
    },
    onCopy: () => {
      clipboardRef.current = [...selectionRef.current];
      setMessage(`${clipboardRef.current.length} clip${clipboardRef.current.length === 1 ? "" : "s"} copied.`);
    },
    onPaste: () => {
      if (!clipboardRef.current.length || !sequenceRef.current) return;
      pushSequenceCommand("Paste clips", {
        kind: "Paste",
        payload: {
          ids: clipboardRef.current,
          offsetFrames: Math.max(1, sequenceRef.current.playheadFrame - (selectedClip?.startFrame || 0)),
        },
      });
    },
    onUndo: undo,
    onRedo: redo,
    onSplit: () => {
      const clip = selectedClip;
      const doc = sequenceRef.current;
      if (!clip || !doc || isGraphicsClipId(clip.id)) return;
      pushSequenceCommand("Split clip", { kind: "Split", payload: { clipId: clip.id, frame: doc.playheadFrame } });
    },
    onCompare: () => setViewerMode("compare"),
    onSplitView: () => setViewerMode("split"),
    onOpenHotkeys: () => setSideTab("hotkeys"),
    onZoom: (dir) => stepMagiZoom(dir),
  });

  const handleSelect = useCallback(
    (ids: string[], additive?: boolean) => {
      if (!sequenceRef.current) return;
      const nextSelection = !additive
        ? ids
        : (() => {
            const next = new Set(selectionRef.current);
            for (const id of ids) {
              if (next.has(id)) next.delete(id);
              else next.add(id);
            }
            return [...next];
          })();
      selectionRef.current = nextSelection;
      setSelection(nextSelection);
      const first = ids[0];
      if (first && isGraphicsClipId(first)) {
        const overlayId = overlayIdFromGraphicsClip(first);
        overlays.setSelectedOverlayId(overlayId);
        const el = flattenOverlayIds(overlays.composition.overlays).find((item) => item.id === overlayId);
        if (el) setSelectedObjectsSlot(overlayObjectsTrack(el));
        const clip = sequenceRef.current.clips.find((item) => item.id === first);
        if (clip) setSelectedTrackId(clip.trackId);
        return;
      }
      overlays.setSelectedOverlayId(null);
      setPreviewPinAssetId(null);
      if (first) {
        const clip = sequenceRef.current.clips.find((item) => item.id === first);
        if (clip?.assetId && clip.ingestRole !== "graphic") setViewerAssetId(clip.assetId);
      }
    },
    [overlays],
  );

  const handleSeek = useCallback(
    (frame: number) => {
      setPreviewPinAssetId(null);
      seekPlayhead(frame);
    },
    [seekPlayhead],
  );

  const handleTrim = useCallback(
    (clipId: string, edge: "left" | "right", deltaFrames: number) => {
      if (isGraphicsClipId(clipId)) {
        const overlayId = overlayIdFromGraphicsClip(clipId);
        const el = flattenOverlayIds(overlays.composition.overlays).find((item) => item.id === overlayId);
        if (!el) return;
        const fps = Math.max(1, sequenceRef.current?.frameRate || 24);
        const start = el.startFrame ?? 0;
        const end = el.endFrame ?? start + Math.max(1, Math.round(fps * 5));
        if (edge === "left") {
          overlays.patchElement(overlayId, { startFrame: Math.max(0, Math.min(end - 1, start + deltaFrames)) });
        } else {
          overlays.patchElement(overlayId, { endFrame: Math.max(start + 1, end + deltaFrames) });
        }
        return;
      }
      const current = sequenceRef.current;
      if (!current) return;
      const clip = current.clips.find((item) => item.id === clipId);
      if (!clip) return;
      let nextDelta = deltaFrames;
      if (edge === "left") {
        const nextStart = snapFrame(clip.trackId, clip.startFrame + deltaFrames, clipId);
        nextDelta = nextStart - clip.startFrame;
      } else {
        const end = clip.startFrame + clip.durationFrames + deltaFrames;
        const snappedEnd = snapFrame(clip.trackId, end, clipId);
        nextDelta = snappedEnd - (clip.startFrame + clip.durationFrames);
      }
      pushSequenceCommand("Trim clip", {
        kind: "Trim",
        payload: { clipId, edge, deltaFrames: nextDelta },
      });
    },
    [overlays, pushSequenceCommand, snapFrame],
  );

  const handleMove = useCallback(
    (clipId: string, startFrame: number, trackId?: string) => {
      if (isGraphicsClipId(clipId)) {
        const overlayId = overlayIdFromGraphicsClip(clipId);
        const el = flattenOverlayIds(overlays.composition.overlays).find((item) => item.id === overlayId);
        if (!el) return;
        const fps = Math.max(1, sequenceRef.current?.frameRate || 24);
        const start = el.startFrame ?? 0;
        const end = el.endFrame ?? start + Math.max(1, Math.round(fps * 5));
        const duration = Math.max(1, end - start);
        const nextStart = Math.max(0, startFrame);
        const targetTrack = trackId
          ? sequenceRef.current?.tracks.find((item) => item.id === trackId) ||
            sequenceForTimeline?.tracks.find((item) => item.id === trackId)
          : undefined;
        const nextSlot = objectsSlotOf(targetTrack);
        overlays.patchElement(overlayId, {
          startFrame: nextStart,
          endFrame: nextStart + duration,
          ...(nextSlot ? { objectsTrack: nextSlot } : {}),
        });
        if (nextSlot) {
          setSelectedObjectsSlot(nextSlot);
          if (trackId) setSelectedTrackId(trackId);
        }
        return;
      }
      const current = sequenceRef.current;
      if (!current) return;
      const clip = current.clips.find((item) => item.id === clipId);
      if (!clip) return;
      const targetTrackId = trackId || clip.trackId;
      const snappedFrame = snapFrame(targetTrackId, startFrame, clipId);
      pushSequenceCommand("Move clip", {
        kind: "Move",
        payload: { clipId, trackId: targetTrackId, startFrame: snappedFrame },
      });
    },
    [overlays, pushSequenceCommand, sequenceForTimeline, snapFrame],
  );

  const handleDropAsset = useCallback(
    (trackId: string, startFrame: number, assetId: string, mode: "Insert" | "Overwrite") => {
      const current = sequenceRef.current;
      const asset = mediaAssets.find((item) => item.id === assetId) || project.assets.find((item) => item.id === assetId);
      if (!current || !asset) return;
      const snappedFrame = snapFrame(trackId, startFrame);
      const track =
        current.tracks.find((item) => item.id === trackId) ||
        sequenceForTimeline?.tracks.find((item) => item.id === trackId);
      if (isObjectsTrackKind(track?.kind)) {
        if (assetKindGroup(asset) !== "image") {
          setMessage("Objects accepts Library images only.");
          return;
        }
        const slot = objectsSlotOf(track) || selectedObjectsSlot;
        overlays.addImage(asset.id, {
          ...overlayTimingFromPlayhead({ ...current, playheadFrame: snappedFrame }),
          objectsTrack: slot,
        });
        setSelectedObjectsSlot(slot);
        setSelectedTrackId(trackId);
        setFocusRegion("viewer");
        return;
      }
      pushSequenceCommand(mode === "Overwrite" ? "Overwrite clip" : "Insert clip", {
        kind: mode,
        payload: {
          trackId,
          assetId,
          startFrame: snappedFrame,
          durationFrames: defaultDurationFrames(current, asset),
          name: asset.tag || asset.filename,
        },
      });
      setViewerAssetId(asset.id);
      setFocusRegion("timeline");
    },
    [mediaAssets, overlays, project.assets, pushSequenceCommand, selectedObjectsSlot, sequenceForTimeline, setFocusRegion, snapFrame],
  );

  const handleAddFromLibrary = useCallback(
    (assetIds: string[]) => {
      const pickingOverlay = imageOverlayPickerOpen;
      setLibraryPickerOpen(false);
      setImageOverlayPickerOpen(false);
      const current = sequenceRef.current;
      if (!current) return;
      if (pickingOverlay) {
        const assetId = assetIds[0];
        const asset =
          mediaAssets.find((item) => item.id === assetId) || project.assets.find((item) => item.id === assetId);
        if (!asset || assetKindGroup(asset) !== "image") {
          setMessage("Choose an image from the Library for this overlay.");
          return;
        }
        overlays.addImage(asset.id, { ...overlayTimingFromPlayhead(current), objectsTrack: selectedObjectsSlot });
        setFocusRegion("viewer");
        return;
      }
      for (const assetId of assetIds) {
        const asset =
          mediaAssets.find((item) => item.id === assetId) || project.assets.find((item) => item.id === assetId);
        if (!asset) continue;
        const track = defaultTrackForAsset(current, asset);
        if (!track) continue;
        handleDropAsset(track.id, current.playheadFrame, assetId, "Insert");
      }
    },
    [handleDropAsset, imageOverlayPickerOpen, mediaAssets, overlays, project.assets, selectedObjectsSlot, setFocusRegion],
  );

  useEffect(() => {
    if (!sequence || !handoffSceneId) return;
    const key = `${project.id}::ingest::${handoffSceneId}`;
    if (timelineImportKeyRef.current === key) return;
    timelineImportKeyRef.current = key;
    bindMagiPlaybackStats();
    void (async () => {
      try {
        const imported = await api.magi.ingestPublishedMaster(project.id, handoffSceneId);
        if (!imported.ok) {
          setUnpublishedSceneId(handoffSceneId);
          setMessage(null);
          return;
        }
        setUnpublishedSceneId(null);
        setMessage(null);
        if (imported.sequence) {
          setSequence(migrateToPostProductionTracks(imported.sequence as unknown as MagiSequenceDocument));
        } else {
          const raw = await fetchMagiSequence(project.id);
          setSequence(migrateToPostProductionTracks(raw));
        }
        const pub = String(imported.publishedAssetId || handoffAssetId || "");
        if (pub) {
          setPublishedMasterId(pub);
          setViewerAssetId(pub);
        }
        const aligned = String(imported.alignedSceneId || "").trim();
        if (aligned && aligned !== handoffSceneId) {
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.set("sceneId", aligned);
            return next;
          }, { replace: true });
        }
        await onChange();
      } catch (error: unknown) {
        const code = error instanceof ApiError ? error.code : "";
        if (code === "PUBLISHED_MASTER_REQUIRED") {
          setUnpublishedSceneId(handoffSceneId);
          setMessage(null);
          return;
        }
        setUnpublishedSceneId(null);
        setMessage(describeMagiError(error));
      }
    })();
  }, [handoffAssetId, handoffSceneId, onChange, project.id, sequence, setSearchParams]);

  const removeClipsForAsset = useCallback(
    (assetId: string) => {
      const current = sequenceRef.current;
      if (!current) return;
      const doomed = current.clips.filter((clip) => clip.assetId === assetId);
      if (doomed.length === 0) {
        setFailedMedia((prev) => {
          const next = { ...prev };
          delete next[assetId];
          return next;
        });
        return;
      }
      const doomedIds = new Set(doomed.map((clip) => clip.id));
      const selectionAfter = selectionRef.current.filter((id) => !doomedIds.has(id));
      mutateSequence(
        `Remove ${doomed.length} clip${doomed.length === 1 ? "" : "s"} using failed media`,
        "RemoveClips",
        (draft) => ({
          doc: {
            ...draft,
            clips: draft.clips.filter((clip) => !doomedIds.has(clip.id)),
            durationFrames: recomputeDuration({ ...draft, clips: draft.clips.filter((clip) => !doomedIds.has(clip.id)) }),
          },
          selection: selectionAfter,
        }),
      );
      setFailedMedia((prev) => {
        const next = { ...prev };
        delete next[assetId];
        return next;
      });
    },
    [mutateSequence],
  );

  const createGraphic = useCallback(
    (kind: "text" | "lower_third" | "shape") => {
      const current = sequenceRef.current;
      if (!current) return;
      const timing = { ...overlayTimingFromPlayhead(current), objectsTrack: selectedObjectsSlot };
      if (kind === "text") overlays.addText({ text: "QUARTERS INTERVIEW", ...timing });
      else if (kind === "lower_third") overlays.addLowerThird("ANADRIYA", "Current Adept", timing);
      else overlays.addShape("rounded_rectangle", { opacity: 0.55, fill: "#111827", ...timing });
      setFocusRegion("viewer");
    },
    [overlays, selectedObjectsSlot, setFocusRegion],
  );

  const handleSelectTrack = useCallback(
    (trackId: string) => {
      setSelectedTrackId(trackId);
      const current = sequenceForTimeline || sequenceRef.current;
      const track = current?.tracks.find((item) => item.id === trackId);
      const slot = objectsSlotOf(track);
      if (slot) setSelectedObjectsSlot(slot);
    },
    [sequenceForTimeline],
  );

  const handleAddObjectsTrack = useCallback(() => {
    if (!sequenceRef.current || !canAddObjectsTrack(sequenceRef.current.tracks)) return;
    mutateSequence("AddTrack", "Add Objects 2", (current) => {
      const next = addOptionalObjectsTrack(current);
      const added = next.tracks.find((track) => objectsSlotOf(track) === 2);
      if (added) {
        setSelectedTrackId(added.id);
        setSelectedObjectsSlot(2);
      }
      return { doc: next };
    });
  }, [mutateSequence]);

  const handleRemoveObjectsTrack = useCallback(() => {
    overlays.reassignObjectsTrack(2, 1);
    mutateSequence("RemoveTrack", "Remove Objects 2", (current) => {
      const next = removeOptionalObjectsTrack(current);
      const o1 = next.tracks.find((track) => objectsSlotOf(track) === 1);
      setSelectedObjectsSlot(1);
      setSelectedTrackId(o1?.id || null);
      return { doc: next };
    });
  }, [mutateSequence, overlays]);

  const queueProposal = useCallback(
    (kind: ProposalKind) => {
      if (isUnsupportedPlacebo(kind)) {
        const copy = UNSUPPORTED_PLACEBO_COPY[kind];
        setPendingProposal({
          kind,
          title: copy.title,
          summary: copy.summary,
          approveLabel: "Acknowledge",
        });
        setAccordion("command", true);
        return;
      }
      const proposal = commandProposal(kind.replace(/_/g, " ")) || {
        kind,
        title:
          kind === "trim"
            ? "Trim selected clip"
            : kind === "replace_clip"
              ? "Replace selected clip"
              : kind === "add_ambience"
                ? "Add ambience bed"
                : kind === "extend_reaction"
                  ? "Extend reaction"
                  : kind === "overlay_text"
                    ? "Add text overlay"
                    : kind === "overlay_lower_third"
                      ? "Add lower third"
                      : "Add shape overlay",
        summary: "Approval required before MAGI changes the sequence.",
        approveLabel: "Approve",
      };
      setPendingProposal(proposal);
      setAccordion("command", true);
    },
    [setAccordion],
  );

  const applyProposal = useCallback(() => {
    if (!pendingProposal || !sequenceRef.current) return;
    const current = sequenceRef.current;
    if (isUnsupportedPlacebo(pendingProposal.kind)) {
      const copy = UNSUPPORTED_PLACEBO_COPY[pendingProposal.kind];
      setPendingProposal(null);
      setMessage(copy.refuseMessage);
      return;
    }
    if (pendingProposal.kind === "overlay_text") {
      overlays.addText();
      setPendingProposal(null);
      setMessage("Text overlay added after approval.");
      return;
    }
    if (pendingProposal.kind === "overlay_lower_third") {
      overlays.addLowerThird();
      setPendingProposal(null);
      setMessage("Lower third added after approval.");
      return;
    }
    if (pendingProposal.kind === "overlay_shape") {
      overlays.addShape();
      setPendingProposal(null);
      setMessage("Shape overlay added after approval.");
      return;
    }
    if (!selectedClip && pendingProposal.kind !== "add_ambience") {
      setMessage("Select a timeline clip before approving this MAGI action.");
      return;
    }
    switch (pendingProposal.kind) {
      case "trim":
        pushSequenceCommand("Proposal trim", {
          kind: "Trim",
          payload: { clipId: selectedClip!.id, edge: "right", deltaFrames: -Math.max(6, Math.round(current.frameRate / 2)) },
        });
        break;
      case "replace_clip":
        if (!viewerAssetId || viewerAssetId === selectedClip!.assetId) {
          setMessage("Pick a different Library asset to replace the selected clip.");
          return;
        }
        mutateSequence("ReplaceClip", "Replace selected clip", (doc) => ({
          doc: {
            ...doc,
            clips: doc.clips.map((clip) =>
              clip.id === selectedClip!.id
                ? { ...clip, assetId: viewerAssetId, name: currentAsset?.tag || currentAsset?.filename || clip.name }
                : clip,
            ),
          },
        }));
        break;
      case "add_ambience": {
        const ambience = audioAssets[0];
        if (!ambience) {
          setMessage("Add an audio asset to the Library before approving ambience.");
          return;
        }
        const audioTrack = current.tracks.find((track) => track.label === "A3") || defaultTrackForAsset(current, ambience);
        if (!audioTrack) return;
        pushSequenceCommand("Add ambience", {
          kind: "Insert",
          payload: {
            trackId: audioTrack.id,
            assetId: ambience.id,
            startFrame: current.playheadFrame,
            durationFrames: defaultDurationFrames(current, ambience),
            name: ambience.tag || ambience.filename,
          },
        });
        break;
      }
      case "extend_reaction":
        pushSequenceCommand("Extend reaction", {
          kind: "Duplicate",
          payload: { offsetFrames: selectedClip!.durationFrames },
        });
        break;
      default:
        break;
    }
    setPendingProposal(null);
    setMessage(`${pendingProposal.title} applied.`);
  }, [
    audioAssets,
    currentAsset,
    mutateSequence,
    overlays,
    pendingProposal,
    pushSequenceCommand,
    selectedClip,
    viewerAssetId,
  ]);

  const runCommandProposal = useCallback(() => {
    const next = commandProposal(command);
    if (!next) {
      if (PRODUCTION_CORRECTION_RE.test(command.toLowerCase())) {
        setMessage(PRODUCTION_CORRECTION_COPY);
        return;
      }
      setMessage("Try trim, replace, or a lower third. Set blends in Transitions and looks in Lighting. Co-Director runs the edit.");
      return;
    }
    setPendingProposal(next);
  }, [command]);

  const applyRecipe = useCallback(
    (recipeId: string) => {
      if (!sequenceRef.current) return;
      mutateSequence("ApplyRecipe", `Apply ${recipeId}`, (doc) => ({
        doc: {
          ...doc,
          recipeId,
          snapEnabled: recipeSnapEnabled(recipeId),
          tracks: recipeTracks(doc, recipeId),
        },
      }));
      setMessage(`${RECIPE_PRESETS.find((recipe) => recipe.id === recipeId)?.name || "Recipe"} applied.`);
    },
    [mutateSequence],
  );

  const onLeftSplitterPointerDown = (event: React.PointerEvent, side: "left" | "right") => {
    dragRef.current = {
      side,
      start: event.clientX,
      size: side === "left" ? layout.leftDockWidth : layout.rightDockWidth,
    };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  };

  const onLeftRightSplitterMove = (event: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    if (drag.side === "left") setLeftWidth(drag.size + (event.clientX - drag.start));
    if (drag.side === "right") setRightWidth(drag.size - (event.clientX - drag.start));
  };

  const onLeftRightSplitterUp = () => {
    dragRef.current = null;
  };

  const paneMenu = (pane: MagiPaneId) => (
    <div className="magi-pane-menu">
      <button type="button" className="magi-pane-btn" aria-label="Move pane left" title="Move left" onClick={() => movePane(pane, "left")}>
        ←
      </button>
      <button type="button" className="magi-pane-btn" aria-label="Move pane right" title="Move right" onClick={() => movePane(pane, "right")}>
        →
      </button>
      <button type="button" className="magi-pane-btn" aria-label="Move pane up" title="Move up" onClick={() => reorderPane(pane, "up")}>
        ↑
      </button>
      <button type="button" className="magi-pane-btn" aria-label="Move pane down" title="Move down" onClick={() => reorderPane(pane, "down")}>
        ↓
      </button>
    </div>
  );

  const renderAssetCard = (asset: Asset) => {
    const group = libraryThumbKind(asset.kind);
    const thumb = !failedThumbs[asset.id] ? libraryThumbUrl(project.id, asset.id, asset.kind) : null;
    return (
    <button
      key={asset.id}
      type="button"
      className={`magi-asset-card ${viewerAssetId === asset.id ? "selected" : ""} ${group === "audio" ? "magi-asset-card--audio" : ""}`}
      draggable
      data-testid={`magi-media-${asset.id}`}
      onClick={() => {
        setViewerAssetId(asset.id);
        setFocusRegion("media_bin");
      }}
      onDragStart={(event) => {
        event.dataTransfer.setData("application/x-adept-asset", asset.id);
        event.dataTransfer.setData("application/x-adept-kind", asset.kind);
        event.dataTransfer.effectAllowed = "copyMove";
      }}
    >
      {thumb ? (
        <img
          src={thumb}
          alt=""
          loading="lazy"
          onError={() => setFailedThumbs((prev) => (prev[asset.id] ? prev : { ...prev, [asset.id]: true }))}
        />
      ) : (
        <div className="magi-asset-card__placeholder">{group === "audio" ? "audio" : group}</div>
      )}
      <span className="label">{asset.tag || asset.filename}</span>
      <span className="meta">{asset.kind}</span>
    </button>
    );
  };

  const renderPane = (pane: MagiPaneId): ReactNode => {
    if (!sequence) return null;
    const open = Boolean(layout.accordionState[pane]);
    const wrap = (title: string, body: ReactNode, badge?: ReactNode) => (
      <div key={pane} className="magi-dock-pane" data-pane={pane}>
        {paneMenu(pane)}
        <MagiAccordion id={pane} title={title} open={open} onToggle={(next) => setAccordion(pane, next)} badge={badge}>
          {body}
        </MagiAccordion>
      </div>
    );

    if (pane === "project") {
      return wrap(
        "Project",
        <div className="magi-pane-copy">
          <strong>{project.name}</strong>
          <p className="magi-empty">One project, one library. MAGI sequences reference Library assets directly.</p>
          <div className="magi-pill-row">
            <span className="magi-pill">Recipe: {sequence.recipeId || "Balanced"}</span>
            <span className="magi-pill">Rev {sequence.revision}</span>
            <span className="magi-pill">Server {serverRevision || sequence.revision}</span>
          </div>
        </div>,
      );
    }
    if (pane === "library" || pane === "media" || pane === "assets") {
      return wrap(
        "Library",
        <div {...bindRegionProps("media_bin")} className="magi-pane-bin" data-testid="magi-library-bin">
          <p className="magi-empty">Project Library. Click to preview. Drag onto VIDEO, OBJECTS, AUDIO, MUSIC, or SFX.</p>
          <div className="magi-actions">
            <button type="button" className="magi-primary" data-testid="magi-library-button" onClick={() => setLibraryPickerOpen(true)}>
              Library
            </button>
            {(["all", "video", "image", "audio"] as const).map((filter) => (
              <button
                key={filter}
                type="button"
                className={`magi-chip ${assetFilter === filter ? "active" : ""}`}
                onClick={() => setAssetFilter(filter)}
              >
                {filter}
              </button>
            ))}
          </div>
          <div className="magi-asset-grid" style={{ marginTop: "0.5rem" }}>
            {filteredAssets.map(renderAssetCard)}
          </div>
        </div>,
        <span>{libraryAssets.length}</span>,
      );
    }
    if (pane === "graphics") {
      return wrap(
        "Objects",
        <div data-testid="magi-text-graphics">
          <div className="magi-actions">
            <button type="button" className="magi-chip" data-testid="magi-graphics-add-text" onClick={() => createGraphic("text")}>
              Add Text
            </button>
            <button type="button" className="magi-chip" data-testid="magi-graphics-add-lt" onClick={() => createGraphic("lower_third")}>
              Lower Third
            </button>
            <button type="button" className="magi-chip" data-testid="magi-graphics-add-shape" onClick={() => createGraphic("shape")}>
              Shape
            </button>
            <button
              type="button"
              className="magi-chip"
              data-testid="magi-graphics-add-image"
              onClick={() => setImageOverlayPickerOpen(true)}
            >
              Image Overlay
            </button>
            <button type="button" className="magi-chip" onClick={() => overlays.setSafeGuides(!overlays.safeGuides)}>
              Safe Guides
            </button>
            <button type="button" className="magi-chip" onClick={() => overlays.setSnapEnabled(!overlays.snapEnabled)}>
              Overlay Snap
            </button>
            <button
              type="button"
              className="magi-primary"
              data-testid="magi-overlay-render"
              onClick={() =>
                void overlays
                  .renderComposition()
                  .then(async () => {
                    if (layout.leftDockCollapsed) toggleLeftDock();
                    setRenderQueueOpen(true);
                    setMessage("Overlay render queued.");
                    await onChange();
                  })
                  .catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)))
              }
            >
              Render Composition
            </button>
          </div>
          <p className="magi-group-label">Presets</p>
          <div className="magi-actions">
            {overlays.presets.map((preset) => (
              <button key={preset.id} type="button" className="magi-chip" onClick={() => overlays.applyPreset(preset.id)}>
                {preset.name}
              </button>
            ))}
          </div>
          {overlays.persistError ? <p className="magi-empty">{overlays.persistError}</p> : null}
        </div>,
      );
    }
    if (pane === "recipes") {
      return wrap(
        "Recipes",
        <div data-testid="magi-recipes">
          <p className="magi-empty">Recipes preconfigure track defaults, snap behavior, and finishing posture.</p>
          <div className="magi-recipe-list">
            {RECIPE_PRESETS.map((recipe) => (
              <button
                key={recipe.id}
                type="button"
                className={`magi-recipe-card ${sequence.recipeId === recipe.id ? "active" : ""}`}
                onClick={() => applyRecipe(recipe.id)}
              >
                <strong>{recipe.name}</strong>
                <span>{recipe.detail}</span>
              </button>
            ))}
          </div>
        </div>,
      );
    }
    if (pane === "actions") {
      return wrap(
        "Actions",
        <div data-testid="magi-actions">
          <p className="magi-empty">Every action opens a proposal first. Nothing changes until you approve it.</p>
          <div className="magi-actions">
            <button type="button" className="magi-chip" onClick={() => queueProposal("trim")}>Trim</button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("replace_clip")}>Replace Clip</button>
            <button
              type="button"
              className="magi-chip magi-chip--unavailable"
              title={UNSUPPORTED_PLACEBO_COPY.remove_silence.summary}
              onClick={() => queueProposal("remove_silence")}
            >
              {UNSUPPORTED_PLACEBO_COPY.remove_silence.chipLabel}
            </button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("add_ambience")}>Add Ambience</button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("extend_reaction")}>Extend Reaction</button>
          </div>
        </div>,
      );
    }
    if (pane === "command") {
      const parsed = commandProposal(command);
      const finishing = proposeFromCommand(command);
      const productionCorrection = PRODUCTION_CORRECTION_RE.test(command.toLowerCase());
      return wrap(
        "Command",
        <div data-testid="magi-command">
          <div className="magi-field">
            <label>Command</label>
            <textarea
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="Try: finish this scene professionally, upscale to 2K, no music, keep original audio"
            />
          </div>
          <p className="magi-empty">Target: {selectedClip?.name || currentAsset?.tag || currentAsset?.filename || "Choose a clip or media item."}</p>
          <p className="magi-empty" data-testid="magi-command-stage">
            Stage: <StatusBadge status={pendingProposal ? "Proposed" : parsed || finishing ? "Draft" : "Draft"} />
          </p>
          {productionCorrection ? (
            <p className="magi-tip" data-testid="magi-command-production-correction" role="status">
              {PRODUCTION_CORRECTION_COPY}
            </p>
          ) : parsed ? (
            <div className="magi-tip">
              <strong>{parsed.title}</strong>
              <p>{parsed.summary}</p>
              <button type="button" className="magi-chip" onClick={runCommandProposal}>Create Proposal</button>
            </div>
          ) : finishing ? (
            <div className="magi-tip" data-testid="magi-command-finishing">
              <strong>{finishing.label}</strong>
              <p>MAGI finishing: {finishing.operation}. Color, upscale, music/SFX, and final render are real. Sound enhancement is part of Upscale. EQ and frame interpolation are not available.</p>
            </div>
          ) : (
            <p className="magi-empty">Command parser supports finishing (color, upscale, audio, render), trims, replacements, ambience, and basic objects. Sound enhancement is chosen inside Upscale. EQ and frame interpolation are not available. Dissolve / brighten / stabilize / silence refuse honestly.</p>
          )}
          {pendingProposal ? (
            <div className="magi-tip" data-testid="magi-overlay-proposal">
              <strong>{pendingProposal.title}</strong>
              <p>{pendingProposal.summary}</p>
              <div className="magi-actions">
                <button type="button" className="magi-chip" onClick={() => setPendingProposal(null)}>Reject</button>
                <button type="button" className="magi-primary" onClick={applyProposal}>
                  {pendingProposal.approveLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>,
      );
    }
    return null;
  };

  const outgoingCut = sequence ? resolveOutgoingCut(sequence, selectedClip) : { status: "none" as const };
  const edgeRole = sequence ? clipEdgeRole(sequence, selectedClip) : { first: false, last: false };
  const playheadBlend = sequence ? blendAtPlayhead(sequence, sequence.playheadFrame) : null;
  const edgeFade = sequence ? edgeFadeAtPlayhead(sequence, sequence.playheadFrame) : null;
  const tailFadeReady =
    edgeRole.last &&
    outgoingCut.status === "last" &&
    maxEdgeFadeSeconds(selectedClip?.durationFrames || 0, sequence?.frameRate || 24) >= 0.1;
  const fadeInReady =
    edgeRole.first && maxEdgeFadeSeconds(selectedClip?.durationFrames || 0, sequence?.frameRate || 24) >= 0.1;
  const transitionReady = (outgoingCut.status === "cut" && outgoingCut.maxSeconds >= 0.1) || tailFadeReady;
  const transitionMaxSeconds =
    outgoingCut.status === "cut" && outgoingCut.maxSeconds >= 0.1
      ? outgoingCut.maxSeconds
      : Math.max(0.1, maxEdgeFadeSeconds(selectedClip?.durationFrames || 0, sequence?.frameRate || 24));
  const transitionSeconds = (() => {
    const fps = Math.max(1, sequence?.frameRate || 24);
    const raw = selectedClip?.transitionDurationFrames || fps;
    const seconds = Math.round(Math.min(3, Math.max(0.1, raw / fps)) * 10) / 10;
    return Math.min(transitionMaxSeconds, seconds);
  })();
  const previewMediaKind = (assetId: string): "video" | "image" => {
    const asset = mediaAssets.find((item) => item.id === assetId);
    return asset && assetKindGroup(asset) === "image" ? "image" : "video";
  };
  const transitionNote = (() => {
    if (!selectedClip || !sequence || outgoingCut.status === "none") {
      return "Select a picture clip that meets the next clip. Transitions stay on that cut.";
    }
    if (outgoingCut.status === "not-picture") return "Transitions stay on picture cuts.";
    if (outgoingCut.status === "last") return "This is the last clip. Fade out is available. Dissolve and wipe need a following clip.";
    if (outgoingCut.status === "gap") return "The next clip does not meet this one, so this cut cannot take a transition.";
    if (!transitionReady) return "These clips are too short for a transition.";
    const at = frameToTimecode(outgoingCut.cutFrame, sequence.frameRate);
    const left = selectedClip.name || "Clip";
    const right = outgoingCut.next.name || "Clip";
    return `Cut: ${left} → ${right} · ${at}`;
  })();

  const viewerModes = (
    [
      { id: "viewer" as ViewerMode, label: "Viewer", disabled: false, shelved: false },
      { id: "compare" as ViewerMode, label: "Compare", disabled: false, shelved: false },
      { id: "split" as ViewerMode, label: "Split View", disabled: false, shelved: false },
      { id: "histogram" as ViewerMode, label: "Histogram (future)", disabled: true, shelved: true },
      { id: "vectorscope" as ViewerMode, label: "Vectorscope (future)", disabled: true, shelved: true },
    ] as const
  )
    .filter((mode) => SHOW_SHELVED_MONITOR_CHROME || !mode.shelved)
    .map(({ id, label, disabled }) => (
    <button
      key={id}
      type="button"
      role="tab"
      aria-selected={viewerMode === id}
      className={`magi-chip${viewerMode === id ? " active" : ""}`}
      disabled={disabled}
      data-testid={`magi-viewer-mode-${id}`}
      onClick={() => setViewerMode(id)}
    >
      {label}
    </button>
  ));

  const viewerControls = (
    <div className="magi-preview-toolbar" data-testid="magi-preview-toolbar">
      <button type="button" title="Save MAGI sequence" aria-label="Save MAGI sequence" onClick={() => void saveAll()}>
        Save
      </button>
      <button
        type="button"
        title="Toggle snapping"
        aria-label="Toggle snapping"
        onClick={() =>
          mutateSequence("ToggleSnap", "Toggle snapping", (doc) => ({
            doc: { ...doc, snapEnabled: !doc.snapEnabled },
          }))
        }
      >
        {sequence?.snapEnabled ? "Snap On" : "Snap Off"}
      </button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-text" aria-label="Add text" title="Add text" onClick={() => createGraphic("text")}>T</button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-lower-third" aria-label="Add lower third" title="Add lower third" onClick={() => createGraphic("lower_third")}>LT</button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-shape" aria-label="Add shape" title="Add shape" onClick={() => createGraphic("shape")}>▢</button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-image" aria-label="Add image overlay" title="Add image overlay from Library" onClick={() => setImageOverlayPickerOpen(true)}>IMG</button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-duplicate" aria-label="Duplicate overlay" title="Duplicate overlay" onClick={() => overlays.duplicateSelected()}>⧉</button>
      <button type="button" className="magi-icon-btn" data-testid="magi-tool-delete" aria-label="Delete overlay" title="Delete overlay" onClick={() => overlays.deleteSelected()}>⌫</button>
    </div>
  );

  const viewerStage = currentAsset ? api.assetUrl(currentAsset.id) : "";
  const compareStage = compareAsset ? api.assetUrl(compareAsset.id) : "";
  const compareOptions = mediaAssets.filter((asset) => asset.id !== viewerAssetId);

  const monitor = (
    <section className="magi-viewer" {...bindRegionProps("viewer")} data-testid="magi-viewer">
      <div className="magi-viewer-stage" data-testid="magi-viewer-stage" data-preview-asset={previewAsset?.id || ""}>
        {!currentAsset && !previewAsset && !splitOriginalId ? (
          <p className="magi-empty">Choose media from the Library or select a clip in the timeline.</p>
        ) : viewerMode === "split" ? (
          splitOriginalId ? (
            <MagiSplitView
              originalSrc={api.assetUrl(splitOriginalId)}
              processedSrc={api.assetUrl(splitOriginalId)}
              processedKind={splitProcessedKind}
              processedFilter={splitRightFilter || undefined}
              processedOpacity={edgeFade?.opacity ?? 1}
              processedBlend={
                playheadBlend && sequence ? (
                  <MagiCutPreview
                    transition={playheadBlend.kind}
                    progress={playheadBlend.progress}
                    driveClock={false}
                    outgoing={{
                      clipId: playheadBlend.outgoing.id,
                      src: api.assetUrl(playheadBlend.outgoing.assetId),
                      kind: previewMediaKind(playheadBlend.outgoing.assetId),
                      timeSeconds: blendSourceSeconds(playheadBlend.outgoing, sequence.playheadFrame, sequence.frameRate),
                    }}
                    incoming={{
                      clipId: playheadBlend.incoming.id,
                      src: api.assetUrl(playheadBlend.incoming.assetId),
                      kind: previewMediaKind(playheadBlend.incoming.assetId),
                      timeSeconds: blendSourceSeconds(playheadBlend.incoming, sequence.playheadFrame, sequence.frameRate),
                    }}
                    playheadClipId={playheadClip?.id || null}
                    playing={playing}
                    muted
                    filter={splitRightFilter || undefined}
                    seekGeneration={seekGeneration}
                    onClock={followMediaClock}
                    onEnded={stopAtMediaEnd}
                    onError={(clipId) => {
                      const failed = sequence.clips.find((item) => item.id === clipId);
                      if (failed) markMediaFailed(failed.assetId);
                    }}
                    onReadySize={() => undefined}
                  />
                ) : null
              }
              timeSeconds={previewVideoTime}
              playing={playing}
              seekGeneration={seekGeneration}
              onClock={followMediaClock}
              onEnded={stopAtMediaEnd}
              onOriginalError={() => markMediaFailed(splitOriginalId)}
              onProcessedError={() => markMediaFailed(splitProcessed.assetId || splitOriginalId)}
              guidesVisible={overlays.safeGuides}
              processedOverlay={
                <MagiOverlayLayer
                  composition={overlays.composition}
                  selectedId={overlays.selectedOverlayId}
                  onSelect={overlays.setSelectedOverlayId}
                  onPatchElement={overlays.patchElement}
                  snapEnabled={overlays.snapEnabled}
                  playheadFrame={sequence?.playheadFrame ?? 0}
                  frameRate={sequence?.frameRate || 24}
                  assetUrl={api.assetUrl}
                  interactive={false}
                  hiddenObjectsSlots={hiddenObjectsSlots}
                />
              }
            />
          ) : (
            <p className="magi-empty">Publish this scene on Timeline first, then open Split View.</p>
          )
        ) : viewerMode === "compare" ? (
          <div className="magi-compare" data-testid="magi-compare-viewer">
            <figure>
              {playheadBlend && sequence ? (
                <MagiPreviewFitFrame mediaWidth={previewSourceSize.w} mediaHeight={previewSourceSize.h} guidesVisible={overlays.safeGuides}>
                  <MagiCutPreview
                    transition={playheadBlend.kind}
                    progress={playheadBlend.progress}
                    outgoing={{
                      clipId: playheadBlend.outgoing.id,
                      src: api.assetUrl(playheadBlend.outgoing.assetId),
                      kind: previewMediaKind(playheadBlend.outgoing.assetId),
                      timeSeconds: blendSourceSeconds(playheadBlend.outgoing, sequence.playheadFrame, sequence.frameRate),
                    }}
                    incoming={{
                      clipId: playheadBlend.incoming.id,
                      src: api.assetUrl(playheadBlend.incoming.assetId),
                      kind: previewMediaKind(playheadBlend.incoming.assetId),
                      timeSeconds: blendSourceSeconds(playheadBlend.incoming, sequence.playheadFrame, sequence.frameRate),
                    }}
                    playheadClipId={playheadClip?.id || null}
                    playing={playing}
                    muted={pictureMuted}
                    filter={viewerLiveFilter || undefined}
                    seekGeneration={seekGeneration}
                    onClock={followMediaClock}
                    onEnded={stopAtMediaEnd}
                    onError={(clipId) => {
                      const failed = sequence.clips.find((item) => item.id === clipId);
                      if (failed) markMediaFailed(failed.assetId);
                    }}
                    onReadySize={(width, height) =>
                      setPreviewSourceSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
                    }
                  />
                </MagiPreviewFitFrame>
              ) : currentAsset ? (
                <MagiCompareFitMedia
                  kind={assetKindGroup(currentAsset) === "video" ? "video" : "image"}
                  src={viewerStage}
                  timeSeconds={previewVideoTime}
                  playing={playing}
                  seekGeneration={seekGeneration}
                  clockRole="authority"
                  filter={viewerLiveFilter || undefined}
                  opacity={edgeFade?.opacity ?? 1}
                  onClock={followMediaClock}
                  onEnded={stopAtMediaEnd}
                  onError={() => markMediaFailed(currentAsset.id)}
                  onReadySize={(width, height) =>
                    setPreviewSourceSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
                  }
                  guidesVisible={overlays.safeGuides}
                />
              ) : null}
              <figcaption>Current</figcaption>
            </figure>
            <figure>
              {compareAsset ? (
                <MagiCompareFitMedia
                  kind={assetKindGroup(compareAsset) === "video" ? "video" : "image"}
                  src={compareStage}
                  timeSeconds={previewVideoTime}
                  playing={playing}
                  seekGeneration={seekGeneration}
                  onError={() => markMediaFailed(compareAsset.id)}
                  guidesVisible={overlays.safeGuides}
                />
              ) : (
                <div className="magi-viewer-placeholder">Choose Compare with in the inspector.</div>
              )}
              <figcaption>
                {compareAssetId && compareAssetId === splitOriginalId
                  ? "Original"
                  : compareAsset?.tag || compareAsset?.filename || "Compare with"}
              </figcaption>
            </figure>
          </div>
        ) : currentAsset && assetKindGroup(currentAsset) === "audio" ? (
          <div className="magi-viewer-placeholder">
            <strong>{currentAsset.tag || currentAsset.filename}</strong>
            <span>Audio clips are arranged in the timeline and previewed through transport focus.</span>
          </div>
        ) : (
          <>
            <MagiPreviewFitFrame mediaWidth={previewSourceSize.w} mediaHeight={previewSourceSize.h} guidesVisible={overlays.safeGuides}>
              {playheadBlend && sequence && !previewPinAssetId ? (
                <MagiCutPreview
                  transition={playheadBlend.kind}
                  progress={playheadBlend.progress}
                  outgoing={{
                    clipId: playheadBlend.outgoing.id,
                    src: api.assetUrl(playheadBlend.outgoing.assetId),
                    kind: previewMediaKind(playheadBlend.outgoing.assetId),
                    timeSeconds: blendSourceSeconds(playheadBlend.outgoing, sequence.playheadFrame, sequence.frameRate),
                  }}
                  incoming={{
                    clipId: playheadBlend.incoming.id,
                    src: api.assetUrl(playheadBlend.incoming.assetId),
                    kind: previewMediaKind(playheadBlend.incoming.assetId),
                    timeSeconds: blendSourceSeconds(playheadBlend.incoming, sequence.playheadFrame, sequence.frameRate),
                  }}
                  playheadClipId={playheadClip?.id || null}
                  playing={playing}
                  muted={pictureMuted}
                  filter={viewerLiveFilter || undefined}
                  seekGeneration={seekGeneration}
                  onClock={followMediaClock}
                  onEnded={stopAtMediaEnd}
                  onError={(clipId) => {
                    const failed = sequence.clips.find((item) => item.id === clipId);
                    if (failed) markMediaFailed(failed.assetId);
                  }}
                  onReadySize={(width, height) =>
                    setPreviewSourceSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
                  }
                />
              ) : previewAsset && assetKindGroup(previewAsset) === "video" ? (
                <MagiVideoStage
                  src={api.assetUrl(previewAsset.id)}
                  timeSeconds={previewPinAssetId ? 0 : previewVideoTime}
                  playing={previewPinAssetId ? false : playing}
                  muted={pictureMuted}
                  filter={previewPinAssetId ? undefined : viewerLiveFilter || undefined}
                  opacity={previewPinAssetId ? 1 : edgeFade?.opacity ?? 1}
                  clockRole="authority"
                  seekGeneration={seekGeneration}
                  onClock={previewPinAssetId ? undefined : followMediaClock}
                  onEnded={previewPinAssetId ? undefined : stopAtMediaEnd}
                  onError={() => markMediaFailed(previewAsset.id)}
                  onReadySize={(width, height) =>
                    setPreviewSourceSize((prev) =>
                      prev.w === width && prev.h === height ? prev : { w: width, h: height },
                    )
                  }
                />
              ) : previewAsset ? (
                <img
                  src={api.assetUrl(previewAsset.id)}
                  alt={previewAsset.tag || previewAsset.filename}
                  style={{
                    ...(previewPinAssetId || !viewerLiveFilter ? {} : { filter: viewerLiveFilter }),
                    opacity: previewPinAssetId ? 1 : edgeFade?.opacity ?? 1,
                  }}
                  onError={() => markMediaFailed(previewAsset.id)}
                  onLoad={(event) => {
                    const image = event.currentTarget;
                    if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                      setPreviewSourceSize({ w: image.naturalWidth, h: image.naturalHeight });
                    }
                  }}
                />
              ) : null}
              {previewPinAssetId ? null : (
              <MagiOverlayLayer
                composition={overlays.composition}
                selectedId={overlays.selectedOverlayId}
                onSelect={overlays.setSelectedOverlayId}
                onPatchElement={overlays.patchElement}
                snapEnabled={overlays.snapEnabled}
                playheadFrame={sequence?.playheadFrame ?? 0}
                frameRate={sequence?.frameRate || 24}
                assetUrl={api.assetUrl}
                interactive
                hiddenObjectsSlots={hiddenObjectsSlots}
              />
              )}
            </MagiPreviewFitFrame>
            {previewAsset && failedMedia[previewAsset.id] ? (
              <div className="magi-media-failed" data-testid="magi-media-failed" role="status">
                <strong>Media failed to load</strong>
                <span>This asset could not be decoded. You can replace it in the Library or remove its clips.</span>
                <button
                  type="button"
                  className="magi-chip"
                  onClick={() => removeClipsForAsset(previewAsset.id)}
                >
                  Remove clips using this media
                </button>
                <button
                  type="button"
                  className="magi-chip"
                  onClick={() =>
                    setFailedMedia((prev) => {
                      const next = { ...prev };
                      delete next[previewAsset.id];
                      return next;
                    })
                  }
                >
                  Dismiss
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
      <div className="magi-transport" data-testid="magi-transport">
        <MagiPreviewTransport
          sequence={sequence}
          playing={playing}
          onTogglePlay={() => setPlaying((value) => !value)}
          onSeekFrame={handleSeek}
        />
        <span data-testid="magi-transport-timecode">{sequence ? frameToTimecode(sequence.playheadFrame, sequence.frameRate) : "00:00:00:00"}</span>
        <span className="magi-volume">
          <button
            type="button"
            className="magi-icon-btn"
            data-testid="magi-preview-mute"
            aria-pressed={previewMuted}
            aria-expanded={volumeOpen}
            title={previewMuted ? "Unmute" : "Sound"}
            aria-label={previewMuted ? "Unmute" : "Sound"}
            onClick={() => {
              if (previewMuted) setPreviewMuted(false);
              setVolumeOpen((open) => !open);
            }}
          >
            {previewMuted || previewVolume <= 0 ? (
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
                <path d="M16.5 8.5 21 13m0-4.5L16.5 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
                <path d="M16.5 8.5a5 5 0 0 1 0 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
                <path d="M18.8 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
              </svg>
            )}
          </button>
          {volumeOpen ? (
            <span className="magi-volume__pop">
              <button type="button" className="magi-chip" data-testid="magi-preview-mute-toggle" onClick={() => setPreviewMuted((value) => !value)}>
                {previewMuted ? "Unmute" : "Mute"}
              </button>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={previewVolume}
                data-testid="magi-preview-volume"
                aria-label="Preview volume"
                title="Preview volume"
                onChange={(event) => {
                  const next = Number(event.target.value);
                  setPreviewVolume(next);
                  if (next > 0 && previewMuted) setPreviewMuted(false);
                }}
              />
            </span>
          ) : null}
        </span>
      </div>
    </section>
  );

  const inspector = (
    <div data-testid="magi-inspector" {...bindRegionProps("inspector")}>
      <div className="magi-inspector-header">
        <strong>Inspector</strong>
        <span className="magi-empty">{currentAsset?.tag || currentAsset?.filename || "No media selected"}</span>
      </div>
      {overlays.selected ? (
        <MagiOverlayInspector
          element={overlays.selected}
          accordion={layout.accordionState}
          setAccordion={setAccordion}
          onChange={(patch) => overlays.patchElement(overlays.selectedOverlayId!, patch)}
          onChangeId={overlays.patchElement}
          onDelete={() => overlays.deleteSelected()}
          onDuplicate={() => overlays.duplicateSelected()}
          onBringForward={overlays.bringForward}
          onSendBackward={overlays.sendBackward}
          onBringToFront={overlays.bringToFront}
          onSendToBack={overlays.sendToBack}
          frameRate={sequence?.frameRate || 24}
        />
      ) : null}
      <MagiAccordion id="transform" title="Transform" open={Boolean(layout.accordionState.transform)} onToggle={(next) => setAccordion("transform", next)}>
        <div className="magi-field">
          <label>Playhead</label>
          <input
            type="text"
            value={sequence ? frameToTimecode(sequence.playheadFrame, sequence.frameRate) : "00:00:00:00"}
            readOnly
          />
        </div>
        <div className="magi-field">
          <label>Selection</label>
          <input type="text" value={selectedClip?.name || "No clip selected"} readOnly />
        </div>
      </MagiAccordion>
      <MagiAccordion id="color" title="Color" open={Boolean(layout.accordionState.color)} onToggle={(next) => setAccordion("color", next)}>
        <div className="magi-field">
          <label>Preset</label>
          <select
            data-testid="magi-color-preset"
            value={gradePreset}
            disabled={!activeClipId}
            onChange={(e) => {
              if (!activeClipId) return;
              const kept: Record<string, number> = {};
              for (const key of ["brightness", "highlights", "shadows", "temperature"]) {
                if (gradeParams[key] != null) kept[key] = gradeParams[key];
              }
              patchFinishingLive({
                clipGrades: {
                  [activeClipId]: {
                    presetId: e.target.value,
                    lightingPresetId: activeGrade.lightingPresetId,
                    params: kept,
                  },
                },
              });
            }}
          >
            <option value="">None</option>
            <option value="cinematic_neutral">Cinematic Neutral</option>
            <option value="cinematic_warm">Warm Cinematic</option>
            <option value="cinematic_cool">Cool Cinematic</option>
            <option value="golden_hour">Golden Hour</option>
            <option value="teal_orange">Teal &amp; Orange</option>
            <option value="film_print">Film Print</option>
            <option value="vintage">Vintage</option>
            <option value="high_contrast">High Contrast</option>
            <option value="low_contrast">Low Contrast</option>
            <option value="bleach_bypass">Bleach Bypass</option>
            <option value="dreamy">Dreamy</option>
            <option value="noir">Noir</option>
            <option value="anime_vibrant">Anime Vibrant</option>
            <option value="muted_drama">Muted Drama</option>
            <option value="night_moonlight">Night / Moonlight</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Exposure <span data-testid="magi-color-exposure-value">{sliderValue("brightness")}</span></label>
          <input data-testid="magi-color-exposure" type="range" min="-50" max="50" value={sliderValue("brightness")} disabled={!activeClipId} onChange={(e) => setGradeParam("brightness", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Contrast <span data-testid="magi-color-contrast-value">{sliderValue("contrast")}</span></label>
          <input data-testid="magi-color-contrast" type="range" min="-50" max="50" value={sliderValue("contrast")} disabled={!activeClipId} onChange={(e) => setGradeParam("contrast", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Saturation <span data-testid="magi-color-saturation-value">{sliderValue("saturation")}</span></label>
          <input data-testid="magi-color-saturation" type="range" min="-50" max="50" value={sliderValue("saturation")} disabled={!activeClipId} onChange={(e) => setGradeParam("saturation", Number(e.target.value))} />
        </div>
        <p className="magi-empty" data-testid="magi-grade-live-hint">
          {activeClipId
            ? "This look is on the selected clip. The viewer and Final Render use it."
            : "Select a clip to adjust the live color look."}
        </p>
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-color-preview"
            title="Optional 3-second FFmpeg bake for Compare. The viewer already shows this look live."
            disabled={!currentAsset}
            onClick={async () => {
              if (!currentAsset) return;
              const result = await api.magi.previewColorGrade(project.id, currentAsset.id, gradePreset, gradeParams, activeClipId);
              const previewId = String(result.output_asset_id || result.assetId || "");
              if (previewId) {
                setCompareAssetId(previewId);
                setViewerMode("compare");
              }
              setMessage("Baked compare ready. The viewer already showed this look live.");
              await onChange();
            }}
          >
            Baked Compare
          </button>
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-color-reset"
            onClick={() => {
              if (!activeClipId) return;
              patchFinishingLive({ clipGrades: { [activeClipId]: { presetId: "", lightingPresetId: "", params: {} } } });
              setMessage(null);
            }}
          >
            Reset
          </button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="lighting" title="Lighting" open={Boolean(layout.accordionState.lighting)} onToggle={(next) => setAccordion("lighting", next)}>
        <div className="magi-field">
          <label>Preset</label>
          <select
            data-testid="magi-lighting-preset"
            value={activeGrade.lightingPresetId || "none"}
            disabled={!activeClipId}
            onChange={(event) => applyLightingPreset(event.target.value)}
          >
            <option value="none">None</option>
            <option value="soft_bright">Soft Bright</option>
            <option value="warm">Warm</option>
            <option value="cool">Cool</option>
            <option value="high_contrast">High Contrast</option>
            <option value="low_light_lift">Low Light Lift</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Brightness <span data-testid="magi-lighting-brightness-value">{sliderValue("brightness")}</span></label>
          <input data-testid="magi-lighting-brightness" type="range" min="-50" max="50" value={sliderValue("brightness")} disabled={!activeClipId} onChange={(e) => setGradeParam("brightness", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Highlights <span data-testid="magi-lighting-highlights-value">{sliderValue("highlights")}</span></label>
          <input data-testid="magi-lighting-highlights" type="range" min="-50" max="50" value={sliderValue("highlights")} disabled={!activeClipId} onChange={(e) => setGradeParam("highlights", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Shadows <span data-testid="magi-lighting-shadows-value">{sliderValue("shadows")}</span></label>
          <input data-testid="magi-lighting-shadows" type="range" min="-50" max="50" value={sliderValue("shadows")} disabled={!activeClipId} onChange={(e) => setGradeParam("shadows", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Temperature <span data-testid="magi-lighting-temperature-value">{sliderValue("temperature")}</span></label>
          <input data-testid="magi-lighting-temperature" type="range" min="-50" max="50" value={sliderValue("temperature")} disabled={!activeClipId} onChange={(e) => setGradeParam("temperature", Number(e.target.value))} />
        </div>
        <p className="magi-empty">This lighting is on the selected clip. The viewer and Final Render use it.</p>
        <button type="button" className="magi-chip" data-testid="magi-stabilize-future" disabled title="Stabilize is a future MAGI control.">
          Stabilize (future)
        </button>
      </MagiAccordion>
      <MagiAccordion id="effects" title="Transitions" open={Boolean(layout.accordionState.effects)} onToggle={(next) => setAccordion("effects", next)}>
        {fadeInReady ? (
          <div className="magi-field">
            <label>Fade in</label>
            <select
              data-testid="magi-fade-in"
              value={selectedClip?.transitionInId === "fade" ? "fade" : "none"}
              onChange={(event) => setOpeningFade(event.target.value, transitionSeconds)}
            >
              <option value="none">None</option>
              <option value="fade">Fade</option>
            </select>
          </div>
        ) : null}
        {fadeInReady && selectedClip?.transitionInId === "fade" ? (
          <div className="magi-field">
            <label>
              Fade in duration{" "}
              <span data-testid="magi-fade-in-duration-value">
                {(
                  Math.round(
                    Math.min(
                      transitionMaxSeconds,
                      Math.max(0.1, (selectedClip.transitionInDurationFrames || selectedClip.transitionDurationFrames || (sequence?.frameRate || 24)) / (sequence?.frameRate || 24)),
                    ) * 10,
                  ) / 10
                ).toFixed(1)}
                s
              </span>
            </label>
            <input
              data-testid="magi-fade-in-duration"
              type="range"
              min={0.1}
              max={transitionMaxSeconds}
              step={0.1}
              value={Math.min(
                transitionMaxSeconds,
                Math.max(0.1, (selectedClip.transitionInDurationFrames || selectedClip.transitionDurationFrames || (sequence?.frameRate || 24)) / (sequence?.frameRate || 24)),
              )}
              onChange={(event) => setOpeningFade("fade", Number(event.target.value))}
            />
          </div>
        ) : null}
        <div className="magi-field">
          <label>{tailFadeReady ? "Fade out" : "At this cut"}</label>
          <select
            data-testid="magi-transition-kind"
            value={selectedClip?.transitionOutId || "none"}
            disabled={!transitionReady}
            onChange={(event) => setBoundaryTransition(event.target.value, transitionSeconds)}
          >
            <option value="none">None</option>
            <option value="dissolve" disabled={tailFadeReady}>Dissolve</option>
            <option value="fade">Fade</option>
            <option value="wipe" disabled={tailFadeReady}>Wipe</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Duration <span data-testid="magi-transition-duration-value">{transitionSeconds.toFixed(1)}s</span></label>
          <input
            data-testid="magi-transition-duration"
            type="range"
            min={0.1}
            max={transitionMaxSeconds}
            step={0.1}
            value={transitionSeconds}
            disabled={!transitionReady || (selectedClip?.transitionOutId || "none") === "none"}
            onChange={(event) => setBoundaryTransition(selectedClip?.transitionOutId || "dissolve", Number(event.target.value))}
          />
        </div>
        <p className="magi-empty" data-testid="magi-transition-note">
          {transitionNote}
        </p>
      </MagiAccordion>
      <MagiAccordion id="audio" title="Audio" open={Boolean(layout.accordionState.audio)} onToggle={(next) => setAccordion("audio", next)}>
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip magi-chip--unavailable"
            title={UNSUPPORTED_PLACEBO_COPY.remove_silence.summary}
            onClick={() => queueProposal("remove_silence")}
          >
            {UNSUPPORTED_PLACEBO_COPY.remove_silence.chipLabel}
          </button>
          <button type="button" className="magi-chip" onClick={() => queueProposal("add_ambience")}>Add Ambience</button>
        </div>
        <p className="magi-group-label">AI Music &amp; SFX</p>
        <div className="magi-field">
          <label>Prompt</label>
          <textarea
            data-testid="magi-audio-prompt"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="Give this scene an intimate mysterious score with subtle café ambience..."
            rows={2}
          />
        </div>
        <p className="magi-empty">Music + SFX create separate MAGI sequence clips and set finishing.audio (Final Render mix authority). This is not the Audio Studio mixer.</p>
        <div className="magi-actions">
          <button type="button" className="magi-chip" data-testid="magi-audio-music" disabled={Boolean(finishingJobId)} onClick={async () => {
            try {
              const result = await api.magi.generateAudio(project.id, "music", command || "ambient background", { range: audioRange, clipId: selectedClip?.id });
              waitAccepted(result, "magi_audio_generate");
            } catch (err: any) {
              setMessage(err?.message || "Music generation failed");
            }
          }}>
            Music
          </button>
          <button type="button" className="magi-chip" data-testid="magi-audio-sfx" disabled={Boolean(finishingJobId)} onClick={async () => {
            try {
              const result = await api.magi.generateAudio(project.id, "sfx", command || "ambient sfx", { range: audioRange, clipId: selectedClip?.id });
              waitAccepted(result, "magi_audio_generate");
            } catch (err: any) {
              setMessage(err?.message || "SFX generation failed");
            }
          }}>
            SFX
          </button>
          <button type="button" className="magi-chip" data-testid="magi-audio-both" disabled={Boolean(finishingJobId)} onClick={async () => {
            try {
              const result = await api.magi.generateAudio(project.id, "all", command || "music and ambience", { range: audioRange, clipId: selectedClip?.id });
              waitAccepted(result, "magi_audio_generate");
            } catch (err: any) {
              setMessage(err?.message || "Audio generation failed");
            }
          }}>
            Music + SFX
          </button>
        </div>
        <div className="magi-field">
          <label>Range</label>
          <select data-testid="magi-audio-range" value={audioRange} onChange={(e) => patchFinishing({ audio: { range: e.target.value as "entire" | "clip" } })}>
            <option value="entire">Entire Edit</option>
            <option value="clip">Selected Clip</option>
          </select>
        </div>
      </MagiAccordion>
      <MagiAccordion id="upscale" title="Upscale" open={Boolean(layout.accordionState.upscale)} onToggle={(next) => setAccordion("upscale", next)}>
        {!gpuReady ? <p className="magi-empty">{gpuMessage}</p> : null}
        <div className="magi-field">
          <label>Target</label>
          <select data-testid="magi-upscale-target" value={activeUpscaleTarget} onChange={(e) => patchFinishing({ upscale: { target: e.target.value, engine: upscaleEngine, model: upscaleModel, enabled: true } })}>
            {upscaleChoices.map((row) => (
              <option key={row.id} value={row.id}>{row.label}</option>
            ))}
          </select>
          {resolvedUpscale ? (
            <p className="magi-empty" data-testid="magi-upscale-resolved">
              {resolvedUpscale.width} × {resolvedUpscale.height}
              <br />
              {resolvedUpscale.aspect || aspectLabel(resolvedUpscale.width, resolvedUpscale.height)}
            </p>
          ) : (
            <p className="magi-empty" data-testid="magi-upscale-resolved">The picture keeps its own shape.</p>
          )}
        </div>
        <div className="magi-field">
          <label title={soundAnalysis?.infoLine || ""}>Sound Enhancement</label>
          {soundAnalysis && !soundAnalysis.hasAudio ? (
            <p className="magi-empty" data-testid="magi-upscale-sound-none">No audio detected</p>
          ) : (
            <>
              <select
                data-testid="magi-upscale-sound"
                value={soundChoices.some((row) => row.id === selectedSound) ? selectedSound : "preserve_original"}
                disabled={!currentAsset || !soundHasAudio}
                title={soundAnalysis?.infoLine || ""}
                onChange={(e) => {
                  if (!currentAsset) return;
                  patchFinishing({
                    upscale: {
                      soundProfile: e.target.value,
                      soundSourceAssetId: currentAsset.id,
                      engine: upscaleEngine,
                      model: upscaleModel,
                      target: activeUpscaleTarget,
                      enabled: true,
                    },
                  });
                }}
              >
                {soundChoices.map((row) => (
                  <option key={row.id} value={row.id} disabled={!row.available}>
                    {row.label}
                    {soundHasAudio && row.id === recommendedSound ? " ★ Recommended" : ""}
                    {!row.available ? " — Component unavailable" : ""}
                  </option>
                ))}
              </select>
              {soundRecommendation?.reason ? (
                <p className="magi-empty" data-testid="magi-upscale-sound-reason">
                  {selectedSound === recommendedSound
                    ? `Recommended because: ${soundRecommendation.reason}`
                    : "Using your choice for this clip."}
                </p>
              ) : (
                <p className="magi-empty" data-testid="magi-upscale-sound-reason">Reading the soundtrack…</p>
              )}
            </>
          )}
        </div>
        <div className="magi-field">
          <label>Engine</label>
          <select data-testid="magi-upscale-engine" value={upscaleEngine} onChange={(e) => patchFinishing({ upscale: { engine: e.target.value, target: activeUpscaleTarget, model: e.target.value === "ffmpeg-scale" ? "lanczos" : "realesrgan-x4plus", enabled: true } })}>
            <option value="ffmpeg-scale">FFmpeg (fast)</option>
            <option value="realesrgan-ncnn-vulkan" disabled={!gpuReady}>Real-ESRGAN (GPU)</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Model</label>
          <select data-testid="magi-upscale-model" value={upscaleModel} onChange={(e) => patchFinishing({ upscale: { model: e.target.value, engine: upscaleEngine, target: activeUpscaleTarget, enabled: true } })}>
            <option value="lanczos">Lanczos (general)</option>
            <option value="bicubic">Bicubic (soft)</option>
            <option value="realesrgan-x4plus">General 4x</option>
            <option value="realesr-animevideov3">Anime Video</option>
            <option value="realesrgan-x4plus-anime">Anime 4x</option>
          </select>
        </div>
        <div className="magi-actions">
          <button type="button" className="magi-primary" data-testid="magi-upscale-preview" disabled={!currentAsset || Boolean(finishingJobId)} onClick={async () => {
            if (!currentAsset) return;
            try {
              const soundProfile = soundHasAudio ? selectedSound : "preserve_original";
              const result = await api.magi.previewUpscale(project.id, currentAsset.id, "ffmpeg-scale", upscaleEngine === "ffmpeg-scale" ? upscaleModel : "lanczos", activeUpscaleTarget, soundProfile);
              if (result.output_asset_id) {
                setCompareAssetId(String(result.output_asset_id));
                setViewerMode("compare");
              }
              setMessage(
                soundProfile !== "preserve_original"
                  ? "Preview is a short sample with the selected sound treatment. Apply Upscale finishes the full clip. Source clip is unchanged."
                  : "Upscale preview ready. Source clip is unchanged.",
              );
              await onChange();
            } catch (err: any) {
              setMessage(err?.message || "Upscale preview failed");
            }
          }}>
            Preview
          </button>
          <button type="button" className="magi-chip" data-testid="magi-upscale-apply" disabled={!currentAsset || Boolean(finishingJobId) || (upscaleEngine === "realesrgan-ncnn-vulkan" && !gpuReady)} onClick={async () => {
            if (!currentAsset) return;
            try {
              const soundProfile = soundHasAudio ? selectedSound : "preserve_original";
              const result = await api.magi.applyUpscale(project.id, currentAsset.id, upscaleEngine, upscaleModel, activeUpscaleTarget, soundProfile);
              waitAccepted(result, "magi_upscale");
            } catch (err: any) {
              setMessage(err?.message || gpuMessage);
            }
          }}>
            Apply Upscale
          </button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="clipProperties" title="Clip Properties" open={Boolean(layout.accordionState.clipProperties)} onToggle={(next) => setAccordion("clipProperties", next)}>
        <div className="magi-field">
          <label>Clip</label>
          <input type="text" value={selectedClip?.name || "No clip selected"} readOnly />
        </div>
        {selectedClip ? (
          <p className="magi-empty">
            Start: {frameToTimecode(selectedClip.startFrame, sequence?.frameRate || 24)}
            <br />
            Duration: {frameToTimecode(selectedClip.durationFrames, sequence?.frameRate || 24)}
            <br />
            In: {selectedClip.inPoint} · Out: {selectedClip.outPoint}
            <br />
            Asset: {selectedClip.assetId || "—"}
          </p>
        ) : (
          <p className="magi-empty">Choose a clip to see its properties.</p>
        )}
        <p className="magi-empty">
          Focus: {focusRegion}
          <br />
          Recipe: {sequence?.recipeId || "Balanced"}
          <br />
          Dirty: {editorDirty ? "Yes" : "No"}
        </p>
      </MagiAccordion>
      <MagiAccordion id="export" title="Export" open={Boolean(layout.accordionState.export)} onToggle={(next) => setAccordion("export", next)}>
        {finishingJob ? (
          <p className="magi-empty" data-testid="magi-job-status">
            {finishingJob.kind}: {finishingJob.status} — {finishingJob.stage || finishingJob.message}
          </p>
        ) : null}
        {finishingJob && ["failed", "cancelled", "canceled", "timed_out"].includes(finishingJob.status) ? (
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-job-retry"
            onClick={() => {
              setFinishingJob(null);
              setFinishingJobId(null);
              setMessage("Ready to try again.");
            }}
          >
            Retry
          </button>
        ) : null}
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-preview-render"
            disabled={!sequence?.clips.length || Boolean(finishingJobId)}
            onClick={async () => {
              try {
                const result = await api.magi.createRender(project.id, {
                  profile: "preview",
                  range: audioRange,
                  clipId: selectedClip?.id,
                  includeColor: true,
                  includeAudio: true,
                  upscale: { enabled: true, engine: "ffmpeg-scale", model: "lanczos", target: activeUpscaleTarget },
                });
                waitAccepted(result, "magi_final_render");
              } catch (err: any) {
                setMessage(err?.message || "Preview render failed");
              }
            }}
          >
            Preview Render
          </button>
          <button
            type="button"
            className="magi-primary"
            data-testid="magi-final-render"
            disabled={!sequence?.clips.length || Boolean(finishingJobId) || finalRenderSession !== null}
            onClick={() => {
              if (finishingJobId || finalRenderLock.current || finalRenderSession) return;
              finalRenderJobRef.current = null;
              const scene = project.scenes.find((item) => item.id === handoffSceneId);
              setFinalOutputName(suggestedFinalVideoName(scene?.name, project.name));
              setFocusRegion("modal");
              setFinalRenderSession(emptyFinalRenderSession());
            }}
          >
            Final Render
          </button>
        </div>
        <p className="magi-empty">Preview is a short look. Final uses MAGI color grades, MAGI finishing.audio (Music/SFX asset ids from this Audio panel), and upscale settings. Audio Studio mixer is adjacent and is not used by Final Render.</p>
      </MagiAccordion>
      <MagiAccordion id="compare" title="Compare" open={Boolean(layout.accordionState.compare)} onToggle={(next) => setAccordion("compare", next)}>
        <div className="magi-field">
          <label>Compare with</label>
          <select
            data-testid="magi-compare-with"
            value={compareAssetId && compareAssetId === splitOriginalId ? "original" : compareAssetId}
            onChange={(event) => {
              const value = event.target.value;
              if (value === "original") {
                if (splitOriginalId) setCompareAssetId(splitOriginalId);
                return;
              }
              setCompareAssetId(value);
            }}
          >
            <option value="">Current only</option>
            {splitOriginalId ? <option value="original">Original</option> : null}
            {compareOptions
              .filter((asset) => asset.id !== splitOriginalId)
              .map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.tag || asset.filename}
                </option>
              ))}
          </select>
        </div>
        <p className="magi-empty" data-testid="magi-compare-label">
          Compare with: {compareAssetId && compareAssetId === splitOriginalId ? "Original" : compareAsset?.tag || compareAsset?.filename || "nothing selected"}
        </p>
        <div className="magi-actions">
          <button type="button" className="magi-chip" data-testid="magi-compare-open" onClick={() => setViewerMode("compare")}>
            Compare
          </button>
          <button type="button" className="magi-chip" data-testid="magi-split-open" onClick={() => setViewerMode("split")}>
            Split View
          </button>
        </div>
        <p className="magi-empty">Compare shows the current grade beside the source above. Split View divides that pair in one picture.</p>
      </MagiAccordion>
    </div>
  );

  const closeFinalRender = () => {
    finalRenderJobRef.current = null;
    finalRenderLock.current = false;
    setFinalRenderSession(null);
  };

  const confirmFinalRender = async () => {
    if (!sequence || finalRenderLock.current || finishingJobId || finalRenderSession?.phase !== "confirm") return;
    const named = normalizeFinalVideoName(finalOutputName);
    if (!named || finalVideoNameMessage(finalOutputName, project.assets)) return;
    const built = buildFinalRenderConfirm({
      sequence,
      range: audioRange,
      selectedClipId: selectedClip?.id,
      upscaleEnabled: finishing.upscale?.enabled === true,
      upscaleEngine,
      upscaleModel,
      upscaleTarget: activeUpscaleTarget,
      resolvedUpscale:
        finishing.upscale?.enabled === true && resolvedUpscale
          ? {
              id: resolvedUpscale.id,
              width: resolvedUpscale.width,
              height: resolvedUpscale.height,
              aspect: resolvedUpscale.aspect,
            }
          : null,
      assets: mediaAssets,
      outputName: named.title,
    });
    finalRenderLock.current = true;
    setFinalRenderSession((current) =>
      current
        ? {
            ...current,
            phase: "running",
            progress: 0,
            stage: "Queued",
            message: "Queued…",
            error: null,
            outputName: named.title,
            outputFile: named.filename,
            log: [{ stage: "Queued", message: "Queued…" }],
          }
        : current,
    );
    try {
      const result = await api.magi.createRender(project.id, built.request);
      const jobId = String(result.jobId || (Array.isArray(result.jobIds) ? result.jobIds[0] : "") || "");
      if (!jobId) {
        const message = String(result.message || "The studio did not accept this render.");
        setFinalRenderSession((current) =>
          current
            ? {
                ...current,
                phase: "failed",
                stage: "Failed",
                message,
                error: message,
                log: [...current.log, { stage: "Failed", message, failed: true }],
              }
            : current,
        );
        return;
      }
      finalRenderJobRef.current = jobId;
      setFinalRenderSession((current) =>
        current ? { ...current, jobId, phase: "running", message: String(result.message || "Queued…") } : current,
      );
      waitAccepted(result, "magi_final_render");
    } catch (err) {
      const message = describeMagiError(err);
      setFinalRenderSession((current) =>
        current
          ? {
              ...current,
              phase: "failed",
              stage: "Failed",
              message,
              error: message,
              log: [...current.log, { stage: "Failed", message, failed: true }],
            }
          : current,
      );
    } finally {
      finalRenderLock.current = false;
    }
  };

  const revealLibraryPane = () => {
    const panes = new Set(["library", "media", "assets"]);
    const inLeft = layout.leftPaneOrder.some((pane) => panes.has(pane));
    const inRight = layout.rightPaneOrder.some((pane) => panes.has(pane));
    if (inLeft && layout.leftDockCollapsed) toggleLeftDock();
    if ((!inLeft || inRight) && layout.rightDockCollapsed && inRight) toggleRightDock();
    for (const pane of [...layout.leftPaneOrder, ...layout.rightPaneOrder]) {
      if (panes.has(pane)) setAccordion(pane, true);
    }
  };

  const openFinishedRender = async (where: "viewer" | "library" | "queue") => {
    const assetId = finalRenderSession?.assetId || null;
    const jobId = finalRenderSession?.jobId || null;
    if ((where === "viewer" || where === "library") && !assetId) return;
    try {
      await onChange();
    } catch {
      /* the finished asset may already be in this project */
    }
    if (where === "viewer" && assetId) {
      setViewerMode("viewer");
      setViewerAssetId(assetId);
      setPreviewPinAssetId(assetId);
      setSeekGeneration((value) => value + 1);
      setFocusRegion("viewer");
    }
    if (where === "library" && assetId) {
      setViewerAssetId(assetId);
      setAssetFilter("all");
      revealLibraryPane();
      setLibraryFocusId(assetId);
      setFocusRegion("media_bin");
    }
    if (where === "queue") {
      if (jobId) setQueueFocusJobId(jobId);
      if (layout.leftDockCollapsed) toggleLeftDock();
      setRenderQueueOpen(true);
      setFocusRegion("media_bin");
    }
    closeFinalRender();
  };

  useEffect(() => {
    if (!layout.renderQueueOpen) return;
    document.querySelector("[data-testid=magi-render-queue]")?.scrollIntoView({ block: "nearest" });
  }, [layout.renderQueueOpen, queueFocusJobId]);

  if (!sequence) {
    return (
      <div className="magi-shell" data-testid="magi-editor">
        <p className="magi-empty">Loading MAGI sequence…</p>
      </div>
    );
  }

  return (
    <div
      ref={workspaceFs.containerRef}
      className={`magi-shell${viewportMode === "EXPANDED" ? " is-expanded-viewport" : ""}`}
      data-testid="magi-editor"
      data-viewport-mode={viewportMode}
    >
      <WorkspaceFullscreenBanner visible={workspaceFs.showBanner} />

      <div className="magi-workspace-bar">
        <strong>Workspace</strong>
        <WorkspaceFullscreenControls
          fs={workspaceFs}
          expandActive={layout.leftDockCollapsed && layout.rightDockCollapsed}
          onExpand={() => {
            setBothDocksCollapsed(nextDualDrawerCollapsed(layout.leftDockCollapsed, layout.rightDockCollapsed));
          }}
        />
        <select
          aria-label="Workspace layout preset"
          value={layout.activePreset}
          onChange={(event) => applyWorkspacePreset(event.target.value as MagiPreset)}
          data-testid="magi-layout-preset"
        >
          <option value="default">Default</option>
          <option value="viewer-focus">Viewer Focus</option>
          <option value="image-editing">Assembly</option>
          <option value="compare-review">Compare Review</option>
          <option value="custom">Custom</option>
        </select>
        <button type="button" className="magi-chip" onClick={() => toggleLeftDock()} data-testid="magi-toggle-left-dock">
          {layout.leftDockCollapsed ? "Show bins" : "Hide bins"}
        </button>
        <button type="button" className="magi-chip" onClick={() => toggleRightDock()} data-testid="magi-toggle-right-dock">
          {layout.rightDockCollapsed ? "Show inspector" : "Hide inspector"}
        </button>
        <button
          type="button"
          className="magi-chip"
          onClick={() => {
            setViewportMode("STANDARD");
            resetWorkspace();
          }}
          data-testid="magi-reset-workspace"
        >
          Reset Workspace
        </button>
        <div className="magi-tabs" role="tablist" aria-label="Viewer mode">
          {viewerModes}
        </div>
        <button
          type="button"
          className={`magi-chip ${overlays.safeGuides ? "active" : ""}`}
          data-testid="magi-viewer-guides"
          aria-pressed={overlays.safeGuides}
          title={overlays.safeGuides ? "Hide composition guides" : "Show composition guides"}
          aria-label={overlays.safeGuides ? "Hide composition guides" : "Show composition guides"}
          onClick={() => overlays.setSafeGuides(!overlays.safeGuides)}
        >
          Guides
        </button>
        {SHOW_SHELVED_MONITOR_CHROME ? (
          <span
            className="magi-chip magi-viewer-fit is-active"
            data-testid="magi-viewer-fit"
            role="status"
            title="The full frame stays inside the Preview Monitor"
            aria-label="Viewer fit: the full frame stays inside the Preview Monitor"
          >
            Fit
          </span>
        ) : null}
        <span className="magi-workspace-status" data-testid="magi-workspace-status">
          <StatusBadge status={saveState === "error" || overlayPersist.error ? "Blocked" : editorDirty ? "Draft" : "Certified"} />
          <span>{saveState === "saving" || overlayPersist.saving ? "Saving…" : editorDirty ? "Unsaved changes" : "Saved"}</span>
          {saveState === "error" || overlayPersist.error ? (
            <button
              type="button"
              className="magi-msg__close"
              data-testid="magi-dismiss-blocked"
              aria-label="Close notice"
              onClick={() => {
                setSaveError(null);
                setSaveState((state) => (state === "error" ? "idle" : state));
                setOverlayPersist((prev) => (prev.error ? { ...prev, error: null } : prev));
              }}
            >
              ×
            </button>
          ) : null}
        </span>
      </div>

      {unpublishedSceneId && !hideUnpublishedNotice ? (
        <MagiNotice
          testId="magi-unpublished-master"
          onClose={() => setHideUnpublishedNotice(true)}
          trailing={(() => {
            const timeline = buildProjectWorkspaceLocation({
              projectId: project.id,
              tab: "timeline",
              sceneId: unpublishedSceneId,
            });
            return timeline ? (
              <Link className="magi-msg__action" to={`${timeline.pathname}${timeline.search}`}>
                Open Timeline
              </Link>
            ) : null;
          })()}
        >
          This scene has not been published from Timeline yet.
        </MagiNotice>
      ) : null}
      {message && !String(message).trim().startsWith("{") ? (
        <MagiNotice onClose={() => setMessage(null)}>{message}</MagiNotice>
      ) : null}
      {saveError && !String(saveError).trim().startsWith("{") ? (
        <MagiNotice
          testId="magi-save-notice"
          onClose={() => {
            setSaveError(null);
            setSaveState((state) => (state === "error" ? "idle" : state));
          }}
        >
          {saveError}
        </MagiNotice>
      ) : null}
      {overlayPersist.error ? (
        <MagiNotice onClose={() => setOverlayPersist((prev) => ({ ...prev, error: null }))}>
          {overlayPersist.error}
        </MagiNotice>
      ) : null}
      {compactNotice && !hideCompactNotice ? (
        <MagiNotice testId="magi-compact-notice" onClose={() => setHideCompactNotice(true)}>
          Compact viewport detected. MAGI keeps the viewer forward and leaves bins collapsible.
        </MagiNotice>
      ) : null}

      <div
        className="timeline-v2__body magi-shell__layout"
        data-testid="magi-workspace-body"
        data-left-open={layout.leftDockCollapsed ? "false" : "true"}
        data-right-open={layout.rightDockCollapsed ? "false" : "true"}
        style={{
          ["--timeline-left-width" as string]: `${layout.leftDockWidth}px`,
          ["--timeline-right-width" as string]: `${layout.rightDockWidth}px`,
        }}
      >
        <button
          type="button"
          className="timeline-v2__drawer-handle timeline-v2__drawer-handle--left"
          data-testid="magi-drawer-handle-left"
          aria-expanded={!layout.leftDockCollapsed}
          title={layout.leftDockCollapsed ? "Open bins" : "Close bins"}
          aria-label={layout.leftDockCollapsed ? "Open bins" : "Close bins"}
          onClick={() => toggleLeftDock()}
        >
          {layout.leftDockCollapsed ? "›" : "‹"}
        </button>
        <aside
          className={`timeline-v2__drawer timeline-v2__drawer--left${layout.leftDockCollapsed ? " timeline-v2__drawer--closed" : " timeline-v2__drawer--open"}`}
          data-testid="magi-drawer-left"
          aria-hidden={layout.leftDockCollapsed}
        >
          <div className="timeline-v2__drawer-body">
            <div className="magi-dock-scroll" {...bindRegionProps("media_bin")}>
              {layout.leftPaneOrder.flatMap((pane) => {
                const paneNode = renderPane(pane);
                if (pane !== "recipes") return [paneNode];
                return [paneNode, (
                  <div key="render-queue" className="magi-dock-pane" data-pane="renderQueue" data-testid="magi-render-queue">
                    <MagiAccordion
                      id="renderQueue"
                      title="Render Queue"
                      open={layout.renderQueueOpen}
                      onToggle={setRenderQueueOpen}
                    >
                      <JobPanel projectId={project.id} focusJobId={queueFocusJobId} onDone={() => void onChange()} />
                    </MagiAccordion>
                  </div>
                )];
              })}
              {layout.leftPaneOrder.includes("recipes") ? null : (
                <div className="magi-dock-pane" data-pane="renderQueue" data-testid="magi-render-queue">
                  <MagiAccordion
                    id="renderQueue"
                    title="Render Queue"
                    open={layout.renderQueueOpen}
                    onToggle={setRenderQueueOpen}
                  >
                    <JobPanel projectId={project.id} focusJobId={queueFocusJobId} onDone={() => void onChange()} />
                  </MagiAccordion>
                </div>
              )}
            </div>
          </div>
          <div
            className="timeline-v2__splitter"
            data-testid="magi-splitter-left"
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={layout.leftDockWidth}
            aria-hidden={layout.leftDockCollapsed}
            tabIndex={layout.leftDockCollapsed ? -1 : 0}
            onPointerDown={(event) => onLeftSplitterPointerDown(event, "left")}
            onPointerMove={onLeftRightSplitterMove}
            onPointerUp={onLeftRightSplitterUp}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") setLeftWidth(layout.leftDockWidth - (event.shiftKey ? 32 : 10));
              if (event.key === "ArrowRight") setLeftWidth(layout.leftDockWidth + (event.shiftKey ? 32 : 10));
            }}
          />
        </aside>

        <main className="timeline-v2__workspace magi-center">
          <MagiWorkspaceStack
            projectId={project.id}
            extraControls={viewerControls}
            expanded={false}
            monitor={monitor}
            timeline={
              <div className="magi-timeline-shell">
                <div className="magi-timeline-toolbar">
                  <div className="magi-toolbar-group" role="toolbar" aria-label="MAGI timeline tools">
                    <button type="button" className="magi-icon-btn" aria-label="Undo" title="Undo" onClick={undo} disabled={!historyRef.current.canUndo()}>↶</button>
                    <button type="button" className="magi-icon-btn" aria-label="Redo" title="Redo" onClick={redo} disabled={!historyRef.current.canRedo()}>↷</button>
                    <button type="button" className="magi-icon-btn" aria-label="Split clip" title="Split clip" onClick={() => selectedClip && !isGraphicsClipId(selectedClip.id) && pushSequenceCommand("Split clip", { kind: "Split", payload: { clipId: selectedClip.id, frame: sequence.playheadFrame } })}>✂</button>
                    <button type="button" className="magi-icon-btn" aria-label="Duplicate selection" title="Duplicate selection" onClick={() => selection.length && pushSequenceCommand("Duplicate clips", { kind: "Duplicate", payload: { offsetFrames: Math.max(1, sequence.frameRate) } })}>⧉</button>
                    <button type="button" className="magi-icon-btn" aria-label="Add marker" title="Add marker" onClick={() => pushSequenceCommand("Add marker", { kind: "AddMarker", payload: { frame: sequence.playheadFrame, label: "Beat" } })}>◆</button>
                  </div>
                  <div className="magi-toolbar-meta">
                    <span>{visibleMagiTracks((sequenceForTimeline || sequence).tracks).length} tracks</span>
                    <span>{(sequenceForTimeline || sequence).clips.length} clips</span>
                    <span>{selection.length} selected</span>
                  </div>
                </div>
                <MagiSequenceTimeline
                  sequence={sequenceForTimeline || sequence}
                  selection={selection}
                  playing={playing}
                  selectedAssetId={viewerAssetId}
                  mediaByAssetId={timelineMedia}
                  onSelect={handleSelect}
                  onSeek={handleSeek}
                  onTrim={handleTrim}
                  onMove={handleMove}
                  onDropAsset={handleDropAsset}
                  failedAssetIds={failedMediaIds}
                  selectedTrackId={selectedTrackId}
                  onSelectTrack={handleSelectTrack}
                  onAddObjectsTrack={handleAddObjectsTrack}
                  onRemoveObjectsTrack={handleRemoveObjectsTrack}
                  onToggleTrackControl={toggleTrackControl}
                />
              </div>
            }
          />
        </main>

        <aside
          className={`timeline-v2__drawer timeline-v2__drawer--right${layout.rightDockCollapsed ? " timeline-v2__drawer--closed" : " timeline-v2__drawer--open"}`}
          data-testid="magi-drawer-right"
          aria-hidden={layout.rightDockCollapsed}
        >
          <div
            className="timeline-v2__splitter"
            data-testid="magi-splitter-right"
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={layout.rightDockWidth}
            aria-hidden={layout.rightDockCollapsed}
            tabIndex={layout.rightDockCollapsed ? -1 : 0}
            onPointerDown={(event) => onLeftSplitterPointerDown(event, "right")}
            onPointerMove={onLeftRightSplitterMove}
            onPointerUp={onLeftRightSplitterUp}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") setRightWidth(layout.rightDockWidth + (event.shiftKey ? 32 : 10));
              if (event.key === "ArrowRight") setRightWidth(layout.rightDockWidth - (event.shiftKey ? 32 : 10));
            }}
          />
          <div className="timeline-v2__drawer-body">
            <div className="magi-dock-scroll">
              <div className="film-timeline__tabs" role="tablist" data-testid="magi-side-tabs">
                {(
                  [
                    ["inspector", "Inspector"],
                    ["hotkeys", "Hot Keys"],
                    ["gpu", "GPU"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={sideTab === id}
                    className={sideTab === id ? "is-selected" : ""}
                    data-testid={`magi-tab-${id}`}
                    onClick={() => setSideTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {sideTab === "inspector" ? inspector : null}
              {sideTab === "hotkeys" ? <TimelineHotKeysPane workspace="magi" /> : null}
              {sideTab === "gpu" ? (
                <TimelineGpuPane project={project} onChange={() => void onChange()} />
              ) : null}
            </div>
          </div>
        </aside>
        <button
          type="button"
          className="timeline-v2__drawer-handle timeline-v2__drawer-handle--right"
          data-testid="magi-drawer-handle-right"
          aria-expanded={!layout.rightDockCollapsed}
          title={layout.rightDockCollapsed ? "Open inspector" : "Close inspector"}
          aria-label={layout.rightDockCollapsed ? "Open inspector" : "Close inspector"}
          onClick={() => toggleRightDock()}
        >
          {layout.rightDockCollapsed ? "‹" : "›"}
        </button>
      </div>

      <MagiPreviewMixer
        sequence={sequence}
        playing={playing}
        muted={previewMuted}
        volume={previewVolume}
        seekGeneration={seekGeneration}
      />
      {libraryPickerOpen || imageOverlayPickerOpen ? (
        <AddFromProjectLibraryModal
          project={project}
          alreadyIds={imageOverlayPickerOpen ? [] : (sequence?.clips || []).map((clip) => clip.assetId)}
          onAdd={handleAddFromLibrary}
          onClose={() => {
            setLibraryPickerOpen(false);
            setImageOverlayPickerOpen(false);
          }}
          onAssetsChanged={() => void onChange()}
        />
      ) : null}

      {finalRenderSession ? (
        <MagiFinalRenderDialog
          summary={
            buildFinalRenderConfirm({
              sequence,
              range: audioRange,
              selectedClipId: selectedClip?.id,
              upscaleEnabled: finishing.upscale?.enabled === true,
              upscaleEngine,
              upscaleModel,
              upscaleTarget: activeUpscaleTarget,
              resolvedUpscale:
                finishing.upscale?.enabled === true && resolvedUpscale
                  ? {
                      id: resolvedUpscale.id,
                      width: resolvedUpscale.width,
                      height: resolvedUpscale.height,
                      aspect: resolvedUpscale.aspect,
                    }
                  : null,
              assets: mediaAssets,
            }).sections
          }
          session={finalRenderSession}
          busy={finalRenderLock.current}
          outputName={finalOutputName}
          nameMessage={finalRenderSession.phase === "confirm" ? finalVideoNameMessage(finalOutputName, project.assets) : null}
          onOutputNameChange={setFinalOutputName}
          onCancel={() => {
            closeFinalRender();
            setFocusRegion("none");
          }}
          onConfirm={() => void confirmFinalRender()}
          onClose={() => {
            closeFinalRender();
            setFocusRegion("none");
          }}
          onShowViewer={() => void openFinishedRender("viewer")}
          onShowLibrary={() => void openFinishedRender("library")}
          onShowQueue={() => void openFinishedRender("queue")}
        />
      ) : null}
    </div>
  );
}

export function MagiEditorWorkspace({
  project,
  onChange,
}: {
  project: Project;
  onChange: () => Promise<void>;
}) {
  return (
    <MagiWorkspaceLayoutProvider>
      <MagiFocusProvider>
        <MagiEditorInner project={project} onChange={onChange} />
      </MagiFocusProvider>
    </MagiWorkspaceLayoutProvider>
  );
}

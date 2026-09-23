import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
import { fetchMagiSequence, saveMagiSequence } from "../../magiSequence/api";
import { MagiFocusProvider, useMagiFocus } from "../../magiSequence";
import { useMagiKeyboard } from "../../magiSequence/useMagiKeyboard";
import { JobPanel } from "../JobPanel";
import { MagiSequenceTimeline } from "./MagiSequenceTimeline";
import { MagiWorkspaceStack } from "./MagiWorkspaceStack";
import { MagiAccordion } from "./layout/MagiAccordion";
import { MagiWorkspaceLayoutProvider, useMagiLayout } from "./layout/MagiWorkspaceLayoutProvider";
import type { MagiPaneId, MagiPreset } from "./layout/MagiLayoutPersistence";
import { MagiOverlayLayer } from "./overlays/MagiOverlayLayer";
import { MagiOverlayInspector } from "./overlays/MagiOverlayInspector";
import { MagiEditorCommandStack } from "./overlays/MagiEditorCommandStack";
import { MagiCompareFitMedia, MagiPreviewFitFrame } from "./MagiPreviewFitFrame";
import { MagiVideoStage } from "./MagiVideoStage";
import { MagiSplitView } from "./MagiSplitView";
import { MagiPreviewMixer, audioLaneOwnsPlayback } from "./MagiPreviewMixer";
import { bindMagiPlaybackStats, secondsToPlayheadFrame } from "./magiPlaybackClock";
import { AddFromProjectLibraryModal } from "../timeline-master/AddFromProjectLibraryModal";
import { libraryThumbKind, libraryThumbUrl } from "../library/libraryThumb";
import { liveGradeCssFilter, liveGradeHasNonLiveChannels } from "../../magiSequence/liveGrade";
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
import "./magi-editor.css";

const PRODUCTION_CORRECTION_RE = /\b(re-?take|inpaint|mask\s*repair|timed\s*prompt)\b/;
const PRODUCTION_CORRECTION_COPY =
  "That is a production correction. Return to Timeline for Re-Take — MAGI only finishes completed takes.";

type ViewerMode = "viewer" | "compare" | "split" | "histogram" | "vectorscope";

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
      "Brighten refused: no brighten engine. Use Inspector Color → Exposure / Apply Grade instead.",
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
  if (text.includes("dissolve")) {
    const copy = UNSUPPORTED_PLACEBO_COPY.add_dissolve;
    return {
      kind: "add_dissolve",
      title: copy.title,
      summary: copy.summary,
      approveLabel: "Acknowledge",
    };
  }
  if (text.includes("stabilize")) {
    const copy = UNSUPPORTED_PLACEBO_COPY.stabilize;
    return {
      kind: "stabilize",
      title: copy.title,
      summary: copy.summary,
      approveLabel: "Acknowledge",
    };
  }
  if (text.includes("brighten")) {
    const copy = UNSUPPORTED_PLACEBO_COPY.brighten;
    return {
      kind: "brighten",
      title: copy.title,
      summary: copy.summary,
      approveLabel: "Acknowledge",
    };
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
  const { t } = useTranslation("magi");
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

  const [sequence, setSequence] = useState<MagiSequenceDocument | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [selectedObjectsSlot, setSelectedObjectsSlot] = useState<1 | 2>(1);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [viewerMode, setViewerMode] = useState<ViewerMode>("viewer");
  const [viewerAssetId, setViewerAssetId] = useState<string | null>(null);
  const [compareAssetId, setCompareAssetId] = useState("");
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [imageOverlayPickerOpen, setImageOverlayPickerOpen] = useState(false);
  const [previewMuted, setPreviewMuted] = useState(false);
  const [previewVolume, setPreviewVolume] = useState(1);
  const [failedThumbs, setFailedThumbs] = useState<Record<string, boolean>>({});
  const [publishedMasterId, setPublishedMasterId] = useState<string | null>(null);
  const [assetFilter, setAssetFilter] = useState<"all" | "video" | "image" | "audio">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [unpublishedSceneId, setUnpublishedSceneId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [seekGeneration, setSeekGeneration] = useState(0);
  const [command, setCommand] = useState("");
  const [pendingProposal, setPendingProposal] = useState<PendingProposal | null>(null);
  const [jobRefreshTick, setJobRefreshTick] = useState(0);
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
    return clipUnderPlayhead(sequence, sequence.playheadFrame);
  }, [sequence]);
  const previewAssetId = playheadClip?.assetId || viewerAssetId;
  const previewAsset = useMemo(
    () => mediaAssets.find((asset) => asset.id === previewAssetId) || null,
    [mediaAssets, previewAssetId],
  );
  const previewVideoTime = useMemo(() => {
    if (!sequence || !playheadClip) return null;
    const sourceFrame = clipSourceFrame(playheadClip, sequence.playheadFrame);
    if (sourceFrame == null) return null;
    return sourceFrame / Math.max(1, sequence.frameRate);
  }, [playheadClip, sequence]);
  const [previewSourceSize, setPreviewSourceSize] = useState({ w: 16, h: 9 });
  useEffect(() => {
    setPreviewSourceSize({ w: 16, h: 9 });
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
        const published =
          loaded.clips.find((clip) => clip.ingestRole === "published_master")?.assetId || null;
        if (published) setPublishedMasterId(published);
        const firstAssetId =
          published ||
          loaded.clips[0]?.assetId ||
          mediaAssets[0]?.id ||
          images[0]?.id ||
          videos[0]?.id ||
          audioAssets[0]?.id ||
          null;
        setViewerAssetId(firstAssetId);
      } catch {
        if (cancelled) return;
        const fallback = migrateToPostProductionTracks(createEmptySequence(project.id, project.fps || 24));
        setSequence(fallback);
        setViewerAssetId(mediaAssets[0]?.id || null);
        setMessage("Started a fresh MAGI sequence locally because no saved sequence was available.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [audioAssets, images, mediaAssets, project.fps, project.id, videos]);

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
      if (nonce === saveNonceRef.current) {
        setSaveState("error");
        setSaveError(error instanceof Error ? error.message : "MAGI sequence save failed");
      }
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

  const followMediaClock = useCallback((seconds: number) => {
    const current = sequenceRef.current;
    if (!current || !playingRef.current) return;
    const frame = secondsToPlayheadFrame(seconds, current.frameRate, current.durationFrames);
    if (current.playheadFrame === frame) return;
    setSequence((prev) => {
      if (!prev || prev.playheadFrame === frame) return prev;
      return { ...prev, playheadFrame: frame };
    });
  }, []);

  const stopAtMediaEnd = useCallback(() => {
    setPlaying(false);
    const current = sequenceRef.current;
    if (!current) return;
    const last = Math.max(0, current.durationFrames - 1);
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

  // m5 B5: send MAGI timeline clips to the W46 Timeline (first scene) as a
  // batch-owned export. No regeneration — provenance is recorded server-side.
  const [timelineExportBusy, setTimelineExportBusy] = useState(false);
  const [finishingJobId, setFinishingJobId] = useState<string | null>(null);
  const [finishingJob, setFinishingJob] = useState<{ status: string; stage: string; message: string; kind: string } | null>(null);
  const [gpuReady, setGpuReady] = useState(false);
  const [gpuMessage, setGpuMessage] = useState("GPU Upscaling unavailable. FFmpeg upscale remains available.");

  const finishing: MagiFinishingState = sequence?.finishing || {};
  const activeClipId = selectedClip?.id || playheadClip?.id || "";
  const activeGrade = (activeClipId && finishing.clipGrades?.[activeClipId]) || {};
  const gradePreset = activeGrade.presetId || "";
  const gradeParams = activeGrade.params || {};
  const sliderValue = (key: string) => Math.round(((gradeParams[key] || 0) * 100));
  const audioRange = finishing.audio?.range || "entire";
  const upscaleEngine = finishing.upscale?.engine || "ffmpeg-scale";
  const upscaleModel = finishing.upscale?.model || (upscaleEngine === "ffmpeg-scale" ? "lanczos" : "realesrgan-x4plus");
  const upscaleTarget = finishing.upscale?.target || "1920x1080";
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
  const viewerLiveFilter =
    previewAssetId && previewAssetId === finishing.visualResultAssetId ? "" : liveFilter;
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
    setSequence(migrateToPostProductionTracks(raw));
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
      patchFinishingLive({ clipGrades: { [activeClipId]: { presetId: gradePreset, params: next } } });
    },
    [activeClipId, gradeParams, gradePreset, patchFinishingLive],
  );

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
        const status = String(job.status || "");
        if (["done", "failed", "cancelled", "canceled", "timed_out"].includes(status)) {
          setFinishingJobId(null);
          if (status === "done") {
            await reloadSequence();
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
  const handleExportToTimeline = useCallback(async () => {
    const current = sequenceRef.current;
    const scene = project.scenes[0];
    if (!current || !scene) {
      setMessage("Add a project scene before exporting to the Timeline.");
      return;
    }
    if (!current.clips.length) {
      setMessage("Add clips to the MAGI timeline before exporting.");
      return;
    }
    if (timelineExportBusy) return;
    setTimelineExportBusy(true);
    setSaveError(null);
    try {
      const result = await api.magi.exportToTimeline(project.id, scene.id, {
        label: "MAGI export",
        clips: current.clips.map((clip) => ({
          clipId: clip.id,
          assetId: clip.assetId,
          name: clip.name,
          startFrame: clip.startFrame,
          durationFrames: clip.durationFrames,
        })),
      });
      if (!result.ok) {
        setMessage("Timeline export did not place all clips.");
        return;
      }
      setMessage(`Exported ${current.clips.length} clip(s) to Timeline batch ${result.batchBlockId}.`);
    } catch (error: unknown) {
      setSaveError(error instanceof Error ? error.message : "Timeline export failed");
    } finally {
      setTimelineExportBusy(false);
    }
  }, [project.id, project.scenes, timelineExportBusy]);

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
      seekPlayhead(Math.max(0, sequenceRef.current.playheadFrame + dir * sequenceRef.current.frameRate));
    },
    onShuttle: () => undefined,
    onFrameStep: (delta) => {
      if (!sequenceRef.current) return;
      seekPlayhead(Math.max(0, sequenceRef.current.playheadFrame + delta));
    },
    onHome: () => seekPlayhead(0),
    onEnd: () => {
      if (!sequenceRef.current) return;
      seekPlayhead(Math.max(0, sequenceRef.current.durationFrames - 1));
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
      if (first) {
        const clip = sequenceRef.current.clips.find((item) => item.id === first);
        if (clip?.assetId && clip.ingestRole !== "graphic") setViewerAssetId(clip.assetId);
      }
    },
    [overlays],
  );

  const handleSeek = useCallback(
    (frame: number) => {
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
      setMessage("Try commands like replace clip, trim, lower third, or add ambience. Dissolve/brighten/stabilize/silence are unavailable.");
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
                    setRenderQueueOpen(true);
                    setJobRefreshTick((tick) => tick + 1);
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
              title={UNSUPPORTED_PLACEBO_COPY.add_dissolve.summary}
              onClick={() => queueProposal("add_dissolve")}
            >
              {UNSUPPORTED_PLACEBO_COPY.add_dissolve.chipLabel}
            </button>
            <button
              type="button"
              className="magi-chip magi-chip--unavailable"
              title={UNSUPPORTED_PLACEBO_COPY.stabilize.summary}
              onClick={() => queueProposal("stabilize")}
            >
              {UNSUPPORTED_PLACEBO_COPY.stabilize.chipLabel}
            </button>
            <button
              type="button"
              className="magi-chip magi-chip--unavailable"
              title={UNSUPPORTED_PLACEBO_COPY.brighten.summary}
              onClick={() => queueProposal("brighten")}
            >
              {UNSUPPORTED_PLACEBO_COPY.brighten.chipLabel}
            </button>
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
          <p className="magi-group-label">Timeline handoff</p>
          <div className="magi-actions">
            <button
              type="button"
              className="magi-primary"
              data-testid="magi-send-to-timeline"
              disabled={timelineExportBusy || !sequence?.clips.length}
              onClick={() => void handleExportToTimeline()}
            >
              {timelineExportBusy ? "Exporting…" : "Send to Timeline"}
            </button>
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
              <p>MAGI finishing: {finishing.operation}. Color, upscale, music/SFX, and final render are real. EQ, 5.1, and frame interpolation are not available.</p>
            </div>
          ) : (
            <p className="magi-empty">Command parser supports finishing (color, upscale, audio, render), trims, replacements, ambience, and basic objects. EQ / 5.1 / frame interpolation are not available. Dissolve / brighten / stabilize / silence refuse honestly.</p>
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

  const viewerControls = (
    <>
      <button type="button" title="Save MAGI sequence" aria-label="Save MAGI sequence" onClick={() => void saveAll()}>
        Save
      </button>
      <button type="button" title="Undo" aria-label="Undo" onClick={undo} disabled={!historyRef.current.canUndo()}>
        ↶
      </button>
      <button type="button" title="Redo" aria-label="Redo" onClick={redo} disabled={!historyRef.current.canRedo()}>
        ↷
      </button>
      <button
        type="button"
        title={playing ? "Pause playback" : "Play playback"}
        aria-label={playing ? "Pause playback" : "Play playback"}
        onClick={() => setPlaying((value) => !value)}
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <button
        type="button"
        data-testid="magi-toolbar-mute"
        title={previewMuted ? "Unmute preview" : "Mute preview"}
        aria-label={previewMuted ? "Unmute preview" : "Mute preview"}
        aria-pressed={previewMuted}
        onClick={() => setPreviewMuted((value) => !value)}
      >
        {previewMuted ? "🔇" : "🔊"}
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
        onChange={(event) => setPreviewVolume(Number(event.target.value))}
      />
      <button type="button" title="Jump to start" aria-label="Jump to start" onClick={() => handleSeek(0)}>
        ⏮
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
    </>
  );

  const viewerStage = currentAsset ? api.assetUrl(currentAsset.id) : "";
  const compareStage = compareAsset ? api.assetUrl(compareAsset.id) : "";
  const compareOptions = mediaAssets.filter((asset) => asset.id !== viewerAssetId);

  const monitor = (
    <section className="magi-viewer" {...bindRegionProps("viewer")} data-testid="magi-viewer">
      <div className="magi-viewer-header">
        <div className="magi-tabs" role="tablist" aria-label="Viewer mode">
          {[
            { id: "viewer" as ViewerMode, label: "Viewer", disabled: false },
            { id: "compare" as ViewerMode, label: "Compare", disabled: false },
            { id: "split" as ViewerMode, label: "Split View", disabled: false },
            { id: "histogram" as ViewerMode, label: "Histogram (future)", disabled: true },
            { id: "vectorscope" as ViewerMode, label: "Vectorscope (future)", disabled: true },
          ].map(({ id, label, disabled }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={viewerMode === id}
              className={viewerMode === id ? "active" : ""}
              disabled={disabled}
              onClick={() => setViewerMode(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <StatusBadge status={editorDirty ? "Draft" : "Certified"} />
        <div className="magi-overlay-toolbar" role="toolbar" aria-label="MAGI viewer tools">
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-text" aria-label="Add text" title="Add text" onClick={() => createGraphic("text")}>T</button>
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-lower-third" aria-label="Add lower third" title="Add lower third" onClick={() => createGraphic("lower_third")}>LT</button>
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-shape" aria-label="Add shape" title="Add shape" onClick={() => createGraphic("shape")}>▢</button>
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-image" aria-label="Add image overlay" title="Add image overlay from Library" onClick={() => setImageOverlayPickerOpen(true)}>IMG</button>
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-duplicate" aria-label="Duplicate overlay" title="Duplicate overlay" onClick={() => overlays.duplicateSelected()}>⧉</button>
          <button type="button" className="magi-icon-btn" data-testid="magi-tool-delete" aria-label="Delete overlay" title="Delete overlay" onClick={() => overlays.deleteSelected()}>⌫</button>
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
          <span
            className="magi-chip magi-viewer-fit is-active"
            data-testid="magi-viewer-fit"
            role="status"
            title="The full frame stays inside the Preview Monitor"
            aria-label="Viewer fit: the full frame stays inside the Preview Monitor"
          >
            Fit
          </span>
        </div>
      </div>
      <div className="magi-viewer-stage" data-testid="magi-viewer-stage">
        {!currentAsset && !previewAsset && !splitOriginalId ? (
          <p className="magi-empty">Choose media from the Library or select a clip in the timeline.</p>
        ) : viewerMode === "split" ? (
          splitOriginalId ? (
            <MagiSplitView
              originalSrc={api.assetUrl(splitOriginalId)}
              processedSrc={api.assetUrl(splitOriginalId)}
              processedKind={splitProcessedKind}
              processedFilter={splitRightFilter || undefined}
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
                />
              }
            />
          ) : (
            <p className="magi-empty">Publish this scene on Timeline first, then open Split View.</p>
          )
        ) : viewerMode === "compare" ? (
          <div className="magi-compare" data-testid="magi-compare-viewer">
            <figure>
              {currentAsset ? (
                <MagiCompareFitMedia
                  kind={assetKindGroup(currentAsset) === "video" ? "video" : "image"}
                  src={viewerStage}
                  timeSeconds={previewVideoTime}
                  playing={playing}
                  seekGeneration={seekGeneration}
                  clockRole="authority"
                  onClock={followMediaClock}
                  onEnded={stopAtMediaEnd}
                  onError={() => markMediaFailed(currentAsset.id)}
                  guidesVisible={overlays.safeGuides}
                />
              ) : null}
              <figcaption>{currentAsset?.tag || currentAsset?.filename}</figcaption>
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
                <div className="magi-viewer-placeholder">Pick a compare asset in Inspector.</div>
              )}
              <figcaption>{compareAsset?.tag || compareAsset?.filename || "Compare"}</figcaption>
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
              {previewAsset && assetKindGroup(previewAsset) === "video" ? (
                <MagiVideoStage
                  src={api.assetUrl(previewAsset.id)}
                  timeSeconds={previewVideoTime}
                  playing={playing}
                  muted={pictureMuted}
                  filter={viewerLiveFilter || undefined}
                  clockRole="authority"
                  seekGeneration={seekGeneration}
                  onClock={followMediaClock}
                  onEnded={stopAtMediaEnd}
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
                  style={viewerLiveFilter ? { filter: viewerLiveFilter } : undefined}
                  onError={() => markMediaFailed(previewAsset.id)}
                  onLoad={(event) => {
                    const image = event.currentTarget;
                    if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                      setPreviewSourceSize({ w: image.naturalWidth, h: image.naturalHeight });
                    }
                  }}
                />
              ) : null}
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
              />
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
      <div className="magi-transport">
        <button type="button" className="magi-icon-btn" aria-label="Previous frame" onClick={() => handleSeek(Math.max(0, (sequence?.playheadFrame || 0) - 1))}>‹</button>
        <button type="button" className="magi-icon-btn" aria-label={playing ? "Pause" : "Play"} onClick={() => setPlaying((value) => !value)}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button type="button" className="magi-icon-btn" aria-label="Next frame" onClick={() => handleSeek((sequence?.playheadFrame || 0) + 1)}>›</button>
        <span>{sequence ? frameToTimecode(sequence.playheadFrame, sequence.frameRate) : "00:00:00:00"}</span>
        <button type="button" className="magi-chip" data-testid="magi-before-after" onClick={() => setViewerMode("split")}>Before / After</button>
        <button
          type="button"
          className="magi-chip"
          data-testid="magi-preview-mute"
          aria-pressed={previewMuted}
          onClick={() => setPreviewMuted((value) => !value)}
        >
          {previewMuted ? "Muted" : "Sound"}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={previewVolume}
          aria-label="Preview volume"
          onChange={(event) => setPreviewVolume(Number(event.target.value))}
        />
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
            onChange={(e) => {
              if (!activeClipId) return;
              patchFinishingLive({ clipGrades: { [activeClipId]: { presetId: e.target.value, params: {} } } });
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
          <label>Exposure</label>
          <input data-testid="magi-color-exposure" type="range" min="-50" max="50" value={sliderValue("brightness")} onChange={(e) => setGradeParam("brightness", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Contrast</label>
          <input data-testid="magi-color-contrast" type="range" min="-50" max="50" value={sliderValue("contrast")} onChange={(e) => setGradeParam("contrast", Number(e.target.value))} />
        </div>
        <div className="magi-field">
          <label>Saturation</label>
          <input data-testid="magi-color-saturation" type="range" min="-50" max="50" value={sliderValue("saturation")} onChange={(e) => setGradeParam("saturation", Number(e.target.value))} />
        </div>
        <p className="magi-empty" data-testid="magi-grade-live-hint">
          Split View shows this look live. Apply Grade saves it for Final Render.
        </p>
        {liveGradeHasNonLiveChannels(gradeParams, gradePreset) ? (
          <p className="magi-empty" data-testid="magi-grade-nonlive">
            Some saved channels (gamma, shadows) appear on the baked render, not in this live preview.
          </p>
        ) : null}
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-color-preview"
            title="Optional 3-second FFmpeg bake for Compare. Split View already shows this look live."
            disabled={!currentAsset}
            onClick={async () => {
              if (!currentAsset) return;
              const result = await api.magi.previewColorGrade(project.id, currentAsset.id, gradePreset, gradeParams, activeClipId);
              const previewId = String(result.output_asset_id || result.assetId || "");
              if (previewId) {
                setCompareAssetId(previewId);
                setViewerMode("compare");
              }
              setMessage("Baked compare ready. Split View already showed this look live.");
              await onChange();
            }}
          >
            Baked Compare
          </button>
          <button
            type="button"
            className="magi-primary"
            data-testid="magi-color-apply"
            title="Commits this look for Final Render. Split View already shows it live."
            disabled={!currentAsset}
            onClick={async () => {
              if (!currentAsset) return;
              try {
                const result = await api.magi.applyColorGrade(project.id, currentAsset.id, gradePreset, gradeParams, activeClipId);
                const gradedId = String(result.output_asset_id || result.assetId || "");
                if (gradedId) setCompareAssetId(gradedId);
                setMessage("Color look saved for Final Render. Split View already showed it live.");
                await reloadSequence();
                await onChange();
              } catch (err: any) {
                setMessage(err?.message || "Color look could not be saved.");
              }
            }}
          >
            Apply Grade
          </button>
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-color-reset"
            onClick={() => {
              if (!activeClipId) return;
              patchFinishingLive({ clipGrades: { [activeClipId]: { presetId: "", params: {} } } });
              setMessage(null);
            }}
          >
            Reset
          </button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="prompt" title="Prompt" open={Boolean(layout.accordionState.prompt)} onToggle={(next) => setAccordion("prompt", next)}>
        <div className="magi-field">
          <label>Direction note</label>
          <textarea value={command} onChange={(event) => setCommand(event.target.value)} />
        </div>
      </MagiAccordion>
      <MagiAccordion id="lighting" title="Lighting" open={Boolean(layout.accordionState.lighting)} onToggle={(next) => setAccordion("lighting", next)}>
        <p className="magi-empty">Brighten / stabilize engines are not available. Use Color grade for exposure.</p>
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip magi-chip--unavailable"
            title={UNSUPPORTED_PLACEBO_COPY.brighten.summary}
            onClick={() => queueProposal("brighten")}
          >
            {UNSUPPORTED_PLACEBO_COPY.brighten.chipLabel}
          </button>
          <button
            type="button"
            className="magi-chip magi-chip--unavailable"
            title={UNSUPPORTED_PLACEBO_COPY.stabilize.summary}
            onClick={() => queueProposal("stabilize")}
          >
            {UNSUPPORTED_PLACEBO_COPY.stabilize.chipLabel}
          </button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="effects" title="Effects" open={Boolean(layout.accordionState.effects)} onToggle={(next) => setAccordion("effects", next)}>
        <p className="magi-empty">Dissolve has no xfade engine yet — delivery remains hard-cut.</p>
        <div className="magi-actions">
          <button
            type="button"
            className="magi-chip magi-chip--unavailable"
            title={UNSUPPORTED_PLACEBO_COPY.add_dissolve.summary}
            onClick={() => queueProposal("add_dissolve")}
          >
            {UNSUPPORTED_PLACEBO_COPY.add_dissolve.chipLabel}
          </button>
          <button type="button" className="magi-chip" onClick={() => queueProposal("extend_reaction")}>Extend Reaction</button>
        </div>
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
          <select data-testid="magi-upscale-target" value={upscaleTarget} onChange={(e) => patchFinishing({ upscale: { target: e.target.value, engine: upscaleEngine, model: upscaleModel, enabled: true } })}>
            <option value="1280x720">720p</option>
            <option value="1920x1080">1080p</option>
            <option value="2560x1440">1440p</option>
            <option value="3840x2160">4K</option>
            <option value="7680x4320">8K</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Engine</label>
          <select data-testid="magi-upscale-engine" value={upscaleEngine} onChange={(e) => patchFinishing({ upscale: { engine: e.target.value, target: upscaleTarget, model: e.target.value === "ffmpeg-scale" ? "lanczos" : "realesrgan-x4plus", enabled: true } })}>
            <option value="ffmpeg-scale">FFmpeg (fast)</option>
            <option value="realesrgan-ncnn-vulkan" disabled={!gpuReady}>Real-ESRGAN (GPU)</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Model</label>
          <select data-testid="magi-upscale-model" value={upscaleModel} onChange={(e) => patchFinishing({ upscale: { model: e.target.value, engine: upscaleEngine, target: upscaleTarget, enabled: true } })}>
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
              const result = await api.magi.previewUpscale(project.id, currentAsset.id, "ffmpeg-scale", upscaleEngine === "ffmpeg-scale" ? upscaleModel : "lanczos", upscaleTarget);
              if (result.output_asset_id) {
                setCompareAssetId(String(result.output_asset_id));
                setViewerMode("compare");
              }
              setMessage("Upscale preview ready. Source clip is unchanged.");
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
              const result = await api.magi.applyUpscale(project.id, currentAsset.id, upscaleEngine, upscaleModel, upscaleTarget);
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
                  upscale: { enabled: true, engine: "ffmpeg-scale", model: "lanczos", target: "1280x720" },
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
            disabled={!sequence?.clips.length || Boolean(finishingJobId)}
            onClick={async () => {
              try {
                const result = await api.magi.createRender(project.id, {
                  profile: "final",
                  range: audioRange,
                  clipId: selectedClip?.id,
                  includeColor: true,
                  includeAudio: true,
                  includeOverlays: true,
                  upscale: { enabled: true, engine: upscaleEngine, model: upscaleModel, target: upscaleTarget },
                });
                waitAccepted(result, "magi_final_render");
              } catch (err: any) {
                setMessage(err?.message || "Final render failed");
              }
            }}
          >
            Final Render
          </button>
          <button
            type="button"
            className="magi-chip"
            data-testid="magi-inspector-export"
            disabled={timelineExportBusy || !sequence?.clips.length}
            onClick={() => void handleExportToTimeline()}
          >
            {timelineExportBusy ? "Exporting…" : "Send to Timeline"}
          </button>
        </div>
        <p className="magi-empty">Preview is a short look. Final uses MAGI color grades, MAGI finishing.audio (Music/SFX asset ids from this Audio panel), and upscale settings. Audio Studio mixer is adjacent and is not used by Final Render.</p>
      </MagiAccordion>
      <MagiAccordion id="compare" title="Compare" open={Boolean(layout.accordionState.compare)} onToggle={(next) => setAccordion("compare", next)}>
        <div className="magi-field">
          <label>Compare asset</label>
          <select value={compareAssetId} onChange={(event) => setCompareAssetId(event.target.value)}>
            <option value="">None</option>
            {compareOptions.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.tag || asset.filename}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="magi-chip" onClick={() => setViewerMode("compare")}>Open compare view</button>
      </MagiAccordion>
      <MagiAccordion id="aiAssist" title="AI Assist" open={Boolean(layout.accordionState.aiAssist)} onToggle={(next) => setAccordion("aiAssist", next)}>
        <div className="magi-ai-assist">
          <button type="button" onClick={() => queueProposal("trim")}>Tighten beat</button>
          <button type="button" onClick={() => queueProposal("replace_clip")}>Replace shot</button>
          <button
            type="button"
            className="magi-chip--unavailable"
            title={UNSUPPORTED_PLACEBO_COPY.add_dissolve.summary}
            onClick={() => queueProposal("add_dissolve")}
          >
            Smooth cut (unavailable)
          </button>
          <button
            type="button"
            className="magi-chip--unavailable"
            title="Use Inspector Color → Exposure for real brightness changes."
            onClick={() => queueProposal("brighten")}
          >
            Lift exposure (unavailable)
          </button>
        </div>
      </MagiAccordion>
    </div>
  );

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
      <div className="magi-strip" role="banner" aria-label={t("title")} data-testid="magi-strip">
        <div className="magi-strip__lava" aria-hidden="true" />
        <div className="magi-strip__glow" aria-hidden="true" />
        <div className="magi-strip__track">
          <span className="magi-strip__copy" data-testid="magi-strip-copy">MAGI Editor — assemble, finish, and protect timing.</span>
        </div>
      </div>

      <div className="magi-workspace-bar">
        <strong>Workspace</strong>
        <WorkspaceFullscreenControls
          fs={workspaceFs}
          expandActive={viewportMode === "EXPANDED"}
          onExpand={() => {
            setViewportMode((m) => (m === "EXPANDED" ? "STANDARD" : "EXPANDED"));
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
        <span className="magi-workspace-status">
          <StatusBadge status={saveState === "error" || overlayPersist.error ? "Blocked" : editorDirty ? "Draft" : "Certified"} />
          <span>{saveState === "saving" || overlayPersist.saving ? "Saving…" : editorDirty ? "Unsaved changes" : "Saved"}</span>
        </span>
      </div>

      {unpublishedSceneId ? (
        <div className="magi-msg magi-msg--action" role="status" data-testid="magi-unpublished-master">
          <span>This scene has not been published from Timeline yet.</span>
          {(() => {
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
        </div>
      ) : null}
      {message && !String(message).trim().startsWith("{") ? <p className="magi-msg" role="status">{message}</p> : null}
      {saveError && !String(saveError).trim().startsWith("{") ? <p className="magi-msg" role="status">{saveError}</p> : null}
      {compactNotice ? <p className="magi-msg" role="status" data-testid="magi-compact-notice">Compact viewport detected. MAGI keeps the viewer forward and leaves bins collapsible.</p> : null}

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
              {layout.leftPaneOrder.map((pane) => renderPane(pane))}
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
            expanded={viewportMode === "EXPANDED"}
            monitor={monitor}
            timeline={
              <div className="magi-timeline-shell">
                <div className="magi-timeline-toolbar">
                  <div className="magi-toolbar-group" role="toolbar" aria-label="MAGI timeline tools">
                    <button type="button" className="magi-icon-btn" aria-label="Undo" title="Undo" onClick={undo} disabled={!historyRef.current.canUndo()}>↶</button>
                    <button type="button" className="magi-icon-btn" aria-label="Redo" title="Redo" onClick={redo} disabled={!historyRef.current.canRedo()}>↷</button>
                    <button type="button" className="magi-icon-btn" aria-label="Home" title="Home" onClick={() => handleSeek(0)}>⏮</button>
                    <button type="button" className="magi-icon-btn" aria-label="Play" title="Play" onClick={() => setPlaying((value) => !value)}>{playing ? "❚❚" : "▶"}</button>
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
            <div className="magi-dock-scroll">{inspector}</div>
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

      <div className="magi-queue" data-testid="magi-render-queue">
        <button
          type="button"
          className="magi-queue__toggle"
          aria-expanded={layout.renderQueueOpen}
          onClick={() => setRenderQueueOpen(!layout.renderQueueOpen)}
        >
          <span>Render Queue</span>
          <span>{layout.renderQueueOpen ? "▾" : "▸"}</span>
        </button>
        {layout.renderQueueOpen ? (
          <div className="magi-queue__body" key={jobRefreshTick}>
            <JobPanel projectId={project.id} onDone={() => void onChange()} />
          </div>
        ) : null}
      </div>
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

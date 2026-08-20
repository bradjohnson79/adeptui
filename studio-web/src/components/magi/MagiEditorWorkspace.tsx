import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import type { Asset, Project } from "../../types";
import {
  applyEditCommand,
  clipSourceFrame,
  clipUnderPlayhead,
  createEmptySequence,
  frameToTimecode,
  nextClipId,
  recomputeDuration,
  type MagiClip,
  type MagiEditCommand,
  type MagiSequenceDocument,
  type MagiTrack,
} from "../../magiSequence";
import { fetchMagiSequence, saveMagiSequence } from "../../magiSequence/api";
import { MagiFocusProvider, useMagiFocus } from "../../magiSequence";
import { useMagiKeyboard } from "../../magiSequence/useMagiKeyboard";
import { ImageMaskEditor } from "../imageEdit/ImageMaskEditor";
import { JobPanel } from "../JobPanel";
import { MagiSequenceTimeline } from "./MagiSequenceTimeline";
import { MagiWorkspaceStack } from "./MagiWorkspaceStack";
import { MagiAccordion } from "./layout/MagiAccordion";
import { MagiWorkspaceLayoutProvider, useMagiLayout } from "./layout/MagiWorkspaceLayoutProvider";
import type { MagiPaneId, MagiPreset } from "./layout/MagiLayoutPersistence";
import { MagiOverlayLayer } from "./overlays/MagiOverlayLayer";
import { MagiOverlayInspector } from "./overlays/MagiOverlayInspector";
import { MagiEditorCommandStack } from "./overlays/MagiEditorCommandStack";
import { useMagiOverlayState } from "./overlays/useMagiOverlayState";
import type { MagiOverlayComposition } from "./overlays/types";
import {
  WorkspaceFullscreenBanner,
  WorkspaceFullscreenControls,
  useWorkspaceFullscreen,
  type WorkspaceViewportMode,
} from "../../workspace/fullscreen";
import "./magi-editor.css";

type ViewerMode = "viewer" | "compare" | "mask" | "histogram" | "vectorscope";

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
  { id: "anime", name: "Anime", detail: "Strong graphics lane and fast reaction coverage." },
  { id: "cinematic", name: "Cinematic", detail: "Wide pacing with overlay and adjustment headroom." },
  { id: "social", name: "Social", detail: "Punchy short-form setup with quick insert defaults." },
] as const;

function StatusBadge({ status }: { status: string }) {
  return <span className={`magi-status-badge ${status}`}>{status}</span>;
}

/** m3: frame-synced video stage. Tracks the playhead-derived source time and
 * seeks the <video> element to it on change; pauses while scrubbing so the
 * preview reflects the frame at the playhead, not a free-running playback. */
function MagiVideoStage({
  src,
  timeSeconds,
  playing,
  onError,
}: {
  src: string;
  timeSeconds: number | null;
  playing: boolean;
  onError: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (timeSeconds == null || !Number.isFinite(timeSeconds)) return;
    const target = Math.max(0, timeSeconds);
    if (Math.abs(video.currentTime - target) > 0.08) {
      video.currentTime = target;
    }
  }, [timeSeconds]);
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (playing) void video.play().catch(() => undefined);
    else video.pause();
  }, [playing]);
  return (
    <video
      ref={videoRef}
      src={src}
      muted
      playsInline
      loop={false}
      onError={onError}
    />
  );
}

function assetKindGroup(asset: Asset): "video" | "image" | "audio" {
  if (asset.kind === "video") return "video";
  if (asset.kind === "audio" || asset.kind === "music" || asset.kind === "sfx") return "audio";
  return "image";
}

function clipForTrackKind(track: MagiTrack, asset: Asset) {
  const kind = assetKindGroup(asset);
  return (
    (kind === "video" && track.kind === "video") ||
    (kind === "image" && track.kind === "image") ||
    (kind === "audio" && track.kind === "audio")
  );
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

function recipeTracks(sequence: MagiSequenceDocument, recipeId: string): MagiTrack[] {
  return sequence.tracks.map((track) => {
    if (recipeId === "podcast") {
      return {
        ...track,
        muted: track.kind === "video" || track.kind === "image",
        solo: track.label === "A1",
        locked: track.kind === "mask",
      };
    }
    if (recipeId === "trailer") {
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
        muted: track.label === "FX",
        solo: false,
        locked: track.label === "M",
      };
    }
    if (recipeId === "anime" || recipeId === "music-video") {
      return {
        ...track,
        muted: false,
        solo: false,
        locked: track.label === "ADJ" ? false : track.locked,
      };
    }
    return { ...track, muted: false, solo: false, locked: track.label === "M" };
  });
}

function recipeSnapEnabled(recipeId: string): boolean {
  return recipeId !== "podcast" && recipeId !== "documentary";
}

function commandProposal(command: string): PendingProposal | null {
  const text = command.trim().toLowerCase();
  if (!text) return null;
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
    return {
      kind: "add_dissolve",
      title: "Add dissolve",
      summary: "Place a dissolve on the selected clip without changing the source media.",
      approveLabel: "Approve dissolve",
    };
  }
  if (text.includes("stabilize")) {
    return {
      kind: "stabilize",
      title: "Add stabilize pass",
      summary: "Lay a stabilize pass on the FX track over the selected clip after approval.",
      approveLabel: "Approve stabilize",
    };
  }
  if (text.includes("brighten")) {
    return {
      kind: "brighten",
      title: "Add brighten pass",
      summary: "Lay a brighten pass on the adjustment track over the selected clip after approval.",
      approveLabel: "Approve brighten",
    };
  }
  if (text.includes("silence")) {
    return {
      kind: "remove_silence",
      title: "Remove silence",
      summary: "Tighten the selected audio clip after approval.",
      approveLabel: "Approve silence trim",
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
  const [viewerMode, setViewerMode] = useState<ViewerMode>("viewer");
  const [viewerAssetId, setViewerAssetId] = useState<string | null>(null);
  const [compareAssetId, setCompareAssetId] = useState("");
  const [assetFilter, setAssetFilter] = useState<"all" | "video" | "image" | "audio">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
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
  const playbackTimerRef = useRef<number | null>(null);
  const dragRef = useRef<{ side: "left" | "right"; start: number; size: number } | null>(null);

  const overlays = useMagiOverlayState(project.id, viewerAssetId || "", {
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
  selectionRef.current = selection;
  viewerAssetRef.current = viewerAssetId;
  compareAssetRef.current = compareAssetId;
  overlayAssetRef.current = viewerAssetId;
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
  const selectedClips = useMemo(() => {
    if (!sequence) return [] as MagiClip[];
    const ids = new Set(selection);
    return sequence.clips.filter((clip) => ids.has(clip.id));
  }, [selection, sequence]);
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

  const filteredAssets = useMemo(() => {
    if (assetFilter === "all") return mediaAssets;
    return mediaAssets.filter((asset) => assetKindGroup(asset) === assetFilter);
  }, [assetFilter, mediaAssets]);

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
        const loaded = await fetchMagiSequence(project.id);
        if (cancelled) return;
        setSequence(loaded);
        setServerRevision(loaded.revision);
        serverRevisionRef.current = loaded.revision;
        lastSavedEditVersionRef.current = 0;
        const firstAssetId =
          loaded.clips[0]?.assetId || mediaAssets[0]?.id || images[0]?.id || videos[0]?.id || audioAssets[0]?.id || null;
        setViewerAssetId(firstAssetId);
      } catch {
        if (cancelled) return;
        const fallback = createEmptySequence(project.id, project.fps || 24);
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

  useEffect(() => {
    if (!sequence || !playing) return;
    if (playbackTimerRef.current) window.clearInterval(playbackTimerRef.current);
    playbackTimerRef.current = window.setInterval(() => {
      setSequence((prev) => {
        if (!prev) return prev;
        const nextFrame = prev.playheadFrame + 1 >= prev.durationFrames ? 0 : prev.playheadFrame + 1;
        return { ...prev, playheadFrame: nextFrame };
      });
    }, Math.max(18, Math.round(1000 / Math.max(1, sequence.frameRate))));
    return () => {
      if (playbackTimerRef.current) window.clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    };
  }, [playing, sequence]);

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
    onDeleteSelection: () => pushSequenceCommand("Delete selection", { kind: "RippleDelete" }),
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
      if (ids[0]) {
        const clip = sequenceRef.current.clips.find((item) => item.id === ids[0]);
        if (clip?.assetId) setViewerAssetId(clip.assetId);
      }
    },
    [],
  );

  const handleSeek = useCallback(
    (frame: number) => {
      seekPlayhead(frame);
    },
    [seekPlayhead],
  );

  const handleTrim = useCallback(
    (clipId: string, edge: "left" | "right", deltaFrames: number) => {
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
    [pushSequenceCommand, snapFrame],
  );

  const handleMove = useCallback(
    (clipId: string, startFrame: number, trackId?: string) => {
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
    [pushSequenceCommand, snapFrame],
  );

  const handleDropAsset = useCallback(
    (trackId: string, startFrame: number, assetId: string, mode: "Insert" | "Overwrite") => {
      const current = sequenceRef.current;
      const asset = mediaAssets.find((item) => item.id === assetId);
      if (!current || !asset) return;
      const snappedFrame = snapFrame(trackId, startFrame);
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
    [mediaAssets, pushSequenceCommand, setFocusRegion, snapFrame],
  );

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

  const queueProposal = useCallback(
    (kind: ProposalKind) => {
      const proposal = commandProposal(kind.replace(/_/g, " ")) || {
        kind,
        title:
          kind === "trim"
            ? "Trim selected clip"
            : kind === "replace_clip"
              ? "Replace selected clip"
              : kind === "add_dissolve"
                ? "Add dissolve"
                : kind === "stabilize"
                  ? "Add stabilize pass"
                  : kind === "brighten"
                    ? "Add brighten pass"
                    : kind === "remove_silence"
                      ? "Remove silence"
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
      case "add_dissolve":
        pushSequenceCommand("Add dissolve", {
          kind: "ApplyTransition",
          payload: { clipId: selectedClip!.id, transitionId: "dissolve", edge: "out" },
        });
        break;
      case "stabilize":
        mutateSequence("Stabilize", "Add stabilize pass", (doc) => {
          const fxTrack = doc.tracks.find((track) => track.label === "FX") || doc.tracks[0];
          const base = selectedClip!;
          const clip: MagiClip = {
            id: nextClipId(),
            trackId: fxTrack.id,
            assetId: base.assetId,
            name: `Stabilize · ${base.name || "Clip"}`,
            startFrame: base.startFrame,
            durationFrames: base.durationFrames,
            inPoint: 0,
            outPoint: base.durationFrames,
          };
          return {
            doc: {
              ...doc,
              clips: [...doc.clips, clip],
              durationFrames: Math.max(doc.durationFrames, clip.startFrame + clip.durationFrames + doc.frameRate),
            },
            selection: [clip.id],
          };
        });
        break;
      case "brighten":
        mutateSequence("Brighten", "Add brighten pass", (doc) => {
          const adjTrack = doc.tracks.find((track) => track.label === "ADJ") || doc.tracks[0];
          const base = selectedClip!;
          const clip: MagiClip = {
            id: nextClipId(),
            trackId: adjTrack.id,
            assetId: base.assetId,
            name: `Brighten · ${base.name || "Clip"}`,
            startFrame: base.startFrame,
            durationFrames: base.durationFrames,
            inPoint: 0,
            outPoint: base.durationFrames,
          };
          return {
            doc: {
              ...doc,
              clips: [...doc.clips, clip],
              durationFrames: Math.max(doc.durationFrames, clip.startFrame + clip.durationFrames + doc.frameRate),
            },
            selection: [clip.id],
          };
        });
        break;
      case "remove_silence":
        pushSequenceCommand("Remove silence", {
          kind: "Trim",
          payload: { clipId: selectedClip!.id, edge: "right", deltaFrames: -Math.max(4, Math.round(current.frameRate * 0.35)) },
        });
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
      setMessage("Try commands like “add dissolve”, “replace clip”, “brighten”, or “lower third”.");
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

  const renderAssetCard = (asset: Asset) => (
    <button
      key={asset.id}
      type="button"
      className={`magi-asset-card ${viewerAssetId === asset.id ? "selected" : ""}`}
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
      {assetKindGroup(asset) === "image" ? (
        <img src={api.assetUrl(asset.id)} alt="" onError={() => markMediaFailed(asset.id)} />
      ) : (
        <div className="magi-asset-card__placeholder">{assetKindGroup(asset)}</div>
      )}
      <span className="label">{asset.tag || asset.filename}</span>
      <span className="meta">{asset.kind}</span>
    </button>
  );

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
    if (pane === "media") {
      return wrap(
        "Media",
        <div {...bindRegionProps("media_bin")} className="magi-pane-bin" data-testid="magi-media-bin">
          <p className="magi-empty">Click to preview. Drag to the timeline to insert. Shift+drop overwrites.</p>
          <div className="magi-asset-grid">{mediaAssets.slice(0, 18).map(renderAssetCard)}</div>
        </div>,
        <span>{mediaAssets.length}</span>,
      );
    }
    if (pane === "assets") {
      return wrap(
        "Assets",
        <div className="magi-pane-bin">
          <div className="magi-actions">
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
      );
    }
    if (pane === "graphics") {
      return wrap(
        "Graphics",
        <div data-testid="magi-text-graphics">
          <div className="magi-actions">
            <button type="button" className="magi-chip" onClick={() => queueProposal("overlay_text")}>
              Add Text
            </button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("overlay_lower_third")}>
              Lower Third
            </button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("overlay_shape")}>
              Shape
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
            <button type="button" className="magi-chip" onClick={() => queueProposal("add_dissolve")}>Add Dissolve</button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("stabilize")}>Stabilize</button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("brighten")}>Brighten</button>
            <button type="button" className="magi-chip" onClick={() => queueProposal("remove_silence")}>Remove Silence</button>
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
      return wrap(
        "Command",
        <div data-testid="magi-command">
          <div className="magi-field">
            <label>Command</label>
            <textarea
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="Try: add dissolve, replace clip, brighten, lower third"
            />
          </div>
          <p className="magi-empty">Target: {selectedClip?.name || currentAsset?.tag || currentAsset?.filename || "Choose a clip or media item."}</p>
          <p className="magi-empty" data-testid="magi-command-stage">
            Stage: <StatusBadge status={pendingProposal ? "Proposed" : parsed ? "Draft" : "Draft"} />
          </p>
          {parsed ? (
            <div className="magi-tip">
              <strong>{parsed.title}</strong>
              <p>{parsed.summary}</p>
              <button type="button" className="magi-chip" onClick={runCommandProposal}>Create Proposal</button>
            </div>
          ) : (
            <p className="magi-empty">Command parser supports trims, replacements, dissolves, ambience, and basic graphics.</p>
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
            { id: "mask" as ViewerMode, label: "Mask", disabled: false },
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
          <button type="button" className="magi-icon-btn" aria-label="Add text" title="Add text" onClick={() => queueProposal("overlay_text")}>T</button>
          <button type="button" className="magi-icon-btn" aria-label="Add lower third" title="Add lower third" onClick={() => queueProposal("overlay_lower_third")}>LT</button>
          <button type="button" className="magi-icon-btn" aria-label="Add shape" title="Add shape" onClick={() => queueProposal("overlay_shape")}>▢</button>
          <button type="button" className="magi-icon-btn" aria-label="Duplicate overlay" title="Duplicate overlay" onClick={() => overlays.duplicateSelected()}>⧉</button>
          <button type="button" className="magi-icon-btn" aria-label="Delete overlay" title="Delete overlay" onClick={() => overlays.deleteSelected()}>⌫</button>
        </div>
      </div>
      <div className="magi-viewer-stage" data-testid="magi-viewer-stage">
        {!currentAsset && !previewAsset ? (
          <p className="magi-empty">Choose media from the Library or select a clip in the timeline.</p>
        ) : viewerMode === "compare" ? (
          <div className="magi-compare" data-testid="magi-compare-viewer">
            <figure>
              {currentAsset &&
                (assetKindGroup(currentAsset) === "video" ? (
                  <video src={viewerStage} muted loop autoPlay playsInline onError={() => markMediaFailed(currentAsset.id)} />
                ) : (
                  <img src={viewerStage} alt="" onError={() => markMediaFailed(currentAsset.id)} />
                ))}
              <figcaption>{currentAsset?.tag || currentAsset?.filename}</figcaption>
            </figure>
            <figure>
              {compareAsset ? (
                assetKindGroup(compareAsset) === "video" ? (
                  <video src={compareStage} muted loop autoPlay playsInline onError={() => markMediaFailed(compareAsset.id)} />
                ) : (
                  <img src={compareStage} alt="" onError={() => markMediaFailed(compareAsset.id)} />
                )
              ) : (
                <div className="magi-viewer-placeholder">Pick a compare asset in Inspector.</div>
              )}
              <figcaption>{compareAsset?.tag || compareAsset?.filename || "Compare"}</figcaption>
            </figure>
          </div>
        ) : viewerMode === "mask" && currentAsset && assetKindGroup(currentAsset) === "image" ? (
          <div className="magi-mask-shell" data-testid="magi-image-canvas">
            <ImageMaskEditor imageUrl={viewerStage} onExport={() => undefined} onChange={() => undefined} />
          </div>
        ) : currentAsset && assetKindGroup(currentAsset) === "audio" ? (
          <div className="magi-viewer-placeholder">
            <strong>{currentAsset.tag || currentAsset.filename}</strong>
            <span>Audio clips are arranged in the timeline and previewed through transport focus.</span>
          </div>
        ) : (
          <>
            {previewAsset && assetKindGroup(previewAsset) === "video" ? (
              <MagiVideoStage
                src={api.assetUrl(previewAsset.id)}
                timeSeconds={previewVideoTime}
                playing={playing}
                onError={() => markMediaFailed(previewAsset.id)}
              />
            ) : previewAsset ? (
              <img
                src={api.assetUrl(previewAsset.id)}
                alt={previewAsset.tag || previewAsset.filename}
                onError={() => markMediaFailed(previewAsset.id)}
              />
            ) : null}
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
            <MagiOverlayLayer
              composition={overlays.composition}
              selectedId={overlays.selectedOverlayId}
              onSelect={overlays.setSelectedOverlayId}
              onPatchElement={overlays.patchElement}
              snapEnabled={overlays.snapEnabled}
              safeAreaEnabled={overlays.safeGuides}
            />
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
        <button type="button" className="magi-chip" onClick={() => setViewerMode("compare")}>Before / After</button>
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
          onDelete={() => overlays.deleteSelected()}
          onDuplicate={() => overlays.duplicateSelected()}
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
            value=""
            onChange={(e) => {
              if (!currentAsset) return;
              const presetId = e.target.value;
              if (presetId) {
                api.magi.previewColorGrade(project.id, currentAsset.id, presetId, {}).then(() => {});
              }
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
          <input type="range" min="-50" max="50" value="0" onChange={() => {}} />
        </div>
        <div className="magi-field">
          <label>Contrast</label>
          <input type="range" min="-50" max="50" value="0" onChange={() => {}} />
        </div>
        <div className="magi-field">
          <label>Saturation</label>
          <input type="range" min="-50" max="50" value="0" onChange={() => {}} />
        </div>
        <div className="magi-actions">
          <button type="button" className="magi-primary" onClick={async () => {
            if (!currentAsset) return;
            await api.magi.applyColorGrade(project.id, currentAsset.id, "", {});
            setMessage("Color grade applied.");
            await onChange();
          }}>
            Apply Grade
          </button>
          <button type="button" className="magi-chip" onClick={() => setMessage("Color graded reset.")}>
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
        <div className="magi-actions">
          <button type="button" className="magi-chip" onClick={() => queueProposal("brighten")}>Brighten Pass</button>
          <button type="button" className="magi-chip" onClick={() => queueProposal("stabilize")}>Stabilize Pass</button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="effects" title="Effects" open={Boolean(layout.accordionState.effects)} onToggle={(next) => setAccordion("effects", next)}>
        <div className="magi-actions">
          <button type="button" className="magi-chip" onClick={() => queueProposal("add_dissolve")}>Dissolve</button>
          <button type="button" className="magi-chip" onClick={() => queueProposal("extend_reaction")}>Extend Reaction</button>
        </div>
      </MagiAccordion>
      <MagiAccordion id="audio" title="Audio" open={Boolean(layout.accordionState.audio)} onToggle={(next) => setAccordion("audio", next)}>
        <div className="magi-actions">
          <button type="button" className="magi-chip" onClick={() => queueProposal("remove_silence")}>Remove Silence</button>
          <button type="button" className="magi-chip" onClick={() => queueProposal("add_ambience")}>Add Ambience</button>
        </div>
        <p className="magi-group-label">AI Music &amp; SFX</p>
        <div className="magi-field">
          <label>Prompt</label>
          <textarea
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="Give this scene an intimate mysterious score with subtle café ambience..."
            rows={2}
          />
        </div>
        <div className="magi-actions">
          <button type="button" className="magi-chip" onClick={async () => {
            try {
              await api.magi.generateAudio(project.id, "music", command || "ambient background");
              setMessage("Music generation queued.");
              await onChange();
            } catch (err: any) {
              setMessage(err?.message || "Music generation failed");
            }
          }}>
            Music
          </button>
          <button type="button" className="magi-chip" onClick={async () => {
            try {
              await api.magi.generateAudio(project.id, "sfx", command || "ambient sfx");
              setMessage("SFX generation queued.");
              await onChange();
            } catch (err: any) {
              setMessage(err?.message || "SFX generation failed");
            }
          }}>
            SFX
          </button>
          <button type="button" className="magi-chip" onClick={async () => {
            try {
              await api.magi.generateAudio(project.id, "all", command || "music and ambience");
              setMessage("Audio generation queued.");
              await onChange();
            } catch (err: any) {
              setMessage(err?.message || "Audio generation failed");
            }
          }}>
            Music + SFX
          </button>
        </div>
        <div className="magi-field">
          <label>Range</label>
          <select defaultValue="all">
            <option value="all">Entire Edit</option>
            <option value="clip">Selected Clip</option>
          </select>
        </div>
      </MagiAccordion>
      <MagiAccordion id="upscale" title="Upscale" open={Boolean(layout.accordionState.upscale)} onToggle={(next) => setAccordion("upscale", next)}>
        <div className="magi-field">
          <label>Target</label>
          <select defaultValue="1920x1080">
            <option value="1280x720">720p</option>
            <option value="1920x1080">1080p</option>
            <option value="2560x1440">1440p</option>
            <option value="3840x2160">4K</option>
            <option value="7680x4320">8K</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Engine</label>
          <select defaultValue="ffmpeg-scale">
            <option value="ffmpeg-scale">FFmpeg (fast)</option>
            <option value="realesrgan-ncnn-vulkan">Real-ESRGAN (GPU)</option>
          </select>
        </div>
        <div className="magi-field">
          <label>Model</label>
          <select defaultValue="lanczos">
            <option value="lanczos">Lanczos (general)</option>
            <option value="bicubic">Bicubic (soft)</option>
            <option value="realesrgan-x4plus">Real-ESRGAN 4x+</option>
            <option value="realesr-animevideov3">Anime Video 4x</option>
          </select>
        </div>
        <div className="magi-actions">
          <button type="button" className="magi-primary" onClick={async () => {
            if (!currentAsset) return;
            await api.magi.previewUpscale(project.id, currentAsset.id, "ffmpeg-scale", "lanczos", "1920x1080");
            setMessage("Upscale preview queued.");
          }}>
            Preview
          </button>
          <button type="button" className="magi-chip" onClick={async () => {
            if (!currentAsset) return;
            await api.magi.applyUpscale(project.id, currentAsset.id, "ffmpeg-scale", "lanczos", "1920x1080");
            setMessage("Upscale applied.");
            await onChange();
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
        <div className="magi-actions">
          <button
            type="button"
            className="magi-primary"
            data-testid="magi-inspector-export"
            disabled={timelineExportBusy || !sequence?.clips.length}
            onClick={() => void handleExportToTimeline()}
          >
            {timelineExportBusy ? "Exporting…" : "Send to Timeline"}
          </button>
          <p className="magi-empty">Place the MAGI sequence clips onto the W46 Timeline with provenance.</p>
        </div>
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
          <button type="button" onClick={() => queueProposal("add_dissolve")}>Smooth cut</button>
          <button type="button" onClick={() => queueProposal("brighten")}>Lift exposure</button>
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
          expandActive={viewportMode === "EXPANDED" || layout.activePreset === "viewer-focus"}
          onExpand={() => {
            setViewportMode((m) => (m === "EXPANDED" ? "STANDARD" : "EXPANDED"));
            if (viewportMode !== "EXPANDED") applyWorkspacePreset("viewer-focus");
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
          <option value="mask-editing">Mask Finishing</option>
          <option value="compare-review">Compare Review</option>
          <option value="custom">Custom</option>
        </select>
        <button type="button" className="magi-chip" onClick={() => toggleLeftDock()} data-testid="magi-toggle-left-dock">
          {layout.leftDockCollapsed ? "Show bins" : "Hide bins"}
        </button>
        <button type="button" className="magi-chip" onClick={() => toggleRightDock()} data-testid="magi-toggle-right-dock">
          {layout.rightDockCollapsed ? "Show inspector" : "Hide inspector"}
        </button>
        <button type="button" className="magi-chip" onClick={() => resetWorkspace()} data-testid="magi-reset-workspace">
          Reset Workspace
        </button>
        <span className="magi-workspace-status">
          <StatusBadge status={saveState === "error" || overlayPersist.error ? "Blocked" : editorDirty ? "Draft" : "Certified"} />
          <span>{saveState === "saving" || overlayPersist.saving ? "Saving…" : editorDirty ? "Unsaved changes" : "Saved"}</span>
        </span>
      </div>

      {message ? <p className="magi-msg" role="status">{message}</p> : null}
      {saveError ? <p className="magi-msg" role="status">{saveError}</p> : null}
      {compactNotice ? <p className="magi-msg" role="status" data-testid="magi-compact-notice">Compact viewport detected. MAGI keeps the viewer forward and leaves bins collapsible.</p> : null}

      <div className="magi-shell__layout">
        <aside
          className={`magi-dock magi-dock--left ${layout.leftDockCollapsed ? "is-collapsed" : ""}`}
          style={{ width: layout.leftDockCollapsed ? 40 : layout.leftDockWidth }}
        >
          {layout.leftDockCollapsed ? (
            <button type="button" className="magi-dock-restore" onClick={() => toggleLeftDock()}>
              Bins
            </button>
          ) : (
            <div className="magi-dock-scroll" {...bindRegionProps("media_bin")}>
              {layout.leftPaneOrder.map((pane) => renderPane(pane))}
            </div>
          )}
        </aside>

        <div
          className="magi-splitter"
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={layout.leftDockWidth}
          tabIndex={0}
          onPointerDown={(event) => onLeftSplitterPointerDown(event, "left")}
          onPointerMove={onLeftRightSplitterMove}
          onPointerUp={onLeftRightSplitterUp}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") setLeftWidth(layout.leftDockWidth - (event.shiftKey ? 32 : 10));
            if (event.key === "ArrowRight") setLeftWidth(layout.leftDockWidth + (event.shiftKey ? 32 : 10));
          }}
        />

        <main className="magi-center">
          <MagiWorkspaceStack
            projectId={project.id}
            extraControls={viewerControls}
            monitor={monitor}
            timeline={
              <div className="magi-timeline-shell">
                <div className="magi-timeline-toolbar">
                  <div className="magi-toolbar-group" role="toolbar" aria-label="MAGI timeline tools">
                    <button type="button" className="magi-icon-btn" aria-label="Undo" title="Undo" onClick={undo} disabled={!historyRef.current.canUndo()}>↶</button>
                    <button type="button" className="magi-icon-btn" aria-label="Redo" title="Redo" onClick={redo} disabled={!historyRef.current.canRedo()}>↷</button>
                    <button type="button" className="magi-icon-btn" aria-label="Home" title="Home" onClick={() => handleSeek(0)}>⏮</button>
                    <button type="button" className="magi-icon-btn" aria-label="Play" title="Play" onClick={() => setPlaying((value) => !value)}>{playing ? "❚❚" : "▶"}</button>
                    <button type="button" className="magi-icon-btn" aria-label="Split clip" title="Split clip" onClick={() => selectedClip && pushSequenceCommand("Split clip", { kind: "Split", payload: { clipId: selectedClip.id, frame: sequence.playheadFrame } })}>✂</button>
                    <button type="button" className="magi-icon-btn" aria-label="Duplicate selection" title="Duplicate selection" onClick={() => selection.length && pushSequenceCommand("Duplicate clips", { kind: "Duplicate", payload: { offsetFrames: Math.max(1, sequence.frameRate) } })}>⧉</button>
                    <button type="button" className="magi-icon-btn" aria-label="Add marker" title="Add marker" onClick={() => pushSequenceCommand("Add marker", { kind: "AddMarker", payload: { frame: sequence.playheadFrame, label: "Beat" } })}>◆</button>
                  </div>
                  <div className="magi-toolbar-meta">
                    <span>{sequence.tracks.length} tracks</span>
                    <span>{sequence.clips.length} clips</span>
                    <span>{selection.length} selected</span>
                  </div>
                </div>
                <MagiSequenceTimeline
                  sequence={sequence}
                  selection={selection}
                  playing={playing}
                  selectedAssetId={viewerAssetId}
                  onSelect={handleSelect}
                  onSeek={handleSeek}
                  onTrim={handleTrim}
                  onMove={handleMove}
                  onDropAsset={handleDropAsset}
                  failedAssetIds={failedMediaIds}
                />
              </div>
            }
          />
        </main>

        <div
          className="magi-splitter"
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={layout.rightDockWidth}
          tabIndex={0}
          onPointerDown={(event) => onLeftSplitterPointerDown(event, "right")}
          onPointerMove={onLeftRightSplitterMove}
          onPointerUp={onLeftRightSplitterUp}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") setRightWidth(layout.rightDockWidth + (event.shiftKey ? 32 : 10));
            if (event.key === "ArrowRight") setRightWidth(layout.rightDockWidth - (event.shiftKey ? 32 : 10));
          }}
        />

        <aside
          className={`magi-dock magi-dock--right ${layout.rightDockCollapsed ? "is-collapsed" : ""}`}
          style={{ width: layout.rightDockCollapsed ? 40 : layout.rightDockWidth }}
        >
          {layout.rightDockCollapsed ? (
            <button type="button" className="magi-dock-restore" onClick={() => toggleRightDock()}>
              Edit
            </button>
          ) : (
            <div className="magi-dock-scroll">{inspector}</div>
          )}
        </aside>
      </div>

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

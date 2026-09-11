import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, bindAssetUrlProject } from "../../api";
import type { Asset, Project } from "../../types";
import type { BatchBlock, SceneTimelineMaster, TimelinePromptSegment } from "../../timelineMaster/contracts";
import { PRODUCTION_ASPECTS, normalizeProductionAspect } from "../../workspacePrefs";
import type { DirectorSelectionKind } from "../../directorSelection";
import {
  focusDomId,
  requestTimelineFocus,
  TIMELINE_FOCUS_EVENT,
  TIMELINE_FOCUS_IDS,
  type TimelineFocusRequest,
} from "../../timelineMaster/timelineFocus";
import {
  clampDrawerWidth,
  loadTimelineWorkspaceLayout,
  saveTimelineWorkspaceLayout,
  LEFT_PANE_MIN,
  LEFT_PANE_MAX,
  RIGHT_PANE_MIN,
  RIGHT_PANE_MAX,
  TIMELINE_LAYOUT_EVENT,
  type DrawerSide,
  type TimelineViewerPreset,
  type TimelineWorkspaceLayout,
} from "../../timelineMaster/workspaceLayout";
import {
  WorkspaceFullscreenBanner,
  WorkspaceFullscreenControls,
  useWorkspaceFullscreen,
  type WorkspaceViewportMode,
} from "../../workspace/fullscreen";
import { useDirectorSelection } from "../DirectorSelectionContext";
import {
  isEditableTarget,
  loadHotkeys,
  matchHotkey,
  registerTimelineCommand,
  runTimelineCommand,
} from "../../timelineMaster/timelineHotkeys";
import {
  DirectorTracks,
  lipSyncTrackHasContent,
  normalizeLipSyncTracks,
  overlayLiveTimeline,
  promptIdsOf,
  syncPromptTombstones,
  type DirectorTimeline,
} from "../DirectorTracks";
import { playableVisualClipsFromMaster } from "../../timelineMaster/playableVisualTakes";
import { bindShellTimelineMutate, bindShellTimelineSnapshot, dropPromptIdsFromMaster } from "./timelineMutateBridge";
import { TimelinePreviewComposer } from "./TimelinePreviewComposer";
import { Timeline } from "../Timeline";
import { AssetTray } from "../AssetTray";
import { AddFromProjectLibraryModal } from "./AddFromProjectLibraryModal";
import { VideoGeneratorDock } from "./VideoGeneratorDock";
import { ReferencesPane } from "../sceneReferences/ReferencesPane";
import { formatDurationSeconds } from "../../lib/formatDuration";
import { creatorGeneratorLine, timelineBoardDurationSec } from "../../timelineMaster/generatorDuration";
import { buildBatchTimeWindows } from "../../timelineMaster/batchWindows";
import { resolveTimelineTransportBounds } from "../../timelineMaster/timelineTransport";
import { useTimelineClock } from "../../timelineMaster/useTimelineClock";
import { useTimelineAudioPlayback } from "./useTimelineAudioPlayback";
import { anyTimelineGeneratorExecutable, resolveGeneratorOption } from "../../timelineMaster/draftCapabilities";
import { useTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { useTimelinePreflight } from "../../timelineMaster/useTimelinePreflight";
import { stepTimelineZoom } from "../../timelineMaster/timelineZoom";
import { useOpenCoDirector } from "../CoDirector";
import { TimelineWorkspaceStack } from "./TimelineWorkspaceStack";
import { TimelineToolbar } from "./TimelineToolbar";
import { SceneStatusStrip } from "./SceneStatusStrip";
import { TimelineInspector } from "./TimelineInspector";
import { TimelineHotKeysPane } from "./TimelineHotKeysPane";
import { ActionWithHelp } from "../HelpTip";
import { getTimelineHelp } from "../../timelineMaster/helpCatalog";
import { completedApprovedBatches } from "../../timelineMaster/sceneStitch";
import { addTimelineBatch } from "../../timelineMaster/addTimelineBatch";
import { CompactRenderQueue } from "./CompactRenderQueue";
import { TimelineGpuPane } from "./TimelineGpuPane";
import { timelineActionError, timelineGenerateEmpty } from "../../timelineMaster/timelineErrors";
import { TimelineGeneratorBanner } from "./TimelineGeneratorBanner";
import { useVideoRetake } from "./useVideoRetake";
import "../../styles/timeline-master/timeline-editor-shell.css";
import "../../styles/timeline-master/timeline-v2-shell.css";
import "../../styles/timeline-master/timeline-v2-canvas.css";


function batchHasContent(batch: BatchBlock) {
  if (batch.approvedClip) return true;
  if (batch.generationJobs?.length) return true;
  if (batch.candidateVersions?.length) return true;
  if (batch.repairRanges?.length) return true;
  if (batch.sourceAnchors?.some((a) => a.assetId)) return true;
  if (batch.promptSegments?.some((s) => (s.text || "").trim())) return true;
  if (batch.status && batch.status !== "Draft") return true;
  return false;
}

type TimelineHistoryEntry = {
  timeline: DirectorTimeline;
  batchPrompts: { batchId: string; promptSegments: TimelinePromptSegment[] }[];
};

function snapshotBatchPrompts(master: SceneTimelineMaster | null): TimelineHistoryEntry["batchPrompts"] {
  return (master?.batchBlocks || []).map((batch) => ({
    batchId: batch.id,
    promptSegments: (batch.promptSegments || []).map((seg) => ({ ...seg })),
  }));
}

export function TimelineEditorShell({
  project,
  selectedScene,
  setSelectedScene,
  refresh,
}: {
  project: Project;
  selectedScene?: string;
  setSelectedScene: (id: string) => void;
  refresh: () => Promise<void>;
}) {
  const { t } = useTranslation(["timeline", "common", "errors"]);
  const { selection, setSelection, setZoom, zoom } = useDirectorSelection();
  const openCoDirector = useOpenCoDirector();
  const selected = useMemo(
    () => project.scenes.find((scene) => scene.id === selectedScene) || project.scenes[0],
    [project.scenes, selectedScene],
  );
  const [playheadSec, setPlayheadSec] = useState(0);
  const [libraryPreviewId, setLibraryPreviewId] = useState<string | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const generatorOptions = useTimelineVideoGenerators();
  const [master, setMaster] = useState<SceneTimelineMaster | null>(null);
  const [directorTimeline, setDirectorTimeline] = useState<DirectorTimeline | null>(null);
  const [appliedSceneId, setAppliedSceneId] = useState<string | null>(null);
  const masterRef = useRef<SceneTimelineMaster | null>(null);
  const directorTimelineRef = useRef<DirectorTimeline | null>(null);
  const masterCacheRef = useRef<Map<string, SceneTimelineMaster>>(new Map());
  const directorCacheRef = useRef<Map<string, DirectorTimeline>>(new Map());
  const liveMaster = appliedSceneId === selected.id ? master : masterCacheRef.current.get(selected.id) ?? null;
  const selectedGenerator = useMemo(
    () =>
      resolveGeneratorOption(
        generatorOptions,
        liveMaster?.sceneGeneratorId,
        liveMaster?.batchBlocks[0]?.generatorId,
        selected.engine,
      ),
    [generatorOptions, liveMaster?.batchBlocks, liveMaster?.sceneGeneratorId, selected.engine],
  );
  const sceneCanGenerate = useMemo(
    () =>
      anyTimelineGeneratorExecutable(
        generatorOptions,
        liveMaster?.sceneGeneratorId,
        ...(liveMaster?.batchBlocks || []).map((batch) => batch.generatorId),
        selected.engine,
      ),
    [generatorOptions, liveMaster?.batchBlocks, liveMaster?.sceneGeneratorId, selected.engine],
  );
  const canReviewExtend = useMemo(
    () => (liveMaster?.batchBlocks || []).some((batch) => batch.approvedClip?.playable),
    [liveMaster?.batchBlocks],
  );
  const liveDirector =
    appliedSceneId === selected.id ? directorTimeline : directorCacheRef.current.get(selected.id) ?? null;
  masterRef.current = liveMaster;
  directorTimelineRef.current = liveDirector;
  const sceneEndSec = timelineBoardDurationSec(liveMaster, liveDirector, selected);
  const batchWindows = useMemo(() => buildBatchTimeWindows(liveMaster?.batchBlocks), [liveMaster?.batchBlocks]);
  const { playing, toggle, seek, pause } = useTimelineClock({ playheadSec, setPlayheadSec, sceneEndSec });
  const { audioHostRef } = useTimelineAudioPlayback({
    projectId: project.id,
    playing,
    playheadSec,
    timeline: liveDirector,
    master: liveMaster,
  });
  const playheadLiveRef = useRef(playheadSec);
  playheadLiveRef.current = playheadSec;
  const selectedBatchId = selection.kind === "batch" ? selection.id : null;
  const resolveTransport = useCallback(() => {
    return resolveTimelineTransportBounds({
      windows: batchWindows,
      playheadSec: playheadLiveRef.current,
      boardDurationSec: sceneEndSec,
      selectedBatchId,
    });
  }, [batchWindows, sceneEndSec, selectedBatchId]);
  const transportBounds = useMemo(
    () =>
      resolveTimelineTransportBounds({
        windows: batchWindows,
        playheadSec,
        boardDurationSec: sceneEndSec,
        selectedBatchId,
      }),
    [batchWindows, playheadSec, sceneEndSec, selectedBatchId],
  );
  const goToSceneStart = useCallback(() => {
    seek(resolveTransport().sceneStart);
  }, [resolveTransport, seek]);
  const goToBatchIn = useCallback(() => {
    seek(resolveTransport().activeBatchStart);
  }, [resolveTransport, seek]);
  const goToBatchOut = useCallback(() => {
    seek(resolveTransport().activeBatchEnd);
  }, [resolveTransport, seek]);
  const goToSceneEnd = useCallback(() => {
    seek(resolveTransport().sceneEnd);
  }, [resolveTransport, seek]);
  const [reloadKey, setReloadKey] = useState(0);
  // Always-on Preflight: event-driven (signature over exactly what the backend
  // run_preflight reads), single-flight, 400ms debounce. One shared state feeds
  // the header button, the toolbar button, the Generate gate, and the Inspector.
  const timelinePreflight = useTimelinePreflight({
    projectId: project.id,
    sceneId: selected?.id ?? null,
    master: liveMaster,
    director: liveDirector,
  });
  const preflightSummary = timelinePreflight.summary;
  const preflightBlockingCount = timelinePreflight.blockingCount;
  const [stitchBusy, setStitchBusy] = useState(false);
  const [rightTab, setRightTab] = useState<"inspector" | "codirector" | "hotkeys" | "gpu">("inspector");
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [generateBusy, setGenerateBusy] = useState(false);
  const [extendBusy, setExtendBusy] = useState(false);
  const [undoStack, setUndoStack] = useState<TimelineHistoryEntry[]>([]);
  const [redoStack, setRedoStack] = useState<TimelineHistoryEntry[]>([]);
  const [focusFinding, setFocusFinding] = useState<string | null>(null);
  const [hideOverlay, setHideOverlay] = useState(false);
  const [pauseUpdates, setPauseUpdates] = useState(false);
  const [viewportMode, setViewportMode] = useState<WorkspaceViewportMode>("STANDARD");
  const workspaceFs = useWorkspaceFullscreen({
    workspaceId: "timeline",
    viewMode: viewportMode,
    onRestoreViewMode: (mode) => setViewportMode(mode),
  });
  const [workspaceLayout, setWorkspaceLayout] = useState(() => loadTimelineWorkspaceLayout());
  const paneDragRef = useRef<{
    side: DrawerSide;
    originX: number;
    originLeft: number;
    originRight: number;
  } | null>(null);
  const layoutRef = useRef(workspaceLayout);
  layoutRef.current = workspaceLayout;
  const openRetakeRef = useRef(() => undefined as void);
  const retakeOpenRef = useRef(false);

  useEffect(() => {
    const onLayout = (event: Event) => {
      const detail = (event as CustomEvent<TimelineWorkspaceLayout>).detail;
      setWorkspaceLayout(detail || loadTimelineWorkspaceLayout());
    };
    window.addEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
    return () => window.removeEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
  }, []);

  const persistLayout = useCallback((patch: Partial<TimelineWorkspaceLayout>) => {
    const saved = saveTimelineWorkspaceLayout(patch);
    setWorkspaceLayout(saved);
    return saved;
  }, []);

  const commitDrawerWidth = useCallback(
    (side: DrawerSide, proposed: number) => {
      const nextWidth = clampDrawerWidth(side, proposed);
      return persistLayout(side === "left" ? { leftWidth: nextWidth } : { rightWidth: nextWidth });
    },
    [persistLayout],
  );

  const setDrawerOpen = useCallback(
    (side: DrawerSide, open: boolean) => {
      persistLayout(side === "left" ? { leftDrawerOpen: open } : { rightDrawerOpen: open });
    },
    [persistLayout],
  );

  const toggleDrawer = useCallback(
    (side: DrawerSide) => {
      const layout = layoutRef.current;
      const open = side === "left" ? !layout.leftDrawerOpen : !layout.rightDrawerOpen;
      setDrawerOpen(side, open);
    },
    [setDrawerOpen],
  );

  const openRightDrawer = useCallback(() => {
    if (!layoutRef.current.rightDrawerOpen) persistLayout({ rightDrawerOpen: true });
  }, [persistLayout]);

  const focusTimelineWorkspace = useCallback(() => {
    persistLayout({ leftDrawerOpen: false, rightDrawerOpen: false });
  }, [persistLayout]);

  const startPaneResize = (side: DrawerSide) => (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const open = side === "left" ? workspaceLayout.leftDrawerOpen : workspaceLayout.rightDrawerOpen;
    if (!open) return;
    event.preventDefault();
    paneDragRef.current = {
      side,
      originX: event.clientX,
      originLeft: workspaceLayout.leftWidth,
      originRight: workspaceLayout.rightWidth,
    };
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    const onMove = (ev: PointerEvent) => {
      const drag = paneDragRef.current;
      if (!drag) return;
      const dx = ev.clientX - drag.originX;
      const proposed = drag.side === "left" ? drag.originLeft + dx : drag.originRight - dx;
      commitDrawerWidth(drag.side, proposed);
    };
    const onUp = (ev: PointerEvent) => {
      paneDragRef.current = null;
      try {
        target.releasePointerCapture(ev.pointerId);
      } catch {
        /* already released */
      }
      target.removeEventListener("pointermove", onMove);
      target.removeEventListener("pointerup", onUp);
      target.removeEventListener("pointercancel", onUp);
    };
    target.addEventListener("pointermove", onMove);
    target.addEventListener("pointerup", onUp);
    target.addEventListener("pointercancel", onUp);
  };

  const onPaneKeyDown = (side: DrawerSide) => (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const open = side === "left" ? workspaceLayout.leftDrawerOpen : workspaceLayout.rightDrawerOpen;
    if (!open) return;
    const step = event.shiftKey ? 32 : 16;
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight" && event.key !== "Home" && event.key !== "End") {
      return;
    }
    event.preventDefault();
    const current = side === "left" ? workspaceLayout.leftWidth : workspaceLayout.rightWidth;
    const paneMin = side === "left" ? LEFT_PANE_MIN : RIGHT_PANE_MIN;
    const paneMax = side === "left" ? LEFT_PANE_MAX : RIGHT_PANE_MAX;
    if (event.key === "Home") {
      commitDrawerWidth(side, paneMin);
      return;
    }
    if (event.key === "End") {
      commitDrawerWidth(side, paneMax);
      return;
    }
    const delta = event.key === "ArrowRight" ? step : -step;
    commitDrawerWidth(side, current + (side === "left" ? delta : -delta));
  };

  const selectedAsset =
    (libraryPreviewId && project.assets.find((asset) => asset.id === libraryPreviewId)) || null;

  useEffect(() => {
    bindAssetUrlProject(project.id);
    return () => bindAssetUrlProject(null);
  }, [project.id]);

  // Stale-fetch guard: a slow master response from a prior scene (or a
  // superseded refresh) must never overwrite newer state (NO_STALE_RELOAD,
  // same generation-token pattern as DirectorTracks.loadTokenRef).
  const masterLoadTokenRef = useRef(0);

  const refreshMaster = useCallback(async () => {
    if (!selected) return;
    const token = ++masterLoadTokenRef.current;
    const sceneId = selected.id;
    const data = await api.directorTimelineMaster(project.id, sceneId);
    if (token !== masterLoadTokenRef.current) return;
    const nextMaster = data.master as SceneTimelineMaster;
    masterCacheRef.current.set(sceneId, nextMaster);
    setMaster(nextMaster);
    setAppliedSceneId(sceneId);
    // TIMELINE_DRIVEN_PREVIEW: fetch the real DirectorTimeline (image_clips,
    // prompt_segments, etc.) so the Preview Composer can resolve the active
    // clip at the playhead. Previously the shell passed `master` (the batch
    // container) cast as the timeline, so the composer never saw clips.
    try {
      const tl = (await api.getDirector(project.id, sceneId)) as DirectorTimeline;
      if (token !== masterLoadTokenRef.current) return;
      const priorForScene = directorCacheRef.current.get(sceneId) ?? null;
      const merged = overlayLiveTimeline(tl, priorForScene);
      directorCacheRef.current.set(sceneId, merged);
      directorTimelineRef.current = merged;
      setDirectorTimeline(merged);
    } catch {
      if (token !== masterLoadTokenRef.current) return;
      directorCacheRef.current.delete(sceneId);
      setDirectorTimeline(null);
    }
  }, [project.id, selected]);

  // Scene-init: reset selection/playhead/undo ONLY when the scene id actually
  // changes. Depending on the `selected` object reference would re-fire on
  // every project refresh (new scenes array) and clobber a clip selection
  // back to scene — the root cause of the Prompt clip selection slip
  // (NO_PASSIVE_SELECTION_LOSS / TIMELINE_OWNS_SELECTION).
  const selectedSceneId = selected?.id;
  useLayoutEffect(() => {
    if (!selectedSceneId) return;
    const cachedMaster = masterCacheRef.current.get(selectedSceneId) ?? null;
    const cachedDirector = directorCacheRef.current.get(selectedSceneId) ?? null;
    setMaster(cachedMaster);
    setDirectorTimeline(cachedDirector);
    directorTimelineRef.current = cachedDirector;
    setAppliedSceneId(cachedMaster ? selectedSceneId : null);
    setSelection({ kind: "scene", id: selectedSceneId });
    pause();
    seek(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSceneId]);
  useEffect(() => {
    if (!selectedSceneId) return;
    // Preflight state is owned by useTimelinePreflight (scene-open triggers a
    // fresh run via the signature effect) — no manual "notRunYet" reset here.
    setUndoStack([]);
    setRedoStack([]);
    void refreshMaster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSceneId]);

  useEffect(() => {
    const onFocus = (event: Event) => {
      const detail = (event as CustomEvent<TimelineFocusRequest>).detail;
      if (!detail) return;
      if (detail.sceneId && selected && detail.sceneId !== selected.id) {
        setSelectedScene(detail.sceneId);
      }
      if (detail.openRightTab) {
        setRightTab(detail.openRightTab);
        openRightDrawer();
      } else if (
        detail.target === "inspectorField" ||
        detail.target === "preflightFinding" ||
        detail.target === "queueJob"
      ) {
        setRightTab("inspector");
        openRightDrawer();
      }
      if (detail.selectionKind) {
        setSelection({
          kind: detail.selectionKind as DirectorSelectionKind,
          id: detail.selectionId,
        });
      }
      if (typeof detail.playheadSec === "number") {
        seek(detail.playheadSec);
        if (selected) {
          void api.getDirector(project.id, selected.id).then((timeline) => {
            void api.putDirector(project.id, selected.id, {
              ...(timeline as DirectorTimeline),
              playhead: detail.playheadSec,
            });
          });
        }
      }
      if (typeof detail.zoom === "number") {
        setZoom(detail.zoom);
      } else if (typeof detail.zoomDelta === "number") {
        setZoom(stepTimelineZoom(zoom, detail.zoomDelta > 0 ? 1 : -1));
      }
      if (detail.findingCode) setFocusFinding(detail.findingCode);
      if (detail.openInpaint === true || detail.openRetake === true) {
        openRetakeRef.current();
      }
      window.setTimeout(() => {
        if (detail.target === "scenePrompt" || detail.fieldId === "scenePrompt") {
          focusDomId(TIMELINE_FOCUS_IDS.scenePrompt);
        } else if (detail.target === "viewer") {
          focusDomId(TIMELINE_FOCUS_IDS.viewer);
        } else if (detail.target === "playhead") {
          focusDomId(TIMELINE_FOCUS_IDS.playhead);
        } else if (detail.target === "queueJob") {
          focusDomId(detail.jobId ? `timeline-queue-job-${detail.jobId}` : TIMELINE_FOCUS_IDS.queue);
        } else if (detail.target === "batch") {
          focusDomId(detail.selectionId ? `timeline-track-item-batch-${detail.selectionId}` : TIMELINE_FOCUS_IDS.batchLane);
        } else if (detail.target === "trackItem" && detail.selectionKind && detail.selectionId) {
          focusDomId(`timeline-track-item-${detail.selectionKind}-${detail.selectionId}`);
        } else if (detail.target === "inspectorField" && detail.fieldId) {
          focusDomId(`timeline-focus-${detail.fieldId}`);
        } else {
          focusDomId(TIMELINE_FOCUS_IDS.inspector);
        }
      }, 50);
    };
    window.addEventListener(TIMELINE_FOCUS_EVENT, onFocus as EventListener);
    return () => window.removeEventListener(TIMELINE_FOCUS_EVENT, onFocus as EventListener);
  }, [openRightDrawer, project.id, seek, selected, setSelectedScene, setSelection, setZoom, zoom]);

  const afterMutation = useCallback(async () => {
    await refresh();
    await refreshMaster();
    setReloadKey((value) => value + 1);
  }, [refresh, refreshMaster]);

  const anyGenerating = useMemo(
    () => (liveMaster?.batchBlocks || []).some((batch) => batch.status === "Generating"),
    [liveMaster?.batchBlocks],
  );
  const takeSignature = useMemo(
    () =>
      (liveMaster?.batchBlocks || [])
        .map((batch) => {
          const approved = batch.approvedClip?.assetId || "";
          const candidates = (batch.candidateVersions || []).map((candidate) => candidate.assetId || "").join(",");
          return `${batch.id}:${batch.status}:${approved}:${candidates}`;
        })
        .join("|"),
    [liveMaster?.batchBlocks],
  );
  const wasGeneratingRef = useRef(false);
  const takeSignatureRef = useRef(takeSignature);

  useEffect(() => {
    if (!anyGenerating) return;
    const timer = window.setInterval(() => {
      void refreshMaster();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [anyGenerating, refreshMaster]);

  useEffect(() => {
    if (wasGeneratingRef.current && !anyGenerating) {
      void afterMutation();
    }
    wasGeneratingRef.current = anyGenerating;
  }, [anyGenerating, afterMutation]);

  useEffect(() => {
    if (takeSignatureRef.current === takeSignature) return;
    takeSignatureRef.current = takeSignature;
    if (!takeSignature) return;
    setReloadKey((value) => value + 1);
  }, [takeSignature]);

  const timelineCancelSupported = useMemo(() => {
    const generating = (liveMaster?.batchBlocks || []).some((b) => b.status === "Generating");
    if (!generating) return false;
    return Boolean(selectedGenerator?.supportsQueuedCancel || selectedGenerator?.supportsRunningCancel);
  }, [liveMaster?.batchBlocks, selectedGenerator?.supportsQueuedCancel, selectedGenerator?.supportsRunningCancel]);

  const handleTimelineCancelRender = useCallback(() => {
    if (!timelineCancelSupported) return;
    void api
      .directorTimelineCancel(project.id, selected.id, { action: "cancel_active_local_job" })
      .then(afterMutation);
  }, [afterMutation, project.id, selected.id, timelineCancelSupported]);

  const runGenerateScene = useCallback(async () => {
    if (!selected || generateBusy) return;
    if (!sceneCanGenerate) {
      setActionNotice(
        t("timeline:generateSceneNotReady", {
          reason: selectedGenerator?.readiness || "no ready video engine is selected",
        }),
      );
      return;
    }
    if (preflightBlockingCount > 0) {
      setActionNotice(t("timeline:generateSceneBlocked", { count: preflightBlockingCount }));
      return;
    }
    setGenerateBusy(true);
    setActionNotice(null);
    try {
      const result = await api.directorTimelineGenerateScene(project.id, selected.id, { scope: "full" });
      const err = timelineActionError(result);
      if (err) {
        setActionNotice(err);
        return;
      }
      if (timelineGenerateEmpty(result)) {
        setActionNotice(t("timeline:generateSceneNothingQueued"));
        return;
      }
      setActionNotice(t("timeline:generateSceneSubmitted"));
      await afterMutation();
    } catch (error) {
      setActionNotice(error instanceof Error && error.message ? error.message : t("timeline:generateSceneNotReady", { reason: "the request failed" }));
    } finally {
      setGenerateBusy(false);
    }
  }, [
    afterMutation,
    generateBusy,
    sceneCanGenerate,
    preflightBlockingCount,
    project.id,
    selected,
    selectedGenerator?.readiness,
    t,
  ]);

  const runReviewExtend = useCallback(async () => {
    if (!selected || extendBusy) return;
    if (!canReviewExtend) {
      setActionNotice(t("timeline:reviewExtendNeedApproved"));
      return;
    }
    setExtendBusy(true);
    setActionNotice(null);
    try {
      const result = await api.directorTimelineExtend(project.id, selected.id, {
        prompt: selected.prompt || "",
        durationSec: 5,
      });
      const err = timelineActionError(result);
      if (err) {
        setActionNotice(err);
        return;
      }
      if (!result.ok) {
        setActionNotice(result.error || result.message || t("timeline:reviewExtendFailed"));
        return;
      }
      setActionNotice(t("timeline:reviewExtendSubmitted"));
      await afterMutation();
    } catch (error) {
      setActionNotice(
        error instanceof Error && error.message
          ? error.message
          : t("timeline:reviewExtendFailed"),
      );
    } finally {
      setExtendBusy(false);
    }
  }, [afterMutation, canReviewExtend, extendBusy, project.id, selected, t]);

  const videoRetake = useVideoRetake({
    projectId: project.id,
    sceneId: selected?.id,
    playheadSec,
    batchWindows,
    pausePlayback: pause,
    afterMutation,
  });
  openRetakeRef.current = videoRetake.open;
  retakeOpenRef.current = videoRetake.session.open;

  const handleOpenRetake = useCallback(() => {
    videoRetake.toggle();
  }, [videoRetake]);

  const handleAddBatch = useCallback(async () => {
    if (!selected) return;
    await addTimelineBatch(project.id, selected.id, master);
    await afterMutation();
  }, [afterMutation, master, project.id, selected]);

  const completedBatches = useMemo(() => completedApprovedBatches(liveMaster), [liveMaster]);
  const canStitch = Boolean(selected?.id) && completedBatches.length >= 2 && !stitchBusy;

  const onStitchBatches = useCallback(async () => {
    if (!selected || stitchBusy) return;
    if (completedApprovedBatches(liveMaster).length < 2) {
      window.alert(t("timeline:stitchNeedTwo"));
      return;
    }
    if (!window.confirm(t("timeline:stitchConfirm"))) return;
    setStitchBusy(true);
    try {
      const result = await api.directorTimelineStitchScene(project.id, selected.id);
      if (result.master) {
        masterCacheRef.current.set(selected.id, result.master);
        setMaster(result.master);
      }
      await afterMutation();
    } catch (error) {
      const message = error instanceof Error && error.message ? error.message : t("timeline:stitchFailed");
      window.alert(message);
    } finally {
      setStitchBusy(false);
    }
  }, [afterMutation, liveMaster, project.id, selected, stitchBusy, t]);

  // c5: refresh project + Timeline master when Co-Director mutates this project
  // so the creator sees approved changes without a manual reload.
  useEffect(() => {
    const onProjectMutated = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId?: string; toolId?: string }>).detail;
      if (!detail || detail.projectId !== project.id) return;
      void afterMutation();
    };
    window.addEventListener("adept:codirector-project-mutated", onProjectMutated);
    return () => window.removeEventListener("adept:codirector-project-mutated", onProjectMutated);
  }, [project.id, afterMutation]);

  const persistBatchPrompts = useCallback(
    async (entries: TimelineHistoryEntry["batchPrompts"]) => {
      if (!selected) return;
      const currentMaster = masterRef.current;
      for (const entry of entries) {
        const existing = currentMaster?.batchBlocks.find((batch) => batch.id === entry.batchId);
        const beforeIds = (existing?.promptSegments || []).map((seg) => seg.id).join(",");
        const afterIds = (entry.promptSegments || []).map((seg) => seg.id).join(",");
        if (beforeIds === afterIds) continue;
        await api.directorTimelinePatchBatch(project.id, selected.id, entry.batchId, {
          promptSegments: entry.promptSegments,
        });
      }
      setMaster((prev) => {
        if (!prev) return prev;
        const byId = new Map(entries.map((entry) => [entry.batchId, entry.promptSegments]));
        const next = {
          ...prev,
          batchBlocks: prev.batchBlocks.map((batch) =>
            byId.has(batch.id) ? { ...batch, promptSegments: byId.get(batch.id) || [] } : batch,
          ),
        };
        masterCacheRef.current.set(selected.id, next);
        return next;
      });
    },
    [project.id, selected],
  );

  const mutateTimeline = useCallback(
    async (
      mutator: (timeline: DirectorTimeline) => DirectorTimeline,
      opts?: { refresh?: boolean },
    ) => {
      if (!selected) return;
      const current = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const next = mutator(current);
      setUndoStack((stack) => [
        ...stack.slice(-19),
        { timeline: current, batchPrompts: snapshotBatchPrompts(masterRef.current) },
      ]);
      setRedoStack([]);
      directorTimelineRef.current = next;
      directorCacheRef.current.set(selected.id, next);
      setDirectorTimeline(next);
      await api.putDirector(project.id, selected.id, next);
      const removed = [...promptIdsOf(current)].filter((id) => !promptIdsOf(next).has(id));
      if (removed.length && masterRef.current) {
        const patched = dropPromptIdsFromMaster(masterRef.current, removed);
        await persistBatchPrompts(
          patched.batchBlocks.map((batch) => ({ batchId: batch.id, promptSegments: batch.promptSegments || [] })),
        );
      }
      syncPromptTombstones(current, next);
      // Soft text edits must not remount the Inspector (preserves focus/cursor).
      if (opts?.refresh === false) return;
      await afterMutation();
    },
    [afterMutation, persistBatchPrompts, project.id, selected],
  );

  useEffect(() => {
    bindShellTimelineMutate(mutateTimeline);
    return () => bindShellTimelineMutate(null);
  }, [mutateTimeline]);

  useEffect(() => {
    bindShellTimelineSnapshot(liveDirector);
    return () => bindShellTimelineSnapshot(null);
  }, [liveDirector]);

  const applyHistorySnapshot = useCallback(
    async (direction: "undo" | "redo") => {
      if (!selected) return;
      if (direction === "undo" && undoStack.length === 0) return;
      if (direction === "redo" && redoStack.length === 0) return;
      const currentTimeline = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const currentEntry: TimelineHistoryEntry = {
        timeline: currentTimeline,
        batchPrompts: snapshotBatchPrompts(masterRef.current),
      };
      let next: TimelineHistoryEntry;
      if (direction === "undo") {
        next = undoStack[undoStack.length - 1];
        setUndoStack((stack) => stack.slice(0, -1));
        setRedoStack((stack) => [...stack, currentEntry]);
      } else {
        next = redoStack[redoStack.length - 1];
        setRedoStack((stack) => stack.slice(0, -1));
        setUndoStack((stack) => [...stack, currentEntry]);
      }
      directorTimelineRef.current = next.timeline;
      directorCacheRef.current.set(selected.id, next.timeline);
      setDirectorTimeline(next.timeline);
      await api.putDirector(project.id, selected.id, next.timeline);
      await persistBatchPrompts(next.batchPrompts);
      syncPromptTombstones(currentTimeline, next.timeline);
      await afterMutation();
      // Restore visible selection state: if the currently selected clip no
      // longer exists in the restored timeline, fall back to scene so the
      // Inspector never shows a stale/deleted item (NO_PASSIVE_SELECTION_LOSS
      // for legitimate state changes; no stale Inspector after undo/redo).
      const s = selection;
      const restored = next.timeline;
      if (s && s.kind !== "scene" && s.kind !== null && s.id) {
        const exists =
          (restored.prompt_segments || []).some((c) => c.id === s.id) ||
          (restored.image_clips || []).some((c) => c.id === s.id) ||
          (restored.video_clips || []).some((c) => c.id === s.id) ||
          (restored.video_reference_clips || []).some((c) => c.id === s.id) ||
          (restored.image_reference_clips || []).some((c) => c.id === s.id) ||
          (restored.audio_clips || []).some((c) => c.id === s.id) ||
          (restored.sfx_clips || []).some((c) => c.id === s.id) ||
          (restored.camera_clips || []).some((c) => c.id === s.id) ||
          normalizeLipSyncTracks(restored.lipsync?.tracks).some((t) =>
            t.id === s.id || (t.clips || []).some((c) => c.id === s.id),
          );
        if (!exists) setSelection({ kind: "scene", id: selected.id });
      }
    },
    [afterMutation, persistBatchPrompts, project.id, redoStack, selected, selection, setSelection, undoStack],
  );

  const deleteSelection = useCallback(async () => {
    if (!selected || !selection.kind || !selection.id) return;
    if (selection.kind === "scene") return;

    if (selection.kind === "batch") {
      const batch = master?.batchBlocks.find((b) => b.id === selection.id);
      if (!batch) return;
      if (batchHasContent(batch)) {
        const ok = window.confirm(t("timeline:removeBatch", { name: batch.label }));
        if (!ok) return;
      }
      await api.directorTimelineDeleteBatch(project.id, selected.id, batch.id);
      setSelection({ kind: "scene", id: selected.id });
      await afterMutation();
      return;
    }

    if (selection.kind === "lipsyncTrack") {
      const timeline = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const tracks = normalizeLipSyncTracks(timeline.lipsync?.tracks);
      const targetIndex = tracks.findIndex((track) => track.id === selection.id);
      if (targetIndex < 1) return;
      const target = tracks[targetIndex];
      if (lipSyncTrackHasContent(target)) {
        const ok = window.confirm(
          `Remove “${target.label || `Lip Sync ${targetIndex + 1}`}”?\n\nIts clips and track settings will be removed from the Timeline.`,
        );
        if (!ok) return;
      }
      await mutateTimeline((current) => ({
        ...current,
        lipsync: {
          ...current.lipsync,
          tracks: normalizeLipSyncTracks(current.lipsync?.tracks).filter((track) => track.id !== selection.id),
        },
      }));
      setSelection({ kind: "scene", id: selected.id });
      return;
    }

    const kindMap: Record<string, "image" | "video" | "videoReference" | "imageReference" | "audio" | "sfx" | "prompt" | "camera" | "lipsyncClip"> = {
      imageClip: "image",
      videoClip: "video",
      videoReferenceClip: "videoReference",
      imageReferenceClip: "imageReference",
      audio: "audio",
      sfx: "sfx",
      promptSeg: "prompt",
      camera: "camera",
      lipsyncClip: "lipsyncClip",
    };
    const clipKind = kindMap[selection.kind];
    if (!clipKind) return;

    const timeline = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
    let confirmed = true;
    if (clipKind === "image") {
      const clip = (timeline.image_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm(t("timeline:removeImage"));
      }
    } else if (clipKind === "video") {
      const playableTakes = playableVisualClipsFromMaster(masterRef.current);
      const clip =
        (timeline.video_clips || []).find((c) => c.id === selection.id) ||
        playableTakes.find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm(t("timeline:removeVideo"));
      }
    } else if (clipKind === "videoReference") {
      const clip = (timeline.video_reference_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm(t("timeline:removeVideoReference"));
      }
    } else if (clipKind === "audio") {
      const clip = (timeline.audio_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm(t("timeline:removeAudio"));
      }
    } else if (clipKind === "sfx") {
      const clip = (timeline.sfx_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm(t("timeline:removeSfx"));
      }
    } else if (clipKind === "prompt") {
      const seg = (timeline.prompt_segments || []).find((c) => c.id === selection.id);
      if (!seg) return;
      if ((seg.text || "").trim()) {
        confirmed = window.confirm(t("timeline:removeInstruction"));
      }
    } else if (clipKind === "camera") {
      confirmed = window.confirm(t("timeline:removeCamera"));
    } else if (clipKind === "lipsyncClip") {
      const track = normalizeLipSyncTracks(timeline.lipsync?.tracks).find(
        (item) => item.id === selection.trackId || (item.clips || []).some((clip) => clip.id === selection.id),
      );
      const clip = track?.clips?.find((item) => item.id === selection.id);
      if (!track || !clip) return;
      confirmed = window.confirm(t("timeline:removeLipSync"));
    }
    if (!confirmed) return;

    await mutateTimeline((current) => {
      const next = { ...current };
      if (clipKind === "image") next.image_clips = (current.image_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "video") {
        const playableTakes = playableVisualClipsFromMaster(masterRef.current);
        const source =
          (current.video_clips || []).length > 0 ? current.video_clips : playableTakes;
        next.video_clips = source.filter((c) => c.id !== selection.id);
        next.media_mode = "video";
      }
      if (clipKind === "videoReference") next.video_reference_clips = (current.video_reference_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "imageReference") next.image_reference_clips = (current.image_reference_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "audio") next.audio_clips = (current.audio_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "sfx") next.sfx_clips = (current.sfx_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "prompt") next.prompt_segments = (current.prompt_segments || []).filter((c) => c.id !== selection.id);
      if (clipKind === "camera") next.camera_clips = (current.camera_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "lipsyncClip") {
        next.lipsync = {
          ...current.lipsync,
          tracks: normalizeLipSyncTracks(current.lipsync?.tracks).map((track) => {
            const clips = (track.clips || []).filter((clip) => clip.id !== selection.id);
            const firstAudio = clips.find((clip) => clip.audio_asset_id);
            const firstCharacterId = clips.find((clip) => clip.character_id);
            const firstCharacterName = clips.find((clip) => clip.character_name);
            return {
              ...track,
              clips,
              audio_asset_id: firstAudio?.audio_asset_id || track.audio_asset_id || null,
              character_id: firstCharacterId?.character_id || track.character_id || null,
              character_name: firstCharacterName?.character_name || track.character_name || null,
            };
          }),
        };
      }
      return next;
    });
    setSelection({ kind: "scene", id: selected.id });
  }, [afterMutation, master, mutateTimeline, project.id, selected, selection.id, selection.kind, selection.trackId, setSelection]);

  const duplicateSelection = useCallback(() => {
    if (!selected || !selection.kind || selection.kind === "scene") return;
    void mutateTimeline((current) => {
      const dup = <T extends { id: string; start: number }>(items: T[]): T[] => {
        const item = items.find((c) => c.id === selection.id);
        if (!item) return items;
        return [...items, { ...item, id: Math.random().toString(36).slice(2, 10), start: item.start + 0.25 }];
      };
      if (selection.kind === "imageClip") return { ...current, image_clips: dup(current.image_clips || []) };
      if (selection.kind === "videoClip") return { ...current, video_clips: dup(current.video_clips || []) };
      if (selection.kind === "videoReferenceClip") return { ...current, video_reference_clips: dup(current.video_reference_clips || []) };
      if (selection.kind === "imageReferenceClip") return { ...current, image_reference_clips: dup(current.image_reference_clips || []) };
      if (selection.kind === "promptSeg") return { ...current, prompt_segments: dup(current.prompt_segments || []) };
      if (selection.kind === "audio") return { ...current, audio_clips: dup(current.audio_clips || []) };
      if (selection.kind === "sfx") return { ...current, sfx_clips: dup(current.sfx_clips || []) };
      if (selection.kind === "camera") return { ...current, camera_clips: dup(current.camera_clips || []) };
      return current;
    });
  }, [mutateTimeline, selected, selection.id, selection.kind]);

  useEffect(() => {
    const unsubscribers = [
      registerTimelineCommand("undo", () => void applyHistorySnapshot("undo")),
      registerTimelineCommand("redo", () => void applyHistorySnapshot("redo")),
      registerTimelineCommand("deleteClip", () => {
        if (!selection.kind || selection.kind === "scene") return;
        void deleteSelection();
      }),
      registerTimelineCommand("deleteClipBackspace", () => {
        if (!selection.kind || selection.kind === "scene") return;
        void deleteSelection();
      }),
      registerTimelineCommand("duplicateClip", () => duplicateSelection()),
      registerTimelineCommand("playPause", () => toggle()),
      registerTimelineCommand("goToSceneStart", () => goToSceneStart()),
      registerTimelineCommand("goToBatchIn", () => goToBatchIn()),
      registerTimelineCommand("goToBatchOut", () => goToBatchOut()),
      registerTimelineCommand("goToSceneEnd", () => goToSceneEnd()),
      registerTimelineCommand("fullscreen", () => void workspaceFs.toggleFullscreen()),
      registerTimelineCommand("openHotkeys", () => {
        setRightTab("hotkeys");
        openRightDrawer();
      }),
      registerTimelineCommand("toggleLeftDrawer", () => toggleDrawer("left")),
      registerTimelineCommand("toggleRightDrawer", () => toggleDrawer("right")),
      registerTimelineCommand("focusTimeline", () => focusTimelineWorkspace()),
      registerTimelineCommand("escape", () => {
        if (videoRetake.session.open) {
          videoRetake.close();
          return;
        }
        if (layoutRef.current.rightDrawerOpen) {
          persistLayout({ rightDrawerOpen: false });
          return;
        }
        if (layoutRef.current.leftDrawerOpen) {
          persistLayout({ leftDrawerOpen: false });
          return;
        }
        if (selected) setSelection({ kind: "scene", id: selected.id });
      }),
      registerTimelineCommand("playheadLeft", () => seek((t) => t - 0.1)),
      registerTimelineCommand("playheadRight", () => seek((t) => t + 0.1)),
      registerTimelineCommand("playheadLeftLarge", () => seek((t) => t - 1)),
      registerTimelineCommand("playheadRightLarge", () => seek((t) => t + 1)),
    ];
    return () => {
      unsubscribers.forEach((off) => off());
    };
  }, [
    applyHistorySnapshot,
    deleteSelection,
    duplicateSelection,
    goToSceneStart,
    goToBatchIn,
    goToBatchOut,
    goToSceneEnd,
    focusTimelineWorkspace,
    openRightDrawer,
    persistLayout,
    videoRetake,
    seek,
    toggle,
    selected,
    selection.kind,
    setSelection,
    toggleDrawer,
    workspaceFs,
  ]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && retakeOpenRef.current) {
        if (e.defaultPrevented) return;
        e.preventDefault();
        runTimelineCommand("escape");
        return;
      }
      if (isEditableTarget(e.target)) return;
      const hit = matchHotkey(e, loadHotkeys());
      if (!hit) return;
      e.preventDefault();
      runTimelineCommand(hit.actionId);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleAddAssetToTimeline = useCallback(
    async (asset: Asset) => {
      if (!selected) return;
      const timeline = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const duration = timeline.duration_sec || selected.duration_sec || 5;
      const id = Math.random().toString(36).slice(2, 10);
      let next = { ...timeline };
      if (asset.kind === "image") {
        // Omni Wave 3A Law 2: Library image → References only (mediaType=image).
        // Do NOT write Visual image_clips guide takes. No silent generation.
        await api.sceneReferences.attach(project.id, {
          asset_id: asset.id,
          scope_type: "project",
          scope_id: project.id,
          reference_type: "image",
          media_kind: "image",
          alias: (asset.tag || asset.filename || "Image").replace(/\s+/g, ""),
          usage_modes: ["appearance"],
          reference_roles: ["image"],
        });
        await afterMutation();
        return;
      } else if (asset.kind === "video") {
        next = {
          ...next,
          media_mode: "video",
          video_clips: [
            {
              id,
              start: 0,
              length: duration,
              label: "Video",
              asset_id: asset.id,
              trim_start: 0,
              mediaType: "video",
              media_type: "video",
            },
          ],
        };
      } else if (asset.kind === "audio") {
        next = {
          ...next,
          audio_clips: [...(timeline.audio_clips || []), { id, start: 0, length: duration, label: asset.tag || "Audio", asset_id: asset.id, volume: 1 }],
        };
      }
      await api.putDirector(project.id, selected.id, next);
      await afterMutation();
    },
    [afterMutation, project.id, selected],
  );

  const handleAddAssetAsReference = useCallback(
    async (asset: Asset) => {
      if (!selected) return;
      if (asset.kind === "audio") return;
      const mediaKind = asset.kind === "video" ? "video" : asset.kind === "image" ? "image" : null;
      if (!mediaKind) return;
      await api.sceneReferences.attach(project.id, {
        asset_id: asset.id,
        scope_type: "project",
        scope_id: project.id,
        reference_type: mediaKind,
        media_kind: mediaKind,
        alias: (asset.tag || asset.filename || mediaKind).replace(/\s+/g, ""),
        usage_modes: mediaKind === "video" ? ["motion"] : ["appearance"],
        reference_roles: [mediaKind],
      });
      await afterMutation();
    },
    [afterMutation, project.id, selected],
  );

  const handleAddFromProjectLibrary = useCallback(
    (assetIds: string[]) => {
      if (!assetIds.length) return;
      void mutateTimeline((current) => {
        const already = new Set(current.library_asset_ids || []);
        const nextIds = [...(current.library_asset_ids || [])];
        for (const id of assetIds) {
          if (!already.has(id)) nextIds.push(id);
        }
        return { ...current, library_asset_ids: nextIds };
      });
    },
    [mutateTimeline],
  );

  const handleRemoveFromLibrary = useCallback(
    (asset: { id: string }) => {
      setLibraryPreviewId((current) => (current === asset.id ? null : current));
      void mutateTimeline((current) => {
        const nextIds = (current.library_asset_ids || []).filter((id) => id !== asset.id);
        if (nextIds.length === (current.library_asset_ids || []).length) return current;
        return { ...current, library_asset_ids: nextIds };
      });
    },
    [mutateTimeline],
  );

  if (!selected) {
    return (
      <div className="timeline-v2" data-testid="timeline-editor-shell" data-empty-scenes="true">
        <header className="timeline-v2__header" data-testid="timeline-scene-header">
          <div className="timeline-v2__header-identity">
            <h2 className="timeline-v2__header-title" data-testid="timeline-scene-header-title">
              No scenes yet
            </h2>
            <p className="timeline-v2__header-meta">Add a Scene to start the Timeline.</p>
          </div>
        </header>
        <button
          type="button"
          className="timeline-v2__drawer-handle timeline-v2__drawer-handle--left"
          data-testid="timeline-drawer-left-toggle"
          aria-expanded={workspaceLayout.leftDrawerOpen}
          aria-controls="timeline-drawer-left"
          onClick={(event) => {
            event.stopPropagation();
            toggleDrawer("left");
          }}
        >
          {workspaceLayout.leftDrawerOpen ? "‹" : "›"}
        </button>
        <aside
          id="timeline-drawer-left"
          data-testid="timeline-drawer-left"
          className={`timeline-v2__drawer timeline-v2__drawer--left${workspaceLayout.leftDrawerOpen ? " timeline-v2__drawer--open" : " timeline-v2__drawer--closed"}`}
        >
          <div className="timeline-v2__drawer-body">
            <div className="timeline-v2__dock timeline-v2__dock--scenes">
              <Timeline
                project={project}
                selectedId={selectedScene}
                onSelect={(id) => {
                  setSelectedScene(id);
                  setSelection({ kind: "scene", id });
                }}
                onChange={() => void refresh()}
              />
            </div>
          </div>
        </aside>
        <main className="timeline-v2__main">
          <p className="empty" data-testid="timeline-scenes-empty">
            Add a Scene to start the Timeline.
          </p>
        </main>
      </div>
    );
  }

  const resetWorkspaceLayout = () => {
    requestTimelineFocus({ target: "viewer", layoutReset: true });
  };

  return (
    <div
      ref={workspaceFs.containerRef}
      className="timeline-v2"
      data-testid="timeline-editor-shell"
      data-viewport-mode={viewportMode}
      style={
        {
          "--timeline-left-width": `${workspaceLayout.leftWidth}px`,
          "--timeline-right-width": `${workspaceLayout.rightWidth}px`,
          "--timeline-drawer-handle-width": "14px",
        } as CSSProperties
      }
    >
      <div ref={audioHostRef} data-testid="timeline-audio-playback" hidden />
      <WorkspaceFullscreenBanner visible={workspaceFs.showBanner} />
      <TimelineGeneratorBanner />
      <header className="timeline-v2__header" data-testid="timeline-scene-header">
        <div className="timeline-v2__header-identity">
          <h2 className="timeline-v2__header-title" data-testid="timeline-scene-header-title">{selected.name}</h2>
          <p className="timeline-v2__header-meta" data-testid="timeline-scene-header-meta">
            {creatorGeneratorLine(
              resolveGeneratorOption(
                generatorOptions,
                liveMaster?.sceneGeneratorId,
                liveMaster?.batchBlocks[0]?.generatorId,
                selected.engine,
              ) || { label: selected.engine || "Engine", executionType: "local" },
            )}{" "}
            · {t("timeline:durationSec", { seconds: formatDurationSeconds(sceneEndSec).replace(/s$/, "") })} ·{" "}
            {master?.mode === "video_finishing" ? t("timeline:videoFinishing") : t("timeline:imagePlanning")}
          </p>
        </div>
        <div className="timeline-v2__header-actions">
          <div className="timeline-v2__header-viewer" data-testid="timeline-scene-header-viewer">
            <button
              type="button"
              className="timeline-v2__header-btn ghost"
              data-testid="timeline-viewer-fit"
              title={t("timeline:fitTitle")}
              aria-label={t("timeline:fitTitle")}
              onClick={() => requestTimelineFocus({ target: "viewer", fitViewer: true })}
            >
              {t("timeline:fit")}
            </button>
            <label className="timeline-v2__header-select">
              <span className="sr-only">{t("timeline:viewerSize")}</span>
              <select
                className="timeline-v2__header-select-control"
                value={workspaceLayout.viewerPreset}
                aria-label={t("timeline:viewerSize")}
                data-testid="timeline-viewer-preset"
                title={t("timeline:viewerSize")}
                onChange={(e) =>
                  requestTimelineFocus({ target: "viewer", viewerPreset: e.target.value as TimelineViewerPreset })
                }
              >
                <option value="large">{t("timeline:viewerSizeLarge")}</option>
                <option value="balanced">{t("timeline:viewerSizeBalanced")}</option>
                <option value="timeline_focus">{t("timeline:viewerSizeTimelineFocus")}</option>
              </select>
            </label>
            <label className="timeline-v2__header-select">
              <span className="sr-only">{t("timeline:pictureShape")}</span>
              <select
                className="timeline-v2__header-select-control"
                data-testid="timeline-viewer-aspect"
                value={normalizeProductionAspect(selected.aspect_ratio)}
                title={t("timeline:pictureShapeTitle")}
                aria-label={t("timeline:pictureShape")}
                onChange={(e) =>
                  void api.updateScene(project.id, selected.id, { ...selected, aspect_ratio: e.target.value }).then(afterMutation)
                }
              >
                {PRODUCTION_ASPECTS.map((ratio) => (
                  <option key={ratio} value={ratio}>
                    {ratio}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className={`timeline-v2__header-btn ${!hideOverlay ? "primary" : "ghost"}`}
              data-testid="timeline-viewer-guides"
              title={hideOverlay ? t("timeline:guidesShow") : t("timeline:guidesHide")}
              aria-label={hideOverlay ? t("timeline:guidesShow") : t("timeline:guidesHide")}
              aria-pressed={!hideOverlay}
              onClick={() => setHideOverlay((v) => !v)}
            >
              {t("timeline:guides")}
            </button>
            <button
              type="button"
              className={`timeline-v2__header-btn ${pauseUpdates ? "primary" : "ghost"}`}
              data-testid="timeline-viewer-pause"
              title={pauseUpdates ? t("timeline:resumeViewerTitle") : t("timeline:pauseViewerTitle")}
              aria-label={pauseUpdates ? t("timeline:resumeViewerTitle") : t("timeline:pauseViewerTitle")}
              aria-pressed={pauseUpdates}
              onClick={() => setPauseUpdates((v) => !v)}
            >
              {pauseUpdates ? t("timeline:resumeViewer") : t("timeline:pauseViewer")}
            </button>
            <button
              type="button"
              className="timeline-v2__header-btn ghost"
              data-testid="timeline-focus-workspace"
              title={t("timeline:focusTimelineTitle")}
              aria-label={t("timeline:focusTimeline")}
              onClick={focusTimelineWorkspace}
            >
              {t("timeline:focusTimeline")}
            </button>
            <button
              type="button"
              className="timeline-v2__header-btn ghost"
              data-testid="timeline-reset-layout"
              title={t("timeline:resetLayoutTitle")}
              aria-label={t("timeline:resetLayout")}
              onClick={resetWorkspaceLayout}
            >
              {t("timeline:resetLayout")}
            </button>
          </div>
          <WorkspaceFullscreenControls
            fs={workspaceFs}
            showExpand={false}
          />
          <button
            type="button"
            className={`timeline-v2__header-btn ${master?.mode === "image_planning" ? "primary" : "ghost"}`}
            data-testid="timeline-mode-image-planning"
            title={t("timeline:imagePlanningTitle")}
            aria-label={t("timeline:imagePlanningTitle")}
            onClick={() => void api.directorTimelineSetMode(project.id, selected.id, "image_planning").then(afterMutation)}
          >
            {t("timeline:imagePlanning")}
          </button>
          <button
            type="button"
            className={`timeline-v2__header-btn ${master?.mode === "video_finishing" ? "primary" : "ghost"}`}
            data-testid="timeline-mode-video-finishing"
            title={t("timeline:videoFinishingTitle")}
            aria-label={t("timeline:videoFinishingTitle")}
            onClick={() => void api.directorTimelineSetMode(project.id, selected.id, "video_finishing").then(afterMutation)}
          >
            {t("timeline:videoFinishing")}
          </button>
          <ActionWithHelp
            help={{
              label: getTimelineHelp("stitch_batches").title,
              content: getTimelineHelp("stitch_batches").body,
              text: getTimelineHelp("stitch_batches").title,
            }}
          >
            <button
              type="button"
              className="timeline-v2__header-btn ghost"
              data-testid="timeline-stitch-batches"
              title={completedBatches.length < 2 ? t("timeline:stitchNeedTwo") : t("timeline:stitchTitle")}
              aria-label={t("timeline:stitchTitle")}
              disabled={!canStitch}
              onClick={() => void onStitchBatches()}
            >
              {stitchBusy ? t("timeline:stitchBusy") : t("timeline:stitch")}
            </button>
          </ActionWithHelp>
          <button
            type="button"
            className="timeline-v2__header-btn"
            title={t("timeline:preflightTitle")}
            aria-label={t("timeline:preflightTitle")}
            data-testid="timeline-header-preflight"
            onClick={() => timelinePreflight.recheckNow()}
          >
            {timelinePreflight.status === "checking"
              ? t("timeline:preflightChecking")
              : t("timeline:preflightRecheck")}
          </button>
          <button
            type="button"
            className="timeline-v2__header-btn primary"
            title={
              !sceneCanGenerate
                ? t("timeline:generateSceneNotReady", {
                    reason: selectedGenerator?.readiness || "no ready video engine is selected",
                  })
                : preflightBlockingCount > 0
                ? t("timeline:generateSceneBlocked", { count: preflightBlockingCount })
                : t("timeline:generateSceneTitle")
            }
            aria-label={t("timeline:generateSceneTitle")}
            data-testid="timeline-header-generate"
            disabled={generateBusy}
            onClick={() => void runGenerateScene()}
          >
            {generateBusy ? t("timeline:generateSceneBusy") : t("timeline:generateScene")}
          </button>
          <button
            type="button"
            className="timeline-v2__header-btn primary"
            title={canReviewExtend ? t("timeline:reviewExtendTitle") : t("timeline:reviewExtendNeedBatch")}
            aria-label={t("timeline:reviewExtendTitle")}
            data-testid="timeline-header-review-extend"
            disabled={extendBusy}
            onClick={() => void runReviewExtend()}
          >
            {extendBusy ? t("timeline:reviewExtendBusy") : t("timeline:reviewExtend")}
          </button>
          <button
            type="button"
            className="timeline-v2__header-btn ghost"
            title={t("timeline:stopJobsTitle")}
            aria-label={t("timeline:stopJobsTitle")}
            onClick={() => void api.directorTimelineCancel(project.id, selected.id, { action: "stop_remaining_scene_jobs" }).then(afterMutation)}
          >
            {t("timeline:stopJobs")}
          </button>
          <button
            type="button"
            className="timeline-v2__header-btn ghost"
            data-testid="timeline-header-resume"
            title={t("timeline:resumeTitle")}
            aria-label={t("timeline:resumeTitle")}
            onClick={() => void api.directorTimelineCancel(project.id, selected.id, { action: "resume_incomplete_only" }).then(afterMutation)}
          >
            {t("timeline:resume")}
          </button>
        </div>
        {actionNotice ? (
          <p className="timeline-v2__action-notice" data-testid="timeline-action-notice" role="status">
            {actionNotice}
          </p>
        ) : null}
      </header>

      <div
        className="timeline-v2__body"
        data-left-open={workspaceLayout.leftDrawerOpen ? "true" : "false"}
        data-right-open={workspaceLayout.rightDrawerOpen ? "true" : "false"}
      >
        <main className="timeline-v2__workspace" data-testid="timeline-v2-workspace">
          <TimelineWorkspaceStack
            projectId={project.id}
            monitor={
              <div id={TIMELINE_FOCUS_IDS.viewer} data-testid="timeline-focus-viewer" tabIndex={-1}>
                <TimelinePreviewComposer
                  project={project}
                  scene={selected}
                  timeline={liveDirector}
                  master={liveMaster}
                  selection={selection}
                  playheadSec={playheadSec}
                  onPlayheadChange={seek}
                  timelinePlaying={playing}
                  sceneEndSec={sceneEndSec}
                  libraryAsset={selectedAsset}
                  onClearLibraryAsset={() => setLibraryPreviewId(null)}
                  hideOverlay={hideOverlay}
                  onHideOverlayChange={setHideOverlay}
                  pauseUpdates={pauseUpdates}
                  onPauseUpdatesChange={setPauseUpdates}
                  inlineActions={false}
                  cancelRenderSupported={timelineCancelSupported}
                  onCancelRender={handleTimelineCancelRender}
                  onAddBatch={() => void handleAddBatch()}
                  onOpenRetake={handleOpenRetake}
                  retakeActive={videoRetake.session.open}
                  retakeSession={videoRetake.session}
                  retakeMediaRef={videoRetake.mediaRef}
                  onRetakeMarkIn={videoRetake.markIn}
                  onRetakeMarkOut={videoRetake.markOut}
                  onRetakeTool={videoRetake.setTool}
                  onRetakeBrushSize={videoRetake.setBrushSize}
                  onRetakePrompt={videoRetake.setPrompt}
                  onRetakeClearMask={videoRetake.clearMask}
                  onRetakeRemoveBackground={() => void videoRetake.removeBackground()}
                  onRetakeCancel={videoRetake.close}
                  onRetakeSubmit={() => void videoRetake.submit()}
                  onRetakeMaskChange={videoRetake.setHasMask}
                  onDismissFailure={(jobId) =>
                    void api.directorTimelineDismissFailure(project.id, selected.id, jobId).then(afterMutation)
                  }
                  onApproved={afterMutation}
                />
              </div>
            }
            timeline={
              <div className="timeline-v2__tracks">
                <SceneStatusStrip projectId={project.id} />
                <TimelineToolbar
                  projectId={project.id}
                  scene={selected}
                  master={liveMaster}
                  onRefresh={afterMutation}
                  onActionError={(message) => setActionNotice(message)}
                  onPreflightRecheck={timelinePreflight.recheckNow}
                  mutateTimeline={mutateTimeline}
                  canUndo={undoStack.length > 0}
                  canRedo={redoStack.length > 0}
                  onUndo={() => void applyHistorySnapshot("undo")}
                  onRedo={() => void applyHistorySnapshot("redo")}
                  onGuidancePriorityChange={(value) => {
                    void mutateTimeline((timeline) => ({ ...timeline, guidance_priority: value }));
                  }}
                  onOpenRetake={handleOpenRetake}
                  retakeActive={videoRetake.session.open}
                  playing={playing}
                  playheadSec={playheadSec}
                  onGoToSceneStart={goToSceneStart}
                  onGoToBatchIn={goToBatchIn}
                  onTogglePlay={toggle}
                  onGoToBatchOut={goToBatchOut}
                  onGoToSceneEnd={goToSceneEnd}
                  transportBounds={transportBounds}
                  transportSceneId={selected.id}
                />
                <DirectorTracks
                  project={project}
                  scene={selected}
                  onChange={() => void afterMutation()}
                  hideEmbeddedStage
                  externalPlayhead={playheadSec}
                  onPlayheadChange={seek}
                  reloadKey={reloadKey}
                  master={liveMaster}
                  shellMode
                  mutateTimeline={mutateTimeline}
                  retakeMode={videoRetake.session.open}
                  retakeRange={videoRetake.highlight}
                />
              </div>
            }
          />
        </main>

        <button
          type="button"
          className="timeline-v2__drawer-handle timeline-v2__drawer-handle--left"
          data-testid="timeline-drawer-left-toggle"
          aria-expanded={workspaceLayout.leftDrawerOpen}
          aria-controls="timeline-drawer-left"
          title={workspaceLayout.leftDrawerOpen ? t("timeline:closeLeftDrawer") : t("timeline:openLeftDrawer")}
          aria-label={workspaceLayout.leftDrawerOpen ? t("timeline:closeLeftDrawer") : t("timeline:openLeftDrawer")}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            toggleDrawer("left");
          }}
        >
          {workspaceLayout.leftDrawerOpen ? "‹" : "›"}
        </button>

        <aside
          id="timeline-drawer-left"
          data-testid="timeline-drawer-left"
          className={`timeline-v2__drawer timeline-v2__drawer--left${workspaceLayout.leftDrawerOpen ? " timeline-v2__drawer--open" : " timeline-v2__drawer--closed"}`}
        >
          <div className="timeline-v2__drawer-body">
            <VideoGeneratorDock
              projectId={project.id}
              scene={selected}
              master={liveMaster}
              timeline={liveDirector}
              onRefresh={afterMutation}
              mutateTimeline={mutateTimeline}
            />
            <div className="timeline-v2__dock timeline-v2__dock--scenes">
              <Timeline
                project={project}
                selectedId={selected.id}
                onSelect={(id) => {
                  setSelectedScene(id);
                  setSelection({ kind: "scene", id });
                }}
                onChange={() => void refresh()}
              />
            </div>
            <div className="timeline-v2__dock timeline-v2__dock--library">
              <AssetTray
                project={project}
                onChange={() => void refresh()}
                selectedAssetId={libraryPreviewId}
                onSelectAsset={(asset) =>
                  setLibraryPreviewId((current) => (current === asset.id ? null : asset.id))
                }
                onAddToTimeline={(asset) => void handleAddAssetToTimeline(asset)}
                onAddAsReference={(asset) => void handleAddAssetAsReference(asset)}
                onRemoveFromLibrary={handleRemoveFromLibrary}
                allowUpload={false}
                stagedAssetIds={liveDirector?.library_asset_ids ?? []}
                onOpenProjectLibrary={() => setLibraryPickerOpen(true)}
              />
            </div>
            <div className="timeline-v2__dock timeline-v2__dock--references">
              <ReferencesPane
                project={project}
                sceneId={selected.id}
                workflowTab="timeline"
                reloadKey={reloadKey}
                onChange={() => void afterMutation()}
              />
            </div>
          </div>
          <div
            className="timeline-v2__splitter"
            data-testid="timeline-splitter-left"
            role="separator"
            aria-orientation="vertical"
            aria-label={t("timeline:resizeLeft")}
            aria-valuenow={Math.round(workspaceLayout.leftWidth)}
            aria-hidden={!workspaceLayout.leftDrawerOpen}
            tabIndex={workspaceLayout.leftDrawerOpen ? 0 : -1}
            onPointerDown={startPaneResize("left")}
            onKeyDown={onPaneKeyDown("left")}
          />
        </aside>

        <aside
          id="timeline-drawer-right"
          data-testid="timeline-drawer-right"
          className={`timeline-v2__drawer timeline-v2__drawer--right${workspaceLayout.rightDrawerOpen ? " timeline-v2__drawer--open" : " timeline-v2__drawer--closed"}`}
        >
          <div
            className="timeline-v2__splitter"
            data-testid="timeline-splitter-right"
            role="separator"
            aria-orientation="vertical"
            aria-label={t("timeline:resizeRight")}
            aria-valuenow={Math.round(workspaceLayout.rightWidth)}
            aria-hidden={!workspaceLayout.rightDrawerOpen}
            tabIndex={workspaceLayout.rightDrawerOpen ? 0 : -1}
            onPointerDown={startPaneResize("right")}
            onKeyDown={onPaneKeyDown("right")}
          />
          <div className="timeline-v2__drawer-body">
          <div className="timeline-v2__tabs" role="tablist" aria-label={t("timeline:inspector")}>
            <button
              type="button"
              role="tab"
              aria-selected={rightTab === "inspector"}
              className={rightTab === "inspector" ? "primary" : "ghost"}
              data-testid="timeline-tab-inspector"
              title={t("timeline:showInspector")}
              aria-label={t("timeline:showInspector")}
              onClick={() => {
                setRightTab("inspector");
                openRightDrawer();
              }}
            >
              {t("timeline:inspector")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightTab === "codirector"}
              className={rightTab === "codirector" ? "primary" : "ghost"}
              data-testid="timeline-tab-codirector"
              title={t("timeline:showCoDirector")}
              aria-label={t("timeline:showCoDirector")}
              onClick={() => {
                setRightTab("codirector");
                openRightDrawer();
              }}
            >
              {t("timeline:coDirector")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightTab === "hotkeys"}
              className={rightTab === "hotkeys" ? "primary" : "ghost"}
              data-testid="timeline-tab-hotkeys"
              title={t("timeline:showHotKeys")}
              aria-label={t("timeline:showHotKeys")}
              onClick={() => {
                setRightTab("hotkeys");
                openRightDrawer();
              }}
            >
              {t("timeline:hotKeys")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightTab === "gpu"}
              className={rightTab === "gpu" ? "primary" : "ghost"}
              data-testid="timeline-tab-gpu"
              title={t("timeline:showGpu")}
              aria-label={t("timeline:showGpu")}
              onClick={() => {
                setRightTab("gpu");
                openRightDrawer();
              }}
            >
              {t("timeline:gpu")}
            </button>
          </div>
          <div className="timeline-v2__right-content">
            <div
              className={`timeline-v2__panel timeline-v2__panel--inspector${rightTab === "inspector" ? "" : " timeline-v2__panel--inactive"}`}
              data-testid="timeline-right-panel-inspector"
            >
              <TimelineInspector
                project={project}
                scene={selected}
                master={liveMaster}
                reloadKey={reloadKey}
                preflightSummary={preflightSummary}
                focusFinding={focusFinding}
                onRefresh={afterMutation}
                onActionError={(message) => setActionNotice(message)}
                mutateTimeline={mutateTimeline}
              />
            </div>
            <div
              className={`timeline-v2__panel timeline-v2__panel--hotkeys${rightTab === "hotkeys" ? "" : " timeline-v2__panel--inactive"}`}
              data-testid="timeline-right-panel-hotkeys"
            >
              <TimelineHotKeysPane />
            </div>
            <div
              className={`timeline-v2__panel timeline-v2__panel--gpu${rightTab === "gpu" ? "" : " timeline-v2__panel--inactive"}`}
              data-testid="timeline-right-panel-gpu"
            >
              <TimelineGpuPane project={project} scene={selected} onChange={afterMutation} />
            </div>
            <div
              className={`timeline-v2__panel timeline-v2__panel--codirector${rightTab === "codirector" ? "" : " timeline-v2__panel--inactive"}`}
              data-testid="timeline-right-panel-codirector"
            >
              <section className="panel timeline-codirector-placeholder" data-testid="timeline-codirector-rail">
                <div className="timeline-inspector__eyebrow">{t("timeline:coDirector")}</div>
                <p className="scene-meta">{t("timeline:coDirectorHint")}</p>
                <button
                  type="button"
                  className="primary"
                  title={t("timeline:openCoDirectorTitle")}
                  aria-label={t("timeline:openCoDirectorTitle")}
                  onClick={() =>
                    openCoDirector(
                      `Focus the Scene Prompt for “${selected.name}” and explain Scene Prompt vs Timed Prompt. Then run Preflight.`,
                    )
                  }
                >
                  {t("timeline:openCoDirector")}
                </button>
              </section>
            </div>
            <div className="timeline-v2__right-queue">
              <CompactRenderQueue projectId={project.id} sceneId={selected.id} onChange={afterMutation} />
            </div>
          </div>
          </div>
        </aside>

        <button
          type="button"
          className="timeline-v2__drawer-handle timeline-v2__drawer-handle--right"
          data-testid="timeline-drawer-right-toggle"
          aria-expanded={workspaceLayout.rightDrawerOpen}
          aria-controls="timeline-drawer-right"
          title={workspaceLayout.rightDrawerOpen ? t("timeline:closeRightDrawer") : t("timeline:openRightDrawer")}
          aria-label={workspaceLayout.rightDrawerOpen ? t("timeline:closeRightDrawer") : t("timeline:openRightDrawer")}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            toggleDrawer("right");
          }}
        >
          {workspaceLayout.rightDrawerOpen ? "›" : "‹"}
        </button>
      </div>
      {libraryPickerOpen ? (
        <AddFromProjectLibraryModal
          project={project}
          alreadyIds={liveDirector?.library_asset_ids || []}
          onAdd={handleAddFromProjectLibrary}
          onAssetsChanged={() => void refresh()}
          onClose={() => setLibraryPickerOpen(false)}
        />
      ) : null}
    </div>
  );
}

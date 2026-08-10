import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Asset, Project } from "../../types";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import type { DirectorSelectionKind } from "../../directorSelection";
import {
  focusDomId,
  TIMELINE_FOCUS_EVENT,
  TIMELINE_FOCUS_IDS,
  type TimelineFocusRequest,
} from "../../timelineMaster/timelineFocus";
import {
  WorkspaceFullscreenBanner,
  WorkspaceFullscreenControls,
  useWorkspaceFullscreen,
  type WorkspaceViewportMode,
} from "../../workspace/fullscreen";
import { useDirectorSelection } from "../DirectorSelectionContext";
import { DirectorTracks, lipSyncTrackHasContent, normalizeLipSyncTracks, type DirectorTimeline } from "../DirectorTracks";
import { TimelinePreviewComposer } from "./TimelinePreviewComposer";
import { Timeline } from "../Timeline";
import { AssetTray } from "../AssetTray";
import { ReferencesPane } from "../sceneReferences/ReferencesPane";
import { useOpenCoDirector } from "../CoDirector";
import { TimelineWorkspaceStack } from "./TimelineWorkspaceStack";
import { TimelineToolbar } from "./TimelineToolbar";
import { SceneStatusStrip } from "./SceneStatusStrip";
import { TimelineInspector } from "./TimelineInspector";
import { CompactRenderQueue } from "./CompactRenderQueue";
import { TimelineGeneratorBanner } from "./TimelineGeneratorBanner";
import { TimelineInpaintWorkspace } from "./TimelineInpaintWorkspace";
import { TimelineRetakeDrawer } from "./TimelineRetakeDrawer";
import "../../styles/timeline-master/timeline-editor-shell.css";

function generatorLabel(engine: string) {
  if (engine === "auto") return "Auto";
  if (engine === "minimax-h3") return "MiniMax H3 (Default)";
  if (engine === "ltx") return "LTX Video";
  if (engine === "hunyuan15") return "HunyuanVideo 1.5";
  if (engine === "hunyuan13b") return "HunyuanVideo 13B";
  if (engine === "wan") return "WAN 2.2";
  return engine.replace(/^fal_/, "").replace(/_/g, " ");
}

function isEditableTarget(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  if (!el) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || Boolean(el.closest("input, textarea, select, [contenteditable='true']"));
}

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
  const { selection, setSelection, setZoom, zoom } = useDirectorSelection();
  const openCoDirector = useOpenCoDirector();
  const selected = useMemo(
    () => project.scenes.find((scene) => scene.id === selectedScene) || project.scenes[0],
    [project.scenes, selectedScene],
  );
  const [playheadSec, setPlayheadSec] = useState(0);
  const [libraryPreviewId, setLibraryPreviewId] = useState<string | null>(null);
  const [master, setMaster] = useState<SceneTimelineMaster | null>(null);
  const [directorTimeline, setDirectorTimeline] = useState<DirectorTimeline | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [preflightSummary, setPreflightSummary] = useState("Not run yet");
  const [rightTab, setRightTab] = useState<"inspector" | "codirector">("inspector");
  const [undoStack, setUndoStack] = useState<DirectorTimeline[]>([]);
  const [redoStack, setRedoStack] = useState<DirectorTimeline[]>([]);
  const [focusFinding, setFocusFinding] = useState<string | null>(null);
  const [hideOverlay, setHideOverlay] = useState(false);
  const [pauseUpdates, setPauseUpdates] = useState(false);
  const [inpaintOpen, setInpaintOpen] = useState(false);
  const [retakeOpen, setRetakeOpen] = useState(false);
  const [viewportMode, setViewportMode] = useState<WorkspaceViewportMode>("STANDARD");
  const workspaceFs = useWorkspaceFullscreen({
    workspaceId: "timeline",
    viewMode: viewportMode,
    onRestoreViewMode: (mode) => setViewportMode(mode),
  });

  const selectedAsset =
    (libraryPreviewId && project.assets.find((asset) => asset.id === libraryPreviewId)) || null;

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
    setMaster(data.master as SceneTimelineMaster);
    // TIMELINE_DRIVEN_PREVIEW: fetch the real DirectorTimeline (image_clips,
    // prompt_segments, etc.) so the Preview Composer can resolve the active
    // clip at the playhead. Previously the shell passed `master` (the batch
    // container) cast as the timeline, so the composer never saw clips.
    try {
      const tl = (await api.getDirector(project.id, sceneId)) as DirectorTimeline;
      if (token !== masterLoadTokenRef.current) return;
      setDirectorTimeline(tl);
    } catch {
      if (token !== masterLoadTokenRef.current) return;
      setDirectorTimeline(null);
    }
  }, [project.id, selected]);

  // Scene-init: reset selection/playhead/undo ONLY when the scene id actually
  // changes. Depending on the `selected` object reference would re-fire on
  // every project refresh (new scenes array) and clobber a clip selection
  // back to scene — the root cause of the Prompt clip selection slip
  // (NO_PASSIVE_SELECTION_LOSS / TIMELINE_OWNS_SELECTION).
  const selectedSceneId = selected?.id;
  useEffect(() => {
    if (!selectedSceneId) return;
    setSelection({ kind: "scene", id: selectedSceneId });
    setPlayheadSec(0);
    setPreflightSummary("Not run yet");
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
      setRightTab(detail.openRightTab || "inspector");
      if (detail.selectionKind) {
        setSelection({
          kind: detail.selectionKind as DirectorSelectionKind,
          id: detail.selectionId,
        });
      }
      if (typeof detail.playheadSec === "number") {
        setPlayheadSec(detail.playheadSec);
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
        setZoom(Math.min(3, Math.max(0.5, Number((zoom + detail.zoomDelta).toFixed(2)))));
      }
      if (detail.findingCode) setFocusFinding(detail.findingCode);
      if (detail.openInpaint === true) {
        setInpaintOpen(true);
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
  }, [project.id, selected, setSelectedScene, setSelection, setZoom, zoom]);

  const afterMutation = useCallback(async () => {
    await refresh();
    await refreshMaster();
    setReloadKey((value) => value + 1);
  }, [refresh, refreshMaster]);

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

  const mutateTimeline = useCallback(
    async (
      mutator: (timeline: DirectorTimeline) => DirectorTimeline,
      opts?: { refresh?: boolean },
    ) => {
      if (!selected) return;
      const current = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const next = mutator(current);
      setUndoStack((stack) => [...stack.slice(-19), current]);
      setRedoStack([]);
      await api.putDirector(project.id, selected.id, next);
      // Soft text edits must not remount the Inspector (preserves focus/cursor).
      if (opts?.refresh === false) return;
      await afterMutation();
    },
    [afterMutation, project.id, selected],
  );

  const applyHistorySnapshot = useCallback(
    async (direction: "undo" | "redo") => {
      if (!selected) return;
      if (direction === "undo" && undoStack.length === 0) return;
      if (direction === "redo" && redoStack.length === 0) return;
      const current = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      let next: DirectorTimeline;
      if (direction === "undo") {
        next = undoStack[undoStack.length - 1];
        setUndoStack((stack) => stack.slice(0, -1));
        setRedoStack((stack) => [...stack, current]);
      } else {
        next = redoStack[redoStack.length - 1];
        setRedoStack((stack) => stack.slice(0, -1));
        setUndoStack((stack) => [...stack, current]);
      }
      await api.putDirector(project.id, selected.id, next);
      await afterMutation();
      // Restore visible selection state: if the currently selected clip no
      // longer exists in the restored timeline, fall back to scene so the
      // Inspector never shows a stale/deleted item (NO_PASSIVE_SELECTION_LOSS
      // for legitimate state changes; no stale Inspector after undo/redo).
      const s = selection;
      if (s && s.kind !== "scene" && s.kind !== null && s.id) {
        const exists =
          (next.prompt_segments || []).some((c) => c.id === s.id) ||
          (next.image_clips || []).some((c) => c.id === s.id) ||
          (next.video_clips || []).some((c) => c.id === s.id) ||
          (next.audio_clips || []).some((c) => c.id === s.id) ||
          (next.sfx_clips || []).some((c) => c.id === s.id) ||
          (next.camera_clips || []).some((c) => c.id === s.id) ||
          normalizeLipSyncTracks(next.lipsync?.tracks).some((t) =>
            t.id === s.id || (t.clips || []).some((c) => c.id === s.id),
          );
        if (!exists) setSelection({ kind: "scene", id: selected.id });
      }
    },
    [afterMutation, project.id, redoStack, selected, selection, setSelection, undoStack],
  );

  const deleteSelection = useCallback(async () => {
    if (!selected || !selection.kind || !selection.id) return;
    if (selection.kind === "scene") return;

    if (selection.kind === "batch") {
      const batch = master?.batchBlocks.find((b) => b.id === selection.id);
      if (!batch) return;
      if (batchHasContent(batch)) {
        const ok = window.confirm(
          `Remove “${batch.label}”?\n\nThis Batch has content or job history. Source assets remain in Project Library.`,
        );
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

    const kindMap: Record<string, "image" | "video" | "audio" | "sfx" | "prompt" | "camera" | "lipsyncClip"> = {
      imageClip: "image",
      videoClip: "video",
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
        confirmed = window.confirm("Remove this Image from the Timeline?\n\nSource assets remain in Project Library.");
      }
    } else if (clipKind === "video") {
      const clip = (timeline.video_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm("Remove this Video from the Timeline?\n\nSource assets remain in Project Library.");
      }
    } else if (clipKind === "audio") {
      const clip = (timeline.audio_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm("Remove this Audio clip from the Timeline?\n\nSource assets remain in Project Library.");
      }
    } else if (clipKind === "sfx") {
      const clip = (timeline.sfx_clips || []).find((c) => c.id === selection.id);
      if (!clip) return;
      if (clip.asset_id) {
        confirmed = window.confirm("Remove this SFX clip from the Timeline?\n\nSource assets remain in Project Library.");
      }
    } else if (clipKind === "prompt") {
      const seg = (timeline.prompt_segments || []).find((c) => c.id === selection.id);
      if (!seg) return;
      if ((seg.text || "").trim()) {
        confirmed = window.confirm("Remove this Timed Instruction?");
      }
    } else if (clipKind === "camera") {
      confirmed = window.confirm("Remove this Camera clip from the Timeline?");
    } else if (clipKind === "lipsyncClip") {
      const track = normalizeLipSyncTracks(timeline.lipsync?.tracks).find(
        (item) => item.id === selection.trackId || (item.clips || []).some((clip) => clip.id === selection.id),
      );
      const clip = track?.clips?.find((item) => item.id === selection.id);
      if (!track || !clip) return;
      confirmed = window.confirm("Remove this Lip Sync Clip from the Timeline?");
    }
    if (!confirmed) return;

    await mutateTimeline((current) => {
      const next = { ...current };
      if (clipKind === "image") next.image_clips = (current.image_clips || []).filter((c) => c.id !== selection.id);
      if (clipKind === "video") next.video_clips = (current.video_clips || []).filter((c) => c.id !== selection.id);
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isEditableTarget(e.target)) return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        void applyHistorySnapshot("undo");
        return;
      }
      if ((mod && e.key.toLowerCase() === "y") || (mod && e.shiftKey && e.key.toLowerCase() === "z")) {
        e.preventDefault();
        void applyHistorySnapshot("redo");
        return;
      }
      if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        if (!selected || !selection.kind || selection.kind === "scene") return;
        void mutateTimeline((current) => {
          const dup = <T extends { id: string; start: number }>(items: T[]): T[] => {
            const item = items.find((c) => c.id === selection.id);
            if (!item) return items;
            return [...items, { ...item, id: Math.random().toString(36).slice(2, 10), start: item.start + 0.25 }];
          };
          if (selection.kind === "imageClip") return { ...current, image_clips: dup(current.image_clips || []) };
          if (selection.kind === "videoClip") return { ...current, video_clips: dup(current.video_clips || []) };
          if (selection.kind === "promptSeg") return { ...current, prompt_segments: dup(current.prompt_segments || []) };
          if (selection.kind === "audio") return { ...current, audio_clips: dup(current.audio_clips || []) };
          if (selection.kind === "sfx") return { ...current, sfx_clips: dup(current.sfx_clips || []) };
          if (selection.kind === "camera") return { ...current, camera_clips: dup(current.camera_clips || []) };
          return current;
        });
        return;
      }
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      if (!selection.kind || selection.kind === "scene") return;
      e.preventDefault();
      void deleteSelection();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [applyHistorySnapshot, deleteSelection, mutateTimeline, selected, selection.id, selection.kind]);

  const handleAddAssetToTimeline = useCallback(
    async (asset: Asset) => {
      if (!selected) return;
      const timeline = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const duration = timeline.duration_sec || selected.duration_sec || 5;
      const id = Math.random().toString(36).slice(2, 10);
      let next = { ...timeline };
      if (asset.kind === "image") {
        const imageClips = timeline.image_clips || [];
        const start = imageClips.reduce((max, clip) => Math.max(max, clip.start + clip.length), 0);
        next = {
          ...next,
          media_mode: "image",
          image_clips: [
            ...imageClips,
            { id, start: Math.min(start, Math.max(0, duration - 1)), length: Math.min(2, duration), label: "Image", role: "guide", asset_id: asset.id },
          ],
        };
      } else if (asset.kind === "video") {
        next = {
          ...next,
          media_mode: "video",
          video_clips: [{ id, start: 0, length: duration, label: "Video", asset_id: asset.id, trim_start: 0 }],
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
      const referenceType =
        asset.kind === "image" ? "character" : asset.kind === "video" ? "environment" : "prop";
      await api.sceneReferences.attach(project.id, {
        asset_id: asset.id,
        scope_type: "scene",
        scope_id: selected.id,
        reference_type: referenceType,
        usage_modes: ["appearance"],
        reference_roles: [referenceType],
      });
      await afterMutation();
    },
    [afterMutation, project.id, selected],
  );

  if (!selected) {
    return <div className="page"><p className="empty">Select a scene to open the Timeline.</p></div>;
  }

  const previewExtraControls = (
    <>
      <button
        type="button"
        className={!hideOverlay ? "primary" : "ghost"}
        title={hideOverlay ? "Show Viewer guides and status overlays" : "Hide Viewer guides and status overlays"}
        aria-label={hideOverlay ? "Show Viewer guides and status overlays" : "Hide Viewer guides and status overlays"}
        aria-pressed={!hideOverlay}
        onClick={() => setHideOverlay((v) => !v)}
      >
        Guides
      </button>
      <button
        type="button"
        className={pauseUpdates ? "primary" : "ghost"}
        title={pauseUpdates ? "Resume Viewer updates" : "Pause Viewer updates"}
        aria-label={pauseUpdates ? "Resume Viewer updates" : "Pause Viewer updates"}
        aria-pressed={pauseUpdates}
        onClick={() => setPauseUpdates((v) => !v)}
      >
        {pauseUpdates ? "Resume" : "Pause"}
      </button>
    </>
  );

  return (
    <div
      ref={workspaceFs.containerRef}
      className={`timeline-editor-shell${viewportMode === "EXPANDED" ? " is-expanded-viewport" : ""}`}
      data-testid="timeline-editor-shell"
      data-viewport-mode={viewportMode}
    >
      <WorkspaceFullscreenBanner visible={workspaceFs.showBanner} />
      <TimelineGeneratorBanner />
      <header className="timeline-scene-header panel" data-testid="timeline-scene-header">
        <div className="timeline-scene-header__identity">
          <h2>{selected.name}</h2>
          <p className="scene-meta">
            {generatorLabel(selected.engine)} · {selected.duration_sec.toFixed(1)} sec · {master?.mode === "video_finishing" ? "Video Finishing" : "Image Planning"}
          </p>
        </div>
        <div className="timeline-scene-header__actions">
          <WorkspaceFullscreenControls
            fs={workspaceFs}
            expandActive={viewportMode === "EXPANDED"}
            onExpand={() => setViewportMode((m) => (m === "EXPANDED" ? "STANDARD" : "EXPANDED"))}
          />
          <button
            type="button"
            className={`timeline-scene-header__btn ${master?.mode === "image_planning" ? "primary" : "ghost"}`}
            title="Set Scene mode to Image Planning"
            aria-label="Set Scene mode to Image Planning"
            onClick={() => void api.directorTimelineSetMode(project.id, selected.id, "image_planning").then(afterMutation)}
          >
            Image Planning
          </button>
          <button
            type="button"
            className={`timeline-scene-header__btn ${master?.mode === "video_finishing" ? "primary" : "ghost"}`}
            title="Set Scene mode to Video Finishing"
            aria-label="Set Scene mode to Video Finishing"
            onClick={() => void api.directorTimelineSetMode(project.id, selected.id, "video_finishing").then(afterMutation)}
          >
            Video Finishing
          </button>
          <button
            type="button"
            className="timeline-scene-header__btn"
            title="Run Co-Director Preflight for this Scene"
            aria-label="Run Co-Director Preflight for this Scene"
            onClick={() =>
              void api.directorTimelinePreflight(project.id, selected.id).then((result) => {
                setPreflightSummary(result.findings.length ? `${result.findings.length} finding(s)` : "Ready");
                void afterMutation();
              })
            }
          >
            Preflight
          </button>
          <button
            type="button"
            className="timeline-scene-header__btn primary"
            title="Generate the full Scene with the Timeline orchestrator"
            aria-label="Generate the full Scene with the Timeline orchestrator"
            onClick={() => void api.directorTimelineGenerateScene(project.id, selected.id, { scope: "full" }).then(afterMutation)}
          >
            Generate Scene
          </button>
          <button
            type="button"
            className="timeline-scene-header__btn ghost"
            title="Stop remaining Scene generation jobs"
            aria-label="Stop remaining Scene generation jobs"
            onClick={() => void api.directorTimelineCancel(project.id, selected.id, { action: "stop_remaining_scene_jobs" }).then(afterMutation)}
          >
            Stop Jobs
          </button>
          <button
            type="button"
            className="timeline-scene-header__btn ghost"
            title="Resume incomplete Scene generation jobs"
            aria-label="Resume incomplete Scene generation jobs"
            onClick={() => void api.directorTimelineCancel(project.id, selected.id, { action: "resume_incomplete_only" }).then(afterMutation)}
          >
            Resume
          </button>
        </div>
      </header>

      <div className="timeline-editor-shell__layout">
        <aside className="timeline-editor-shell__left">
          <div className="timeline-editor-shell__dock timeline-editor-shell__dock--scenes">
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
          <div className="timeline-editor-shell__dock">
            <AssetTray
              project={project}
              onChange={() => void refresh()}
              selectedAssetId={libraryPreviewId}
              onSelectAsset={(asset) => setLibraryPreviewId(asset.id)}
              onAddToTimeline={(asset) => void handleAddAssetToTimeline(asset)}
              onAddAsReference={(asset) => void handleAddAssetAsReference(asset)}
            />
          </div>
          <div className="timeline-editor-shell__dock">
            <ReferencesPane
              project={project}
              sceneId={selected.id}
              workflowTab="timeline"
              onChange={() => void refresh()}
            />
          </div>
        </aside>

        <main className="timeline-editor-shell__center">
          <TimelineWorkspaceStack
            projectId={project.id}
            extraControls={previewExtraControls}
            monitor={
              <div id={TIMELINE_FOCUS_IDS.viewer} data-testid="timeline-focus-viewer" tabIndex={-1}>
                <TimelinePreviewComposer
                  project={project}
                  scene={selected}
                  timeline={directorTimeline}
                  master={master}
                  selection={selection}
                  playheadSec={playheadSec}
                  onPlayheadChange={setPlayheadSec}
                  libraryAsset={selectedAsset}
                  onClearLibraryAsset={() => setLibraryPreviewId(null)}
                  hideOverlay={hideOverlay}
                  onHideOverlayChange={setHideOverlay}
                  pauseUpdates={pauseUpdates}
                  onPauseUpdatesChange={setPauseUpdates}
                  inlineActions={false}
                  onDismissFailure={(jobId) =>
                    void api.directorTimelineDismissFailure(project.id, selected.id, jobId).then(afterMutation)
                  }
                />
              </div>
            }
            timeline={
              <div className="timeline-editor-shell__tracks">
                <SceneStatusStrip projectId={project.id} />
                <TimelineToolbar
                  projectId={project.id}
                  scene={selected}
                  master={master}
                  onRefresh={afterMutation}
                  onPreflight={(result) => {
                    setPreflightSummary(result.findings.length ? `${result.findings.length} finding(s)` : "Ready");
                  }}
                  mutateTimeline={mutateTimeline}
                  canUndo={undoStack.length > 0}
                  canRedo={redoStack.length > 0}
                  onUndo={() => void applyHistorySnapshot("undo")}
                  onRedo={() => void applyHistorySnapshot("redo")}
                  onGuidancePriorityChange={(value) => {
                    void mutateTimeline((timeline) => ({ ...timeline, guidance_priority: value }));
                  }}
                  onOpenInpaint={() => setInpaintOpen(true)}
                  onOpenRetake={() => setRetakeOpen(true)}
                />
                <DirectorTracks
                  project={project}
                  scene={selected}
                  onChange={() => void afterMutation()}
                  hideEmbeddedStage
                  externalPlayhead={playheadSec}
                  onPlayheadChange={setPlayheadSec}
                  reloadKey={reloadKey}
                  master={master}
                  shellMode
                />
                <TimelineInpaintWorkspace
                  open={inpaintOpen}
                  projectId={project.id}
                  scene={selected}
                  master={master}
                  playheadSec={playheadSec}
                  onClose={() => setInpaintOpen(false)}
                  onRefresh={afterMutation}
                />
                <TimelineRetakeDrawer
                  projectId={project.id}
                  sceneId={selected.id}
                  shotId={`scene-${selected.id}-shot-1`}
                  open={retakeOpen}
                  onClose={() => setRetakeOpen(false)}
                  baselinePrompt="A glowing glass bottle on a dark studio table, slow cinematic push-in, subtle condensation, controlled rim lighting."
                />
              </div>
            }
          />
        </main>

        <aside className="timeline-editor-shell__right">
          <div className="timeline-editor-shell__tabs">
            <button
              type="button"
              className={rightTab === "inspector" ? "primary" : "ghost"}
              title="Show the Timeline Inspector"
              aria-label="Show the Timeline Inspector"
              onClick={() => setRightTab("inspector")}
            >
              Inspector
            </button>
            <button
              type="button"
              className={rightTab === "codirector" ? "primary" : "ghost"}
              title="Show the Co-Director rail"
              aria-label="Show the Co-Director rail"
              onClick={() => setRightTab("codirector")}
            >
              Co-Director
            </button>
          </div>
          {rightTab === "inspector" ? (
            <TimelineInspector
              project={project}
              scene={selected}
              master={master}
              reloadKey={reloadKey}
              preflightSummary={preflightSummary}
              focusFinding={focusFinding}
              onRefresh={afterMutation}
              mutateTimeline={mutateTimeline}
            />
          ) : (
            <section className="panel timeline-codirector-placeholder" data-testid="timeline-codirector-rail">
              <div className="timeline-inspector__eyebrow">Co-Director</div>
              <p className="scene-meta">
                Ask Co-Director to inspect this Scene, focus the Scene Prompt, move the playhead, or run Preflight.
                Mutations use ProposalService approval — the same Timeline state as this shell.
              </p>
              <button
                type="button"
                className="primary"
                title="Open Co-Director with a Scene Prompt focus prompt"
                aria-label="Open Co-Director with a Scene Prompt focus prompt"
                onClick={() =>
                  openCoDirector(
                    `Focus the Scene Prompt for “${selected.name}” and explain Scene Prompt vs Timed Instructions. Then run Preflight.`,
                  )
                }
              >
                Open Co-Director
              </button>
            </section>
          )}
          <CompactRenderQueue projectId={project.id} sceneId={selected.id} onChange={afterMutation} />
        </aside>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import type { Scene } from "../../types";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { rematerializeThenGenerateScene } from "../../timelineMaster/rematerializeThenGenerate";
import { addTimelineBatch } from "../../timelineMaster/addTimelineBatch";
import { getTimelineHelp } from "../../timelineMaster/helpCatalog";
import { anyTimelineGeneratorExecutable, resolveGeneratorOption } from "../../timelineMaster/draftCapabilities";
import { loadTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { useDirectorSelection } from "../DirectorSelectionContext";
import { ActionWithHelp, HelpTip } from "../HelpTip";
import {
  type TimelineBoardView,
  type PromptSegment,
  type TimelineClip,
} from "../DirectorTracks";
import { TimelineSettingsDrawer } from "./TimelineSettingsDrawer";
import { registerTimelineCommand } from "../../timelineMaster/timelineHotkeys";
import { stepTimelineZoom, sliderToZoom, zoomToSlider } from "../../timelineMaster/timelineZoom";
import { TIMELINE_BATCHES_CREATOR_UI } from "../../timelineMaster/timelineBatchesCreatorUi";
import { TIMELINE_LIPSYNC_CREATOR_UI } from "../../timelineMaster/timelineLipSyncCreatorUi";
import { timelineActionError, timelineGenerateEmpty } from "../../timelineMaster/timelineErrors";
import { findSameTrackIntersection } from "../../timelineMaster/sameTrackNoOverlap";
import type { AudioClipModalKind } from "../../timelineMaster/audioClipModal";

/** Header + transport generate controls for the Timeline board. */
function nid() {
  return Math.random().toString(36).slice(2, 10);
}

function Help({ id }: { id: string }) {
  const help = getTimelineHelp(id);
  return <HelpTip label={help.title} content={help.body} text={help.title} />;
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


function PlusMinusGroup({
  label,
  helpId,
  onAdd,
  onRemove,
  addTitle,
  removeTitle,
  disabled,
  testId,
}: {
  label: string;
  helpId?: string;
  onAdd: () => void;
  onRemove: () => void;
  addTitle: string;
  removeTitle: string;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <div className="timeline-pm-group" role="group" aria-label={label} data-testid={testId}>
      <span className="timeline-pm-group__label">
        {label}
        {helpId ? <Help id={helpId} /> : null}
      </span>
      <button
        type="button"
        className="timeline-pm-group__btn"
        disabled={disabled}
        title={addTitle}
        aria-label={addTitle}
        data-testid={testId ? `${testId}-add` : undefined}
        onClick={onAdd}
      >
        +
      </button>
      <button
        type="button"
        className="timeline-pm-group__btn"
        disabled={disabled}
        title={removeTitle}
        aria-label={removeTitle}
        data-testid={testId ? `${testId}-remove` : undefined}
        onClick={onRemove}
      >
        −
      </button>
    </div>
  );
}

export function TimelineToolbar({
  projectId,
  scene,
  master,
  onRefresh,
  onPreflightRecheck,
  mutateTimeline,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onGuidancePriorityChange,
  onOpenRetake,
  onGenerationStandby,
  onActionError,
  retakeActive: _retakeActive,
  playing,
  playheadSec,
  onGoToSceneStart,
  onGoToBatchIn,
  onTogglePlay,
  onGoToBatchOut,
  onGoToSceneEnd,
  transportBounds,
  transportSceneId,
  onOpenAudioClip,
  onOptimisticMaster,
}: {
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  onRefresh: () => void | Promise<void>;
  /** Manual "Re-check now" — routes into the shell's always-on preflight hook. */
  onPreflightRecheck: () => void;
  mutateTimeline: (mutator: (timeline: TimelineBoardView) => TimelineBoardView) => Promise<void>;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void | Promise<void>;
  onRedo: () => void | Promise<void>;
  onGuidancePriorityChange: (value: TimelineBoardView["guidance_priority"]) => void;
  onOpenRetake?: () => void;
  onGenerationStandby?: (standby: boolean) => void;
  onActionError?: (message: string) => void;
  retakeActive?: boolean;
  playing: boolean;
  playheadSec: number;
  onGoToSceneStart: () => void;
  onGoToBatchIn: () => void;
  onTogglePlay: () => void;
  onGoToBatchOut: () => void;
  onGoToSceneEnd: () => void;
  transportBounds: {
    sceneStart: number;
    sceneEnd: number;
    activeBatchStart: number;
    activeBatchEnd: number;
  };
  transportSceneId?: string;
  onOpenAudioClip?: (request: { kind: AudioClipModalKind; clipId: string | null; start: number }) => void;
  /** Instant Update: apply Master patch locally before refresh readback. */
  onOptimisticMaster?: (master: SceneTimelineMaster) => void;
}) {
  const { selection, snap, setSnap, zoom, setZoom, setSelection } = useDirectorSelection();
  const { t } = useTranslation("timeline");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generatorOptions, setGeneratorOptions] = useState(
    () => [] as Awaited<ReturnType<typeof loadTimelineVideoGenerators>>,
  );

  useEffect(() => {
    let alive = true;
    void loadTimelineVideoGenerators()
      .then((rows) => {
        if (alive) setGeneratorOptions(rows);
      })
      .catch(() => {
        if (alive) setGeneratorOptions([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  const selectedBatch = useMemo(
    () => (selection.kind === "batch" ? master?.batchBlocks.find((b) => b.id === selection.id) : null),
    [master, selection],
  );
  const selectedGen = resolveGeneratorOption(
    generatorOptions,
    selectedBatch?.generatorId,
    master?.batchBlocks[0]?.generatorId,
    master?.sceneGeneratorId,
    scene.engine,
  );
  const draftAvailable = (selectedGen?.draftPathway || "none") !== "none";
  const generating = (master?.batchBlocks || []).some((b) => b.status === "Generating");
  const canStop = generating && (selectedGen?.supportsQueuedCancel || selectedGen?.supportsRunningCancel);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      await onRefresh();
    } finally {
      setBusy(false);
    }
  };

  const addPrompt = async () => {
    if (!master) return;
    const { flattenMasterPrompts, patchMasterPrompt } = await import("../../timelineMaster/masterTimelineMutate");
    const segments = flattenMasterPrompts(master);
    const last = segments[segments.length - 1];
    const duration = Math.max(0.5, Number(scene.duration_sec) || 5);
    const length = Math.min(2, duration);
    const lastEnd = last ? Number(last.start) + Number(last.length) : 0;
    let start = Math.max(0, lastEnd);
    if (start + length > duration) start = Math.max(0, duration - length);
    await patchMasterPrompt(projectId, scene.id, master, {
      start,
      length,
      text: "",
    });
    await onRefresh();
  };

  const removePrompt = async () => {
    if (!master) return;
    const {
      applyPromptRemovalToMaster,
      flattenMasterPrompts,
      removeMasterPrompts,
    } = await import("../../timelineMaster/masterTimelineMutate");
    const segments = flattenMasterPrompts(master);
    if (!segments.length) return;
    const selectedId = selection.kind === "promptSeg" ? selection.id : undefined;
    const target = selectedId ? segments.find((s) => s.id === selectedId) : segments[segments.length - 1];
    if (!target) return;
    if ((target.text || "").trim()) {
      const ok = window.confirm(t("removeInstruction"));
      if (!ok) return;
    }
    const ids = [target.id];
    if (target.legacyPromptSegmentId) ids.push(target.legacyPromptSegmentId);
    // Instant Update: drop from Master projection before network round-trip.
    onOptimisticMaster?.(applyPromptRemovalToMaster(master, ids));
    await removeMasterPrompts(projectId, scene.id, master, ids);
    if (selection.kind === "promptSeg" && selection.id === target.id) {
      setSelection({ kind: "scene", id: scene.id });
    }
    await onRefresh();
  };

  const addImage = async () => {
    if (!master) return;
    const { projectMasterPreviewClips: projectClips, syncMasterClips } = await import(
      "../../timelineMaster/masterTimelineMutate"
    );
    const projected = projectClips(master);
    const lane = [...projected.imageClips, ...projected.videoClips];
    const duration = Math.max(0.15, Number(scene.duration_sec || 5));
    const wanted = Math.min(2, duration);
    const sorted = [...lane].sort((a, b) => Number(a.start) - Number(b.start));
    let cursor = 0;
    let slot: { start: number; length: number } | null = null;
    for (const clip of sorted) {
      const start = Number(clip.start) || 0;
      const length = Number(clip.length) || 0;
      if (start >= cursor + wanted - 1e-9) {
        slot = { start: cursor, length: wanted };
        break;
      }
      cursor = Math.max(cursor, start + length);
    }
    if (!slot && cursor < duration - 0.15) {
      slot = { start: cursor, length: Math.min(wanted, duration - cursor) };
    }
    if (!slot || findSameTrackIntersection(lane, { id: "__image_add__", ...slot })) {
      onActionError?.("Cannot add Image — the Visual track has no free time in this scene.");
      return;
    }
    await syncMasterClips(projectId, scene.id, master, {
      attr: "visualClips",
      upserts: [
        {
          id: nid(),
          kind: "image",
          start: slot.start,
          length: slot.length,
          label: `Image ${projected.imageClips.length + 1}`,
          assetId: null,
          role: "guide",
        },
      ],
    });
    await onRefresh();
  };

  const removeImage = async () => {
    if (!master) return;
    const { projectMasterPreviewClips: projectClips, removeMasterClips } = await import(
      "../../timelineMaster/masterTimelineMutate"
    );
    const clips = projectClips(master).imageClips;
    if (!clips.length) return;
    const selectedId = selection.kind === "imageClip" ? selection.id : undefined;
    const target = selectedId ? clips.find((c) => c.id === selectedId) : clips[clips.length - 1];
    if (!target) return;
    if (target.asset_id) {
      const ok = window.confirm(
        "Remove this Image from the Timeline?\n\nSource assets remain in Project Library.",
      );
      if (!ok) return;
    }
    await removeMasterClips(projectId, scene.id, master, [target.id], "visualClips");
    if (selection.kind === "imageClip" && selection.id === target.id) {
      setSelection({ kind: "scene", id: scene.id });
    }
    await onRefresh();
  };

  const removeAudioClip = async (kind: "audio" | "sfx") => {
    await mutateTimeline((timeline) => {
      const clips = kind === "audio" ? timeline.audioClips || [] : timeline.sfxClips || [];
      if (!clips.length) return timeline;
      const selKind = kind === "audio" ? "audio" : "sfx";
      const selectedId = selection.kind === selKind ? selection.id : undefined;
      const target = selectedId ? clips.find((c) => c.id === selectedId) : clips[clips.length - 1];
      if (!target) return timeline;
      if (target.asset_id) {
        const ok = window.confirm(
          `Remove this ${kind === "audio" ? "Audio" : "SFX"} clip from the Timeline?\n\nSource assets remain in Project Library.`,
        );
        if (!ok) return timeline;
      }
      if (selection.kind === selKind && selection.id === target.id) {
        setSelection({ kind: "scene", id: scene.id });
      }
      return kind === "audio"
        ? { ...timeline, audioClips: clips.filter((c) => c.id !== target.id) }
        : { ...timeline, sfxClips: clips.filter((c) => c.id !== target.id) };
    });
  };


  const toggleMode = async () => {
    const next = master?.mode === "video_finishing" ? "image_planning" : "video_finishing";
    await run(async () => {
      await api.directorTimelineSetMode(projectId, scene.id, next);
    });
  };

  const setMode = async (next: "image_planning" | "video_finishing") => {
    if (master?.mode === next) return;
    await run(async () => {
      await api.directorTimelineSetMode(projectId, scene.id, next);
    });
  };

  // Preflight is always-on via useTimelinePreflight in the editor shell — this
  // button is a manual "Re-check now" through the same shared hook state.
  const preflight = () => {
    onPreflightRecheck();
  };

  const sceneCanGenerate = anyTimelineGeneratorExecutable(
    generatorOptions,
    selectedBatch?.generatorId,
    ...(master?.batchBlocks || []).map((batch) => batch.generatorId),
    master?.sceneGeneratorId,
    scene.engine,
  );

  const addBatch = async () => {
    if (!TIMELINE_BATCHES_CREATOR_UI) return;
    await run(async () => {
      await addTimelineBatch(projectId, scene.id, master);
    });
  };

  const removeBatch = async () => {
    if (!TIMELINE_BATCHES_CREATOR_UI) return;
    const batches = master?.batchBlocks || [];
    if (!batches.length) return;
    const selectedId = selection.kind === "batch" ? selection.id : undefined;
    const target = selectedId ? batches.find((b) => b.id === selectedId) : batches[batches.length - 1];
    if (!target) return;
    if (batchHasContent(target)) {
      const ok = window.confirm(
        `Remove "${target.label}"?\n\nThis Batch has content or job history. Source assets remain in Project Library.`,
      );
      if (!ok) return;
    }
    await run(async () => {
      await api.directorTimelineDeleteBatch(projectId, scene.id, target.id);
      if (selection.kind === "batch" && selection.id === target.id) {
        setSelection({ kind: "scene", id: scene.id });
      }
    });
  };


  const generateScene = async (_scope: "full" | "selected" = "full") => {
    if (!sceneCanGenerate) {
      onActionError?.(
        `Generate is not ready — ${selectedGen?.readiness || "no ready video engine is selected"}`,
      );
      return;
    }
    await run(async () => {
      try {
        const durationSeconds = Number(scene.duration_sec || 0) || undefined;
        const result = await rematerializeThenGenerateScene({
          projectId,
          sceneId: scene.id,
          generatorId: selectedGen?.id || master?.sceneGeneratorId || scene.engine,
          durationSeconds,
          draftMode: draftAvailable || undefined,
          beforeGenerate: async () => {
            await onRefresh();
            onGenerationStandby?.(true);
          },
        });
        const err = timelineActionError(result);
        if (err) {
          onGenerationStandby?.(false);
          onActionError?.(err);
          return;
        }
        if (timelineGenerateEmpty(result)) {
          onGenerationStandby?.(false);
          onActionError?.("Nothing was queued to generate. Finished batches stay as they are.");
        }
      } catch (error) {
        onGenerationStandby?.(false);
        throw error;
      }
    });
  };

  useEffect(() => {
    const unsubscribers = [
      registerTimelineCommand("generateScene", () => void generateScene("full")),
      registerTimelineCommand("preflight", () => void preflight()),
      registerTimelineCommand("retake", () => onOpenRetake?.()),
      registerTimelineCommand("imagePlanning", () => void setMode("image_planning")),
      registerTimelineCommand("videoFinishing", () => void setMode("video_finishing")),
      registerTimelineCommand("zoomIn", () => setZoom(stepTimelineZoom(zoom, 1))),
      registerTimelineCommand("zoomOut", () => setZoom(stepTimelineZoom(zoom, -1))),
      registerTimelineCommand("toggleSnap", () => setSnap(!snap)),
      registerTimelineCommand("addPrompt", () => void addPrompt()),
    ];
    return () => {
      unsubscribers.forEach((off) => off());
    };
  }, [addPrompt, generateScene, onOpenRetake, preflight, setMode, setSnap, setZoom, snap, zoom]);

  const modeLabel = master?.mode === "video_finishing" ? "Video Finishing" : "Image Planning";
  const modeTitle =
    master?.mode === "video_finishing"
      ? "Switch Timeline mode to Image Planning"
      : "Switch Timeline mode to Video Finishing";
  const addButtons = (
    <>
      <PlusMinusGroup
        label="Image"
        testId="timeline-toolbar-image"
        onAdd={() => void addImage()}
        onRemove={() => void removeImage()}
        addTitle="Add an Image clip to the Visual track"
        removeTitle="Remove the selected or last Image clip"
        disabled={busy || !master}
      />
      <PlusMinusGroup
        label="Prompt"
        testId="timeline-toolbar-prompt"
        onAdd={() => void addPrompt()}
        onRemove={() => void removePrompt()}
        addTitle={t("addTimedPromptTitle")}
        removeTitle={t("removeTimedPromptTitle")}
        disabled={busy || !master}
      />
      <PlusMinusGroup
        label="Audio"
        testId="timeline-toolbar-audio"
        onAdd={() => onOpenAudioClip?.({ kind: "audio", clipId: null, start: playheadSec })}
        onRemove={() => void removeAudioClip("audio")}
        addTitle="Add an Audio clip"
        removeTitle="Remove the selected or last Audio clip"
        disabled={busy}
      />
      <PlusMinusGroup
        label="SFX"
        testId="timeline-toolbar-sfx"
        onAdd={() => onOpenAudioClip?.({ kind: "sfx", clipId: null, start: playheadSec })}
        onRemove={() => void removeAudioClip("sfx")}
        addTitle="Add an SFX clip"
        removeTitle="Remove the selected or last SFX clip"
        disabled={busy}
      />
    </>
  );

  const generateButtons = (
    <>
      <ActionWithHelp
        help={{
          label: getTimelineHelp("preflight").title,
          content: getTimelineHelp("preflight").body,
          text: getTimelineHelp("preflight").title,
        }}
      >
        <button
          type="button"
          title="Preflight runs automatically as you edit — Re-check now refreshes it"
          aria-label="Preflight runs automatically as you edit — Re-check now refreshes it"
          data-testid="timeline-toolbar-preflight"
          onClick={() => void preflight()}
        >
          Re-check now
        </button>
      </ActionWithHelp>
      <button
        type="button"
        className="primary"
        title={
          !sceneCanGenerate
            ? `Generate is not ready — ${selectedGen?.readiness || "no ready video engine is selected"}`
            : draftAvailable
              ? "Generate a low-cost preview first"
              : "Generate the full Scene"
        }
        aria-label={draftAvailable ? "Generate Draft for the full Scene" : "Generate the full Scene"}
        data-testid="timeline-generate-scene"
        disabled={busy}
        onClick={() => void generateScene("full")}
      >
        {draftAvailable ? "Generate Draft" : "Generate"}
      </button>
      {selection.kind === "batch" && selection.id ? (
        <button
          type="button"
          title="Generate only the selected Batch Block"
          aria-label="Generate only the selected Batch Block"
          data-testid="timeline-gen-batch"
          disabled={!sceneCanGenerate}
          onClick={() => void generateScene("selected")}
        >
          {draftAvailable ? "Draft Batch" : "Gen Batch"}
        </button>
      ) : null}
      {generating && canStop ? (
        <button
          type="button"
          data-testid="timeline-toolbar-stop"
          title="Stop the current local generation"
          aria-label="Stop the current local generation"
          onClick={() =>
            void run(async () => {
              await api.directorTimelineCancel(projectId, scene.id, { action: "cancel_active_local_job" });
            })
          }
        >
          Stop
        </button>
      ) : null}
      {generating && !canStop ? (
        <span className="scene-meta" data-testid="timeline-toolbar-cancel-unavailable">
          Provider is rendering — cancellation unavailable
        </span>
      ) : null}
      <button
        type="button"
        className="ghost"
        title={modeTitle}
        aria-label={modeTitle}
        data-testid="timeline-toolbar-mode"
        onClick={() => void toggleMode()}
      >
        {modeLabel}
      </button>
    </>
  );

  const toolButtons = (
    <>
      <button
        type="button"
        disabled={!canUndo}
        title="Undo the last Timeline edit"
        aria-label="Undo the last Timeline edit"
        onClick={() => void onUndo()}
      >
        Undo
      </button>
      <button
        type="button"
        disabled={!canRedo}
        title="Redo the last undone Timeline edit"
        aria-label="Redo the last undone Timeline edit"
        onClick={() => void onRedo()}
      >
        Redo
      </button>
      <button
        type="button"
        title={`Zoom out (current ${zoom.toFixed(2)}×)`}
        aria-label={`Zoom out timeline (current ${zoom.toFixed(2)} times)`}
        data-testid="timeline-toolbar-zoom-out"
        onClick={() => setZoom(stepTimelineZoom(zoom, -1))}
      >
        −Z
      </button>
      <button
        type="button"
        title={`Zoom in (current ${zoom.toFixed(2)}×)`}
        aria-label={`Zoom in timeline (current ${zoom.toFixed(2)} times)`}
        data-testid="timeline-toolbar-zoom-in"
        onClick={() => setZoom(stepTimelineZoom(zoom, 1))}
      >
        +Z
      </button>
      <span className="scene-meta" data-testid="timeline-toolbar-zoom-value" aria-live="polite">
        {zoom.toFixed(2)}×
      </span>
      <label className="timeline-toolbar-zoom-slider" title="Timeline zoom">
        <span className="sr-only">Timeline zoom</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.001}
          value={zoomToSlider(zoom)}
          data-testid="timeline-toolbar-zoom-slider"
          aria-label="Timeline zoom"
          onChange={(e) => setZoom(sliderToZoom(Number(e.target.value)))}
        />
      </label>
      <button
        type="button"
        className={snap ? "primary" : ""}
        data-testid="timeline-toolbar-snap"
        title={snap ? "Disable clip snapping" : "Enable clip snapping"}
        aria-label={snap ? "Disable clip snapping" : "Enable clip snapping"}
        onClick={() => setSnap(!snap)}
      >
        Snap
      </button>
    </>
  );

  const playLabel = playing ? t("pauseTimeline") : t("playTimeline");

  return (
    <div className="timeline-toolbar-shell" data-testid="timeline-toolbar" aria-busy={busy}>
      <div className="timeline-toolbar__row timeline-toolbar__row--transport" role="toolbar" aria-label="Timeline add, transport, and edit controls">
        <div className="timeline-toolbar__group timeline-toolbar__group--left">{addButtons}</div>
        <div className="timeline-toolbar__group timeline-toolbar__group--center">
          <div
            className="timeline-toolbar__transport"
            data-testid="timeline-transport"
            role="group"
            aria-label="Timeline transport"
            data-scene-id={transportSceneId || ""}
            data-scene-start={String(transportBounds.sceneStart)}
            data-scene-end={String(transportBounds.sceneEnd)}
            data-batch-in={String(transportBounds.activeBatchStart)}
            data-batch-out={String(transportBounds.activeBatchEnd)}
            data-playhead={String(playheadSec)}
          >
            <button
              type="button"
              data-testid="timeline-transport-scene-start"
              title={t("goToSceneStartTitle")}
              aria-label={t("goToSceneStart")}
              onClick={onGoToSceneStart}
            >
              <span className="timeline-toolbar__transport-glyph">{"|<<"}</span>
            </button>
            <button
              type="button"
              data-testid="timeline-transport-in"
              title={t("goToBatchInTitle")}
              aria-label={t("goToBatchIn")}
              onClick={onGoToBatchIn}
            >
              <span className="timeline-toolbar__transport-glyph">{"|<"}</span>
            </button>
            <button
              type="button"
              className={playing ? "primary" : ""}
              data-testid="timeline-transport-play"
              title={t("playPauseTitle")}
              aria-label={playLabel}
              aria-pressed={playing}
              onClick={onTogglePlay}
            >
              <span className="timeline-toolbar__transport-glyph">{playing ? "⏸" : "▶"}</span>
            </button>
            <button
              type="button"
              data-testid="timeline-transport-out"
              title={t("goToBatchOutTitle")}
              aria-label={t("goToBatchOut")}
              onClick={onGoToBatchOut}
            >
              <span className="timeline-toolbar__transport-glyph">{">|"}</span>
            </button>
            <button
              type="button"
              data-testid="timeline-transport-scene-end"
              title={t("goToSceneEndTitle")}
              aria-label={t("goToSceneEnd")}
              onClick={onGoToSceneEnd}
            >
              <span className="timeline-toolbar__transport-glyph">{">>|"}</span>
            </button>
          </div>
        </div>
        <div className="timeline-toolbar__group timeline-toolbar__group--right">
          {toolButtons}
          <button
            type="button"
            className="ghost"
            title="Open Timeline Settings"
            aria-label="Open Timeline Settings"
            onClick={() => setSettingsOpen((value) => !value)}
          >
            ⚙
          </button>
        </div>
      </div>
      <div className="timeline-toolbar__row" role="toolbar" aria-label="Timeline generate controls">
        <div className="timeline-toolbar__group">{generateButtons}</div>
      </div>
      <TimelineSettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onGuidancePriorityChange={onGuidancePriorityChange}
      />
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Scene } from "../../types";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { getTimelineHelp } from "../../timelineMaster/helpCatalog";
import { generatorOptionsFromPayload } from "../../timelineMaster/draftCapabilities";
import { useDirectorSelection } from "../DirectorSelectionContext";
import { HelpTip } from "../HelpTip";
import {
  createLipSyncTrack,
  lipSyncTrackHasContent,
  normalizeLipSyncTracks,
  type DirectorTimeline,
  type PromptSegment,
  type TimelineClip,
} from "../DirectorTracks";
import { TimelineSettingsDrawer } from "./TimelineSettingsDrawer";

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

function resolveSelectedLipSyncTrackId(
  selection: ReturnType<typeof useDirectorSelection>["selection"],
  trackIds: string[],
) {
  if (selection.kind === "lipsyncTrack") return selection.id;
  if (selection.kind === "lipsyncClip") return selection.trackId;
  if (selection.kind === "lipsync") {
    const idx = selection.trackIndex ?? Number(selection.id || 0);
    return trackIds[idx];
  }
  return undefined;
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
  onPreflight,
  mutateTimeline,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onGuidancePriorityChange,
  onOpenInpaint,
  onOpenRetake,
}: {
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  onRefresh: () => void | Promise<void>;
  onPreflight: (result: { ok: boolean; findings: Array<{ severity: string; message: string; code?: string }> }) => void;
  mutateTimeline: (mutator: (timeline: DirectorTimeline) => DirectorTimeline) => Promise<void>;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void | Promise<void>;
  onRedo: () => void | Promise<void>;
  onGuidancePriorityChange: (value: DirectorTimeline["guidance_priority"]) => void;
  onOpenInpaint: () => void;
  onOpenRetake?: () => void;
}) {
  const { selection, snap, setSnap, zoom, setZoom, setSelection } = useDirectorSelection();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generatorOptions, setGeneratorOptions] = useState(() => [] as ReturnType<typeof generatorOptionsFromPayload>);

  useEffect(() => {
    let alive = true;
    void api.directorTimelineGenerators().then((payload) => {
      if (!alive) return;
      setGeneratorOptions(generatorOptionsFromPayload(payload));
    }).catch(() => {
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
  const selectedGen = generatorOptions.find((g) => g.id === selectedBatch?.generatorId)
    || generatorOptions.find((g) => g.id === master?.batchBlocks[0]?.generatorId);
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
    await mutateTimeline((timeline) => {
      const segments = timeline.prompt_segments || [];
      const last = segments[segments.length - 1];
      const start = last ? Math.min(scene.duration_sec - 0.5, last.start + last.length) : 0;
      const segment: PromptSegment = {
        id: nid(),
        start: Math.max(0, start),
        length: Math.min(2, scene.duration_sec || 5),
        text: "",
        weight: 1,
        region: null,
      };
      return { ...timeline, prompt_segments: [...segments, segment] };
    });
  };

  const removePrompt = async () => {
    await mutateTimeline((timeline) => {
      const segments = timeline.prompt_segments || [];
      if (!segments.length) return timeline;
      const selectedId = selection.kind === "promptSeg" ? selection.id : undefined;
      const target = selectedId ? segments.find((s) => s.id === selectedId) : segments[segments.length - 1];
      if (!target) return timeline;
      if ((target.text || "").trim()) {
        const ok = window.confirm("Remove this Timed Instruction? Its text will be deleted from the Timeline.");
        if (!ok) return timeline;
      }
      const next = segments.filter((s) => s.id !== target.id);
      if (selection.kind === "promptSeg" && selection.id === target.id) {
        setSelection({ kind: "scene", id: scene.id });
      }
      return { ...timeline, prompt_segments: next };
    });
  };

  const addImage = async () => {
    await mutateTimeline((timeline) => {
      const clips = timeline.image_clips || [];
      const start = clips.reduce((max, clip) => Math.max(max, clip.start + clip.length), 0);
      const next: TimelineClip = {
        id: nid(),
        start: Math.min(start, Math.max(0, (timeline.duration_sec || scene.duration_sec || 5) - 1)),
        length: Math.min(2, timeline.duration_sec || scene.duration_sec || 5),
        label: `Image ${clips.length + 1}`,
        role: "guide",
        asset_id: null,
      };
      return {
        ...timeline,
        media_mode: "image",
        image_clips: [...clips, next],
      };
    });
  };

  const removeImage = async () => {
    await mutateTimeline((timeline) => {
      const clips = timeline.image_clips || [];
      if (!clips.length) return timeline;
      const selectedId = selection.kind === "imageClip" ? selection.id : undefined;
      const target = selectedId ? clips.find((c) => c.id === selectedId) : clips[clips.length - 1];
      if (!target) return timeline;
      if (target.asset_id) {
        const ok = window.confirm(
          "Remove this Image from the Timeline?\n\nSource assets remain in Project Library.",
        );
        if (!ok) return timeline;
      }
      if (selection.kind === "imageClip" && selection.id === target.id) {
        setSelection({ kind: "scene", id: scene.id });
      }
      return { ...timeline, image_clips: clips.filter((c) => c.id !== target.id) };
    });
  };

  const addBatch = async () => {
    await run(async () => {
      await api.directorTimelineAddBatch(projectId, scene.id, { plannedDuration: scene.duration_sec });
    });
  };

  const removeBatch = async () => {
    const batches = master?.batchBlocks || [];
    if (!batches.length) return;
    const selectedId = selection.kind === "batch" ? selection.id : undefined;
    const target = selectedId ? batches.find((b) => b.id === selectedId) : batches[batches.length - 1];
    if (!target) return;
    if (batchHasContent(target)) {
      const ok = window.confirm(
        `Remove “${target.label}”?\n\nThis Batch has content or job history. Source assets remain in Project Library.`,
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

  const addAudioClip = async (kind: "audio" | "sfx") => {
    await mutateTimeline((timeline) => {
      const base: TimelineClip = {
        id: nid(),
        start: 0,
        length: Math.min(2, timeline.duration_sec || scene.duration_sec || 5),
        label: kind === "audio" ? "Audio" : "SFX",
        asset_id: null,
        volume: 1,
      };
      return kind === "audio"
        ? { ...timeline, audio_clips: [...(timeline.audio_clips || []), base] }
        : { ...timeline, sfx_clips: [...(timeline.sfx_clips || []), base] };
    });
  };

  const removeAudioClip = async (kind: "audio" | "sfx") => {
    await mutateTimeline((timeline) => {
      const clips = kind === "audio" ? timeline.audio_clips || [] : timeline.sfx_clips || [];
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
        ? { ...timeline, audio_clips: clips.filter((c) => c.id !== target.id) }
        : { ...timeline, sfx_clips: clips.filter((c) => c.id !== target.id) };
    });
  };

  const addLipSyncTrack = async () => {
    await mutateTimeline((timeline) => {
      const tracks = normalizeLipSyncTracks(timeline.lipsync?.tracks);
      const nextTrack = createLipSyncTrack(tracks.length + 1);
      setSelection({
        kind: "lipsyncTrack",
        id: nextTrack.id,
        trackId: nextTrack.id,
        trackIndex: tracks.length,
      });
      return {
        ...timeline,
        lipsync: {
          ...timeline.lipsync,
          tracks: [...tracks, nextTrack],
        },
      };
    });
  };

  const removeLipSyncTrack = async () => {
    await mutateTimeline((timeline) => {
      const tracks = normalizeLipSyncTracks(timeline.lipsync?.tracks);
      if (tracks.length <= 1) return timeline;
      const selectedTrackId = resolveSelectedLipSyncTrackId(
        selection,
        tracks.map((track) => track.id),
      );
      const targetIndex = tracks.findIndex((track, index) => index > 0 && track.id === selectedTrackId);
      if (targetIndex < 1) return timeline;
      const target = tracks[targetIndex];
      if (lipSyncTrackHasContent(target)) {
        const ok = window.confirm(
          `Remove “${target.label || `Lip Sync ${targetIndex + 1}`}”?\n\nIts clips and track settings will be removed from the Timeline.`,
        );
        if (!ok) return timeline;
      }
      if (
        (selection.kind === "lipsyncTrack" && selection.id === target.id) ||
        (selection.kind === "lipsyncClip" && selection.trackId === target.id)
      ) {
        setSelection({ kind: "scene", id: scene.id });
      }
      return {
        ...timeline,
        lipsync: {
          ...timeline.lipsync,
          tracks: tracks.filter((track) => track.id !== target.id),
        },
      };
    });
  };

  const toggleMode = async () => {
    const next = master?.mode === "video_finishing" ? "image_planning" : "video_finishing";
    await run(async () => {
      await api.directorTimelineSetMode(projectId, scene.id, next);
    });
  };

  const preflight = async () => {
    setBusy(true);
    try {
      const result = await api.directorTimelinePreflight(projectId, scene.id);
      onPreflight(result);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  };

  const generateScene = async (scope: "full" | "selected") => {
    await run(async () => {
      if (scope === "selected" && selection.kind === "batch" && selection.id) {
        await api.directorTimelineGenerateBatch(projectId, scene.id, selection.id);
        return;
      }
      await api.directorTimelineGenerateScene(projectId, scene.id, { scope: "full" });
    });
  };

  const modeLabel = master?.mode === "video_finishing" ? "Video Finishing" : "Image Planning";
  const modeTitle =
    master?.mode === "video_finishing"
      ? "Switch Timeline mode to Image Planning"
      : "Switch Timeline mode to Video Finishing";
  const inpaintEnabled = selection.kind === "videoClip" || selection.kind === "repair";
  const inpaintTitle =
    selection.kind === "videoClip" || selection.kind === "repair"
      ? "Open the Inpaint workspace for this selected range"
      : "Select the Video clip or a Repair range to open Inpaint";

  const addButtons = (
    <>
      <PlusMinusGroup
        label="Batch"
        helpId="add_batch"
        testId="timeline-toolbar-batch"
        onAdd={() => void addBatch()}
        onRemove={() => void removeBatch()}
        addTitle="Add a Batch Block to this Scene"
        removeTitle="Remove the selected or last Batch Block"
        disabled={busy}
      />
      <PlusMinusGroup
        label="Image"
        testId="timeline-toolbar-image"
        onAdd={() => void addImage()}
        onRemove={() => void removeImage()}
        addTitle="Add an Image clip to the Visual track"
        removeTitle="Remove the selected or last Image clip"
        disabled={busy}
      />
      <PlusMinusGroup
        label="Prompt"
        testId="timeline-toolbar-prompt"
        onAdd={() => void addPrompt()}
        onRemove={() => void removePrompt()}
        addTitle="Add a Timed Instruction to the Prompt track"
        removeTitle="Remove the selected or last Timed Instruction"
        disabled={busy}
      />
      <PlusMinusGroup
        label="Audio"
        testId="timeline-toolbar-audio"
        onAdd={() => void addAudioClip("audio")}
        onRemove={() => void removeAudioClip("audio")}
        addTitle="Add an Audio clip"
        removeTitle="Remove the selected or last Audio clip"
        disabled={busy}
      />
      <PlusMinusGroup
        label="SFX"
        testId="timeline-toolbar-sfx"
        onAdd={() => void addAudioClip("sfx")}
        onRemove={() => void removeAudioClip("sfx")}
        addTitle="Add an SFX clip"
        removeTitle="Remove the selected or last SFX clip"
        disabled={busy}
      />
      <PlusMinusGroup
        label="Lip Sync"
        testId="timeline-toolbar-lipsync"
        onAdd={() => void addLipSyncTrack()}
        onRemove={() => void removeLipSyncTrack()}
        addTitle="Add a Lip Sync track"
        removeTitle="Remove the selected additional Lip Sync track"
        disabled={busy}
      />
    </>
  );

  const generateButtons = (
    <>
      <button
        type="button"
        title="Run Co-Director Preflight inspection for this Scene"
        aria-label="Run Co-Director Preflight inspection for this Scene"
        onClick={() => void preflight()}
      >
        Preflight <Help id="preflight" />
      </button>
      <button
        type="button"
        className="primary"
        title={draftAvailable ? "Generate a low-cost preview first" : "Generate the full Scene"}
        aria-label={draftAvailable ? "Generate Draft for the full Scene" : "Generate the full Scene"}
        data-testid="timeline-generate-scene"
        onClick={() => void generateScene("full")}
      >
        {draftAvailable ? "Generate Draft" : "Generate"}
      </button>
      {onOpenRetake ? (
        <button
          type="button"
          className="primary"
          title="Open Re-take for the selected Timeline shot (MiniMax H3)"
          aria-label="Open Re-take"
          data-testid="timeline-open-retake"
          onClick={onOpenRetake}
        >
          Re-take
        </button>
      ) : null}
      {selection.kind === "batch" && selection.id ? (
        <button
          type="button"
          title="Generate only the selected Batch Block"
          aria-label="Generate only the selected Batch Block"
          data-testid="timeline-gen-batch"
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
      {master?.mode === "video_finishing" ? (
        <button
          type="button"
          className={inpaintEnabled ? "primary" : ""}
          disabled={!inpaintEnabled}
          title={inpaintTitle}
          aria-label={inpaintTitle}
          data-testid="timeline-toolbar-inpaint"
          onClick={onOpenInpaint}
        >
          Inpaint
        </button>
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
        onClick={() => setZoom(Math.max(0.5, +(zoom - 0.25).toFixed(2)))}
      >
        −Z
      </button>
      <button
        type="button"
        title={`Zoom in (current ${zoom.toFixed(2)}×)`}
        aria-label={`Zoom in timeline (current ${zoom.toFixed(2)} times)`}
        data-testid="timeline-toolbar-zoom-in"
        onClick={() => setZoom(Math.min(3, +(zoom + 0.25).toFixed(2)))}
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
          min={0.5}
          max={3}
          step={0.05}
          value={zoom}
          data-testid="timeline-toolbar-zoom-slider"
          aria-label="Timeline zoom"
          onChange={(e) => setZoom(Number(e.target.value) || 1)}
        />
      </label>
      <button
        type="button"
        className={snap ? "primary" : ""}
        title={snap ? "Disable clip snapping" : "Enable clip snapping"}
        aria-label={snap ? "Disable clip snapping" : "Enable clip snapping"}
        onClick={() => setSnap(!snap)}
      >
        Snap
      </button>
    </>
  );

  return (
    <div className="timeline-toolbar-shell" data-testid="timeline-toolbar" aria-busy={busy}>
      <div className="timeline-toolbar__row" role="toolbar" aria-label="Timeline add controls">
        <div className="timeline-toolbar__group">{addButtons}</div>
      </div>
      <div className="timeline-toolbar__row" role="toolbar" aria-label="Timeline generate and edit controls">
        <div className="timeline-toolbar__group">{generateButtons}</div>
        <div className="timeline-toolbar__group">
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
      <TimelineSettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onGuidancePriorityChange={onGuidancePriorityChange}
      />
    </div>
  );
}

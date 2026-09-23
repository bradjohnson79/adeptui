import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Asset, Job, Project, Scene } from "../../types";
import { api } from "../../api";
import { apiUrl } from "../../runtime/apiBase";
import type { TimelineBoardView } from "../DirectorTracks";
import type { DirectorSelection } from "../../directorSelection";
import { LivePreviewMonitor } from "../LivePreviewMonitor";
import {
  comfyProgressPercentFromJob,
  comfyProgressPercentFromText,
  previewGenerationNotice,
  sceneGenerationCompleteNotice,
} from "../../timelineMaster/sceneRenderProgress";
import { batchWindowAtTime, buildBatchTimeWindows } from "../../timelineMaster/batchWindows";
import { hasGeneratedTakeForRetake } from "../../timelineMaster/retakeEligibility";
import { shouldMutePreviewVideoSoundtrack } from "./shouldMutePreviewVideoSoundtrack";
import type { VideoRetakeSession } from "../../timelineMaster/videoRetake";
import { TimelineDiagnostics } from "./TimelineDiagnostics";
import { resolveTimelineAtTime } from "./resolveTimelineAtTime";
import { resolveSceneTake } from "../../timelineMaster/playableVisualTakes";
import { sceneTakeDisplayLabel } from "../../timelineMaster/sceneTakes";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { shouldPreviewSceneStitch } from "../../timelineMaster/sceneStitch";
import { resolvePublishChrome } from "../../timelineMaster/scenePublish";
import { preferredPublishSource } from "../../timelineMaster/magiUpscaleTargets";
import { pollMagiUpscaleJob } from "../../timelineMaster/pollMagiUpscaleJob";
import { MagiUpscaleChooser, choiceFromChooser } from "./MagiUpscaleChooser";
import { useProjectJobs } from "../../runtime/projectJobsStore";
import { shouldSuspendDependentPolling } from "../../runtime/studioApiConnection";
import { activeTakeLineage, selectActiveSceneJob } from "../../timelineMaster/activeSceneJob";


/**
 * PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH
 *
 * Nothing else decides what appears in the Timeline Preview Monitor — not the
 * Image component, Prompt component, Generation component, or Library
 * component. The flow is strictly:
 *
 *   Timeline State -> TimelinePreviewComposer -> Preview Monitor
 *
 * The composer resolves a single `PreviewComposition` from all inputs
 * (selection, playhead, active clips, generation state, library asset, scene
 * output) and hands it to the presentational `LivePreviewMonitor`, which only
 * renders what the composer resolved. This eliminates the class of
 * synchronization bugs where multiple components independently mutate preview
 * content.
 *
 * EDITING_AND_GENERATION_STATES_ARE_SEPARATE: the composer owns the
 * generation state machine (Ready -> Queued -> Preparing -> Generating ->
 * Preview Available -> Completed -> Failed -> Cancelled) via polling/SSE, and
 * the editing state (what clip is selected / playhead) is observed but never
 * mutated here.
 */

export type PreviewComposition =
  | { kind: "idle" }
  | { kind: "preparing"; job: Job }
  | { kind: "generation_draft"; job: Job; previewSrc: string; sourceStill: string }
  | { kind: "final_output"; src: string; mediaKind: "video" | "image"; job?: Job }
  | { kind: "failed"; job: Job; previewSrc: string | null }
  | { kind: "cancelled"; job: Job; previewSrc: string | null }
  | { kind: "library"; asset: Asset; src: string; mediaKind: "video" | "image" | "audio" }
  | {
      kind: "timeline_frame";
      visualSrc: string;
      mediaKind: "video" | "image";
      promptText: string | null;
      promptLabel: string | null;
      batchId: string | null;
      batchLocalTime: number;
      visualLocalTime: number;
      videoAssetId?: string | null;
      sourceClipId?: string | null;
    };

type PreviewPayload = {
  jobId?: string;
  sceneId?: string;
  sequenceNumber?: number;
  stage?: string;
  progress?: number;
  mediaType?: string;
  sourceUrl?: string;
  localPath?: string;
};

function libraryMediaKind(asset: Asset): "video" | "image" | "audio" {
  const k = (asset.kind || "").toLowerCase();
  if (k === "audio" || /\.(wav|mp3|ogg|m4a|aac|flac)(\?|$)/i.test(asset.filename || "")) return "audio";
  if (k === "video" || /\.(mp4|webm|mov)(\?|$)/i.test(asset.filename || "")) return "video";
  return "image";
}

function isVideoSrc(src: string): boolean {
  return /\.(mp4|webm|mov)(\?|$)/i.test(src);
}

/**
 * useGenerationState — owns the generation state machine for the active scene.
 * Returns jobs, the active job, and the latest streamed preview payload.
 * Pausing updates freezes preview frame ingestion without dropping the job.
 */
export function useGenerationState(
  projectId: string,
  scene: Scene | undefined,
  pauseUpdates: boolean,
  master?: SceneTimelineMaster | null,
): {
  jobs: Job[];
  activeJob: Job | null;
  preview: PreviewPayload | null;
  seq: number;
} {
  const { jobs } = useProjectJobs(projectId);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [seq, setSeq] = useState(0);
  const seqRef = useRef(0);
  seqRef.current = seq;

  // Scene-switch reset: the component is NOT remounted across scene changes,
  // so without this the prior scene's high-water seq would reject the new
  // scene's early preview frames and its stale payload could render against
  // the new scene's running job.
  const sceneId = scene?.id;
  useEffect(() => {
    setPreview(null);
    setSeq(0);
    seqRef.current = 0;
  }, [sceneId]);

  const sceneJobs = jobs.filter((j) => j.scene_id === scene?.id);
  const activeJob = selectActiveSceneJob(sceneJobs, activeTakeLineage(master));
  const activePreviewJobId =
    activeJob && (activeJob.status === "queued" || activeJob.status === "running")
      ? activeJob.id
      : undefined;

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      // VISIBILITY_GATED_POLLING: skip network work while the tab is hidden;
      // the interval keeps ticking cheaply and the next visible tick resyncs.
      if (document.visibilityState === "hidden") return;
      if (shouldSuspendDependentPolling()) return;
      if (!activePreviewJobId || pauseUpdates) return;
      try {
        const p = await api.getJobPreview(activePreviewJobId);
        if (!alive) return;
        if (p.preview && (p.preview.sequenceNumber || 0) >= seqRef.current) {
          setSeq(p.preview.sequenceNumber || seqRef.current);
          setPreview(p.preview);
        }
      } catch {
        /* ignore */
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 2500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [activePreviewJobId, pauseUpdates]);

  useEffect(() => {
    try {
      const es = new EventSource(apiUrl(`/api/projects/${projectId}/preview/stream`));
      es.onmessage = (ev) => {
        if (pauseUpdates) return;
        try {
          const data = JSON.parse(ev.data);
          if (data.event === "preview_updated" || data.event === "preview_available") {
            const p = data.preview as PreviewPayload;
            if (p?.sceneId && scene?.id && p.sceneId !== scene.id) return;
            if ((p?.sequenceNumber || 0) < seqRef.current) return;
            setSeq(p.sequenceNumber || seqRef.current);
            setPreview(p);
          }
        } catch {
          /* ignore */
        }
      };
      return () => {
        es.close();
      };
    } catch {
      return;
    }
  }, [projectId, scene?.id, pauseUpdates, scene?.name]);

  return { jobs, activeJob, preview, seq };
}

/**
 * Resolve the single authoritative PreviewComposition from all inputs.
 * Pure function — no side effects — so it is trivial to test and reason about.
 */
export function resolvePreviewComposition(args: {
  scene: Scene | undefined;
  timeline: TimelineBoardView | null;
  master: SceneTimelineMaster | null;
  selection: DirectorSelection;
  playheadSec: number;
  libraryAsset: Asset | null;
  activeJob: Job | null;
  preview: PreviewPayload | null;
  timelinePlaying?: boolean;
  previewTakeId?: string | null;
}): PreviewComposition {
  const { scene, libraryAsset, activeJob, preview } = args;
  const previewTake = resolveSceneTake(args.master, args.previewTakeId);
  const previewingOther = Boolean(args.previewTakeId && args.previewTakeId !== args.master?.currentSceneTakeId);

  if (previewingOther && previewTake?.resultAssetId) {
    return {
      kind: "timeline_frame",
      visualSrc: api.assetUrl(previewTake.resultAssetId),
      mediaKind: "video",
      promptText: null,
      promptLabel: sceneTakeDisplayLabel(previewTake.label),
      batchId: null,
      batchLocalTime: args.playheadSec,
      visualLocalTime: args.playheadSec,
    };
  }

  if (args.selection.kind === "imageReferenceClip") {
    const clip = (args.timeline?.image_reference_clips || []).find((item) => item.id === args.selection.id);
    if (clip?.asset_id) {
      return {
        kind: "timeline_frame",
        visualSrc: api.assetUrl(clip.asset_id),
        mediaKind: "image",
        promptText: "Image Reference — appearance guidance",
        promptLabel: clip.label || "Image Reference",
        batchId: null,
        batchLocalTime: 0,
        visualLocalTime: Math.max(0, args.playheadSec - (clip.start || 0)),
      };
    }
  }

  if (args.selection.kind === "videoReferenceClip") {
    const clip = (args.timeline?.video_reference_clips || []).find((item) => item.id === args.selection.id);
    if (clip?.asset_id) {
      return {
        kind: "timeline_frame",
        visualSrc: api.assetUrl(clip.asset_id),
        mediaKind: "video",
        promptText: "Video Reference — motion and performance guidance",
        promptLabel: clip.label || "Video Reference",
        batchId: null,
        batchLocalTime: 0,
        visualLocalTime: Math.max(0, args.playheadSec - (clip.start || 0)) + (clip.trim_start || 0),
      };
    }
  }

  // Play uses the stitched scene clip as one file, even if a Library preview
  // or batch inspect is sitting underneath. Paused inspect stays below.
  if (
    args.timelinePlaying &&
    shouldPreviewSceneStitch({
      master: args.master,
      selection: { kind: null },
      playheadSec: args.playheadSec,
      timelinePlaying: true,
    }) &&
    args.master?.sceneStitch?.assetId
  ) {
    return {
      kind: "timeline_frame",
      visualSrc: api.assetUrl(args.master.sceneStitch.assetId),
      mediaKind: "video",
      promptText: null,
      promptLabel: "Full scene",
      batchId: null,
      batchLocalTime: args.playheadSec,
      visualLocalTime: args.playheadSec,
    };
  }

  // 1. Library asset takes precedence (creator explicitly previewing a file).
  if (libraryAsset) {
    const src = api.assetUrl(libraryAsset.id);
    return {
      kind: "library",
      asset: libraryAsset,
      src,
      mediaKind: libraryMediaKind(libraryAsset),
    };
  }

  // 2. Failed / cancelled generation — keep the latest draft frame visible
  // when one was streamed (the overlay copy promises preservation).
  // A creator-dismissed failure (acknowledged via Dismiss, persisted on the
  // master) no longer pins the monitor — fall through to the normal views.
  // A NEW failure (different job id) re-enters this branch.
  const failureDismissed =
    activeJob?.status === "failed" &&
    (args.master?.dismissedFailureJobIds ?? []).includes(activeJob.id);
  if (activeJob && (activeJob.status === "failed" || activeJob.status === "cancelled") && !failureDismissed) {
    const draftSrc =
      preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");
    return {
      kind: activeJob.status === "failed" ? "failed" : "cancelled",
      job: activeJob,
      previewSrc: draftSrc || null,
    };
  }

  // 3. Active generation with preview frames available.
  if (activeJob && (activeJob.status === "queued" || activeJob.status === "running")) {
    const previewSrc =
      preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");
    // 1 Frame stores its opening still on scene.start_asset_id. That slot is not
    // a Timeline picture. Draft preview waits for a real generation frame.
    const sourceStill = "";
    const stage = (activeJob.stage || activeJob.message || "").toLowerCase();
    const isPreparing = stage.includes("prepar") || stage.includes("load");
    if (isPreparing && !previewSrc) return { kind: "preparing", job: activeJob };
    return {
      kind: "generation_draft",
      job: activeJob,
      previewSrc,
      sourceStill,
    };
  }

  // 3.5 TIMELINE_DRIVEN_PREVIEW — composed Visual (videoClips / approved take /
  // A|Retake|B rtclip_*) is the sole Visual playback authority.
  // FE CONTRACT: do NOT read scene.lipsync_output_path or timeline.lipsync tracks
  // for Preview Visual / dialogue authority (Timeline UX owns Lip Sync strip UI;
  // field may still exist on the scene row for MAGI/legacy provenance).
  const frame = resolveTimelineAtTime(args.timeline, args.master, args.playheadSec, {
    takeId: args.previewTakeId,
  });
  if (frame.activeVisual && frame.activeVisual.assetId) {
    return {
      kind: "timeline_frame",
      visualSrc: api.assetUrl(frame.activeVisual.assetId),
      mediaKind: frame.activeVisual.kind,
      promptText: frame.activePrompt?.text ?? null,
      promptLabel: frame.activePrompt?.label ?? null,
      batchId: frame.activeBatch?.id ?? null,
      batchLocalTime: frame.batchLocalTime,
      visualLocalTime: frame.visualLocalTime,
      videoAssetId: frame.activeVisual.kind === "video" ? frame.activeVisual.assetId : null,
      sourceClipId: frame.activeVisual.clipId,
    };
  }

  // 3.6 lipsync_output_path DEMOTION — never Visual authority for Timeline Preview.
  // Range retakes live on videoClips (rtclip_* via replace_visual_range). Gaps fall
  // through to scene stitch / output_path only.

  // 4. Stitched scene clip — Play (and parked scene preview) uses the joined
  // file as one continuous source when no per-batch visual is at playhead.
  // Inspecting a batch while paused still shows that batch's own take above.
  if (
    shouldPreviewSceneStitch({
      master: args.master,
      selection: args.selection,
      playheadSec: args.playheadSec,
      timelinePlaying: args.timelinePlaying,
    }) &&
    args.master?.sceneStitch?.assetId
  ) {
    return {
      kind: "timeline_frame",
      visualSrc: api.assetUrl(args.master.sceneStitch.assetId),
      mediaKind: "video",
      promptText: null,
      promptLabel: "Full scene",
      batchId: null,
      batchLocalTime: args.playheadSec,
      visualLocalTime: args.playheadSec,
    };
  }

  // 6. Completed generation with no intersecting clip — show scene.output_path only
  // (lipsync_output_path intentionally ignored for Preview).
  if (activeJob && activeJob.status === "done") {
    const finalSrc = scene?.output_path ? api.mediaUrl(scene.output_path) : "";
    return {
      kind: "final_output",
      src: finalSrc,
      mediaKind: finalSrc && isVideoSrc(finalSrc) ? "video" : "image",
      job: activeJob,
    };
  }

  // 7. No intersecting clip and no completed job — leftover scene.output_path only.
  const finalSrc = scene?.output_path ? api.mediaUrl(scene.output_path) : "";
  if (finalSrc) {
    return {
      kind: "final_output",
      src: finalSrc,
      mediaKind: isVideoSrc(finalSrc) ? "video" : "image",
    };
  }

  return { kind: "idle" };
}

export function TimelinePreviewComposer({
  project,
  scene,
  timeline,
  master,
  selection,
  playheadSec,
  timelinePlaying = false,
  onTogglePlay,
  sceneEndSec = 0,
  libraryAsset,
  onClearLibraryAsset,
  onPlayheadChange,
  hideOverlay,
  onHideOverlayChange,
  pauseUpdates,
  onPauseUpdatesChange,
  inlineActions = false,
  cancelRenderSupported,
  onCancelRender,
  onOpenRetake,
  retakeActive = false,
  retakeSession,
  onRetakeMarkIn,
  onRetakeMarkOut,
  onRetakePrompt,
  onRetakeRemoveBackground,
  onRetakeCancel,
  onRetakeSubmit,
  onDismissFailure,
  onApproved,
  onMasterMutated,
  previewTakeId = null,
  generationStandby = false,
}: {
  project: Project;
  scene: Scene | undefined;
  timeline: TimelineBoardView | null;
  master: SceneTimelineMaster | null;
  selection: DirectorSelection;
  playheadSec: number;
  timelinePlaying?: boolean;
  onTogglePlay?: () => void;
  sceneEndSec?: number;
  libraryAsset: Asset | null;
  onClearLibraryAsset?: () => void;
  onPlayheadChange?: (t: number) => void;
  hideOverlay?: boolean;
  onHideOverlayChange?: (value: boolean) => void;
  pauseUpdates?: boolean;
  onPauseUpdatesChange?: (value: boolean) => void;
  inlineActions?: boolean;
  /** Timeline honesty: only true when generator supportsQueuedCancel/supportsRunningCancel and a job is generating. */
  cancelRenderSupported?: boolean;
  onCancelRender?: () => void;
  onOpenRetake?: () => void;
  retakeActive?: boolean;
  retakeSession?: VideoRetakeSession;
  onRetakeMarkIn?: () => void;
  onRetakeMarkOut?: () => void;
  onRetakePrompt?: (value: string) => void;
  onRetakeRemoveBackground?: () => void;
  onRetakeCancel?: () => void;
  onRetakeSubmit?: () => void;
  onDismissFailure?: (jobId: string) => void;
  onApproved?: () => void | Promise<void>;
  /** Reload master after publish / MAGI (shell afterMutation). */
  onMasterMutated?: () => void | Promise<void>;
  previewTakeId?: string | null;
  /** True from the click that starts Generate Scene, Re-Take, or New Take until live progress arrives. */
  generationStandby?: boolean;
}) {
  const { activeJob, preview } = useGenerationState(project.id, scene, Boolean(pauseUpdates), master);

  const composition = useMemo(
    () =>
      resolvePreviewComposition({
        scene,
        timeline,
        master,
        selection,
        playheadSec,
        libraryAsset,
        activeJob,
        preview,
        timelinePlaying,
        previewTakeId,
      }),
    [scene, timeline, master, selection, playheadSec, libraryAsset, activeJob, preview, timelinePlaying, previewTakeId],
  );

  // ORIGINAL_VOICE_SUPPRESSION (Re-Take-only): Lip Sync tracks are NOT Timeline
  // dialogue authority. Mute only when an enabled legacy lipsync clip would still
  // be layered — shouldMutePreviewVideoSoundtrack ignores lipsync_output_path and
  // returns false under rtclip_* / when tracks are absent (retake AAC owns AV).
  // Legacy Lip Sync tracks no longer dialogue/mute authority (Re-Take AV owns window).
  const hasGeneratedTakeAtPlayhead = useMemo(() => {
    const windows = buildBatchTimeWindows(master?.batchBlocks);
    const win = batchWindowAtTime(windows, playheadSec ?? 0);
    const batch = (master?.batchBlocks || []).find((entry) => entry.id === win?.id);
    return batch ? hasGeneratedTakeForRetake(batch) : false;
  }, [master?.batchBlocks, playheadSec]);

  const muteVideoAudio = shouldMutePreviewVideoSoundtrack({
    lipsyncOutputPath: null,
    tracks: [],
    playheadSec: playheadSec ?? 0,
    activeVisualClipId: composition?.kind === "timeline_frame" ? composition.sourceClipId ?? null : null,
  });


  const publishChrome = useMemo(() => {
    const chrome = resolvePublishChrome(master);
    const accepted = String(master?.sceneFinalCheck?.lifecycleStatus || "") === "SCENE_FINISHED_WITH_ACCEPTED_ISSUES";
    return { ...chrome, acceptedIssues: accepted };
  }, [master]);

  const [publishBusy, setPublishBusy] = useState(false);
  const [upscaleBusy, setUpscaleBusy] = useState(false);
  const [upscaleOpen, setUpscaleOpen] = useState(false);
  const [upscaleLoading, setUpscaleLoading] = useState(false);
  const [upscaleError, setUpscaleError] = useState<string | null>(null);
  const [upscaleStatus, setUpscaleStatus] = useState<string | null>(null);
  const [upscaleHonesty, setUpscaleHonesty] = useState<string | null>(null);
  const [upscaleSourceRes, setUpscaleSourceRes] = useState("");
  const [upscaleSourceAssetId, setUpscaleSourceAssetId] = useState("");
  const [realesrganReady, setRealesrganReady] = useState(false);
  const [upscaleEngines, setUpscaleEngines] = useState<Array<{ id: string; label?: string; available?: boolean; models?: Array<{ id: string; label?: string }> }>>([]);
  const [upscaleTargets, setUpscaleTargets] = useState<Array<{ id: string; label: string; width: number; height: number }>>([]);
  const [upscaleEngine, setUpscaleEngine] = useState("ffmpeg-scale");
  const [upscaleModel, setUpscaleModel] = useState("lanczos");
  const [upscaleTargetId, setUpscaleTargetId] = useState("");
  const navigate = useNavigate();
  const publishSource = preferredPublishSource(master?.scenePublish?.upscaledAssetId);

  const handlePublish = async () => {
    if (!scene?.id || publishBusy) return;
    setPublishBusy(true);
    try {
      const result = await api.directorTimelinePublishScene(project.id, scene.id, {
        update: false,
        source: publishSource,
      });
      if (!result.ok) {
        window.alert(result.creatorMessage || result.error || "Publish failed");
        return;
      }
      await onMasterMutated?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Publish failed";
      window.alert(message);
    } finally {
      setPublishBusy(false);
    }
  };

  const handleUpdatePublished = async () => {
    if (!scene?.id || publishBusy) return;
    const expectedVersion = master?.scenePublish?.version;
    setPublishBusy(true);
    try {
      const result = await api.directorTimelinePublishScene(project.id, scene.id, {
        update: true,
        expectedVersion,
        source: publishSource,
      });
      if (!result.ok) {
        window.alert(result.creatorMessage || result.error || "Update Published failed");
        return;
      }
      await onMasterMutated?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Update Published failed";
      window.alert(message);
    } finally {
      setPublishBusy(false);
    }
  };

  const loadUpscaleOptions = async () => {
    if (!scene?.id) return;
    setUpscaleLoading(true);
    setUpscaleError(null);
    try {
      const opts = await api.directorTimelineMagiUpscaleOptions(project.id, scene.id);
      if (!opts.ok) {
        setUpscaleError(opts.creatorMessage || opts.error || "MAGI could not read this master.");
        return;
      }
      const targets = opts.targets || [];
      const engines = (opts.engines || []) as Array<{
        id: string;
        label?: string;
        available?: boolean;
        models?: Array<{ id: string; label?: string }>;
      }>;
      const gpuReady = Boolean(opts.realesrganReady);
      setUpscaleTargets(targets);
      setUpscaleEngines(engines);
      setRealesrganReady(gpuReady);
      setUpscaleHonesty(opts.honesty || null);
      setUpscaleSourceRes(opts.sourceResolution || "");
      setUpscaleSourceAssetId(opts.sourceAssetId || "");
      setUpscaleEngine(opts.defaultEngine || (gpuReady ? "realesrgan-ncnn-vulkan" : "ffmpeg-scale"));
      setUpscaleModel(opts.defaultModel || (gpuReady ? "realesrgan-x4plus" : "lanczos"));
      setUpscaleTargetId(opts.defaultTarget || targets[0]?.id || "");
    } catch (err) {
      setUpscaleError(err instanceof Error ? err.message : "MAGI could not read this master.");
    } finally {
      setUpscaleLoading(false);
    }
  };

  const handleOpenUpscale = async () => {
    if (!scene?.id || upscaleBusy) return;
    setUpscaleOpen(true);
    setUpscaleStatus(null);
    await loadUpscaleOptions();
  };

  const handleConfirmUpscale = async () => {
    if (!scene?.id || upscaleBusy) return;
    const choice = choiceFromChooser({
      engine: upscaleEngine,
      model: upscaleModel,
      targetId: upscaleTargetId,
      targets: upscaleTargets,
    });
    setUpscaleBusy(true);
    setUpscaleError(null);
    setUpscaleStatus("Starting MAGI…");
    try {
      const result = await api.directorTimelineMagiUpscale(project.id, scene.id, {
        engine: choice.engine,
        model: choice.model,
        targetResolution: choice.targetResolution,
      });
      if (!result.ok) {
        setUpscaleError(result.creatorMessage || result.error || "MAGI upscale failed");
        return;
      }
      const jobId = String(result.jobId || "").trim();
      if (!jobId) {
        setUpscaleError("MAGI did not start an upscale job.");
        return;
      }
      setUpscaleStatus("Enhancing the full scene…");
      const done = await pollMagiUpscaleJob(project.id, jobId, {
        onTick: (snap) => {
          const pct = Math.round((snap.progress || 0) * 100);
          setUpscaleStatus(snap.message || (pct ? `Enhancing… ${pct}%` : "Enhancing the full scene…"));
        },
      });
      if (!done.ok) {
        setUpscaleError(done.message || "MAGI upscale failed");
        return;
      }
      setUpscaleStatus("Saved. Reload to keep this enhanced master.");
      setUpscaleOpen(false);
      await onMasterMutated?.();
    } catch (err) {
      setUpscaleError(err instanceof Error ? err.message : "MAGI upscale failed");
    } finally {
      setUpscaleBusy(false);
    }
  };

  const sceneGenerationStatus = useMemo(
    () => previewGenerationNotice(master, generationStandby),
    [master, generationStandby],
  );
  const generationCompleteNotice = useMemo(() => sceneGenerationCompleteNotice(master), [master]);
  const comfyProgressPercent = useMemo(() => {
    return (
      comfyProgressPercentFromText(sceneGenerationStatus) ??
      comfyProgressPercentFromJob(activeJob)
    );
  }, [sceneGenerationStatus, activeJob]);

  return (
    <>
      <LivePreviewMonitor
        project={project}
        scene={scene}
        libraryAsset={libraryAsset}
        onClearLibraryAsset={onClearLibraryAsset}
        playheadSec={playheadSec}
        timelinePlaying={timelinePlaying}
        onTogglePlay={onTogglePlay}
        sceneEndSec={sceneEndSec}
        onPlayheadChange={onPlayheadChange}
        inlineActions={inlineActions}
        cancelRenderSupported={cancelRenderSupported}
        onCancelRender={onCancelRender}
        hideOverlay={hideOverlay}
        onHideOverlayChange={onHideOverlayChange}
        pauseUpdates={pauseUpdates}
        onPauseUpdatesChange={onPauseUpdatesChange}
        composition={composition}
        muteVideoAudio={muteVideoAudio}
        sceneMode={master?.mode}
        onOpenRetake={onOpenRetake}
        hasGeneratedTakeAtPlayhead={hasGeneratedTakeAtPlayhead}
        retakeActive={retakeActive}
        retakeSession={retakeSession}
        onRetakeMarkIn={onRetakeMarkIn}
        onRetakeMarkOut={onRetakeMarkOut}
        onRetakePrompt={onRetakePrompt}
        onRetakeRemoveBackground={onRetakeRemoveBackground}
        onRetakeCancel={onRetakeCancel}
        onRetakeSubmit={onRetakeSubmit}
        onDismissFailure={onDismissFailure}
        onApproved={onApproved}
        sceneGenerationStatus={sceneGenerationStatus}
        generationCompleteNotice={generationCompleteNotice}
        comfyProgressPercent={comfyProgressPercent}
        publishChrome={publishChrome}
        onPublish={handlePublish}
        onUpdatePublished={handleUpdatePublished}
        onUpscaleWithMagi={handleOpenUpscale}
        publishBusy={publishBusy}
        upscaleBusy={upscaleBusy}
        upscalePanelOpen={upscaleOpen}
        upscalePanel={
          upscaleOpen ? (
            <MagiUpscaleChooser
              loading={upscaleLoading}
              error={upscaleError}
              honesty={upscaleHonesty}
              sourceResolution={upscaleSourceRes}
              realesrganReady={realesrganReady}
              engines={upscaleEngines}
              targets={upscaleTargets}
              engine={upscaleEngine}
              model={upscaleModel}
              targetId={upscaleTargetId}
              busy={upscaleBusy}
              statusText={upscaleStatus}
              onEngineChange={(next) => {
                setUpscaleEngine(next);
                if (next === "ffmpeg-scale") setUpscaleModel("lanczos");
                else if (upscaleModel === "lanczos") setUpscaleModel("realesrgan-x4plus");
              }}
              onModelChange={setUpscaleModel}
              onTargetChange={setUpscaleTargetId}
              onCancel={() => {
                if (!upscaleBusy) setUpscaleOpen(false);
              }}
              onConfirm={() => void handleConfirmUpscale()}
              onOpenInMagi={() => {
                const params = new URLSearchParams();
                params.set("workspace", "magi");
                if (scene?.id) params.set("sceneId", scene.id);
                if (upscaleSourceAssetId) params.set("assetId", upscaleSourceAssetId);
                navigate(`/project/${project.id}?${params.toString()}`);
              }}
            />
          ) : null
        }
      />
      <TimelineDiagnostics selection={selection} composition={composition} reloadKey={0} saveError={null} />
    </>
  );
}

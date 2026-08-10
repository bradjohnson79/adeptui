import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, Job, Project, Scene } from "../../types";
import { api } from "../../api";
import { apiUrl } from "../../runtime/apiBase";
import type { DirectorTimeline } from "../DirectorTracks";
import type { DirectorSelection } from "../../directorSelection";
import { LivePreviewMonitor } from "../LivePreviewMonitor";
import { TimelineDiagnostics } from "./TimelineDiagnostics";
import { resolveTimelineAtTime } from "./resolveTimelineAtTime";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";

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
): {
  jobs: Job[];
  activeJob: Job | null;
  preview: PreviewPayload | null;
  seq: number;
} {
  const [jobs, setJobs] = useState<Job[]>([]);
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

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      // VISIBILITY_GATED_POLLING: skip network work while the tab is hidden;
      // the interval keeps ticking cheaply and the next visible tick resyncs.
      if (document.visibilityState === "hidden") return;
      try {
        const list = await api.listJobs(projectId);
        if (!alive) return;
        setJobs(list);
        const job = list.find(
          (j) => j.scene_id === scene?.id && (j.status === "queued" || j.status === "running"),
        );
        if (job && !pauseUpdates) {
          const p = await api.getJobPreview(job.id);
          if (p.preview && (p.preview.sequenceNumber || 0) >= seqRef.current) {
            setSeq(p.preview.sequenceNumber || seqRef.current);
            setPreview(p.preview);
          }
        }
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [projectId, scene?.id, pauseUpdates]);

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

  const sceneJobs = jobs.filter((j) => j.scene_id === scene?.id);
  const activeJob =
    sceneJobs.find((j) => j.status === "queued" || j.status === "running") ||
    // Newest terminal job wins — explicitly sorted, never reliant on listJobs
    // response ordering (the failed-overlay dismissal logic depends on this).
    sceneJobs.slice().sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0] ||
    null;

  return { jobs, activeJob, preview, seq };
}

/**
 * Resolve the single authoritative PreviewComposition from all inputs.
 * Pure function — no side effects — so it is trivial to test and reason about.
 */
export function resolvePreviewComposition(args: {
  scene: Scene | undefined;
  timeline: DirectorTimeline | null;
  master: SceneTimelineMaster | null;
  selection: DirectorSelection;
  playheadSec: number;
  libraryAsset: Asset | null;
  activeJob: Job | null;
  preview: PreviewPayload | null;
}): PreviewComposition {
  const { scene, libraryAsset, activeJob, preview } = args;

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

  // 3. Completed generation -> final output.
  if (activeJob && activeJob.status === "done") {
    const finalSrc = scene?.lipsync_output_path
      ? api.mediaUrl(scene.lipsync_output_path)
      : scene?.output_path
        ? api.mediaUrl(scene.output_path)
        : "";
    return {
      kind: "final_output",
      src: finalSrc,
      mediaKind: finalSrc && isVideoSrc(finalSrc) ? "video" : "image",
      job: activeJob,
    };
  }

  // 4. Active generation with preview frames available.
  if (activeJob && (activeJob.status === "queued" || activeJob.status === "running")) {
    const previewSrc =
      preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");
    const sourceStill = scene?.start_asset_id ? api.assetUrl(scene.start_asset_id) : "";
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

  // 5. No active job — show final scene output if present.
  const finalSrc = scene?.lipsync_output_path
    ? api.mediaUrl(scene.lipsync_output_path)
    : scene?.output_path
      ? api.mediaUrl(scene.output_path)
      : "";
  if (finalSrc) {
    return {
      kind: "final_output",
      src: finalSrc,
      mediaKind: isVideoSrc(finalSrc) ? "video" : "image",
    };
  }

  // 6. TIMELINE_DRIVEN_PREVIEW — resolve the active clip at the playhead.
  // When there is no generation and no scene output, the Preview Monitor shows
  // whatever image/video clip the playhead intersects, with the active prompt
  // as a lower-third overlay (never burned into the asset). This is what makes
  // the monitor "timeline-driven" instead of stuck on Idle.
  const frame = resolveTimelineAtTime(args.timeline, args.master, args.playheadSec);
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
  libraryAsset,
  onClearLibraryAsset,
  onPlayheadChange,
  hideOverlay,
  onHideOverlayChange,
  pauseUpdates,
  onPauseUpdatesChange,
  inlineActions = false,
  onDismissFailure,
}: {
  project: Project;
  scene: Scene | undefined;
  timeline: DirectorTimeline | null;
  master: SceneTimelineMaster | null;
  selection: DirectorSelection;
  playheadSec: number;
  libraryAsset: Asset | null;
  onClearLibraryAsset?: () => void;
  onPlayheadChange?: (t: number) => void;
  hideOverlay?: boolean;
  onHideOverlayChange?: (value: boolean) => void;
  pauseUpdates?: boolean;
  onPauseUpdatesChange?: (value: boolean) => void;
  inlineActions?: boolean;
  onDismissFailure?: (jobId: string) => void;
}) {
  const { activeJob, preview } = useGenerationState(project.id, scene, Boolean(pauseUpdates));

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
      }),
    [scene, timeline, master, selection, playheadSec, libraryAsset, activeJob, preview],
  );

  return (
    <>
      <LivePreviewMonitor
        project={project}
        scene={scene}
        libraryAsset={libraryAsset}
        onClearLibraryAsset={onClearLibraryAsset}
        playheadSec={playheadSec}
        onPlayheadChange={onPlayheadChange}
        inlineActions={inlineActions}
        hideOverlay={hideOverlay}
        onHideOverlayChange={onHideOverlayChange}
        pauseUpdates={pauseUpdates}
        onPauseUpdatesChange={onPauseUpdatesChange}
        composition={composition}
        onDismissFailure={onDismissFailure}
      />
      <TimelineDiagnostics selection={selection} composition={composition} reloadKey={0} saveError={null} />
    </>
  );
}

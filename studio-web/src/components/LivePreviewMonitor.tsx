import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Job, Project, Scene } from "../types";
import { api } from "../api";
import { apiUrl } from "../runtime/apiBase";
import { aspectCssValue } from "../workspacePrefs";
import { usePreviewFullscreen } from "../workspace/fullscreen/usePreviewFullscreen";
import { formatJobTimestamp } from "../lib/formatDuration";
import { PanelHeading } from "./HelpTip";
import { PreviewApproveAsBar } from "./PreviewApproveAsBar";
import { canApproveLibraryImage } from "./previewApproveAs";
import type { PreviewComposition } from "./timeline-master/TimelinePreviewComposer";
import { timelineLibraryIdentity } from "./library/timelineLibraryIdentity";
import { PreviewVideoActionMenu } from "./timeline-master/PreviewVideoActionMenu";
import { PreviewFullscreenTransport } from "./timeline-master/PreviewFullscreenTransport";
import { shouldShowPreviewVideoMenu } from "../timelineMaster/previewVideoActionMenu";
import { TimelineRetakeOverlay } from "./timeline-master/TimelineRetakeOverlay";
import type { VideoRetakeSession } from "../timelineMaster/videoRetake";
import { PreviewGuidesOverlay } from "./timeline-master/PreviewGuidesOverlay";
import "../styles/timeline-master/timeline-retake-overlay.css";
import "../styles/timeline-master/preview-fullscreen.css";
import { appendDraftFrame } from "./draftFrameSequence";
import { DraftSequencePlayer } from "./DraftSequencePlayer";
import {
  RENDER_QUEUE_DISMISS_EVENT,
  loadDismissedRenderJobIds,
  saveDismissedRenderJobIds,
} from "../renderQueueDismiss";
import {
  loadTimelineWorkspaceLayout,
  saveTimelineWorkspaceLayout,
  TIMELINE_LAYOUT_EVENT,
  type TimelineWorkspaceLayout,
} from "../timelineMaster/workspaceLayout";
import {
  appendComfyPercentLine,
  comfyProgressPercentFromJob,
  comfyProgressPercentFromText,
  PREVIEW_GENERATION_STANDBY,
} from "../timelineMaster/sceneRenderProgress";

function LivePreviewComfyProgress({ percent }: { percent: number }) {
  const safe = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div
      className="live-preview-progress"
      data-testid="live-preview-comfy-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={safe}
      aria-label={`Render ${safe} percent`}
    >
      <div className="live-preview-progress__track">
        <div className="live-preview-progress__fill" style={{ width: `${safe}%` }} />
      </div>
      <span className="live-preview-progress__pct">{safe}%</span>
    </div>
  );
}

function lastActivityLabel(iso?: string | null): string {
  if (!iso) return "";
  const stamp = Date.parse(iso);
  if (!Number.isFinite(stamp)) return "";
  const sec = Math.max(0, (Date.now() - stamp) / 1000);
  if (sec < 60) return `${Math.max(1, Math.round(sec))} seconds ago`;
  return `${Math.max(1, Math.round(sec / 60))} minutes ago`;
}

function formatSceneClock(seconds: number): string {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const whole = Math.floor(safe + 1e-6);
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function PreviewPublishBarEyeIcon({ hidden }: { hidden: boolean }) {
  return (
    <svg
      className="live-preview-publish-bar__eye-icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M2.5 12s3.6-6.5 9.5-6.5S21.5 12 21.5 12 17.9 18.5 12 18.5 2.5 12 2.5 12Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.8" />
      {hidden ? (
        <path
          d="M4 20 L20 4"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}

function PreviewPublishBarVisibilityToggle({
  visible,
  attention,
  onToggle,
}: {
  visible: boolean;
  attention: boolean;
  onToggle: () => void;
}) {
  const label = visible ? "Hide preview actions" : "Show preview actions";
  return (
    <button
      type="button"
      className="live-preview-publish-bar__visibility"
      data-testid="live-preview-publish-bar-visibility"
      title={label}
      aria-label={label}
      aria-pressed={!visible}
      aria-expanded={visible}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (event.key === " " || event.key === "Enter") event.stopPropagation();
      }}
    >
      <PreviewPublishBarEyeIcon hidden={!visible} />
      {!visible && attention ? (
        <span className="live-preview-publish-bar__attention" data-testid="live-preview-publish-bar-attention" aria-hidden="true" />
      ) : null}
      {!visible && attention ? <span className="sr-only">Changes pending</span> : null}
    </button>
  );
}

export type PreviewMonitorState =
  | "idle"
  | "preparing"
  | "live_preview"
  | "processing"
  | "assembling"
  | "post"
  | "complete"
  | "failed"
  | "cancelled";

type PreviewPayload = {
  jobId?: string;
  sceneId?: string;
  engineId?: string;
  sequenceNumber?: number;
  stage?: string;
  progress?: number;
  mediaType?: string;
  sourceUrl?: string;
  localPath?: string;
  /** Optional server-side frame history (Approach B / future). Client buffers when absent. */
  frameUrls?: string[];
  /** Hint: still | sequence — client may ignore and infer from buffer length. */
  playbackHint?: string;
};

export type PreviewChromeState = {
  hideOverlay: boolean;
  pauseUpdates: boolean;
  canClearLibrary: boolean;
  canCancel: boolean;
  canSaveFrame: boolean;
  setHideOverlay: (value: boolean) => void;
  setPauseUpdates: (value: boolean) => void;
  clearLibrary: () => void;
  cancelRender: () => void;
  saveFrame: () => Promise<void>;
};

export function LivePreviewMonitor({
  project,
  scene,
  fitMode = "contain",
  libraryAsset = null,
  onClearLibraryAsset,
  playheadSec,
  timelinePlaying = false,
  onPlayheadChange,
  onTogglePlay,
  inlineActions = true,
  cancelRenderSupported,
  onCancelRender,
  hideOverlay: hideOverlayProp,
  onHideOverlayChange,
  pauseUpdates: pauseUpdatesProp,
  onPauseUpdatesChange,
  onChromeStateChange,
  /**
   * When provided (Timeline path), this composition is the SOLE source of truth
   * for what appears in the monitor (PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH).
   * The renderer does not independently resolve content from libraryAsset/jobs.
   * When omitted (legacy/non-Timeline callers), internal resolution is used.
   */
  composition,
  muteVideoAudio = false,
  sceneMode,
  onOpenRetake,
  hasGeneratedTakeAtPlayhead = false,
  retakeActive = false,
  retakeSession,
  onRetakeMarkIn,
  onRetakeMarkOut,
  onRetakePrompt,
  onRetakeRemoveBackground,
  onRetakeCancel,
  onRetakeSubmit,
  onDismissFailure,
  sceneEndSec,
  onApproved,
  idleTitle,
  idleDetail,
  sceneGenerationStatus = null,
  generationCompleteNotice = null,
  comfyProgressPercent = null,
  publishChrome = null,
  onPublish = undefined,
  onUpdatePublished = undefined,
  onUpscaleWithMagi = undefined,
  publishBusy = false,
  upscaleBusy = false,
  upscalePanelOpen = false,
  upscalePanel = null,
}: {
  project: Project;
  scene?: Scene;
  fitMode?: "contain" | "cover" | "none";
  /** Real library asset selected from Assets tray — shown in the monitor (no mock). */
  libraryAsset?: Asset | null;
  onClearLibraryAsset?: () => void;
  /** Shared timeline playhead — syncs video scrub with Director Tracks. */
  playheadSec?: number;
  /** When true, the Timeline clock owns time — do not let the video element write a second clock. */
  timelinePlaying?: boolean;
  onPlayheadChange?: (t: number) => void;
  /** Timeline play/pause when Full Screen has no video element yet. */
  onTogglePlay?: () => void;
  /** When false, hide overlay/pause/save chrome. Cancel stays in the Preview Monitor when wired. */
  inlineActions?: boolean;
  /**
   * Optional extra enable signal. Timeline always wires onCancelRender so Cancel
   * stays visible in the Preview Monitor. Do not use this flag to hide Cancel.
   */
  cancelRenderSupported?: boolean;
  onCancelRender?: () => void;
  hideOverlay?: boolean;
  onHideOverlayChange?: (value: boolean) => void;
  pauseUpdates?: boolean;
  onPauseUpdatesChange?: (value: boolean) => void;
  /** Notifies parent of actionable chrome state for external control rows. */
  onChromeStateChange?: (state: PreviewChromeState) => void;
  /** Authoritative composition resolved by TimelinePreviewComposer. */
  composition?: PreviewComposition;
  /** When true, mute preview <video> AAC so lipsync wavs are sole dialogue authority. */
  muteVideoAudio?: boolean;
  /** Scene modality — video menu is Video Finishing only. */
  sceneMode?: string | null;
  onOpenRetake?: () => void;
  hasGeneratedTakeAtPlayhead?: boolean;
  retakeActive?: boolean;
  retakeSession?: VideoRetakeSession;
  onRetakeMarkIn?: () => void;
  onRetakeMarkOut?: () => void;
  onRetakePrompt?: (value: string) => void;
  onRetakeRemoveBackground?: () => void;
  onRetakeCancel?: () => void;
  onRetakeSubmit?: () => void;
  /** Creator acknowledgment of a terminal failure — clears the failed overlay. */
  onDismissFailure?: (jobId: string) => void;
  /** Scene / board length for the monitor clock. Clip files can be shorter. */
  sceneEndSec?: number;
  onApproved?: () => void | Promise<void>;
  /** Creator-facing idle title when the monitor has no media (Text to Video, etc.). */
  idleTitle?: string;
  idleDetail?: string;
  /** Multi-batch Generate Scene progress (primary creator chrome inside monitor). */
  sceneGenerationStatus?: string | null;
  /** Dismissible Generation Complete banner (100%) — not Final Check chrome. */
  generationCompleteNotice?: { percent: number; fingerprint: string } | null;
  /** Comfy value/max percent (0–100). Live Preview displays this as-is. */
  comfyProgressPercent?: number | null;
  publishChrome?: {
    showPublish: boolean;
    showUpdatePublished: boolean;
    showUpscaleWithMagi: boolean;
    changesPending: boolean;
    changesPendingLabel?: string | null;
    hasPublished?: boolean;
    acceptedIssues?: boolean;
  } | null;
  onPublish?: () => void | Promise<void>;
  onUpdatePublished?: () => void | Promise<void>;
  onUpscaleWithMagi?: () => void | Promise<void>;
  publishBusy?: boolean;
  upscaleBusy?: boolean;
  upscalePanelOpen?: boolean;
  upscalePanel?: ReactNode;
}) {
  const { t } = useTranslation("timeline");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [dismissedJobIds, setDismissedJobIds] = useState<Set<string>>(
    () => loadDismissedRenderJobIds(project.id),
  );
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [seq, setSeq] = useState(0);
  const [hideOverlayLocal, setHideOverlayLocal] = useState(false);
  const [genCompleteDismissedFp, setGenCompleteDismissedFp] = useState<string | null>(null);
  const [pauseUpdatesLocal, setPauseUpdatesLocal] = useState(false);
  const [announce, setAnnounce] = useState("");
  const objectUrlRef = useRef<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stageEl, setStageEl] = useState<HTMLElement | null>(null);
  const syncingFromPropRef = useRef(false);
  /** While Preview Monitor fullscreen, transport owns <video> — clock must not pause/seek-fight. */
  const previewFsOwnsRef = useRef(false);
  /** Successive draft still URLs for low-FPS sequence playback (Approach A). */
  const [draftFrames, setDraftFrames] = useState<string[]>([]);
  const draftJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    const refresh = () => setDismissedJobIds(loadDismissedRenderJobIds(project.id));
    refresh();
    window.addEventListener(RENDER_QUEUE_DISMISS_EVENT, refresh);
    return () => window.removeEventListener(RENDER_QUEUE_DISMISS_EVENT, refresh);
  }, [project.id]);

  const hideOverlay = hideOverlayProp ?? hideOverlayLocal;

  useEffect(() => {
    const fp = generationCompleteNotice?.fingerprint || null;
    if (!fp || !scene?.id) {
      setGenCompleteDismissedFp(null);
      return;
    }
    try {
      const key = `adept.preview.genCompleteDismissed.${scene.id}.${fp}`;
      setGenCompleteDismissedFp(sessionStorage.getItem(key) === "1" ? fp : null);
    } catch {
      setGenCompleteDismissedFp(null);
    }
  }, [generationCompleteNotice?.fingerprint, scene?.id]);

  const pauseUpdates = pauseUpdatesProp ?? pauseUpdatesLocal;
  const [publishBarVisible, setPublishBarVisible] = useState(
    () => loadTimelineWorkspaceLayout().previewPublishBarVisible !== false,
  );

  useEffect(() => {
    if (!publishChrome) return;
    const onLayout = (event: Event) => {
      const detail = (event as CustomEvent<TimelineWorkspaceLayout>).detail;
      const next = detail || loadTimelineWorkspaceLayout();
      setPublishBarVisible(next.previewPublishBarVisible !== false);
    };
    window.addEventListener(TIMELINE_LAYOUT_EVENT, onLayout);
    return () => window.removeEventListener(TIMELINE_LAYOUT_EVENT, onLayout);
  }, [publishChrome]);

  const togglePublishBarVisible = () => {
    const next = !publishBarVisible;
    setPublishBarVisible(next);
    saveTimelineWorkspaceLayout({ previewPublishBarVisible: next });
  };
  const setHideOverlay = (value: boolean) => {
    if (onHideOverlayChange) onHideOverlayChange(value);
    else setHideOverlayLocal(value);
  };
  const setPauseUpdates = (value: boolean) => {
    if (onPauseUpdatesChange) onPauseUpdatesChange(value);
    else setPauseUpdatesLocal(value);
  };

  // When a composition is provided (Timeline path via TimelinePreviewComposer),
  // it is the SOLE source of truth — we derive all display state from it and
  // skip the legacy internal resolution (PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH).
  const composed = composition;

  const activeJob = composed
    ? composed.kind === "preparing" ||
      composed.kind === "generation_draft" ||
      composed.kind === "failed" ||
      composed.kind === "cancelled" ||
      composed.kind === "final_output"
      ? composed.job ?? null
      : null
    : jobs.find(
        (j) =>
          j.scene_id === scene?.id && (j.status === "queued" || j.status === "running"),
      ) ||
      jobs.find((j) => j.scene_id === scene?.id && !dismissedJobIds.has(j.id)) ||
      null;

  const resolvedComfyPercent = (() => {
    if (typeof comfyProgressPercent === "number" && Number.isFinite(comfyProgressPercent)) {
      return Math.max(0, Math.min(100, Math.round(comfyProgressPercent)));
    }
    return comfyProgressPercentFromText(sceneGenerationStatus) ?? comfyProgressPercentFromJob(activeJob);
  })();
  const showGenerationComplete =
    Boolean(generationCompleteNotice) &&
    !sceneGenerationStatus &&
    !hideOverlay &&
    genCompleteDismissedFp !== generationCompleteNotice?.fingerprint;
  const displayGenerationStatus =
    sceneGenerationStatus && resolvedComfyPercent != null
      ? appendComfyPercentLine(sceneGenerationStatus, resolvedComfyPercent)
      : sceneGenerationStatus;
  const generationStandbyNotice = sceneGenerationStatus === PREVIEW_GENERATION_STANDBY;

  const libraryKind = (libraryAsset?.kind || "").toLowerCase();
  const librarySrc = libraryAsset ? api.assetUrl(libraryAsset.id) : "";

  const monitorState: PreviewMonitorState = (() => {
    if (composed) {
      switch (composed.kind) {
        case "idle":
          return "idle";
        case "preparing":
          return "preparing";
        case "generation_draft":
          return preview ? "live_preview" : "processing";
        case "final_output":
          return "complete";
        case "failed":
          // Session dismiss hides the banner on this click. The Timeline
          // composition stays "failed" until the master records the job id,
          // so waiting on that round trip left Dismiss looking dead.
          if (activeJob && dismissedJobIds.has(activeJob.id)) return "complete";
          return "failed";
        case "cancelled":
          return "cancelled";
        case "library":
          return "complete";
        case "timeline_frame":
          return "complete";
      }
    }
    // Legacy internal resolution (non-Timeline callers).
    const showingLibraryLegacy = Boolean(libraryAsset && librarySrc);
    if (showingLibraryLegacy) return "complete";
    if (!activeJob) {
      if (scene?.output_path) return "complete";
      return "idle";
    }
    if (activeJob.status === "failed") return "failed";
    if (activeJob.status === "cancelled") return "cancelled";
    if (activeJob.status === "done") return "complete";
    const stage = (activeJob.stage || activeJob.message || "").toLowerCase();
    if (stage.includes("prepar") || stage.includes("load")) return "preparing";
    if (stage.includes("assembl")) return "assembling";
    if (stage.includes("lipsync") || stage.includes("mix") || stage.includes("post")) return "post";
    if (preview) return "live_preview";
    return "processing";
  })();

  const showingLibrary = composed
    ? composed.kind === "library"
    : Boolean(libraryAsset && librarySrc);

  useEffect(() => {
    if (libraryAsset) {
      const identity = timelineLibraryIdentity(libraryAsset, { relatedAssets: project.assets });
      setAnnounce(
        `Previewing ${identity.title} (${libraryAsset.kind}) from Library.`,
      );
      return;
    }
    setAnnounce((current) => (current.includes("from Library") ? "" : current));
  }, [libraryAsset, project.assets]);

  useEffect(() => {
    // Generation state polling is owned by TimelinePreviewComposer on the
    // Timeline path. Only poll here for legacy/non-composed callers.
    if (composed) return;
    let alive = true;
    const tick = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const list = await api.listJobs(project.id);
        if (!alive) return;
        setJobs(list);
        const job = list.find(
          (j) => j.scene_id === scene?.id && (j.status === "queued" || j.status === "running")
        );
        if (job && !pauseUpdates) {
          const p = await api.getJobPreview(job.id);
          if (p.preview && (p.preview.sequenceNumber || 0) >= seq) {
            setSeq(p.preview.sequenceNumber || seq);
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
  }, [project.id, scene?.id, pauseUpdates, seq, composed]);

  useEffect(() => {
    // SSE preview stream owned by composer on Timeline path.
    if (composed) return;
    try {
      const es = new EventSource(apiUrl(`/api/projects/${project.id}/preview/stream`));
      esRef.current = es;
      es.onmessage = (ev) => {
        if (pauseUpdates) return;
        try {
          const data = JSON.parse(ev.data);
          if (data.event === "preview_updated" || data.event === "preview_available") {
            const p = data.preview as PreviewPayload;
            if (p?.sceneId && scene?.id && p.sceneId !== scene.id) return;
            if ((p?.sequenceNumber || 0) < seq) return;
            setSeq(p.sequenceNumber || seq);
            setPreview(p);
            if (data.event === "preview_available") {
              setAnnounce(`Live preview is now available for ${scene?.name || "scene"}.`);
            }
          }
        } catch {
          /* ignore */
        }
      };
      return () => {
        es.close();
        esRef.current = null;
      };
    } catch {
      return;
    }
  }, [project.id, scene?.id, pauseUpdates, seq, scene?.name, composed]);

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, []);

  // Playback authority: never prefer legacy lipsync_output_path.
  const finalSrc = scene?.output_path ? api.mediaUrl(scene.output_path) : "";
  const sourceStill = scene?.start_asset_id ? api.assetUrl(scene.start_asset_id) : "";
  const previewSrc = preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");

  // Resolve mediaSrc from the composition when present; otherwise legacy.
  const mediaSrc = composed
    ? composed.kind === "library"
      ? composed.src
      : composed.kind === "final_output"
        ? composed.src
        : composed.kind === "generation_draft"
          ? composed.previewSrc || composed.sourceStill
          : composed.kind === "preparing"
            ? ""
            : composed.kind === "timeline_frame"
              ? composed.visualSrc
              : composed.kind === "failed" || composed.kind === "cancelled"
                ? composed.previewSrc || finalSrc
                : finalSrc
    : showingLibrary
      ? librarySrc
      : monitorState === "complete" && finalSrc
        ? finalSrc
        : previewSrc || (monitorState === "preparing" || monitorState === "live_preview" || monitorState === "processing" || monitorState === "assembling" || monitorState === "post" ? sourceStill : finalSrc || sourceStill);

  const showDraft =
    !showingLibrary &&
    (monitorState === "live_preview" ||
      monitorState === "processing" ||
      monitorState === "assembling" ||
      monitorState === "post" ||
      monitorState === "preparing");

  // Streamed draft still only (never storyboard/source fallback) — Approach A buffer.
  const liveDraftSrc =
    (Array.isArray(preview?.frameUrls) && preview.frameUrls.length
      ? preview.frameUrls[preview.frameUrls.length - 1]
      : "") ||
    (composed?.kind === "generation_draft" ? composed.previewSrc : "") ||
    previewSrc;

  useEffect(() => {
    const jobId = activeJob?.id || null;
    if (!showDraft) {
      draftJobIdRef.current = null;
      setDraftFrames([]);
      return;
    }
    if (draftJobIdRef.current && jobId && draftJobIdRef.current !== jobId) {
      setDraftFrames([]);
    }
    draftJobIdRef.current = jobId;
    if (Array.isArray(preview?.frameUrls) && preview.frameUrls.length) {
      setDraftFrames(preview.frameUrls.filter(Boolean).slice(-48));
      return;
    }
    if (!liveDraftSrc) return;
    setDraftFrames((prev) => appendDraftFrame(prev, liveDraftSrc));
  }, [showDraft, liveDraftSrc, activeJob?.id, preview?.frameUrls]);

  const aspect = aspectCssValue(scene?.aspect_ratio);
  const fit = fitMode === "cover" ? "cover" : fitMode === "none" ? "none" : "contain";
  const isLibraryVideo =
    showingLibrary &&
    (composed
      ? composed.kind === "library" && composed.mediaKind === "video"
      : libraryKind === "video" || /\.(mp4|webm|mov)(\?|$)/i.test(libraryAsset?.filename || ""));
  const isLibraryAudio =
    showingLibrary &&
    (composed
      ? composed.kind === "library" && composed.mediaKind === "audio"
      : libraryKind === "audio" || /\.(wav|mp3|ogg|m4a|aac|flac)(\?|$)/i.test(libraryAsset?.filename || ""));
  const isTimelineFrameVideo =
    composed?.kind === "timeline_frame" && composed.mediaKind === "video";
  const isJobVideo =
    !showingLibrary && (isTimelineFrameVideo || /\.(mp4|webm|mov)(\?|$)/i.test(mediaSrc) || preview?.mediaType === "video");

  // TIMELINE_CLIP_LOCAL_TIME: a timeline_frame video clip's element time is
  // clip-local (0 = clip start), while playheadSec is global timeline time.
  // The Timeline clock owns playheadSec. During Play, let the element run so
  // Batch 2 is moving video — do not pause-and-scrub every frame (that freezes
  // on keyframes / the last frame of a clip shorter than its batch).
  const timelineVideoLocalTime =
    composed?.kind === "timeline_frame" ? composed.visualLocalTime : null;
  const timelineVideoOffset =
    isTimelineFrameVideo && playheadSec != null && timelineVideoLocalTime != null
      ? playheadSec - timelineVideoLocalTime
      : 0;
  const videoTargetTime =
    isTimelineFrameVideo && timelineVideoLocalTime != null ? timelineVideoLocalTime : playheadSec;
  const sceneClockTotal = Math.max(0, Number(sceneEndSec || 0));
  const sceneClockNow = Math.max(0, Number(playheadSec || 0));
  const showSceneClock = isJobVideo && sceneClockTotal > 0;
  // ORIGINAL_VOICE_SUPPRESSION (Re-Take-only): mute only when composer requests it.
  // Lip Sync tracks demoted; rtclip_* retake AAC owns [markIn,markOut).
  // Library inspect stays unmuted so creators can audition asset audio.
  const suppressOriginalVoice = Boolean(muteVideoAudio) && !showingLibrary;

  const timelinePlayingRef = useRef(timelinePlaying);
  const videoTargetTimeRef = useRef(videoTargetTime);
  const mediaSrcRef = useRef(mediaSrc);
  timelinePlayingRef.current = timelinePlaying;
  videoTargetTimeRef.current = videoTargetTime;

  const applyTimelineVideoClock = (v: HTMLVideoElement) => {
    // Fullscreen transport owns play/pause/seek while Preview is fullscreen.
    if (previewFsOwnsRef.current) return;
    const target = videoTargetTimeRef.current;
    if (target == null || Number.isNaN(target)) return;
    const driftLimit = timelinePlayingRef.current ? 0.25 : 0.04;
    if (Math.abs(v.currentTime - target) > driftLimit) {
      syncingFromPropRef.current = true;
      try {
        v.currentTime = Math.min(
          target,
          Number.isFinite(v.duration) ? v.duration : target,
        );
      } catch {
        /* ignore seek before metadata */
      }
    }
    if (timelinePlayingRef.current) {
      // Keep the same <video> element across batch src changes. Remounting at
      // the Batch 1 → Batch 2 boundary loses user-activation and play() is
      // blocked, so Batch 2 freezes on a still.
      // After Batch 1 EOF, ended===true makes play() a no-op until seek/load;
      // do not gate on !ended — seek above clears EOF when target is in-range.
      if (v.paused || v.ended) void v.play().catch(() => undefined);
    } else if (!v.paused) {
      v.pause();
    }
  };

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = suppressOriginalVoice;
    // ATOMIC_BATCH_SRC: same <video> element must restart its media pipeline
    // when composition switches Batch Visual URLs. React updates the attribute,
    // but after EOF some engines keep the prior still until load() + clock.
    if (mediaSrc && mediaSrcRef.current !== mediaSrc) {
      mediaSrcRef.current = mediaSrc;
      if (v.getAttribute("src") !== mediaSrc) {
        v.src = mediaSrc;
      }
      try {
        v.load();
      } catch {
        /* ignore */
      }
    }
    applyTimelineVideoClock(v);
  }, [videoTargetTime, mediaSrc, timelinePlaying, suppressOriginalVoice]);


  // Server-side EngineCapabilities decide preview honesty. Never sniff provider names.
  const capsUnsupported = false;

  const jobCancellable = Boolean(activeJob && (activeJob.status === "queued" || activeJob.status === "running"));
  const canCancel = Boolean(onCancelRender) || Boolean(cancelRenderSupported) || jobCancellable;
  const triggerCancel = () => {
    if (onCancelRender) {
      onCancelRender();
      return;
    }
    if (activeJob) void api.cancelJob(activeJob.id);
  };
  const canSaveFrame = Boolean(activeJob && previewSrc);

  useEffect(() => {
    if (!onChromeStateChange) return;
    onChromeStateChange({
      hideOverlay,
      pauseUpdates,
      canClearLibrary: showingLibrary,
      canCancel,
      canSaveFrame,
      setHideOverlay,
      setPauseUpdates,
      clearLibrary: () => onClearLibraryAsset?.(),
      cancelRender: () => {
        triggerCancel();
      },
      saveFrame: async () => {
        if (!activeJob) return;
        await api.savePreviewFrame(activeJob.id, project.id, `${scene?.name || "scene"}_preview`);
        setAnnounce("Preview frame saved to Assets.");
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    hideOverlay,
    pauseUpdates,
    showingLibrary,
    canCancel,
    canSaveFrame,
    activeJob?.id,
    cancelRenderSupported,
    onCancelRender,
    project.id,
    scene?.name,
    onClearLibraryAsset,
  ]);

  // Preview Monitor fullscreen — fullscreens ONLY the preview stage, not the
  // entire Timeline UI. The video element is NOT remounted; playback state
  // (time, play/pause, volume) survives the transition.
  const previewFullscreen = usePreviewFullscreen();
  previewFsOwnsRef.current = previewFullscreen.isFullscreen;

  const setStageRef = (el: HTMLElement | null) => {
    (previewFullscreen.containerRef as { current: HTMLElement | null }).current = el;
    setStageEl(el);
  };

  // Guides bind to the composition frame derived from the selected Timeline aspect ratio.

  return (
    <div
      className="panel live-preview-monitor"
      data-testid="live-preview-monitor"
      data-playhead={playheadSec != null && Number.isFinite(playheadSec) ? String(playheadSec) : undefined}
    >
      <PanelHeading
        title={t("previewMonitor")}
        tip="Click a Library asset to preview it here. During renders, live generation frames appear when the engine provides them."
      />
      <div
        ref={setStageRef}
        className={`live-preview-stage${previewFullscreen.isFullscreen ? " is-preview-fullscreen" : ""}`}
        style={{ aspectRatio: aspect, height: "100%" }}
        data-testid="live-preview-stage"
      >
        {(showingLibrary || libraryAsset) && onClearLibraryAsset ? (
          <button
            type="button"
            className="live-preview-close"
            data-testid="live-preview-close"
            title={t("closePreviewTitle")}
            aria-label={t("closePreviewTitle")}
            onClick={() => {
              setAnnounce("");
              onClearLibraryAsset();
            }}
          >
            ×
          </button>
        ) : null}
        {onCancelRender || (canCancel && activeJob) ? (
          <button
            type="button"
            className="live-preview-cancel-in-stage"
            data-testid="live-preview-cancel-in-stage"
            title="Cancel render"
            aria-label="Cancel render"
            onClick={() => triggerCancel()}
          >
            Cancel
          </button>
        ) : null}
        {showingLibrary && isLibraryAudio ? (
          <div className="live-preview-audio" data-testid="live-preview-library-audio">
            <strong>@{libraryAsset?.tag || libraryAsset?.filename}</strong>
            <span className="scene-meta">{libraryAsset?.filename}</span>
            <audio key={librarySrc} src={librarySrc} controls autoPlay style={{ width: "min(100%, 28rem)" }} />
          </div>
        ) : mediaSrc ? (
          isLibraryVideo || isJobVideo ? (
            <video
              ref={videoRef}
              src={mediaSrc}
              muted={suppressOriginalVoice}
              controls={!showSceneClock}
              playsInline
              autoPlay={showingLibrary && !timelinePlaying}
              data-testid={showingLibrary ? "live-preview-library-video" : "live-preview-video"}
              data-suppress-original-voice={suppressOriginalVoice ? "1" : "0"}
              style={{ objectFit: fit }}
              onLoadedData={(e) => {
                applyTimelineVideoClock(e.currentTarget);
              }}
              onCanPlay={(e) => {
                applyTimelineVideoClock(e.currentTarget);
              }}
              onTimeUpdate={(e) => {
                if (timelinePlaying) return;
                if (syncingFromPropRef.current) {
                  syncingFromPropRef.current = false;
                  return;
                }
                const el = e.currentTarget;
                if (!el.paused && onPlayheadChange) {
                  onPlayheadChange(el.currentTime + timelineVideoOffset);
                }
              }}
              onSeeked={() => {
                syncingFromPropRef.current = false;
              }}
            />
          ) : showDraft && draftFrames.length > 0 ? (
            <DraftSequencePlayer
              urls={draftFrames}
              alt="Live generation preview (draft)"
              fit={fit}
              paused={pauseUpdates}
              testId="live-preview-draft-sequence"
            />
          ) : (
            <img
              key={mediaSrc}
              src={mediaSrc}
              alt={
                showingLibrary
                  ? `@${libraryAsset?.tag || libraryAsset?.filename}`
                  : showDraft
                    ? "Live generation preview (draft)"
                    : "Scene preview"
              }
              data-testid={showingLibrary ? "live-preview-library-image" : "live-preview-image"}
              style={{ objectFit: fit }}
            />
          )
        ) : (
          <div className="director-stage-empty" data-testid="live-preview-idle">
            <strong>{monitorState === "preparing" ? "Preparing…" : generationStandbyNotice ? PREVIEW_GENERATION_STANDBY : sceneGenerationStatus ? "Generating…" : idleTitle || "Idle"}</strong>
            {scene ? <span>{scene.name}</span> : idleDetail ? null : <span>Select a scene</span>}
            <span className="scene-meta" style={sceneGenerationStatus ? { whiteSpace: "pre-line" } : undefined}>
              {displayGenerationStatus || idleDetail || "Click a Library image, video, or audio to preview it here."}
            </span>
            {sceneGenerationStatus && resolvedComfyPercent != null ? (
              <LivePreviewComfyProgress percent={resolvedComfyPercent} />
            ) : null}
          </div>
        )}

        <PreviewGuidesOverlay stage={stageEl} aspectRatio={scene?.aspect_ratio} visible={!hideOverlay} />

        {(showDraft || composed?.kind === "generation_draft" || (libraryAsset?.tag || "").toLowerCase().includes("draft")) && (
          <div
            className="live-preview-draft-badge"
            data-testid="timeline-draft-badge"
            aria-label="Draft preview"
            style={{
              position: "absolute",
              top: "0.45rem",
              left: "0.45rem",
              zIndex: 3,
              background: "color-mix(in srgb, #c9a227 85%, #0b0d12)",
              color: "#0b0d12",
              fontSize: "0.7rem",
              fontWeight: 700,
              letterSpacing: "0.08em",
              padding: "0.15rem 0.45rem",
              borderRadius: "0.25rem",
              pointerEvents: "none",
            }}
          >
            DRAFT
          </div>
        )}

        {showingLibrary && !hideOverlay && (
          <div className="live-preview-overlay" aria-live="polite">
            <div className="pill">LIBRARY · {libraryAsset?.kind}</div>
            <div>@{libraryAsset?.tag || "untagged"}</div>
            <div className="scene-meta">{libraryAsset?.filename}</div>
          </div>
        )}

        {libraryAsset &&
        canApproveLibraryImage({
          showingLibrary,
          mediaKind: composed?.kind === "library" ? composed.mediaKind : null,
          assetKind: libraryAsset.kind,
          filename: libraryAsset.filename,
        }) ? (
          <PreviewApproveAsBar
            key={libraryAsset.id}
            projectId={project.id}
            sceneId={scene?.id}
            asset={libraryAsset}
            onApproved={onApproved}
          />
        ) : null}

                {sceneGenerationStatus && !showDraft && (!hideOverlay || generationStandbyNotice) ? (
          <div
            className="live-preview-overlay live-preview-overlay--scene-generation"
            data-testid="live-preview-scene-generation-status"
            aria-live="polite"
            role="status"
          >
            <div className="pill warn">
              {generationStandbyNotice ? PREVIEW_GENERATION_STANDBY : "GENERATE SCENE · Multi-batch"}
            </div>
            {generationStandbyNotice
              ? null
              : (displayGenerationStatus || sceneGenerationStatus).split("\n").map((line, i) => (
                  <div key={`scene-gen-${i}`} className={i === 0 ? undefined : "scene-meta"}>
                    {line}
                  </div>
                ))}
            {resolvedComfyPercent != null ? <LivePreviewComfyProgress percent={resolvedComfyPercent} /> : null}
          </div>
        ) : null}

        {showGenerationComplete ? (
          <div
            className="live-preview-overlay live-preview-overlay--generation-complete"
            data-testid="live-preview-generation-complete"
            aria-live="polite"
            role="status"
          >
            <div className="live-preview-generation-complete__row">
              <div className="pill">Generation Complete</div>
              <button
                type="button"
                className="live-preview-generation-complete__close"
                data-testid="live-preview-generation-complete-dismiss"
                aria-label="Close generation complete notice"
                title="Close"
                onClick={() => {
                  const fp = generationCompleteNotice?.fingerprint;
                  if (!fp || !scene?.id) {
                    setGenCompleteDismissedFp(fp || "dismissed");
                    return;
                  }
                  try {
                    sessionStorage.setItem(`adept.preview.genCompleteDismissed.${scene.id}.${fp}`, "1");
                  } catch {
                    /* ignore */
                  }
                  setGenCompleteDismissedFp(fp);
                }}
              >
                ×
              </button>
            </div>
            <div>Generation Complete — {generationCompleteNotice?.percent ?? 100}%</div>
            <LivePreviewComfyProgress percent={generationCompleteNotice?.percent ?? 100} />
          </div>
        ) : null}


        {showDraft && !hideOverlay && (
          <div
            className="live-preview-overlay"
            data-testid={sceneGenerationStatus ? "live-preview-scene-generation-status" : undefined}
            aria-live="polite"
            role="status"
          >
            <div className="pill warn">
              {generationStandbyNotice ? PREVIEW_GENERATION_STANDBY : "LIVE PREVIEW · Draft quality"}
            </div>
            {generationStandbyNotice ? null : sceneGenerationStatus ? (
              (displayGenerationStatus || sceneGenerationStatus).split("\n").map((line, i) => (
                <div key={`scene-gen-draft-${i}`} className={i === 0 ? undefined : "scene-meta"}>
                  {line}
                </div>
              ))
            ) : (
              <>
                <div>
                  {scene?.name} — {scene?.engine}
                </div>
                <div className="scene-meta">
                  {activeJob?.generation_stalled
                    ? "Generation may be stalled"
                    : activeJob?.phase_label || activeJob?.stage || activeJob?.message || monitorState}
                  {resolvedComfyPercent != null ? ` · ${resolvedComfyPercent}%` : ""}
                  {activeJob?.generation_stalled && activeJob.last_runtime_event_at
                    ? ` · Last activity: ${lastActivityLabel(activeJob.last_runtime_event_at)}`
                    : ""}
                  {draftFrames.length >= 2
                    ? ` · Draft motion · ${draftFrames.length} frames @ ~6fps`
                    : draftFrames.length === 1
                      ? " · Draft still — waiting for more frames"
                      : liveDraftSrc
                        ? ""
                        : " · No draft frames yet"}
                </div>
              </>
            )}
            {resolvedComfyPercent != null ? <LivePreviewComfyProgress percent={resolvedComfyPercent} /> : null}
            {!sceneGenerationStatus && capsUnsupported && (
              <div className="scene-meta">
                This engine does not provide intermediate preview frames. Storyboard/source remains until final.
              </div>
            )}
            {sceneGenerationStatus && (
              <div className="scene-meta">
                {scene?.name} — {scene?.engine}
                {draftFrames.length >= 2
                  ? ` · Draft motion · ${draftFrames.length} frames @ ~6fps`
                  : draftFrames.length === 1
                    ? " · Draft still — waiting for more frames"
                    : liveDraftSrc
                      ? ""
                      : " · No draft frames yet"}
              </div>
            )}
          </div>
        )}

        {monitorState === "failed" && !showingLibrary && (
          <div className="live-preview-overlay bad" data-testid="live-preview-failed-overlay">
            <strong>
              Render failed
              {activeJob?.updated_at ? ` · ${formatJobTimestamp(activeJob.updated_at)}` : ""}
            </strong>
            {activeJob?.message ? <div className="scene-meta">{activeJob.message}</div> : null}
            <div className="scene-meta">Latest draft preview preserved when available.</div>
            {activeJob ? (
              <button
                type="button"
                className="ghost"
                data-testid="live-preview-dismiss-failure"
                title="Clear this failure message and return to the preview — the job history is kept"
                onClick={() => {
                  const next = new Set(loadDismissedRenderJobIds(project.id));
                  next.add(activeJob.id);
                  saveDismissedRenderJobIds(project.id, next);
                  setDismissedJobIds(next);
                  setPreview(null);
                  setSeq(0);
                  onDismissFailure?.(activeJob.id);
                }}
              >
                Dismiss
              </button>
            ) : null}
          </div>
        )}

        {monitorState === "cancelled" && !showingLibrary && (
          <div className="live-preview-overlay" data-testid="live-preview-cancelled-overlay">
            <strong>Render cancelled</strong>
            <div className="scene-meta">Latest draft preview preserved when available. Resume or re-take when ready.</div>
          </div>
        )}

        {showSceneClock ? (
          <div className="live-preview-scene-clock" data-testid="live-preview-scene-clock">
            {formatSceneClock(sceneClockNow)} / {formatSceneClock(sceneClockTotal)}
          </div>
        ) : null}

                {/* Owner 2026-09-08: Prompt lower-third must NOT appear on Preview Monitor.
            Timed Prompt text lives on the Timeline track / Inspector, not over video. */}

        {publishChrome ? (
          <div
            className={[
              "live-preview-publish-bar",
              upscalePanelOpen && publishBarVisible ? "live-preview-publish-bar--chooser" : "",
              !publishBarVisible ? "live-preview-publish-bar--collapsed" : "",
              !publishBarVisible && (showingLibrary || libraryAsset) && onClearLibraryAsset
                ? "live-preview-publish-bar--offset-close"
                : "",
            ].filter(Boolean).join(" ")}
            data-testid="live-preview-publish-bar"
            data-collapsed={publishBarVisible ? "false" : "true"}
            role="group"
            aria-label="Timeline publish and MAGI upscale"
          >
            {publishBarVisible ? (
              <div className="live-preview-publish-bar__row">
                {publishChrome.changesPending && publishChrome.changesPendingLabel ? (
                  <span className="live-preview-publish-bar__pending" data-testid="live-preview-changes-pending">
                    {publishChrome.changesPendingLabel}
                  </span>
                ) : null}
                {!publishChrome.changesPending && publishChrome.hasPublished && !publishChrome.showPublish ? (
                  <span className="live-preview-publish-bar__published" data-testid="live-preview-published-badge">
                    Published{publishChrome.acceptedIssues ? " (accepted issues)" : ""}
                  </span>
                ) : null}
                <button
                  type="button"
                  className="live-preview-publish-bar__btn live-preview-publish-bar__btn--publish"
                  data-testid="live-preview-publish"
                  title="Register Video Published Master in the Library from the full stitched scene"
                  aria-label="Publish"
                  disabled={publishBusy || upscaleBusy}
                  onClick={() => void onPublish?.()}
                >
                  {publishBusy ? "Publishing…" : "PUBLISH"}
                </button>
                <button
                  type="button"
                  className="live-preview-publish-bar__btn live-preview-publish-bar__btn--update"
                  data-testid="live-preview-update-published"
                  title="Update the Video Published Master from the current full stitch"
                  aria-label="Update Published"
                  disabled={publishBusy || upscaleBusy}
                  onClick={() => void onUpdatePublished?.()}
                >
                  {publishBusy ? "Updating…" : "UPDATE PUBLISHED"}
                </button>
                {!upscalePanelOpen ? (
                  <button
                    type="button"
                    className="live-preview-publish-bar__btn live-preview-publish-bar__btn--upscale"
                    data-testid="live-preview-upscale-magi"
                    title="Upscale the full stitched (or published) master with MAGI — does not auto-publish"
                    aria-label="Upscale with MAGI"
                    disabled={publishBusy || upscaleBusy}
                    onClick={() => void onUpscaleWithMagi?.()}
                  >
                    {upscaleBusy ? "Upscaling…" : "UPSCALE WITH MAGI"}
                  </button>
                ) : null}
                <PreviewPublishBarVisibilityToggle
                  visible
                  attention={false}
                  onToggle={togglePublishBarVisible}
                />
              </div>
            ) : (
              <PreviewPublishBarVisibilityToggle
                visible={false}
                attention={Boolean(publishChrome.changesPending)}
                onToggle={togglePublishBarVisible}
              />
            )}
            {publishBarVisible && upscalePanelOpen ? upscalePanel : null}
          </div>
        ) : null}

        {retakeSession && onRetakeMarkIn && onRetakeSubmit ? (
          <TimelineRetakeOverlay
            session={retakeSession}
            videoAvailable={isJobVideo}
            onMarkIn={onRetakeMarkIn}
            onMarkOut={onRetakeMarkOut || (() => undefined)}
            onPrompt={onRetakePrompt || (() => undefined)}
            onRemoveBackground={onRetakeRemoveBackground || (() => undefined)}
            onCancel={onRetakeCancel || (() => undefined)}
            onSubmit={onRetakeSubmit}
          />
        ) : null}
        <PreviewVideoActionMenu
          enabled={shouldShowPreviewVideoMenu({ sceneMode, composition: composed, hasGeneratedTakeAtPlayhead })}
          retakeActive={retakeActive}
          onOpenRetake={onOpenRetake}
          isFullscreen={previewFullscreen.isFullscreen}
          onToggleFullscreen={previewFullscreen.toggleFullscreen}
        />
        <PreviewFullscreenTransport
          videoRef={videoRef}
          isFullscreen={previewFullscreen.isFullscreen}
          isVideoMedia={isLibraryVideo || isJobVideo}
          onExitFullscreen={previewFullscreen.exitFullscreen}
          onTogglePlay={onTogglePlay}
          timelineTimeSec={playheadSec}
          timelineDurationSec={sceneEndSec}
          timelinePlaying={timelinePlaying}
          onSeekLocalTime={(localSec) => {
            if (!onPlayheadChange) return;
            onPlayheadChange(localSec + timelineVideoOffset);
          }}
          onRetake={onOpenRetake}
          retakeActive={retakeActive}
        />
      </div>

      {onCancelRender || inlineActions ? (
        <div className="row-actions" style={{ marginTop: 8 }}>
          {inlineActions && showingLibrary && (
            <button
              type="button"
              className="ghost"
              data-testid="live-preview-clear-library"
              title="Clear library asset from the Preview Monitor"
              aria-label="Clear library asset from the Preview Monitor"
              onClick={() => onClearLibraryAsset?.()}
            >
              Clear library preview
            </button>
          )}
          {inlineActions ? (
            <button
              type="button"
              className="ghost"
              title={hideOverlay ? "Show status overlays on the Preview Monitor" : "Hide status overlays on the Preview Monitor"}
              aria-label={hideOverlay ? "Show status overlays on the Preview Monitor" : "Hide status overlays on the Preview Monitor"}
              onClick={() => setHideOverlay(!hideOverlay)}
            >
              {hideOverlay ? "Show Overlay" : "Hide Overlay"}
            </button>
          ) : null}
          {inlineActions ? (
            <button
              type="button"
              className="ghost"
              title={pauseUpdates ? "Resume live preview frame updates" : "Pause live preview frame updates"}
              aria-label={pauseUpdates ? "Resume live preview frame updates" : "Pause live preview frame updates"}
              onClick={() => setPauseUpdates(!pauseUpdates)}
            >
              {pauseUpdates ? "Resume Updates" : "Pause Preview Updates"}
            </button>
          ) : null}
          {(onCancelRender || (canCancel && activeJob)) && null}
          {inlineActions && canSaveFrame && activeJob && (
            <button
              type="button"
              title="Save the current preview frame to Project Assets"
              aria-label="Save the current preview frame to Project Assets"
              onClick={async () => {
                await api.savePreviewFrame(activeJob.id, project.id, `${scene?.name || "scene"}_preview`);
                setAnnounce("Preview frame saved to Assets.");
              }}
            >
              Save Preview Frame
            </button>
          )}
        </div>
      ) : null}
      {announce && (
        <p className="scene-meta" role="status">
          {announce}
        </p>
      )}
    </div>
  );
}

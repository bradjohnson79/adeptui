import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Job, Project, Scene } from "../types";
import { api } from "../api";
import { apiUrl } from "../runtime/apiBase";
import { useProjectJobs } from "../runtime/projectJobsStore";
import { aspectCssValue } from "../workspacePrefs";
import { PanelHeading } from "./HelpTip";
import type { PreviewComposition } from "./timeline-master/TimelinePreviewComposer";
import { localGenerationFailureCopy, previewMonitorPhase, resolvePreviewJobId } from "./livePreviewFailure";

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
};

export function LivePreviewMonitor({
  project,
  scene,
  fitMode = "contain",
  libraryAsset = null,
  onClearLibraryAsset,
  playheadSec,
  onPlayheadChange,
  inlineActions = true,
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
  onDismissFailure,
  onRetry,
}: {
  project: Project;
  scene?: Scene;
  fitMode?: "contain" | "cover" | "none";
  /** Real library asset selected from Assets tray — shown in the monitor (no mock). */
  libraryAsset?: Asset | null;
  onClearLibraryAsset?: () => void;
  /** Shared timeline playhead — syncs video scrub with Director Tracks. */
  playheadSec?: number;
  onPlayheadChange?: (t: number) => void;
  /** When false, no buttons render inside the Preview Monitor pane. */
  inlineActions?: boolean;
  hideOverlay?: boolean;
  onHideOverlayChange?: (value: boolean) => void;
  pauseUpdates?: boolean;
  onPauseUpdatesChange?: (value: boolean) => void;
  /** Notifies parent of actionable chrome state for external control rows. */
  onChromeStateChange?: (state: {
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
  }) => void;
  /** Authoritative composition resolved by TimelinePreviewComposer. */
  composition?: PreviewComposition;
  /** Creator acknowledgment of a terminal failure — clears the failed overlay. */
  onDismissFailure?: (jobId: string) => void;
  /** Re-queue via the existing Timeline generate path — not a parallel payload. */
  onRetry?: () => void;
}) {
  const { t } = useTranslation("timeline");
  const composed = composition;
  const projectJobs = useProjectJobs(composed ? undefined : project.id);
  const jobs = composed ? [] : projectJobs.jobs;
  const jobsRef = useRef<Job[]>([]);
  jobsRef.current = jobs;
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [seq, setSeq] = useState(0);
  const [hideOverlayLocal, setHideOverlayLocal] = useState(false);
  const [pauseUpdatesLocal, setPauseUpdatesLocal] = useState(false);
  const [announce, setAnnounce] = useState("");
  const objectUrlRef = useRef<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const syncingFromPropRef = useRef(false);

  const hideOverlay = hideOverlayProp ?? hideOverlayLocal;
  const pauseUpdates = pauseUpdatesProp ?? pauseUpdatesLocal;
  const setHideOverlay = (value: boolean) => {
    if (onHideOverlayChange) onHideOverlayChange(value);
    else setHideOverlayLocal(value);
  };
  const setPauseUpdates = (value: boolean) => {
    if (onPauseUpdatesChange) onPauseUpdatesChange(value);
    else setPauseUpdatesLocal(value);
  };

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
      jobs.find((j) => j.scene_id === scene?.id) ||
      null;

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
      if (scene?.lipsync_output_path || scene?.output_path) return "complete";
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
      setAnnounce(
        `Previewing @${libraryAsset.tag || libraryAsset.filename} (${libraryAsset.kind}) from Library.`,
      );
    }
  }, [libraryAsset]);

  useEffect(() => {
    // Jobs list polling is shared via projectJobsStore. This effect only keeps
    // the legacy scene-preview frame fetch on its original cadence.
    if (composed) return;
    let alive = true;
    const tick = async () => {
      if (document.visibilityState === "hidden") return;
      const list = jobsRef.current;
      const job = list.find(
        (j) => j.scene_id === scene?.id && (j.status === "queued" || j.status === "running"),
      );
      if (job && !pauseUpdates) {
        try {
          const p = await api.getJobPreview(job.id);
          if (!alive) return;
          if (p.preview && (p.preview.sequenceNumber || 0) >= seq) {
            setSeq(p.preview.sequenceNumber || seq);
            setPreview(p.preview);
          }
        } catch {
          /* ignore */
        }
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

  const finalSrc = scene?.lipsync_output_path
    ? api.mediaUrl(scene.lipsync_output_path)
    : scene?.output_path
      ? api.mediaUrl(scene.output_path)
      : "";
  const sourceStill = scene?.start_asset_id ? api.assetUrl(scene.start_asset_id) : "";
  const previewSrc = preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");

  // Resolve mediaSrc from the composition when present; otherwise legacy.
  const mediaSrc = composed
    ? composed.kind === "library"
      ? composed.src
      : composed.kind === "final_output"
        ? composed.src
        : composed.kind === "generation_draft"
          ? composed.previewSrc || composed.sourceStill || finalSrc || sourceStill
          : composed.kind === "preparing"
            ? sourceStill || finalSrc
            : composed.kind === "timeline_frame"
              ? composed.visualSrc
              : composed.kind === "failed" || composed.kind === "cancelled"
                ? composed.previewSrc || finalSrc || sourceStill
                : finalSrc || sourceStill
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
  // Seek to the clip-local visualLocalTime and translate playback time back
  // to global via the offset (clip's global start = playhead - local).
  const timelineVideoLocalTime =
    composed?.kind === "timeline_frame" ? composed.visualLocalTime : null;
  const timelineVideoOffset =
    isTimelineFrameVideo && playheadSec != null && timelineVideoLocalTime != null
      ? playheadSec - timelineVideoLocalTime
      : 0;
  const videoTargetTime =
    isTimelineFrameVideo && timelineVideoLocalTime != null ? timelineVideoLocalTime : playheadSec;

  useEffect(() => {
    const v = videoRef.current;
    if (!v || videoTargetTime == null || Number.isNaN(videoTargetTime)) return;
    if (Math.abs(v.currentTime - videoTargetTime) > 0.04) {
      syncingFromPropRef.current = true;
      try {
        v.currentTime = videoTargetTime;
      } catch {
        /* ignore seek before metadata */
      }
    }
  }, [videoTargetTime, mediaSrc]);

  const capsUnsupported =
    activeJob &&
    String(scene?.engine || "").startsWith("fal_") &&
    !previewSrc;

  const canCancel = Boolean(activeJob && (activeJob.status === "queued" || activeJob.status === "running"));
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
        if (activeJob) void api.cancelJob(activeJob.id);
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
    project.id,
    scene?.name,
    onClearLibraryAsset,
  ]);

  const phase = previewMonitorPhase(monitorState);
  const failureCopy =
    monitorState === "failed"
      ? localGenerationFailureCopy({ id: activeJob?.id, jobId: activeJob?.jobId, internalJobId: activeJob?.internalJobId, message: activeJob?.message, stage: activeJob?.stage, status: activeJob?.status, reasonCode: activeJob?.reasonCode, errorCode: activeJob?.errorCode, errorMessage: activeJob?.errorMessage, historyJson: activeJob?.history_json })
      : null;

  return (
    <div className="panel live-preview-monitor" data-testid="live-preview-monitor" data-preview-state={phase}>
      <PanelHeading
        title={t("previewMonitor")}
        tip="Click a Library asset to preview it here. During renders, live generation frames appear when the engine provides them."
      />
      <div className="live-preview-stage" style={{ aspectRatio: aspect, height: "100%" }} data-testid="live-preview-stage">
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
              key={mediaSrc}
              src={mediaSrc}
              controls
              playsInline
              autoPlay={showingLibrary}
              data-testid={showingLibrary ? "live-preview-library-video" : "live-preview-video"}
              style={{ objectFit: fit }}
              onTimeUpdate={(e) => {
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
        ) : (monitorState === "failed" || monitorState === "cancelled") ? (
          // Navy empty fill only — Idle copy must never sit under overlay.bad.
          // Failed/cancelled chrome is the overlay card with real failureCopy.
          <div className="director-stage-empty" data-testid="live-preview-empty-stage" aria-hidden="true" />
        ) : (
          <div className="director-stage-empty">
            <strong>{monitorState === "preparing" ? "Preparing…" : "Idle"}</strong>
            <span>{scene ? scene.name : "Select a scene"}</span>
            <span className="scene-meta">Click a Library image, video, or audio to preview it here.</span>
          </div>
        )}

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

        {showDraft && !hideOverlay && (
          <div className="live-preview-overlay" aria-live="polite">
            <div className="pill warn">LIVE PREVIEW · Draft quality</div>
            <div>
              {scene?.name} — {scene?.engine}
            </div>
            <div className="scene-meta">
              {activeJob?.stage || phase} ·{" "}
              {Math.round((activeJob?.progress || 0) * 100)}%
            </div>
            {capsUnsupported && (
              <div className="scene-meta">
                This engine does not provide intermediate preview frames. Storyboard/source remains until final.
              </div>
            )}
          </div>
        )}

        {monitorState === "failed" && !showingLibrary && failureCopy && (
          <div
            className="live-preview-overlay bad"
            data-testid="live-preview-failed-overlay"
            aria-live="polite"
          >
            <strong data-testid="live-preview-failed-title">{failureCopy.title}</strong>
            <div className="scene-meta" data-testid="live-preview-failed-reason">
              {failureCopy.reason}
            </div>
            <div className="live-preview-failed-actions">
              {onRetry ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="live-preview-retry"
                  title="Retry local generation"
                  aria-label="Retry local generation"
                  onClick={() => onRetry()}
                >
                  Retry
                </button>
              ) : null}
              {onDismissFailure && activeJob ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="live-preview-dismiss-failure"
                  title="Clear this failure message and return to the preview — the job history is kept"
                  onClick={() => onDismissFailure(resolvePreviewJobId(activeJob) || activeJob.id)}
                >
                  Dismiss
                </button>
              ) : null}
            </div>
            {failureCopy.details ? (
              <details className="live-preview-failed-details" data-testid="live-preview-failed-details">
                <summary>Details</summary>
                <pre data-testid="live-preview-failed-diagnostics">{failureCopy.details}</pre>
              </details>
            ) : null}
          </div>
        )}

        {monitorState === "cancelled" && !showingLibrary && (
          <div className="live-preview-overlay" data-testid="live-preview-cancelled-overlay">
            <strong>Render cancelled</strong>
            <div className="scene-meta">Latest draft preview preserved when available. Resume or re-take when ready.</div>
          </div>
        )}

        {composed?.kind === "timeline_frame" && !hideOverlay && composed.promptText && (
          <div
            className="live-preview-overlay timeline-prompt-lower-third"
            aria-live="polite"
            data-testid="timeline-prompt-lower-third"
          >
            <div className="pill">PROMPT{composed.promptLabel ? ` · ${composed.promptLabel}` : ""}</div>
            <div className="timeline-prompt-text">{composed.promptText}</div>
          </div>
        )}
      </div>

      {inlineActions ? (
        <div className="row-actions" style={{ marginTop: 8 }}>
          {showingLibrary && (
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
          <button
            type="button"
            className="ghost"
            title={hideOverlay ? "Show status overlays on the Preview Monitor" : "Hide status overlays on the Preview Monitor"}
            aria-label={hideOverlay ? "Show status overlays on the Preview Monitor" : "Hide status overlays on the Preview Monitor"}
            onClick={() => setHideOverlay(!hideOverlay)}
          >
            {hideOverlay ? "Show Overlay" : "Hide Overlay"}
          </button>
          <button
            type="button"
            className="ghost"
            title={pauseUpdates ? "Resume live preview frame updates" : "Pause live preview frame updates"}
            aria-label={pauseUpdates ? "Resume live preview frame updates" : "Pause live preview frame updates"}
            onClick={() => setPauseUpdates(!pauseUpdates)}
          >
            {pauseUpdates ? "Resume Updates" : "Pause Preview Updates"}
          </button>
          {canCancel && activeJob && (
            <button
              type="button"
              className="danger"
              title="Cancel the active render job"
              aria-label="Cancel the active render job"
              onClick={() => api.cancelJob(activeJob.id)}
            >
              Cancel Render
            </button>
          )}
          {canSaveFrame && activeJob && (
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

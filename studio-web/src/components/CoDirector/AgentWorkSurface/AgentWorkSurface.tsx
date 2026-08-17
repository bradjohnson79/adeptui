/**
 * AgentWorkSurface — the right-pane live execution controller.
 *
 * Spec §18: "The right Co-Director pane becomes a dynamic AGENT WORK SURFACE
 * during execution. Normal mode: Wiki/Notes/Story/... Execution mode: the pane
 * visually presents the real task currently being performed."
 * Spec §20: "Do NOT implement fake animated agent behavior. Every visible
 * Generating/Processing/Saving/Completed/Failed must correspond to actual
 * backend/task state. No fake progress."
 * Spec §21: "Preserve the two-pane interaction: LEFT conversation, RIGHT project/work.
 * The user can talk, observe, intervene, modify instructions while work continues."
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { useCoDirectorSession } from "../CoDirectorSession";
import type {
  ChildJobView,
  WorkSurfaceState,
  SurfaceType,
} from "./types";
import { isAgentWork, isTerminal } from "./types";
import { persistThenOpenSceneCreator } from "../SceneCreator/persistThenOpenSceneCreator";
import { normalizeErsError } from "../SpatialMap/ersErrorMessage";
import "./agentWorkSurface.css";

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 80; // ~4 minutes

/** Surface types that come from the Spatial Map workflow. */
const SPATIAL_SURFACE_TYPES: SurfaceType[] = ["atlas_shot_generation", "ers_generation", "scene_generation"];

/** Honest regenerate-failure copy: the existing look is untouched. */
export const REGENERATE_FAILED_MESSAGE =
  "Regeneration failed — the existing look was not changed.";

/**
 * True when the overlay's poll budget is spent while the execution is still
 * live. The job may legitimately still be running server-side; only the
 * overlay stopped checking. Exposed as pure logic so the honesty contract
 * (paused, not failed) is directly testable.
 */
export function pollPausedFor(
  pack: WorkSurfaceState | null,
  pollAttempts: number,
  maxAttempts: number = MAX_POLL_ATTEMPTS,
): boolean {
  return Boolean(pack && !isTerminal(pack) && pollAttempts >= maxAttempts);
}

export function AgentWorkSurface() {
  const { uiContext, activeExecution, setActiveExecution } = useCoDirectorSession();
  const projectId = uiContext.projectId || activeExecution?.project_id || "";
  const executionId = activeExecution?.execution_id || "";
  const [pack, setPack] = useState<WorkSurfaceState | null>(activeExecution ?? null);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [pollAttempts, setPollAttempts] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const [continueError, setContinueError] = useState<string | null>(null);
  const [continuing, setContinuing] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const [busyFrame, setBusyFrame] = useState<number | null>(null);

  const buildPack = useCallback(
    (res: any): WorkSurfaceState => ({
      mode: "agent_work",
      execution_id: res.execution_id,
      capability: res.capability,
      surface_type: (res.surface_type as SurfaceType) || "",
      status: res.status,
      progress: res.progress,
      focused_artifact_ids: res.result_asset_ids || [],
      child_jobs: (res.child_jobs || []).map((c: any) => ({
        job_id: c.job_id,
        label: c.label || (res.surface_type === "storyboard_generation" ? `Output ${c.child_index + 1}` : `Item ${c.child_index + 1}`),
        status: c.status,
        asset_id: c.asset_id,
        error: c.error,
        progress: c.progress || 0,
        stage: c.stage || "",
        child_index: c.child_index ?? 0,
        metadata: c.metadata || {},
      })),
      result_asset_ids: res.result_asset_ids || [],
      collection_id: res.collection_id,
      error: res.error,
      project_id: projectId,
    }),
    [projectId],
  );

  // Poll the advance endpoint for real execution state.
  const advance = useCallback(async () => {
    if (!projectId || !executionId) return;
    try {
      const res = await api.advanceExecution(projectId, executionId);
      const updated = buildPack(res);
      setPack(updated);
      setActiveExecution(updated);

      if (isTerminal(updated)) {
        return; // Stop polling.
      }
    } catch (err) {
      // Non-fatal — will retry on next interval.
      console.warn("AgentWorkSurface advance failed:", err);
    }
  }, [projectId, executionId, setActiveExecution, buildPack]);

  useEffect(() => {
    if (!projectId || !executionId) return;
    if (!pack || isTerminal(pack)) return;
    if (pollAttempts >= MAX_POLL_ATTEMPTS) return;

    const timer = setTimeout(() => {
      void advance().then(() => setPollAttempts((n) => n + 1));
    }, POLL_INTERVAL_MS);

    return () => clearTimeout(timer);
  }, [pack, projectId, executionId, pollAttempts, advance]);

  // Initial load.
  useEffect(() => {
    if (projectId && executionId) {
      void advance();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, executionId]);

  // Regenerate a single frame — wired to api.regenerateFrame.
  const handleRegenerate = useCallback(
    async (idx: number) => {
      if (!projectId || !executionId || busyFrame !== null) return;
      setBusyFrame(idx);
      setRegenerateError(null);
      try {
        const res = await api.regenerateFrame(projectId, executionId, {
          child_index: idx,
          user_instructions: "",
        });
        const updated = buildPack(res);
        setPack(updated);
        setActiveExecution(updated);
      } catch (err) {
        console.error("Regenerate frame failed:", err);
        setRegenerateError(REGENERATE_FAILED_MESSAGE);
      } finally {
        setBusyFrame(null);
      }
    },
    [projectId, executionId, busyFrame, buildPack, setActiveExecution],
  );

  // Regenerate all frames — issues one regenerate per child job sequentially.
  const handleRegenerateAll = useCallback(async () => {
    if (!projectId || !executionId || !pack) return;
    const indices = pack.child_jobs.map((j) => j.child_index);
    setRegenerateError(null);
    for (const idx of indices) {
      setBusyFrame(idx);
      try {
        const res = await api.regenerateFrame(projectId, executionId, {
          child_index: idx,
          user_instructions: "",
        });
        const updated = buildPack(res);
        setPack(updated);
        setActiveExecution(updated);
      } catch (err) {
        console.error("Regenerate-all failed at frame", idx, err);
        // Any failed frame leaves a visible error; a later success does not
        // silently erase an earlier failure within the same operation.
        setRegenerateError(REGENERATE_FAILED_MESSAGE);
      } finally {
        setBusyFrame(null);
      }
    }
  }, [projectId, executionId, pack, buildPack, setActiveExecution]);

  // Cancel the running execution — wired to api.cancelExecution.
  const handleCancel = useCallback(async () => {
    if (!projectId || !executionId || cancelling) return;
    setCancelling(true);
    try {
      const res = await api.cancelExecution(projectId, executionId);
      const updated = buildPack(res);
      setPack(updated);
      setActiveExecution(updated);
    } catch (err) {
      console.error("Cancel execution failed:", err);
      // Refresh state on failure so UI reflects truth.
      await advance();
    } finally {
      setCancelling(false);
    }
  }, [projectId, executionId, cancelling, buildPack, setActiveExecution, advance]);

  // Dismiss the overlay and restore the underlying tab.
  const handleClose = useCallback(() => {
    setActiveExecution(null);
  }, [setActiveExecution]);

  // Escape key dismisses the overlay when terminal (Law #8 — no trapped UI).
  useEffect(() => {
    if (!pack || !isTerminal(pack)) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [pack, handleClose]);

  const handleContinueToSceneCreator = useCallback(async () => {
    setContinueError(null);
    setContinuing(true);
    try {
      await persistThenOpenSceneCreator({
        projectId,
        sceneId: pack?.scene_id || undefined,
        onGoTab: uiContext.onGoTab,
        onClose: handleClose,
      });
    } catch (err) {
      setContinueError(err instanceof Error ? err.message : "Could not continue to Scene Creator.");
    } finally {
      setContinuing(false);
    }
  }, [handleClose, pack?.scene_id, projectId, uiContext.onGoTab]);

  if (!pack || !isAgentWork(pack)) {
    return null;
  }

  const surfaceType = pack.surface_type;
  const completed = pack.child_jobs.filter((c) => c.status === "completed").length;
  const total = pack.child_jobs.length;
  const failed = pack.child_jobs.filter((c) => c.status === "failed").length;
  const nonTerminal = !isTerminal(pack);
  const pollPaused = pollPausedFor(pack, pollAttempts);

  const cancelLabel = cancelling ? "Cancelling…" : pack.status === "cancelled" ? "Cancelled" : "Cancel";

  return (
    <div className="agent-work-surface" data-testid="agent-work-surface" data-surface={surfaceType}>
      <div className="agent-work-surface__header">
        <h3 className="agent-work-surface__title">
          {surfaceType === "storyboard_generation" ? "STORYBOARD GENERATION" :
           surfaceType === "image_generation" ? "CREATING IMAGE" :
           surfaceType === "casting_candidates" ? "CASTING CANDIDATES" :
           surfaceType === "voice_generation" ? "VOICE GENERATION" :
           surfaceType === "atlas_shot_generation" ? "ATLAS SHOT" :
           surfaceType === "ers_generation" ? "ENVIRONMENT REFERENCE SHEET" :
           surfaceType === "scene_generation" ? "SCENE GENERATION" :
           "WORKING"}
        </h3>
        {pack.character_id && (
          <span className="agent-work-surface__subtitle muted">
            {pack.character_id}
          </span>
        )}
        <div className="agent-work-surface__progress">
          <span className="agent-work-surface__progress-count">
            {surfaceType === "storyboard_generation"
              ? `${completed} / ${total} Outputs Complete`
              : `${completed} / ${total}${total > 1 ? " Complete" : ""}`}
          </span>
          {failed > 0 && (
            <span className="agent-work-surface__failed-count">
              {failed} failed
            </span>
          )}
          {pack.status === "running" || pack.status === "queued" ? (
            <span className="agent-work-surface__spinner" aria-label="Working" />
          ) : pack.status === "completed" ? (
            <span className="agent-work-surface__done">✓ Complete</span>
          ) : pack.status === "failed" ? (
            <span className="agent-work-surface__error">Failed</span>
          ) : pack.status === "cancelled" ? (
            <span className="agent-work-surface__cancelled">Cancelled</span>
          ) : null}
          {nonTerminal && (
            <button
              type="button"
              className="ghost agent-work-surface__cancel-btn"
              onClick={handleCancel}
              disabled={cancelling || pack.status === "cancelled"}
              data-testid="agent-work-cancel"
            >
              {cancelLabel}
            </button>
          )}
          {isTerminal(pack) && (
            <button
              type="button"
              className="agent-work-surface__close-x"
              onClick={handleClose}
              aria-label="Close result and return to workspace"
              data-testid="agent-work-close-x"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <TaskChecklist childJobs={pack.child_jobs} />

      <div className="agent-work-surface__body">
        {surfaceType === "storyboard_generation" && (
          <StoryboardFrameGrid
            childJobs={pack.child_jobs}
            expandedJob={expandedJob}
            onToggle={setExpandedJob}
            onRegenerate={handleRegenerate}
            busyFrame={busyFrame}
          />
        )}
        {surfaceType === "image_generation" && (
          <ImageGenerationView
            childJobs={pack.child_jobs}
            onRegenerate={handleRegenerate}
            busyFrame={busyFrame}
          />
        )}
        {surfaceType === "casting_candidates" && (
          <CastingCandidatesView childJobs={pack.child_jobs} />
        )}
        {surfaceType === "voice_generation" && (
          <VoiceGenerationView childJobs={pack.child_jobs} />
        )}
        {!["storyboard_generation", "image_generation", "casting_candidates", "voice_generation"].includes(surfaceType) && (
          <GenericJobList
            childJobs={pack.child_jobs}
            expandedJob={expandedJob}
            onToggle={setExpandedJob}
          />
        )}
      </div>

      {isTerminal(pack) && (
        <div className="agent-work-surface__action-row" data-testid="agent-work-actions">
          {surfaceType === "storyboard_generation" && total > 1 && (
            <button
              type="button"
              className="ghost"
              onClick={handleRegenerateAll}
              disabled={busyFrame !== null}
              data-testid="agent-work-regenerate-all"
            >
              Regenerate All
            </button>
          )}
          {SPATIAL_SURFACE_TYPES.includes(surfaceType) && pack.result_asset_ids.length > 0 && (
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => {
                if (surfaceType === "atlas_shot_generation") {
                  handleClose();
                  return;
                }
                void handleContinueToSceneCreator();
              }}
              disabled={continuing}
              data-testid="agent-work-continue"
            >
              {surfaceType === "atlas_shot_generation"
                ? "Continue to Spatial Map"
                : continuing
                  ? "Opening Scene Creator…"
                  : "Continue to Scene Creator"}
            </button>
          )}
          {pack.result_asset_ids.length > 0 && (
            <button
              type="button"
              className="ghost"
              onClick={() => uiContext.onGoTab?.("library")}
            >
              Open in Library
            </button>
          )}
          {pack.collection_id && surfaceType === "storyboard_generation" && (
            <button
              type="button"
              className="ghost"
              onClick={() => uiContext.onGoTab?.("timeline")}
            >
              Send to Timeline
            </button>
          )}
          {pack.collection_id && surfaceType === "scene_generation" && (
            <button
              type="button"
              className="ghost"
              onClick={() => uiContext.onGoTab?.("timeline")}
            >
              Send to Timeline
            </button>
          )}
          <button
            type="button"
            className="ghost"
            onClick={handleClose}
            data-testid="agent-work-close"
          >
            Close
          </button>
        </div>
      )}
      {continueError ? (
        <p className="agent-work-surface__error-detail" role="alert" data-testid="agent-work-continue-error">
          {continueError}
        </p>
      ) : null}

      {regenerateError ? (
        <p className="agent-work-surface__error-detail" role="alert" data-testid="agent-work-regenerate-error">
          {regenerateError}
        </p>
      ) : null}

      {pollPaused && (
        <div className="agent-work-surface__poll-paused" role="status" data-testid="agent-work-poll-paused">
          <span>
            Live progress paused — generation may still be running. The overlay stopped checking so it does not
            poll forever; the job is not marked failed.
          </span>
          <button
            type="button"
            className="ghost"
            onClick={() => setPollAttempts(0)}
            data-testid="agent-work-resume-poll"
          >
            Resume checking
          </button>
        </div>
      )}

      {pack.error && (
        <div className="agent-work-surface__error-detail" role="alert">
          {pack.surface_type === "ers_generation" ? normalizeErsError(pack.error) : pack.error}
        </div>
      )}
    </div>
  );
}

function TaskChecklist({ childJobs }: { childJobs: ChildJobView[] }) {
  if (!childJobs.length) return null;
  return (
    <div className="agent-work-surface__checklist" data-testid="agent-work-checklist">
      <div className="agent-work-surface__checklist-title">Progress</div>
      {childJobs.map((job) => {
        const icon =
          job.status === "completed" ? "✓" :
          job.status === "failed" ? "✗" :
          job.status === "running" || job.status === "preview" ? "●" :
          "○";
        const showSpinner = job.status === "running" || job.status === "preview";
        return (
          <div
            key={job.job_id}
            className={`agent-work-surface__checklist-item ${job.status}`}
            data-testid={`agent-work-checklist-${job.child_index}`}
          >
            <span className="agent-work-surface__check-icon">
              {showSpinner ? (
                <span className="agent-work-surface__check-spinner" aria-label="In progress" />
              ) : (
                icon
              )}
            </span>
            <span className="agent-work-surface__check-label">{job.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function StoryboardFrameGrid({
  childJobs,
  expandedJob,
  onToggle,
  onRegenerate,
  busyFrame,
}: {
  childJobs: ChildJobView[];
  expandedJob: string | null;
  onToggle: (id: string | null) => void;
  onRegenerate: (frameIndex: number) => void;
  busyFrame: number | null;
}) {
  return (
    <div className="agent-work-surface__storyboard-grid" data-testid="storyboard-frame-grid">
      {childJobs.map((job) => (
          <FrameCard
            key={job.job_id}
            job={job}
            onToggle={() => onToggle(expandedJob === job.job_id ? null : job.job_id)}
            onRegenerate={() => onRegenerate(job.child_index)}
            busy={busyFrame === job.child_index}
          />
      ))}
    </div>
  );
}

function ImageGenerationView({
  childJobs,
  onRegenerate,
  busyFrame,
}: {
  childJobs: ChildJobView[];
  onRegenerate: (frameIndex: number) => void;
  busyFrame: number | null;
}) {
  return (
    <div className="agent-work-surface__image-view" data-testid="image-generation-view">
      {childJobs.map((job) => (
        <FrameCard
          key={job.job_id}
          job={job}
          onToggle={() => {}}
          onRegenerate={() => onRegenerate(job.child_index)}
          busy={busyFrame === job.child_index}
        />
      ))}
    </div>
  );
}

function CastingCandidatesView({ childJobs }: { childJobs: ChildJobView[] }) {
  return (
    <div className="agent-work-surface__candidates" data-testid="casting-candidates-view">
      {childJobs.map((job) => (
        <FrameCard key={job.job_id} job={job} onToggle={() => {}} />
      ))}
    </div>
  );
}

function VoiceGenerationView({ childJobs }: { childJobs: ChildJobView[] }) {
  return (
    <div className="agent-work-surface__voice-view" data-testid="voice-generation-view">
      {childJobs.map((job) => {
        const statusText =
          job.status === "completed" ? null :
          job.status === "running" || job.status === "preview" ? (job.stage || "Generating…") :
          job.status === "failed" ? "Failed" :
          job.status === "cancelled" ? "Cancelled" :
          "Queued";
        return (
          <div
            key={job.job_id}
            className={`agent-work-surface__voice-slot ${job.status}`}
            data-testid={`voice-slot-${job.child_index}`}
          >
            <div className="agent-work-surface__voice-slot-label">{job.label}</div>
            {job.asset_id ? (
              <audio
                className="agent-work-surface__voice-audio"
                controls
                src={api.assetUrl(job.asset_id)}
                data-testid={`voice-audio-${job.child_index}`}
              />
            ) : (
              <span
                className={`agent-work-surface__voice-slot-status ${job.status === "failed" ? "failed" : ""}`}
              >
                {statusText}
              </span>
            )}
            {job.error && job.status === "failed" && (
              <div className="agent-work-surface__frame-error">{job.error}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function GenericJobList({
  childJobs,
  expandedJob,
  onToggle,
}: {
  childJobs: ChildJobView[];
  expandedJob: string | null;
  onToggle: (id: string | null) => void;
}) {
  return (
    <div className="agent-work-surface__generic-list">
      {childJobs.map((job) => (
          <FrameCard
            key={job.job_id}
            job={job}
            onToggle={() => onToggle(expandedJob === job.job_id ? null : job.job_id)}
          />
      ))}
    </div>
  );
}

function FrameCard({
  job,
  onToggle,
  onRegenerate,
  busy,
}: {
  job: ChildJobView;
  onToggle: () => void;
  onRegenerate?: () => void;
  busy?: boolean;
}) {
  void onToggle;
  const hasImage = !!job.asset_id;
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";
  const isRunning = job.status === "running" || job.status === "queued" || job.status === "preview";

  const handleRetry = () => {
    if (onRegenerate) {
      onRegenerate();
    }
  };

  return (
    <div
      className={`agent-work-surface__frame-card ${job.status}`}
      data-testid={`frame-card-${job.child_index}`}
      data-state={job.status}
    >
      <div className="agent-work-surface__frame-preview">
        {hasImage ? (
          <img
            src={api.assetUrl(job.asset_id!)}
            alt={job.label}
            className="agent-work-surface__frame-image"
          />
        ) : (
          <div className="agent-work-surface__frame-placeholder">
            {isFailed ? (
              <span className="agent-work-surface__frame-failed">Failed</span>
            ) : isRunning ? (
              <span className="agent-work-surface__frame-generating">
                {busy ? "Regenerating…" : (job.stage || "Generating…")}
              </span>
            ) : (
              <span className="muted">Queued</span>
            )}
          </div>
        )}
      </div>
      <div className="agent-work-surface__frame-label">
        <span>{job.label}</span>
        {isCompleted && onRegenerate && (
          <button
            type="button"
            className="ghost agent-work-surface__regen-btn"
            onClick={onRegenerate}
            disabled={busy}
            data-testid={`frame-regen-${job.child_index}`}
          >
            {busy ? "Regenerating…" : "Regenerate"}
          </button>
        )}
        {isFailed && (
          <button
            type="button"
            className="ghost agent-work-surface__retry-btn"
            onClick={handleRetry}
            disabled={busy}
            data-testid={`frame-retry-${job.child_index}`}
          >
            {busy ? "Retrying…" : "Retry"}
          </button>
        )}
      </div>
      {job.error && isFailed && (
        <div className="agent-work-surface__frame-error">{job.error}</div>
      )}
    </div>
  );
}

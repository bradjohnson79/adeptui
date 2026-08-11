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
import "./agentWorkSurface.css";

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 80; // ~4 minutes

export function AgentWorkSurface() {
  const { uiContext, activeExecution, setActiveExecution } = useCoDirectorSession();
  const projectId = uiContext.projectId || activeExecution?.project_id || "";
  const executionId = activeExecution?.execution_id || "";
  const [pack, setPack] = useState<WorkSurfaceState | null>(activeExecution ?? null);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [pollAttempts, setPollAttempts] = useState(0);

  // Poll the advance endpoint for real execution state.
  const advance = useCallback(async () => {
    if (!projectId || !executionId) return;
    try {
      const res = await api.advanceExecution(projectId, executionId);
      const updated: WorkSurfaceState = {
        mode: "agent_work",
        execution_id: res.execution_id,
        capability: res.capability,
        surface_type: (res.surface_type as SurfaceType) || "",
        status: res.status,
        progress: res.progress,
        focused_artifact_ids: res.result_asset_ids || [],
        child_jobs: (res.child_jobs || []).map((c: any) => ({
          job_id: c.job_id,
          label: c.label || `Frame ${c.child_index + 1}`,
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
      };
      setPack(updated);
      setActiveExecution(updated);

      if (isTerminal(updated)) {
        return; // Stop polling.
      }
    } catch (err) {
      // Non-fatal — will retry on next interval.
      console.warn("AgentWorkSurface advance failed:", err);
    }
  }, [projectId, executionId, setActiveExecution]);

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

  if (!pack || !isAgentWork(pack)) {
    return null;
  }

  const surfaceType = pack.surface_type;
  const completed = pack.child_jobs.filter((c) => c.status === "completed").length;
  const total = pack.child_jobs.length;
  const failed = pack.child_jobs.filter((c) => c.status === "failed").length;

  return (
    <div className="agent-work-surface" data-testid="agent-work-surface" data-surface={surfaceType}>
      <div className="agent-work-surface__header">
        <h3 className="agent-work-surface__title">
          {surfaceType === "storyboard_generation" ? "STORYBOARD GENERATION" :
           surfaceType === "image_generation" ? "CREATING IMAGE" :
           surfaceType === "casting_candidates" ? "CASTING CANDIDATES" :
           surfaceType === "voice_generation" ? "VOICE GENERATION" :
           "WORKING"}
        </h3>
        {pack.character_id && (
          <span className="agent-work-surface__subtitle muted">
            {pack.character_id}
          </span>
        )}
        <div className="agent-work-surface__progress">
          <span className="agent-work-surface__progress-count">
            {completed} / {total} {total > 1 ? "Complete" : ""}
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
        </div>
      </div>

      <div className="agent-work-surface__body">
        {surfaceType === "storyboard_generation" && (
          <StoryboardFrameGrid
            childJobs={pack.child_jobs}
            expandedJob={expandedJob}
            onToggle={setExpandedJob}
            onRegenerate={(_idx) => {
              void _idx;
            }}
          />
        )}
        {surfaceType === "image_generation" && (
          <ImageGenerationView childJobs={pack.child_jobs} />
        )}
        {surfaceType === "casting_candidates" && (
          <CastingCandidatesView childJobs={pack.child_jobs} />
        )}
        {!["storyboard_generation", "image_generation", "casting_candidates"].includes(surfaceType) && (
          <GenericJobList
            childJobs={pack.child_jobs}
            expandedJob={expandedJob}
            onToggle={setExpandedJob}
          />
        )}
      </div>

      {isTerminal(pack) && (
        <div className="agent-work-surface__footer">
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
              onClick={() => uiContext.onGoTab?.("library")}
            >
              Send to Timeline
            </button>
          )}
          <button
            type="button"
            className="ghost"
            onClick={() => setActiveExecution(null)}
          >
            Done
          </button>
        </div>
      )}

      {pack.error && (
        <div className="agent-work-surface__error-detail" role="alert">
          {pack.error}
        </div>
      )}
    </div>
  );
}

function StoryboardFrameGrid({
  childJobs,
  expandedJob,
  onToggle,
  onRegenerate,
}: {
  childJobs: ChildJobView[];
  expandedJob: string | null;
  onToggle: (id: string | null) => void;
  onRegenerate: (frameIndex: number) => void;
}) {
  return (
    <div className="agent-work-surface__storyboard-grid" data-testid="storyboard-frame-grid">
      {childJobs.map((job) => (
          <FrameCard
            key={job.job_id}
            job={job}
            onToggle={() => onToggle(expandedJob === job.job_id ? null : job.job_id)}
            onRegenerate={() => onRegenerate(job.child_index)}
          />
      ))}
    </div>
  );
}

function ImageGenerationView({ childJobs }: { childJobs: ChildJobView[] }) {
  return (
    <div className="agent-work-surface__image-view" data-testid="image-generation-view">
      {childJobs.map((job) => (
        <FrameCard key={job.job_id} job={job} onToggle={() => {}} />
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
}function GenericJobList({
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
}: {
  job: ChildJobView;
  onToggle: () => void;
  onRegenerate?: () => void;
}) {
  void onToggle;
  const hasImage = !!job.asset_id;
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";
  const isRunning = job.status === "running" || job.status === "queued" || job.status === "preview";

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
                {job.stage || "Generating…"}
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
          >
            Regenerate
          </button>
        )}
        {isFailed && (
          <button
            type="button"
            className="ghost agent-work-surface__retry-btn"
            onClick={onToggle}
          >
            Retry
          </button>
        )}
      </div>
      {job.error && isFailed && (
        <div className="agent-work-surface__frame-error">{job.error}</div>
      )}
    </div>
  );
}

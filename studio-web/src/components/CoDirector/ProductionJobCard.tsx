import type { CSSProperties } from "react";

export type ProductionJobCardModel = {
  jobId: string;
  operation?: string | null;
  sceneId?: string | null;
  shotId?: string | null;
  workflowKey?: string | null;
  provider?: string | null;
  state?: string | null;
  stage?: string | null;
  progress?: number | null;
  progressMode?: "numeric" | "stage" | null;
  cancellationState?: string | null;
  retryAvailable?: boolean;
  failureReason?: string | null;
  resultLink?: string | null;
};

/**
 * Compact expandable production job card for Co-Director (W6P-8 / W6P-11).
 * Never invents numeric progress — stage-only when progress is absent.
 */
export function ProductionJobCard({
  job,
  expanded,
  onToggle,
  onCancel,
  onRetry,
}: {
  job: ProductionJobCardModel;
  expanded: boolean;
  onToggle: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
}) {
  const cancelling =
    job.cancellationState === "cancel_requested" ||
    job.cancellationState === "cancelling" ||
    job.state === "cancelling";
  const cancelled = job.state === "cancelled" || job.cancellationState === "cancelled";
  const failed = job.state === "failed";
  const completed = job.state === "completed";

  const barStyle: CSSProperties | undefined =
    job.progressMode === "numeric" && typeof job.progress === "number"
      ? { width: `${Math.max(0, Math.min(100, job.progress * 100))}%` }
      : undefined;

  return (
    <section
      className="codirector-production-job-card"
      data-testid={`codirector-job-card-${job.jobId}`}
      data-state={job.state || "unknown"}
      aria-label={`Production job ${job.operation || job.jobId}`}
    >
      <button type="button" className="ghost codirector-job-card-header" onClick={onToggle}>
        <span>
          {job.operation || "Production job"}
          {job.stage ? ` · ${job.stage}` : ""}
        </span>
        <span className="muted">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded && (
        <div className="codirector-job-card-body">
          <dl className="codirector-proposal-meta">
            <div>
              <dt>Status</dt>
              <dd>{job.state || "—"}</dd>
            </div>
            <div>
              <dt>Workflow</dt>
              <dd>{job.workflowKey || "—"}</dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{job.provider || "local"}</dd>
            </div>
            <div>
              <dt>Scene / shot</dt>
              <dd>
                {job.sceneId || "—"}
                {job.shotId ? ` / ${job.shotId}` : ""}
              </dd>
            </div>
          </dl>
          {barStyle ? (
            <div className="codirector-job-progress" aria-valuenow={job.progress ?? 0} role="progressbar">
              <div style={barStyle} />
            </div>
          ) : (
            <p className="muted">Stage-based progress · {job.stage || "Queued"}</p>
          )}
          {failed && job.failureReason ? (
            <p className="codirector-proposal-warning" role="alert">
              {job.failureReason}
            </p>
          ) : null}
          {cancelled ? <p className="muted">Cancelled — no completion after cancel.</p> : null}
          <div className="row-actions">
            {!completed && !cancelled && onCancel ? (
              <button type="button" className="ghost danger" disabled={cancelling} onClick={onCancel}>
                {cancelling ? "Cancelling…" : "Cancel"}
              </button>
            ) : null}
            {job.retryAvailable && onRetry ? (
              <button type="button" className="ghost" onClick={onRetry}>
                Retry
              </button>
            ) : null}
            {job.resultLink ? (
              <a className="ghost" href={job.resultLink}>
                Open result
              </a>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}

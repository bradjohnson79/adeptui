import { useEffect, useState, type CSSProperties } from "react";
import { api } from "../../api";
import { LibraryQuickPreviewModal, type LibraryQuickPreviewAsset } from "../library/LibraryQuickPreviewModal";
import type { CoDirectorImageJob } from "./types";

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

function isFinishedJob(status: string): boolean {
  return ["completed", "complete", "done", "succeeded", "success"].includes(status.toLowerCase());
}

function jobPercent(progress: number | null | undefined, status: string): number {
  if (isFinishedJob(status)) return 100;
  if (typeof progress !== "number" || !Number.isFinite(progress)) return 0;
  const pct = progress > 1 ? progress : progress * 100;
  return Math.max(0, Math.min(99, Math.round(pct)));
}

function stageLabel(stage: string, status: string): string {
  const state = status.toLowerCase();
  if (isFinishedJob(status)) return "Done";
  if (state === "failed") return "Didn't finish";
  if (state === "cancelled") return "Cancelled";
  const key = stage.replace(/\s+/g, "").toLowerCase();
  const labels: Record<string, string> = {
    queued: "Waiting to start",
    preparing: "Getting ready",
    loadingmodels: "Loading the model",
    sampling: "Drawing",
    validating: "Checking the picture",
    saving: "Saving",
    registeringasset: "Saving",
  };
  if (labels[key]) return labels[key];
  const spaced = stage.replace(/([a-z])([A-Z])/g, "$1 $2").trim();
  return spaced || "Waiting to start";
}

function finishedStillUrl(
  row: { output_path?: string | null; params_json?: string | null },
  projectId: string,
): string {
  try {
    const params = JSON.parse(row.params_json || "{}") as {
      output_asset_id?: string;
      outputAssetIds?: string[];
    };
    const assetId = String(params.output_asset_id || params.outputAssetIds?.[0] || "").trim();
    if (assetId) {
      const fromAsset = api.assetUrl(assetId, null, projectId);
      if (fromAsset) return fromAsset;
    }
  } catch {
    /* The saved file path is the fallback. */
  }
  return api.mediaUrl(row.output_path);
}

function previewUrl(preview: { localPath?: string; sequenceNumber?: number } | null | undefined): string {
  const path = String(preview?.localPath || "").trim();
  if (!path) return "";
  const base = api.mediaUrl(path);
  if (!base) return "";
  const rev = Number(preview?.sequenceNumber || 0);
  const join = base.includes("?") ? "&" : "?";
  return `${base}${join}t=${rev}`;
}

/**
 * Live still card for every local image model Co-Director starts.
 * Polls the existing job and preview endpoints. The percentage stays below
 * 100 until the job itself says it is done.
 */
export function ImageJobProgressCard({
  job,
  projectId,
}: {
  job: CoDirectorImageJob;
  projectId: string;
}) {
  const [status, setStatus] = useState("queued");
  const [stage, setStage] = useState("Queued");
  const [progress, setProgress] = useState<number | null>(0);
  const [thumb, setThumb] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<LibraryQuickPreviewAsset | null>(null);
  const pct = jobPercent(progress, status);
  const frame = [job.aspect, job.width > 0 && job.height > 0 ? `${job.width} × ${job.height}` : ""]
    .filter(Boolean)
    .join(" · ");

  useEffect(() => {
    let stop = false;
    let timer = 0;
    const tick = async () => {
      try {
        const row = await api.getJob(job.jobId);
        if (stop) return;
        const nextStatus = String(row?.status || "queued");
        const finished = isFinishedJob(nextStatus);
        setStage(String(row?.stage || ""));
        setProgress(typeof row?.progress === "number" ? row.progress : null);
        const live = await api.getJobPreview(job.jobId);
        let picture = previewUrl(live?.preview);
        if (finished) {
          const full = finishedStillUrl(row, projectId);
          if (full) picture = full;
        }
        if (!stop) setThumb(picture);
        if (finished && !picture) {
          setStatus("failed");
          setNote("The picture finished without a visible image.");
        } else {
          setStatus(nextStatus);
          if (nextStatus.toLowerCase() === "failed") {
            const message = String(row?.message || "").trim();
            setNote(message.slice(0, 240));
          }
        }
        const done = finished || ["failed", "cancelled"].includes(nextStatus.toLowerCase());
        if (done || stop) return;
      } catch {
        if (stop) return;
      }
      if (!stop) timer = window.setTimeout(() => void tick(), 2000);
    };
    void tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [job.jobId, projectId]);

  const failed = status.toLowerCase() === "failed";

  return (
    <section
      className={`codirector-image-job${failed ? " is-failed" : ""}`}
      data-testid="codirector-image-job-card"
      data-job-id={job.jobId}
    >
      <div className="codirector-image-job-layout">
        {thumb ? (
          <button
            type="button"
            className="codirector-concept-thumb"
            data-testid="codirector-image-job-preview"
            aria-label="Open the preview larger"
            onClick={() =>
              setPreview({
                id: job.jobId,
                kind: "image",
                name: job.modelLabel || "Still in progress",
                previewSrc: thumb,
              })
            }
          >
            <img src={thumb} alt="Preview of the still" />
          </button>
        ) : (
          <div className="codirector-concept-thumb codirector-job-thumb-pending" data-testid="codirector-image-job-preview">
            Preview appears as it draws
          </div>
        )}
        <div>
          <p className="codirector-image-job-title">{job.modelLabel || "Local image model"}</p>
          <dl className="codirector-proposal-meta">
            <div>
              <dt>Frame</dt>
              <dd>{frame || "—"}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{stageLabel(stage, status)}</dd>
            </div>
          </dl>
          <div
            className="codirector-exec-progress"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            data-testid="codirector-image-job-progress"
          >
            <div className="codirector-exec-progress-bar" style={{ width: `${pct}%` }} />
          </div>
          <p className="muted">{pct}%</p>
          {failed && note ? (
            <p className="codirector-proposal-warning" role="alert">
              {note}
            </p>
          ) : null}
        </div>
      </div>
      <LibraryQuickPreviewModal asset={preview} projectId={projectId} onClose={() => setPreview(null)} />
    </section>
  );
}

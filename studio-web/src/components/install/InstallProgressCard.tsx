import { useState } from "react";
import { Button } from "../ui";
import {
  installJobPercent,
  installJobStateLabel,
  type InstallJob,
  type InstallRecoveryAction,
} from "../../contracts/installJobs";
import { formatBytes, formatDuration } from "../../setup/helpers";
import { InstallErrorPanel } from "./InstallErrorPanel";
import "./install-progress.css";

function stateTone(job: InstallJob) {
  if (job.stallStatus && job.stallStatus !== "none") return "attention";
  if (job.state === "ready" || job.state === "completed") return "ready";
  if (job.state === "failed" || job.state === "repair_required" || job.state === "cancelled") return "error";
  if (job.state === "paused") return "attention";
  return "installing";
}

function defaultPhases(job: InstallJob) {
  if (job.phaseSteps?.length) return job.phaseSteps;
  if (job.progress?.phaseSteps?.length) return job.progress.phaseSteps;
  return [
    { id: "preparing", label: "Preparing runtime", status: "pending" },
    { id: "downloading", label: "Downloading model", status: "pending" },
    { id: "verifying_download", label: "Verifying files", status: "pending" },
    { id: "installing", label: "Installing dependencies", status: "pending" },
    { id: "configuring", label: "Configuring provider", status: "pending" },
    { id: "verifying_install", label: "Final health check", status: "pending" },
  ];
}

export function InstallProgressCard({
  job,
  onPause,
  onResume,
  onCancel,
  onRetry,
  onRepair,
  onAction,
  onDetails,
}: {
  job: InstallJob;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  onRepair?: () => void;
  onAction?: (action: string) => void;
  onDetails?: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const percent = installJobPercent(job);
  const totalKnown = job.progress?.bytesTotal != null;
  const phase = installJobStateLabel(job);
  const currentFile = job.progress?.currentFile;
  const speed = formatBytes(job.progress?.speedBytesPerSecond ?? null);
  const bytesDownloaded = formatBytes(job.progress?.bytesDownloaded ?? null);
  const bytesTotal = formatBytes(job.progress?.bytesTotal ?? null);
  const stepLabel = job.progress?.currentStep || job.message;
  const phases = defaultPhases(job);
  const stallActions: InstallRecoveryAction[] = (job.recoveryActions || []).filter((action) =>
    ["retry_connection", "resume", "restart_worker", "open_diagnostics", "cancel_safely", "restart_comfyui", "restart_later"].includes(
      action.action,
    ),
  );

  const runAction = (action: string) => {
    if (action === "cancel_safely" || action === "cancel") {
      onCancel?.();
      return;
    }
    if (action === "resume") {
      onResume?.();
      onAction?.(action);
      return;
    }
    if (action === "open_diagnostics") {
      setDetailsOpen(true);
      onDetails?.();
      onAction?.(action);
      return;
    }
    onAction?.(action);
  };

  return (
    <section
      className={`install-progress-card install-progress-card--${stateTone(job)}`}
      data-testid={`install-progress-${job.componentId}`}
      data-state={job.state}
      data-stall={job.stallStatus || "none"}
    >
      <div className="install-progress-card__header">
        <div>
          <div className="install-progress-card__eyebrow">
            {job.componentName || job.componentId}
          </div>
          <h4>{phase}</h4>
          {stepLabel ? <p className="install-progress-card__step">{stepLabel}</p> : null}
        </div>
        <span className="install-progress-card__pill">
          {job.stallLabel || job.state.replace(/_/g, " ")}
        </span>
      </div>

      <ol className="install-progress-card__phases" data-testid="install-phase-steps">
        {phases.map((step) => (
          <li key={step.id} data-status={step.status} className={`is-${step.status}`}>
            <span className="install-progress-card__phase-mark" />
            <span>{step.label}</span>
            <em>{step.status === "complete" ? "Complete" : step.status === "active" ? "In progress" : step.status === "failed" ? "Failed" : "Pending"}</em>
          </li>
        ))}
      </ol>

      <div className="install-progress-card__track-wrap">
        <div className="install-progress-card__track-copy">
          <span>
            {totalKnown
              ? `${bytesDownloaded || "0 B"} of ${bytesTotal}`
              : `${job.progress?.stepIndex ?? 0} steps / files completed`}
          </span>
          <span>{percent == null || job.progress?.indeterminate ? "Working…" : `${Math.round(percent)}%`}</span>
        </div>
        <div
          className={`install-progress-card__track${percent == null || job.progress?.indeterminate ? " is-indeterminate" : ""}`}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent == null ? undefined : Math.round(percent)}
          aria-valuetext={percent == null ? "Working" : `${Math.round(percent)} percent`}
        >
          <span style={{ width: `${percent == null ? 34 : percent}%` }} />
        </div>
      </div>

      <div className="install-progress-card__stats">
        <span>{bytesDownloaded || "0 B"} / {totalKnown ? bytesTotal : "unknown total"}</span>
        <span>Speed {job.state === "downloading" && speed ? `${speed}/s` : "—"}</span>
        <span>ETA {job.progress?.etaSeconds != null ? formatDuration(job.progress.etaSeconds) : "—"}</span>
      </div>

      {currentFile ? (
        <p className="install-progress-card__file" data-testid="install-progress-current-file">
          Current: <code>{currentFile}</code>
        </p>
      ) : null}

      {job.stallStatus && job.stallStatus !== "none" ? (
        <div className="install-progress-card__stall" data-testid="install-stall-banner">
          <strong>{job.stallLabel}</strong>
          <p>
            {job.stallStatus === "interrupted"
              ? "The install worker is unavailable. Progress has stopped."
              : job.stallStatus === "waiting_for_source"
                ? "The connection is up, but the source has gone quiet."
                : "No byte or phase progress was reported for longer than expected. The download may still be slow — not necessarily failed."}
          </p>
          <div className="install-progress-card__actions">
            {stallActions.map((action) => (
              <Button
                key={action.action}
                variant={action.destructive ? "ghost" : "secondary"}
                onClick={() => runAction(action.action)}
                data-testid={`install-stall-${action.action}`}
              >
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {job.error ? (
        <InstallErrorPanel
          error={job.error}
          recoveryActions={job.recoveryActions}
          onRetry={onRetry}
          onRepair={onRepair}
          onAction={runAction}
          onDetails={() => setDetailsOpen(true)}
        />
      ) : null}

      <div className="install-progress-card__actions">
        {job.capabilities?.canPause && onPause ? (
          <Button variant="secondary" onClick={onPause}>
            Pause
          </Button>
        ) : null}
        {job.capabilities?.canResume && onResume ? (
          <Button variant="primary" onClick={onResume}>
            Resume
          </Button>
        ) : null}
        {(job.capabilities?.canRetry || job.state === "failed") && onRetry ? (
          <Button variant="primary" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
        {!job.error && (job.capabilities?.canRepair || job.state === "repair_required") && onRepair ? (
          <Button variant="secondary" onClick={onRepair} data-testid="install-error-repair">
            {job.recoveryActions?.[0]?.label || "Repair"}
          </Button>
        ) : null}
        {(job.phase === "restart_required" || job.raw?.awaitingRestart) && onAction ? (
          <>
            <Button variant="primary" onClick={() => onAction("restart_comfyui")} data-testid="install-restart-comfyui">
              Restart ComfyUI
            </Button>
            <Button variant="ghost" onClick={() => onAction("restart_later")}>
              Restart Later
            </Button>
          </>
        ) : null}
        <Button
          variant="ghost"
          onClick={() => {
            setDetailsOpen((value) => !value);
            onDetails?.();
          }}
          data-testid="install-details-toggle"
        >
          {detailsOpen ? "Hide details" : "Details"}
        </Button>
        {job.capabilities?.canCancel !== false && job.state !== "completed" && job.state !== "ready" && onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>

      {detailsOpen ? (
        <div className="install-progress-card__details" data-testid="install-details-drawer">
          <dl>
            <div><dt>Component</dt><dd>{job.componentName || job.componentId}</dd></div>
            <div><dt>Job ID</dt><dd><code>{job.id}</code></dd></div>
            <div><dt>Install path</dt><dd>{job.destinationRoot || job.destination || "—"}</dd></div>
            <div><dt>Source</dt><dd>{String(job.source?.sourceUrl || job.sourceId || "—")}</dd></div>
            <div><dt>Phase</dt><dd>{job.phase || "—"}</dd></div>
            <div><dt>Status</dt><dd>{job.state}</dd></div>
            <div><dt>Worker alive</dt><dd>{job.heartbeat?.workerAlive ? "Yes" : "No"}</dd></div>
            <div><dt>Last progress</dt><dd>{job.heartbeat?.lastProgressAt || "—"}</dd></div>
          </dl>
        </div>
      ) : null}
    </section>
  );
}

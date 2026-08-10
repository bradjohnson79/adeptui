import { useState } from "react";
import { api } from "../api";
import { useInstallJobsPoll } from "../hooks/useInstallJobsPoll";
import type { InstallJob } from "../contracts/installJobs";
import { InstallProgressCard } from "./install/InstallProgressCard";

export function ActiveDownloadsPanel({ onChanged }: { onChanged?: () => void }) {
  const { jobs, error, refresh } = useInstallJobsPoll(true, 900, { activeOnly: true });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const run = async (jobId: string, action: () => Promise<unknown>) => {
    setBusyId(jobId);
    setActionError(null);
    try {
      await action();
      await refresh();
      onChanged?.();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="setup-component-section" aria-labelledby="active-downloads-heading">
      <div className="setup-section-heading">
        <h2 id="active-downloads-heading">Active Downloads</h2>
        <p>Real progress from the persistent download queue.</p>
        <button type="button" className="linkish" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      {(error || actionError) && (
        <p className="setup-message error" role="alert">
          {actionError || error}
        </p>
      )}
      {jobs.length === 0 ? (
        <p className="setup-message" data-testid="active-downloads-empty">
          No active downloads.
        </p>
      ) : (
        <div className="setup-component-grid" data-testid="active-downloads-list">
          {jobs.map((job) => (
            <DownloadCard
              key={job.id}
              job={job}
              busy={busyId === job.id}
              onCancel={() => run(job.id, () => cancelJob(job))}
              onPause={() => run(job.id, () => pauseJob(job))}
              onResume={() => run(job.id, () => resumeJob(job))}
              onRetry={() => run(job.id, () => retryJob(job))}
              onRepair={() =>
                run(job.id, () =>
                  api.installJobs.repair(
                    job.id,
                    job.recoveryActions?.[0]?.action ||
                      job.error?.suggestedAction ||
                      job.error?.recommendedAction ||
                      "retry_download",
                  ),
                )
              }
              onAction={(action) =>
                run(job.id, () =>
                  action === "resume"
                    ? resumeJob(job)
                    : action === "cancel_safely" || action === "cancel"
                      ? cancelJob(job)
                      : api.installJobs.repair(job.id, action),
                )
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}

function isLegacyDownloadJob(job: InstallJob): boolean {
  return job.metadata?.origin === "download";
}

function pauseJob(job: InstallJob) {
  return isLegacyDownloadJob(job) ? api.pauseDownload(job.id) : api.installJobs.pause(job.id);
}

function resumeJob(job: InstallJob) {
  return isLegacyDownloadJob(job) ? api.resumeDownload(job.id) : api.installJobs.resume(job.id);
}

function cancelJob(job: InstallJob) {
  return isLegacyDownloadJob(job) ? api.cancelDownload(job.id) : api.installJobs.cancel(job.id);
}

function retryJob(job: InstallJob) {
  return isLegacyDownloadJob(job) ? api.retryDownload(job.id) : api.installJobs.retry(job.id);
}

function DownloadCard({
  job,
  busy,
  onCancel,
  onPause,
  onResume,
  onRetry,
  onRepair,
  onAction,
}: {
  job: InstallJob;
  busy: boolean;
  onCancel: () => void;
  onPause: () => void;
  onResume: () => void;
  onRetry: () => void;
  onRepair: () => void;
  onAction: (action: string) => void;
}) {
  return (
    <article className="setup-component-card" data-testid={`download-op-${job.id}`} data-phase={job.phase || job.state}>
      <header className="setup-card-header">
        <div>
          <h3>{job.componentName || job.componentId}</h3>
          <span className="setup-requirement">{job.providerId || "install job"}</span>
        </div>
        <span className="setup-status" data-state={job.state === "failed" ? "error" : job.state === "paused" ? "attention" : "installing"}>
          {job.stallLabel || job.state.replace(/_/g, " ")}
        </span>
      </header>
      <InstallProgressCard
        job={job}
        onPause={job.capabilities?.canPause && !busy ? onPause : undefined}
        onResume={job.capabilities?.canResume && !busy ? onResume : undefined}
        onCancel={!busy ? onCancel : undefined}
        onRetry={!busy ? onRetry : undefined}
        onRepair={!busy ? onRepair : undefined}
        onAction={!busy ? onAction : undefined}
      />
    </article>
  );
}

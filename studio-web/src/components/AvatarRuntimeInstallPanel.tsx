import { useMemo, useState } from "react";
import { api } from "../api";
import type { InstallJob } from "../contracts/installJobs";
import type { SetupComponentStatus } from "../setup/types";
import { formatBytes } from "../setup/helpers";
import { InstallProgressCard } from "./install/InstallProgressCard";
import { AddSourceWorkflow } from "./install/AddSourceWorkflow";
import { PreflightDialog, type PreflightConfirm } from "./install/PreflightDialog";
import { StatusBadge } from "./ui";

function runtimeBadge(component: SetupComponentStatus, job?: InstallJob): { kind: "Ready" | "InstallRequired" | "NeedsAttention"; label: string } {
  const healthState = String((component.environment?.healthState as string | undefined) || "");
  if (job && !["ready", "completed", "failed", "repair_required", "cancelled"].includes(job.state)) {
    return { kind: "NeedsAttention", label: "Installing" };
  }
  if (healthState === "experimental") {
    return { kind: "NeedsAttention", label: "Experimental" };
  }
  if (component.status === "ready") {
    return { kind: "Ready", label: "Ready" };
  }
  if (component.status === "error" || component.status === "update_available") {
    return { kind: "NeedsAttention", label: component.status === "update_available" ? "Update Available" : "Repair Required" };
  }
  return { kind: "InstallRequired", label: "Not Installed" };
}

function primaryLabel(component: SetupComponentStatus, job?: InstallJob): string {
  if (job && !["ready", "completed", "failed", "repair_required", "cancelled"].includes(job.state)) {
    return "View Progress";
  }
  if (component.status === "update_available") return "Update";
  if (component.status === "ready") return "Verify";
  if (component.status === "error") return "Repair";
  return "Download and Install";
}

export function AvatarRuntimeInstallPanel({
  components,
  installJobsByComponent,
  onChanged,
}: {
  components: SetupComponentStatus[];
  installJobsByComponent: Record<string, InstallJob>;
  onChanged: () => Promise<void>;
}) {
  const avatarComponents = useMemo(
    () => components.filter((component) => component.category === "Avatar Runtimes"),
    [components],
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sourceWorkflowFor, setSourceWorkflowFor] = useState<SetupComponentStatus | null>(null);
  const [preflightFor, setPreflightFor] = useState<SetupComponentStatus | null>(null);
  const [logsFor, setLogsFor] = useState<string | null>(null);

  const refresh = async () => {
    await onChanged();
  };

  const run = async (componentId: string, action: () => Promise<void>) => {
    setBusyId(componentId);
    setError(null);
    setMessage(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  const runInstallJobAction = async (job: InstallJob, action: "verify" | "repair" | "retry" | "cancel" | string) => {
    if (action === "verify") {
      await api.installJobs.verify(job.id);
      return;
    }
    if (action === "repair") {
      const preferred =
        job.recoveryActions?.[0]?.action ||
        job.error?.suggestedAction ||
        job.error?.recommendedAction ||
        "repair_dependencies";
      await api.installJobs.repair(job.id, preferred);
      return;
    }
    if (action === "retry") {
      await api.installJobs.retry(job.id);
      return;
    }
    if (action === "cancel") {
      await api.installJobs.cancel(job.id);
      return;
    }
    await api.installJobs.repair(job.id, action);
  };

  const browseAndLink = async (component: SetupComponentStatus) => {
    const result = await api.setupBrowsePath({
      mode: "directory",
      start_dir: component.installation_path ?? undefined,
      component_id: component.id,
      title: "Select existing runtime folder",
    });
    if (result.cancelled || !result.path) return;
    await api.setupAction(component.id, "link_existing", result.path, true);
    setMessage(`Linked existing folder for ${component.name}.`);
  };

  const removeRuntime = async (component: SetupComponentStatus) => {
    if (!window.confirm(`Remove ${component.name}? This deletes the isolated runtime folder.`)) return;
    await api.setupAction(component.id, "remove", component.installation_path ?? "", true);
    setMessage(`Removed ${component.name}.`);
  };

  const benchmarkRuntime = async (component: SetupComponentStatus) => {
    await api.setupAction(component.id, "benchmark", component.installation_path ?? "", true);
    setMessage(`Recorded benchmark hook for ${component.name}.`);
  };

  const verifyRuntime = async (component: SetupComponentStatus) => {
    const job = installJobsByComponent[component.id];
    if (job) {
      await runInstallJobAction(job, "verify");
      return;
    }
    await api.setupAction(component.id, "verify", component.installation_path ?? "", true);
  };

  const confirmPreflight = async (component: SetupComponentStatus, payload: PreflightConfirm) => {
    await api.installJobs.create(component.id, {
      action: component.status === "error" ? "repair" : component.status === "update_available" ? "update" : "install",
      destinationRoot: payload.destinationRoot,
      confirm: payload.confirm,
      confirmDownloadModels: payload.confirmDownloadModels,
    });
    setPreflightFor(null);
  };

  if (avatarComponents.length === 0) return null;

  return (
    <section className="setup-component-section ds-surface" aria-labelledby="sm-avatar-runtimes-heading">
      <div className="setup-section-heading">
        <div>
          <h2 id="sm-avatar-runtimes-heading">Avatar Runtimes</h2>
          <p>
            Install LongCat, InfiniteTalk, MuseTalk, and EchoMimicV2 into isolated runtime folders.
            Model downloads always require explicit confirmation. Installed providers stay labeled
            Experimental until live benchmarks are available.
          </p>
        </div>
        <button type="button" className="linkish" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      {message ? (
        <p className="setup-message" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="setup-message error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="setup-component-grid" data-testid="avatar-runtime-panel">
        {avatarComponents.map((component) => {
          const job = installJobsByComponent[component.id];
          const badge = runtimeBadge(component, job);
          const env = (component.environment || {}) as Record<string, unknown>;
          const logs = Array.isArray(component.logs) ? component.logs : [];
          const isLogsOpen = logsFor === component.id;
          return (
            <article
              key={component.id}
              className={`setup-component-card status-${component.status}`}
              data-testid={`avatar-runtime-${component.id}`}
            >
              <header className="setup-card-header">
                <div>
                  <h3>{component.name}</h3>
                  <span className="setup-requirement">{component.purpose || "Avatar runtime"}</span>
                </div>
                <StatusBadge kind={badge.kind} label={badge.label} compact />
              </header>
              <p className="setup-component-description">{component.description}</p>
              <div className="setup-card-meta">
                <span>Download ~{formatBytes(component.expected_download_bytes ?? component.download_bytes ?? null) || "unknown"}</span>
                {component.recommended_vram_gb ? <span>GPU {component.recommended_vram_gb} GB recommended</span> : null}
                {component.source_repo ? (
                  <span>
                    <a href={component.source_repo} target="_blank" rel="noreferrer">
                      Official source
                    </a>
                  </span>
                ) : null}
              </div>
              {component.issue_summary ? (
                <p className="setup-issue">
                  <strong>Issue</strong> {component.issue_summary}
                </p>
              ) : null}
              {env.blockers && Array.isArray(env.blockers) && env.blockers.length > 0 ? (
                <p className="muted tiny">{String(env.blockers[0])}</p>
              ) : null}
              {job ? (
                <InstallProgressCard
                  job={job}
                  onRetry={busyId === component.id ? undefined : () => void run(component.id, () => runInstallJobAction(job, "retry"))}
                  onRepair={busyId === component.id ? undefined : () => void run(component.id, () => runInstallJobAction(job, "repair"))}
                  onCancel={busyId === component.id ? undefined : () => void run(component.id, () => runInstallJobAction(job, "cancel"))}
                  onAction={busyId === component.id ? undefined : (action) => void run(component.id, () => runInstallJobAction(job, action))}
                />
              ) : null}
              <div className="setup-card-actions">
                <button
                  type="button"
                  className="primary"
                  disabled={busyId != null}
                  onClick={() => {
                    const label = primaryLabel(component, job);
                    if (label === "View Progress") {
                      document.getElementById("active-downloads-heading")?.scrollIntoView({ behavior: "smooth", block: "start" });
                      return;
                    }
                    if (label === "Verify") {
                      void run(component.id, () => verifyRuntime(component));
                      return;
                    }
                    setPreflightFor(component);
                  }}
                >
                  {busyId === component.id ? "Working..." : primaryLabel(component, job)}
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busyId != null}
                  onClick={() => setPreflightFor(component)}
                >
                  Choose Install Location
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busyId != null}
                  onClick={() => void run(component.id, () => browseAndLink(component))}
                >
                  Link Existing Folder
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busyId != null}
                  onClick={() => setSourceWorkflowFor(component)}
                >
                  Add Source URL
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busyId != null}
                  onClick={() => void run(component.id, () => benchmarkRuntime(component))}
                >
                  Benchmark
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={logs.length === 0}
                  onClick={() => setLogsFor(isLogsOpen ? null : component.id)}
                >
                  Open Logs
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busyId != null}
                  onClick={() => void run(component.id, () => removeRuntime(component))}
                >
                  Remove
                </button>
              </div>
              {isLogsOpen ? (
                <details className="setup-ready-details" open>
                  <summary>Runtime details</summary>
                  {component.installation_path ? <div><span>Path</span><code>{component.installation_path}</code></div> : null}
                  {logs.map((entry) => (
                    <div key={entry}><span>Log</span><code>{entry}</code></div>
                  ))}
                  {component.license ? <div><span>License</span><code>{component.license}</code></div> : null}
                </details>
              ) : null}
            </article>
          );
        })}
      </div>
      {sourceWorkflowFor ? (
        <AddSourceWorkflow
          open
          componentId={sourceWorkflowFor.id}
          componentName={sourceWorkflowFor.name}
          onClose={() => setSourceWorkflowFor(null)}
          onSaved={() => {
            setSourceWorkflowFor(null);
            void refresh();
          }}
        />
      ) : null}
      {preflightFor ? (
        <PreflightDialog
          open
          componentId={preflightFor.id}
          componentName={preflightFor.name}
          expectedBytes={preflightFor.expected_download_bytes ?? preflightFor.download_bytes ?? null}
          gpuSummary={preflightFor.recommended_vram_gb ? `${preflightFor.recommended_vram_gb} GB recommended` : null}
          requiresModelDownloadConfirm
          busy={busyId === preflightFor.id}
          onClose={() => setPreflightFor(null)}
          onConfirm={(payload) => void run(preflightFor.id, () => confirmPreflight(preflightFor, payload))}
        />
      ) : null}
    </section>
  );
}

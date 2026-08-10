import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, ApiError } from "../api";
import {
  componentStateLabel,
  formatBytes,
  formatComponentSize,
  formatDuration,
  isNetworkUnavailableError,
  nextPollDelayMs,
  overallStatus,
  OVERALL_LABELS,
  primaryActionKind,
  progressPercent,
  RECOMMENDATION_LABELS,
  summarizeComponents,
} from "../setup/helpers";
import type {
  ComponentDiagnosticResult,
  SetupCheckpoint,
  SetupComponentStatus,
  SetupLegacyDetection,
  SetupOperation,
  SetupPrimaryAction,
  SetupPrimaryActionKind,
  SetupStatusResponse,
  StudioPreparationPlan,
} from "../setup/types";
import type { InstallJob } from "../contracts/installJobs";
import { useInstallJobsPoll } from "../hooks/useInstallJobsPoll";
import { requiredBlockers, useCapabilities } from "./CapabilityPanel";
import { VideoModelLibrary } from "./VideoModelLibrary";
import { AddCustomCapability } from "./docker-runtime/AddCustomCapability";
import { PromptIntelligenceBenchmarkDashboard } from "./CoDirector/PromptIntelligenceBenchmarkDashboard";
import { DownloadSourcesPanel } from "./DownloadSourcesPanel";
import { HostedProvidersSetupPanel } from "./HostedProvidersSetupPanel";
import { ModelStoragePanel } from "./ModelStoragePanel";
import { PanelHeading } from "./HelpTip";
import { AddSourceWorkflow } from "./install/AddSourceWorkflow";
import { InstallProgressCard } from "./install/InstallProgressCard";
import { PreflightDialog, type PreflightConfirm } from "./install/PreflightDialog";
import { AiGuidedSetupPanel } from "../setup/lifecycle/AiGuidedSetupPanel";

const TERMINAL_OPERATION_STATES = new Set(["completed", "failed", "cancelled", "interrupted"]);
type SetupMode = "guided" | "ai_guided" | "manual";

function installActionLabel(component: SetupComponentStatus, job?: InstallJob | null): string {
  if (job && !["ready", "completed", "failed", "repair_required", "cancelled"].includes(job.state)) {
    return "View Progress";
  }
  if (!component.source_available || component.source_valid === false) return "Add Source";
  if (component.status === "ready") return "Verify";
  if (component.status === "error") return "Repair";
  return "Install";
}

function SetupProgress({ operation, component }: {
  operation?: SetupOperation;
  component: SetupComponentStatus;
}) {
  const progress = operation?.progress ?? component.progress;
  const stage = operation?.stage ?? component.stage ?? "Preparing…";
  const eta = operation?.estimated_remaining_seconds ?? component.estimated_remaining_seconds;
  const value = progressPercent(progress);

  return (
    <div className="setup-progress" role="status" aria-live="polite">
      <div className="setup-progress-copy">
        <span>{stage}</span>
        <span>{formatDuration(eta)}</span>
      </div>
      <div
        className={`setup-progress-track${progress == null ? " indeterminate" : ""}`}
        role="progressbar"
        aria-label={`${component.name} progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress == null ? undefined : Math.round(value)}
        aria-valuetext={progress == null ? "Estimating progress" : `${Math.round(value)} percent`}
      >
        <span style={{ width: `${progress == null ? 35 : value}%` }} />
      </div>
    </div>
  );
}

function DiagnosticResult({
  diagnostic,
  issueSummary,
}: {
  diagnostic: ComponentDiagnosticResult;
  issueSummary?: string | null;
}) {
  const nextStep = (() => {
    if (diagnostic.healthy) return diagnostic.summary;
    if (diagnostic.issue_code === "source_not_published") {
      return "No official distribution has been published for this pack yet. Use Add Source URL when you have a verified archive, or Link Existing Folder if the pack files are already on disk.";
    }
    if (
      diagnostic.issue_code === "source_not_configured"
      || diagnostic.issue_code === "download_source_missing"
      || diagnostic.issue_code === "pack_provider_not_configured"
    ) {
      return "No official source has been assigned to this component. Add a Source URL or Link Existing Folder. A shared GitHub owner/repository environment variable is not used as a universal pack source.";
    }
    if (diagnostic.issue_code === "pack_release_not_found") {
      return "The configured repository exists, but no compatible published release was found. Use Check Again, Add Source URL, or Link Existing Folder.";
    }
    if (diagnostic.issue_code === "github_rate_limited") {
      return "Try again later, or configure ADEPT_PACK_GITHUB_TOKEN to raise API limits.";
    }
    if (diagnostic.issue_code === "required_files_missing") {
      return diagnostic.recommendation === "install"
        ? "Retry the download. If it fails again, open diagnostics."
        : "Link a folder that already contains the required pack files, or refresh the download source.";
    }
    if (issueSummary && diagnostic.summary.trim() === issueSummary.trim()) {
      return RECOMMENDATION_LABELS[diagnostic.recommendation] ?? "Open diagnostics for details.";
    }
    return diagnostic.summary;
  })();
  return (
    <div className={`setup-diagnostic ${diagnostic.healthy ? "healthy" : "attention"}`} role="status">
      <strong>{diagnostic.healthy ? "Diagnostic complete" : "Recommended next step"}</strong>
      <span>{nextStep}</span>
    </div>
  );
}

function SetupComponentCard({
  component,
  operation,
  installJob,
  busy,
  onPrimaryAction,
  onLater,
  onSecondaryAction,
  onPackAction,
  onInstallJobPause,
  onInstallJobResume,
  onInstallJobCancel,
  onInstallJobRetry,
  onInstallJobRepair,
  onInstallJobAction,
}: {
  component: SetupComponentStatus;
  operation?: SetupOperation;
  installJob?: InstallJob;
  busy: boolean;
  onPrimaryAction: (component: SetupComponentStatus) => void;
  onLater: (componentId: string) => void;
  onSecondaryAction?: (component: SetupComponentStatus) => void;
  onPackAction?: (component: SetupComponentStatus, action: SetupPrimaryActionKind) => void;
  onInstallJobPause?: (job: InstallJob) => void;
  onInstallJobResume?: (job: InstallJob) => void;
  onInstallJobCancel?: (job: InstallJob) => void;
  onInstallJobRetry?: (job: InstallJob) => void;
  onInstallJobRepair?: (job: InstallJob) => void;
  onInstallJobAction?: (job: InstallJob, action: string) => void;
}) {
  const errorActionKind: SetupPrimaryActionKind =
    component.diagnostic?.recommendation === "install"
      ? "install"
      : component.diagnostic?.recommendation === "refresh_source"
        ? "refresh_source"
        : "recommended_action";
  const action: SetupPrimaryAction | null | undefined =
    component.status === "error" && component.diagnostic
      ? component.diagnostic.recommendation === "none"
        ? null
        : {
            action: errorActionKind,
            label: component.diagnostic.recommended_action_label
              ?? RECOMMENDATION_LABELS[component.diagnostic.recommendation],
          }
      : component.primary_action;
  const size = formatComponentSize(component);
  const hasInstallJob = Boolean(installJob);
  const isInstallJobActive = Boolean(installJob && !["ready", "completed", "failed", "repair_required", "cancelled"].includes(installJob.state));
  const isActive = component.status === "installing" || component.status === "checking" || Boolean(operation) || isInstallJobActive;
  // Never block Download/Install when a concrete source is available (retry after failure).
  const isCredential = component.component_kind === "credential" || component.installer === "credentials";
  const installDisabled = component.source_available
    ? Boolean(component.status === "ready")
    : (
      Boolean(component.install_disabled)
      || component.status === "download_unavailable"
      || component.status === "source_pending"
      || (
        component.source_valid === false
        && (action?.action === "install" || action?.kind === "install")
      )
    );
  const showIssue = Boolean(component.issue_summary);
  const showDiagnostic = Boolean(component.diagnostic)
    && !(
      showIssue
      && component.diagnostic
      && component.issue_summary
      && component.diagnostic.summary.trim() === component.issue_summary.trim()
      && component.status !== "download_unavailable"
      && component.status !== "source_pending"
      && component.issue_code !== "required_files_missing"
      && component.issue_code !== "download_source_missing"
      && component.issue_code !== "source_not_published"
      && component.issue_code !== "source_not_configured"
    );

  return (
    <article
      className={`setup-component-card status-${component.status}${component.status === "source_pending" ? " status-pending" : ""}`}
      aria-labelledby={`setup-${component.id}`}
      // Anchor target for capability blockers' "View required components" jump.
      id={`setup-card-${component.id}`}
      data-testid={`setup-card-${component.id}`}
      data-status={component.status}
      data-kind={component.component_kind || component.installer || ""}
    >
      <header className="setup-card-header">
        <div>
          <h3 id={`setup-${component.id}`}>{component.name}</h3>
          <span className="setup-requirement">{component.required ? "Required" : "Optional"}</span>
        </div>
        <span
          className="setup-status"
          data-state={component.status === "source_pending" ? "source_pending" : component.status}
        >
          <span className="setup-status-mark" aria-hidden="true" />
          {componentStateLabel(component)}
        </span>
      </header>
      <p className="setup-component-description">{component.description}</p>
      <div className="setup-card-meta">
        {(component.installed_version || component.pack_version) && (
          <span>Version {component.installed_version ?? component.pack_version}</span>
        )}
        {size && <span>{size}</span>}
        {component.status === "update_available" && component.available_version && (
          <span>Version {component.available_version} available</span>
        )}
      </div>

      {showIssue && <p className="setup-issue"><strong>Issue</strong> {component.issue_summary}</p>}
      {component.diagnostic && (
        showDiagnostic
        || component.status === "download_unavailable"
        || component.status === "source_pending"
      ) && (
        <DiagnosticResult diagnostic={component.diagnostic} issueSummary={component.issue_summary} />
      )}
      {isActive && !isInstallJobActive && <SetupProgress operation={operation} component={component} />}
      {installJob && (
        <InstallProgressCard
          job={installJob}
          onPause={installJob.capabilities?.canPause && onInstallJobPause ? () => onInstallJobPause(installJob) : undefined}
          onResume={installJob.capabilities?.canResume && onInstallJobResume ? () => onInstallJobResume(installJob) : undefined}
          onCancel={onInstallJobCancel ? () => onInstallJobCancel(installJob) : undefined}
          onRetry={onInstallJobRetry ? () => onInstallJobRetry(installJob) : undefined}
          onRepair={onInstallJobRepair ? () => onInstallJobRepair(installJob) : undefined}
          onAction={onInstallJobAction ? (action) => onInstallJobAction(installJob, action) : undefined}
        />
      )}

      {(component.status === "ready" || hasInstallJob) && (component.installation_path || component.last_verified_at || installJob?.destinationRoot || installJob?.providerId) && (
        <details className="setup-ready-details" open={Boolean(isInstallJobActive)}>
          <summary>Installation details</summary>
          {component.installation_path && <div><span>Path</span><code>{component.installation_path}</code></div>}
          {installJob?.destinationRoot && <div><span>Destination</span><code>{installJob.destinationRoot}</code></div>}
          {installJob?.providerId && <div><span>Provider</span><code>{installJob.providerId}</code></div>}
          {installJob?.progress?.currentFile && <div><span>Current file</span><code>{installJob.progress.currentFile}</code></div>}
          {component.last_verified_at && (
            <div><span>Last verified</span><time dateTime={component.last_verified_at}>{new Date(component.last_verified_at).toLocaleString()}</time></div>
          )}
          {installJob?.updatedAt && (
            <div><span>Updated</span><time dateTime={installJob.updatedAt}>{new Date(installJob.updatedAt).toLocaleString()}</time></div>
          )}
        </details>
      )}

      {(
        component.status === "download_unavailable"
        || component.status === "source_pending"
        || (component.provider_id === "github_releases" && component.source_available)
      ) && (
        <details className="setup-ready-details">
          <summary>View Pack Specification</summary>
          <div><span>Distribution</span><code>{component.distribution_label || component.distribution_status || "unknown"}</code></div>
          <div><span>Provider</span><code>{component.provider_id === "github_releases" ? "Per-component / pending" : (component.source_type ?? "unassigned")}</code></div>
          {component.repository && <div><span>Repository</span><code>{component.repository}</code></div>}
          {component.tag_name && <div><span>Release</span><code>{component.tag_name}</code></div>}
          {component.archive_asset_name && <div><span>Asset</span><code>{component.archive_asset_name}</code></div>}
          {component.required_files?.length ? (
            <div><span>Required</span><code>{component.required_files.join(", ")}</code></div>
          ) : null}
          {!component.source_available && (
            <div>
              <span>Source</span>
              <code>No official distribution published yet. Add Source URL or Link Existing Folder.</code>
            </div>
          )}
          {component.custom_source_active && (
            <div><span>Custom source</span><code>Active (defaults remain recoverable)</code></div>
          )}
        </details>
      )}

      {!isActive && (component.installer === "asset_pack" || component.verifier === "asset_pack") && onPackAction ? (
        <div className="setup-card-actions">
          {!component.source_available || component.source_valid === false ? (
            <>
              <button
                type="button"
                className="primary"
                disabled={busy}
                onClick={() => onPackAction(component, "refresh_source")}
              >
                Use Official
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => onPackAction(component, "add_source_url")}
                data-testid={`add-source-url-${component.id}`}
              >
                Add Source URL
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => onPackAction(component, "link_existing")}
              >
                Link Existing Folder
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="primary"
                disabled={busy || installDisabled}
                title={installDisabled ? "Download and Install requires a verified per-component source." : undefined}
                onClick={() => onPackAction(component, component.status === "error" ? "recommended_action" : "install")}
              >
                {installActionLabel(component, installJob)}
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => onPackAction(component, "link_existing")}
              >
                Link Existing Folder
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => onPackAction(component, "add_source_url")}
                data-testid={`add-source-url-${component.id}`}
              >
                Add Source URL
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => onPackAction(component, "refresh_source")}
              >
                Check Again
              </button>
            </>
          )}
          {component.status === "update_available" && (
            <button type="button" className="linkish setup-later" disabled={busy} onClick={() => onLater(component.id)}>
              Later
            </button>
          )}
        </div>
      ) : !isActive && action ? (
        <div className="setup-card-actions">
          <button
            type="button"
            className="primary"
            disabled={busy || action.disabled || (action.action === "install" && installDisabled)}
            data-testid={isCredential ? `configure-credential-${component.id}` : undefined}
            onClick={() => onPrimaryAction({ ...component, primary_action: action })}
          >
            {action.label}
          </button>
          {component.secondary_action && onSecondaryAction && (
            <button
              type="button"
              className="linkish"
              disabled={busy}
              onClick={() => onSecondaryAction(component)}
            >
              {component.secondary_action.label}
            </button>
          )}
          {component.status === "update_available" && (
            <button type="button" className="linkish setup-later" disabled={busy} onClick={() => onLater(component.id)}>
              Later
            </button>
          )}
        </div>
      ) : null}
    </article>
  );
}

function SetupSummary({
  status,
  preparing,
  projectId,
  onPrepare,
}: {
  status: SetupStatusResponse;
  preparing: boolean;
  projectId?: string;
  onPrepare: () => void;
}) {
  const counts = status.counts ?? status.summary ?? summarizeComponents(status.components);
  const componentOverall = status.overall_status ?? overallStatus(status.components);
  const { snapshot } = useCapabilities({ pollMs: 30000 });
  const blockers = requiredBlockers(snapshot);

  // Component states alone can read "ready" while a capability that needs them is still
  // blocked — a missing ComfyUI node type, or a pack with no published source. When the
  // registry reports a required capability as blocked, the wizard must not claim readiness.
  const overall = componentOverall === "ready" && blockers.length > 0
    ? "additional_setup_required"
    : componentOverall;
  const needsPreparation = overall !== "ready" && overall !== "preparing";

  return (
    <section className="panel setup-summary" aria-labelledby="setup-system-status">
      <div className="setup-summary-main">
        <div>
          <div className="section-label">System Status</div>
          <div className="setup-counts" id="setup-system-status">
            <span><strong>{counts.ready}</strong> Ready</span>
            <span><strong>{counts.not_installed}</strong> Not Installed</span>
            <span><strong>{counts.needs_attention}</strong> Needs Attention</span>
          </div>
        </div>
        <div className="setup-overall" role="status" aria-live="polite">
          <span>Overall Status</span>
          <strong data-testid="setup-overall-status">
            {OVERALL_LABELS[preparing ? "preparing" : overall]}
          </strong>
        </div>
      </div>
      {blockers.length > 0 && (
        <div className="setup-capability-blockers" data-testid="setup-capability-blockers">
          <p className="setup-issue">
            {blockers.length} capability {blockers.length === 1 ? "blocker" : "blockers"} must be
            cleared before generation can run:
          </p>
          <ul>
            {blockers.map((blocker) => (
              <li key={blocker.capabilityId} data-testid={`setup-blocker-${blocker.capabilityId}`}>
                <strong>{blocker.displayName}</strong> — {blocker.message}
                {blocker.componentIds.length > 0 && (
                  <>
                    {" "}
                    <a
                      href={`#setup-card-${blocker.componentIds[0]}`}
                      data-testid={`setup-blocker-jump-${blocker.capabilityId}`}
                    >
                      View required components
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
          <Link to={`/source-manager${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`} data-testid="setup-blockers-open-source-manager">
            Open Source Manager
          </Link>
        </div>
      )}
      {needsPreparation && (
        <button type="button" className="primary setup-prepare-button" disabled={preparing} onClick={onPrepare}>
          {preparing ? "Preparing Studio…" : "Prepare My Studio"}
        </button>
      )}
    </section>
  );
}

function SetupAdvancedPanel({
  status,
  legacy,
  operations,
  busyId,
  pathDrafts,
  onPathChange,
  onAction,
  onOpen,
}: {
  status: SetupStatusResponse;
  legacy: SetupLegacyDetection | null;
  operations: Record<string, SetupOperation>;
  busyId: string | null;
  pathDrafts: Record<string, string>;
  onPathChange: (componentId: string, value: string) => void;
  onAction: (component: SetupComponentStatus, action: string) => void;
  onOpen: () => void;
}) {
  const components = status.components.map((component): SetupComponentStatus => {
    const catalog = legacy?.catalog.find((item) => item.id === component.id);
    return catalog ? { ...catalog, ...component } : component;
  });

  return (
    <details className="panel setup-advanced" onToggle={(event) => {
      if (event.currentTarget.open) onOpen();
    }}>
      <summary>Advanced</summary>
      <p className="muted">Maintenance, installation details, environment information, and support data.</p>
      {(status.environment || legacy) && (
        <details className="setup-advanced-environment">
          <summary>Environment</summary>
          <pre>{JSON.stringify(status.environment ?? legacy, null, 2)}</pre>
        </details>
      )}
      {Object.values(operations).some((operation) => operation.logs?.length) && (
        <details className="setup-advanced-environment">
          <summary>Operation logs</summary>
          {Object.values(operations).map((operation) => operation.logs?.length ? (
            <div key={operation.operation_id}>
              <strong>{operation.stage ?? operation.operation_id}</strong>
              <pre>{operation.logs.map((entry) => typeof entry === "string" ? entry : `${entry.at}  ${entry.message}`).join("\n")}</pre>
            </div>
          ) : null)}
        </details>
      )}
      <div className="setup-advanced-list">
        {components.map((component) => (
          <details key={component.id} className="setup-advanced-component">
            <summary>{component.name}</summary>
            <dl className="setup-detail-list">
              <div><dt>Status</dt><dd>{componentStateLabel(component)}</dd></div>
              {component.installed_version && <div><dt>Installed version</dt><dd>{component.installed_version}</dd></div>}
              {component.available_version && <div><dt>Available version</dt><dd>{component.available_version}</dd></div>}
              {component.executable_path && <div><dt>Executable</dt><dd><code>{component.executable_path}</code></dd></div>}
              {component.installation_path && <div><dt>Installation path</dt><dd><code>{component.installation_path}</code></dd></div>}
              {component.source_repo && <div><dt>Source</dt><dd><a href={component.source_repo} target="_blank" rel="noreferrer">{component.source_repo}</a></dd></div>}
              {component.license && <div><dt>License</dt><dd>{component.license}</dd></div>}
              {component.modes?.length && <div><dt>Modes</dt><dd>{component.modes.join(", ")}</dd></div>}
              {component.dependencies?.length && <div><dt>Dependencies</dt><dd>{component.dependencies.join(", ")}</dd></div>}
            </dl>
            {(component.install_kind === "path_link" || component.installer === "path_link" || component.install_kind === "download") && (
              <div className="field setup-path-field">
                <span className="setup-path-field-label">Install / model path</span>
                <SetupPathChooser
                  componentId={component.id}
                  pathSelector={component.path_selector === "file" ? "file" : "directory"}
                  path={pathDrafts[component.id] ?? component.installation_path ?? ""}
                  busy={busyId != null}
                  onPathChange={(value) => onPathChange(component.id, value)}
                />
              </div>
            )}
            <div className="row-actions">
              <button type="button" disabled={busyId != null} onClick={() => onAction(component, "verify")}>Verify</button>
              <button type="button" disabled={busyId != null} onClick={() => onAction(component, "repair")}>Repair</button>
              <button type="button" disabled={busyId != null} onClick={() => onAction(component, "update")}>Update</button>
              <button type="button" className="danger" disabled={busyId != null} onClick={() => onAction(component, "remove")}>Remove</button>
            </div>
            {component.diagnostic?.technical_details?.length && (
              <details className="setup-technical-details">
                <summary>Diagnostic details</summary>
                <ul>{component.diagnostic.technical_details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
              </details>
            )}
            {component.logs?.length && (
              <details className="setup-technical-details">
                <summary>Logs</summary>
                <pre>{component.logs.join("\n")}</pre>
              </details>
            )}
          </details>
        ))}
      </div>
    </details>
  );
}

function SetupDialogShell({
  titleId,
  title,
  busy,
  onClose,
  children,
}: {
  titleId: string;
  title: string;
  busy?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, onClose]);

  return (
    <div
      className="setup-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (!busy && event.target === event.currentTarget) onClose();
      }}
    >
      <section className="setup-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="setup-dialog-header">
          <h2 id={titleId}>{title}</h2>
          <button
            type="button"
            className="setup-dialog-close"
            aria-label="Close"
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

function SetupPathChooser({
  componentId,
  suggestedPath,
  pathSelector,
  path,
  busy,
  workflow,
  onPathChange,
}: {
  componentId?: string | null;
  suggestedPath?: string | null;
  pathSelector?: "directory" | "file" | null;
  path: string;
  busy: boolean;
  workflow?: string | null;
  onPathChange: (value: string) => void;
}) {
  const [browsing, setBrowsing] = useState(false);
  const [chooserMessage, setChooserMessage] = useState<string | null>(null);
  const [recommended, setRecommended] = useState(suggestedPath?.trim() || "");
  const [resolvedSelector, setResolvedSelector] = useState<"directory" | "file">(
    pathSelector === "file" ? "file" : "directory",
  );
  const mode = resolvedSelector;

  useEffect(() => {
    setRecommended(suggestedPath?.trim() || "");
  }, [suggestedPath]);

  useEffect(() => {
    setResolvedSelector(pathSelector === "file" ? "file" : "directory");
  }, [pathSelector]);

  useEffect(() => {
    if (!componentId) return;
    let cancelled = false;
    void api.setupSuggestedPath(componentId)
      .then((result) => {
        if (cancelled) return;
        setRecommended((current) => current || result.suggested_path);
        if (result.path_selector === "file" || result.path_selector === "directory") {
          setResolvedSelector(result.path_selector);
        }
      })
      .catch(async () => {
        // Compatibility fallback for an API process that has not yet reloaded
        // the suggested-path route. Reuse a verified model location when one is
        // available instead of exposing an empty or invented path.
        try {
          const current = await api.setupStatus();
          const component = current.components.find((item) => item.id === componentId);
          const ltx = current.components.find((item) => item.id === "ltx_checkpoint");
          const verifiedPath = component?.installation_path || ltx?.installation_path || "";
          let fallback = verifiedPath;
          const normalized = verifiedPath.replace(/\//g, "\\");
          const modelsMarker = normalized.toLowerCase().lastIndexOf("\\models\\");
          if (componentId !== "ltx_checkpoint" && modelsMarker >= 0) {
            fallback = normalized.slice(0, modelsMarker + "\\models".length);
          }
          if (!fallback) {
            const legacy = await api.setupDetect();
            const dataDir = legacy.paths?.data_dir;
            if (typeof dataDir === "string" && dataDir.trim()) {
              fallback = `${dataDir.replace(/[\\/]+$/, "")}\\models`;
            }
          }
          if (!cancelled && fallback) setRecommended(fallback);
        } catch {
          // Browse remains available once the local API has reloaded.
        }
      });
    return () => {
      cancelled = true;
    };
  }, [componentId]);

  const useRecommended = () => {
    if (!recommended) {
      setChooserMessage("Adept UI could not determine a recommended path yet.");
      return;
    }
    onPathChange(recommended);
    setChooserMessage(null);
  };

  const browse = async () => {
    setBrowsing(true);
    setChooserMessage(null);
    try {
      const e2eForced =
        typeof window !== "undefined"
          ? String((window as Window & { __ADEPT_E2E_FORCED_PATH__?: string }).__ADEPT_E2E_FORCED_PATH__ || "").trim()
          : "";
      const result = await api.setupBrowsePath({
        mode,
        start_dir: path || recommended || undefined,
        component_id: componentId ?? undefined,
        title: mode === "file" ? "Select model file" : "Select installation folder",
        ...(e2eForced ? { forced_path: e2eForced } : {}),
      });
      if (result.cancelled || !result.path) {
        setChooserMessage("Browse cancelled.");
        return;
      }
      onPathChange(result.path);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setChooserMessage(
        text.includes("Not Found") || text.includes("404")
          ? "The path browser service is still starting. Restart the local API, then try Browse again."
          : text,
      );
    } finally {
      setBrowsing(false);
    }
  };

  const isLinkExisting = workflow === "link_existing";
  const lead = isLinkExisting
    ? "Choose a folder that already contains this pack. A valid pack.json manifest is required."
    : "Choose an empty folder or create a new folder for this pack. Adept UI will download and install the required files.";

  return (
    <div className="setup-path-chooser">
      <p className="setup-path-chooser-lead">{lead}</p>
      <div className="setup-path-options">
        <button
          type="button"
          className={`setup-path-option${path && recommended && path === recommended ? " selected" : ""}`}
          disabled={busy || browsing || !recommended}
          onClick={useRecommended}
        >
          <strong>{isLinkExisting ? "Use suggested existing path" : "Use Adept recommended path"}</strong>
          <span>{recommended || "Recommended path unavailable"}</span>
        </button>
        <button
          type="button"
          className={`setup-path-option${path && (!recommended || path !== recommended) ? " selected" : ""}`}
          disabled={busy || browsing}
          onClick={() => void browse()}
        >
          <strong>{browsing ? "Opening browser…" : mode === "file" ? "Browse for file…" : "Browse for folder…"}</strong>
          <span>
            {isLinkExisting
              ? "Select a folder that already contains verified pack files."
              : "Select an empty folder or create a new install location."}
          </span>
        </button>
      </div>
      {path && (
        <div className="setup-selected-path" role="status">
          <span>Selected path</span>
          <code>{path}</code>
        </div>
      )}
      {chooserMessage && <p className="setup-path-chooser-message">{chooserMessage}</p>}
    </div>
  );
}

function SetupCheckpointDialog({
  checkpoint,
  busy,
  onSubmit,
  onClose,
}: {
  checkpoint: SetupCheckpoint;
  busy: boolean;
  onSubmit: (answer: {
    accepted?: boolean;
    license_accepted?: boolean;
    path?: string;
    completed?: boolean;
    cancelled?: boolean;
  }) => void;
  onClose: () => void;
}) {
  const kind = checkpoint.kind ?? checkpoint.type ?? "manual_help";
  const [path, setPath] = useState(checkpoint.suggested_path ?? "");
  const [accepted, setAccepted] = useState(false);

  const openIntegrationSettings = () => {
    sessionStorage.setItem("adept_settings_tab", "integrations");
    const url = new URL(window.location.href);
    url.searchParams.set("workspace", "settings");
    window.location.assign(url);
  };

  const needsLicenseConsent = kind === "license" || checkpoint.requires_license_acceptance === true;
  const needsConsent = needsLicenseConsent || kind === "elevation";
  const needsPath = kind === "path" || kind === "model_path";
  const canContinue = !needsPath || path.trim().length > 0;

  return (
    <SetupDialogShell
      titleId="setup-checkpoint-title"
      title={checkpoint.title ?? "Setup Needs Your Input"}
      busy={busy}
      onClose={onClose}
    >
      <p>{checkpoint.message ?? checkpoint.summary ?? "Complete this step to continue setup."}</p>
      {needsPath && (
        <SetupPathChooser
          componentId={checkpoint.component_id}
          suggestedPath={checkpoint.suggested_path}
          pathSelector={checkpoint.path_selector}
          path={path}
          busy={busy}
          workflow={checkpoint.workflow ?? checkpoint.action}
          onPathChange={setPath}
        />
      )}
      {kind === "credentials" && (
        <div className="setup-credential-guidance">
          <p>Credentials are entered only in the secure Integration Settings screen. Setup does not display or store them here.</p>
          <button type="button" onClick={openIntegrationSettings}>Open Setup → AI Providers</button>
        </div>
      )}
      {(checkpoint.help_url || checkpoint.license_url) && (
        <p><a href={checkpoint.help_url ?? checkpoint.license_url ?? "#"} target="_blank" rel="noreferrer">
          {needsLicenseConsent ? `Review ${checkpoint.license_name ?? checkpoint.license ?? "license"}` : "Open setup help"}
        </a></p>
      )}
      {needsConsent && (
        <label className="setup-consent">
          <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
          <span>{needsLicenseConsent ? "I accept the license terms" : "I am ready to approve the system elevation prompt"}</span>
        </label>
      )}
      <div className="row-actions">
        <button
          type="button"
          className="primary"
          disabled={busy || !canContinue || (needsConsent && !accepted)}
          onClick={() => onSubmit({
            accepted: needsConsent ? accepted : undefined,
            license_accepted: needsLicenseConsent ? accepted : undefined,
            path: needsPath ? path.trim() : undefined,
            completed: kind === "credentials" || kind === "manual_help" || kind === "manual_installer" ? true : undefined,
          })}
        >
          {busy ? "Continuing…" : checkpoint.action_label ?? (kind === "credentials" ? "I've Configured It" : "Continue")}
        </button>
        <button type="button" className="ghost" disabled={busy} onClick={onClose}>
          Cancel
        </button>
      </div>
    </SetupDialogShell>
  );
}

function PreparationPlanDialog({
  plan,
  busy,
  onCancel,
  onConfirm,
}: {
  plan: StudioPreparationPlan;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <SetupDialogShell titleId="setup-plan-title" title="Prepare My Studio" busy={busy} onClose={onCancel}>
      <p className="setup-plan-summary">
        {plan.required_actions.length} required component{plan.required_actions.length === 1 ? "" : "s"}
        {plan.required_disk_bytes > 0 ? ` · ${formatBytes(plan.required_disk_bytes)} required` : ""}
        {plan.estimated_seconds ? ` · about ${Math.max(1, Math.ceil(plan.estimated_seconds / 60))} minutes` : ""}
      </p>
      <p>Setup will install or configure required components, then check each installation automatically.</p>
      {!plan.can_run_unattended && <p className="setup-plan-note">Setup will pause when your input is required.</p>}
      <div className="row-actions">
        <button type="button" className="primary" disabled={busy} onClick={onConfirm}>
          {busy ? "Starting…" : "Prepare Studio"}
        </button>
        <button type="button" className="ghost" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </SetupDialogShell>
  );
}

export function SetupWizardPanel({ projectId }: { projectId?: string }) {
  const location = useLocation();
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const forcedSetupMode = searchParams.get("setupMode");
  const focusedSetupComponentId = searchParams.get("setupComponent") || searchParams.get("componentId") || undefined;
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [operations, setOperations] = useState<Record<string, SetupOperation>>({});
  const [trackedOperationIds, setTrackedOperationIds] = useState<string[]>([]);
  const [activeCheckpoint, setActiveCheckpoint] = useState<{ operationId: string; checkpoint: SetupCheckpoint } | null>(null);
  const [plan, setPlan] = useState<StudioPreparationPlan | null>(null);
  const [legacyDetection, setLegacyDetection] = useState<SetupLegacyDetection | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pathDrafts, setPathDrafts] = useState<Record<string, string>>({});
  const [addSourceFor, setAddSourceFor] = useState<SetupComponentStatus | null>(null);
  const [preflightFor, setPreflightFor] = useState<SetupComponentStatus | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [setupMode, setSetupMode] = useState<SetupMode>(() => {
    if (typeof window === "undefined") return "guided";
    const params = new URLSearchParams(window.location.search);
    const forced = params.get("setupMode");
    if (forced === "guided" || forced === "ai_guided" || forced === "manual") return forced;
    const saved = window.localStorage.getItem("adept.setup.mode");
    return saved === "guided" || saved === "ai_guided" || saved === "manual" ? saved : "guided";
  });
  const { jobs: installJobs, refresh: refreshInstallJobs } = useInstallJobsPoll(true, 1000, { activeOnly: false });

  useEffect(() => {
    window.localStorage.setItem("adept.setup.mode", setupMode);
  }, [setupMode]);

  useEffect(() => {
    if (forcedSetupMode === "guided" || forcedSetupMode === "ai_guided" || forcedSetupMode === "manual") {
      setSetupMode(forcedSetupMode);
    }
  }, [forcedSetupMode]);

  const refresh = useCallback(async () => {
    const next = await api.setupStatus();
    setStatus(next);
    const ids = [
      next.active_operation?.operation_id,
      ...next.components.map((component) => component.operation_id),
    ].filter((id): id is string => Boolean(id));
    if (ids.length) {
      setTrackedOperationIds((current) => Array.from(new Set([...current, ...ids])));
    }
    if (next.active_operation) {
      setOperations((current) => ({ ...current, [next.active_operation!.operation_id]: next.active_operation! }));
    }
  }, []);

  useEffect(() => {
    refresh().catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
  }, [refresh]);

  useEffect(() => {
    if (!trackedOperationIds.length) return;
    let cancelled = false;
    let consecutiveFailures = 0;
    let timer: number | undefined;

    const schedule = (delayMs: number) => {
      timer = window.setTimeout(() => {
        void poll();
      }, delayMs);
    };

    const poll = async () => {
      try {
        const results = await Promise.allSettled(
          trackedOperationIds.map((id) => api.setupOperation(id)),
        );
        if (cancelled) return;

        const networkFailures = results.filter(
          (result) =>
            result.status === "rejected" && isNetworkUnavailableError(result.reason),
        ).length;
        if (networkFailures === results.length && results.length > 0) {
          consecutiveFailures += 1;
          setMessage(
            consecutiveFailures >= 2
              ? "Studio API is unreachable. Retrying with backoff…"
              : "Studio API is unreachable.",
          );
          schedule(nextPollDelayMs(consecutiveFailures));
          return;
        }
        consecutiveFailures = 0;

        const snapshots = results.flatMap((result) =>
          result.status === "fulfilled" ? [result.value] : []
        );
        const missingIds = trackedOperationIds.filter((_, index) => {
          const result = results[index];
          return (
            result?.status === "rejected"
            && result.reason instanceof ApiError
            && result.reason.status === 404
          );
        });
        if (missingIds.length) {
          setTrackedOperationIds((current) => current.filter((id) => !missingIds.includes(id)));
          setActiveCheckpoint((current) =>
            current && missingIds.includes(current.operationId) ? null : current
          );
          setOperations((current) => {
            const next = { ...current };
            missingIds.forEach((id) => delete next[id]);
            return next;
          });
        }
        setOperations((current) => {
          const next = { ...current };
          snapshots.forEach((operation) => { next[operation.operation_id] = operation; });
          return next;
        });
        const waiting = snapshots.find((operation) => operation.status === "awaiting_checkpoint" && operation.checkpoint);
        if (waiting?.checkpoint) {
          setActiveCheckpoint({ operationId: waiting.operation_id, checkpoint: waiting.checkpoint });
        }
        const terminalIds = snapshots
          .filter((operation) => TERMINAL_OPERATION_STATES.has(operation.status))
          .map((operation) => operation.operation_id);
        if (terminalIds.length) {
          setTrackedOperationIds((current) => current.filter((id) => !terminalIds.includes(id)));
          await refresh();
        }
        if (!cancelled && trackedOperationIds.length) {
          schedule(nextPollDelayMs(0));
        }
      } catch (error: unknown) {
        if (cancelled) return;
        if (isNetworkUnavailableError(error)) {
          consecutiveFailures += 1;
          setMessage(
            consecutiveFailures >= 2
              ? "Studio API is unreachable. Retrying with backoff…"
              : (error instanceof Error ? error.message : String(error)),
          );
          schedule(nextPollDelayMs(consecutiveFailures));
          return;
        }
        setMessage(error instanceof Error ? error.message : String(error));
        schedule(nextPollDelayMs(consecutiveFailures || 1));
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [refresh, trackedOperationIds]);

  const operationsByComponent = useMemo(() => {
    const byComponent: Record<string, SetupOperation> = {};
    Object.values(operations).forEach((operation) => {
      if (operation.component_id && !TERMINAL_OPERATION_STATES.has(operation.status)) {
        byComponent[operation.component_id] = operation;
      }
      if (!TERMINAL_OPERATION_STATES.has(operation.status)) {
        operation.component_ids?.forEach((componentId) => { byComponent[componentId] = operation; });
      }
    });
    return byComponent;
  }, [operations]);

  const installJobsByComponent = useMemo(() => {
    const byComponent: Record<string, InstallJob> = {};
    installJobs.forEach((job) => {
      if (!job.componentId) return;
      const existing = byComponent[job.componentId];
      const existingTime = existing?.updatedAt ? new Date(existing.updatedAt).getTime() : 0;
      const nextTime = job.updatedAt ? new Date(job.updatedAt).getTime() : 0;
      if (!existing || nextTime >= existingTime) byComponent[job.componentId] = job;
    });
    return byComponent;
  }, [installJobs]);

  const trackOperation = (operationId: string, operation?: SetupOperation) => {
    setTrackedOperationIds((current) => Array.from(new Set([...current, operationId])));
    if (operation) setOperations((current) => ({ ...current, [operation.operation_id]: operation }));
  };

  const preparePlan = async () => {
    setBusyId("prepare-plan");
    setMessage(null);
    try {
      setPlan(await api.setupPreparePlan());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const startPreparation = async () => {
    setBusyId("prepare");
    setMessage(null);
    try {
      const result = await api.setupPrepare();
      trackOperation(result.operation_id, result);
      setPlan(null);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const runPackAction = async (
    component: SetupComponentStatus,
    kind: SetupPrimaryActionKind,
  ) => {
    if (kind === "add_source_url") {
      setAddSourceFor(component);
      return;
    }
    setBusyId(component.id);
    setMessage(null);
    try {
      if (kind === "refresh_source") {
        const result = await api.setupRefreshSource(component.id);
        if (!result.source_valid) {
          setMessage(
            result.error?.message
              ?? "Automatic source discovery did not find a compatible download.",
          );
        }
      } else if (kind === "link_existing") {
        const result = await api.setupLinkExisting(component.id);
        trackOperation(result.operation_id, result);
      } else if (kind === "choose_install_location" || kind === "install") {
        setPreflightFor(component);
        return;
      } else if (kind === "recommended_action" && component.status === "error" && component.source_available) {
        const existing = installJobsByComponent[component.id];
        if (existing) {
          await api.installJobs.repair(existing.id);
          await refreshInstallJobs();
        } else {
          setPreflightFor(component);
        }
        return;
      } else if (kind === "update" || kind === "recommended_action") {
        const result = await api.setupRecommendedAction(component.id);
        trackOperation(result.operation_id, result);
      } else if (kind === "diagnostics") {
        await api.setupDiagnostics(component.id);
      } else {
        const result = await api.setupRecommendedAction(component.id);
        trackOperation(result.operation_id, result);
      }
      await refresh();
    } catch (error) {
      if (isNetworkUnavailableError(error)) {
        setMessage("Studio API is unreachable. Start the local API, then try again.");
      } else {
        setMessage(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusyId(null);
    }
  };

  const confirmPreflight = async (component: SetupComponentStatus, payload: PreflightConfirm) => {
    setPreflightBusy(true);
    setMessage(null);
    try {
      await api.installJobs.create(component.id, {
        projectId,
        action: component.status === "error" ? "repair" : "install",
        destinationRoot: payload.destinationRoot,
        confirm: payload.confirm,
        confirmDownloadModels: payload.confirmDownloadModels,
      });
      setPreflightFor(null);
      await Promise.all([refresh(), refreshInstallJobs()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setPreflightBusy(false);
    }
  };

  const runInstallJobAction = async (
    job: InstallJob,
    action: "pause" | "resume" | "cancel" | "retry" | "repair" | string,
  ) => {
    setBusyId(job.id);
    setMessage(null);
    try {
      if (action === "pause") await api.installJobs.pause(job.id);
      else if (action === "resume") await api.installJobs.resume(job.id);
      else if (action === "cancel" || action === "cancel_safely") await api.installJobs.cancel(job.id);
      else if (action === "retry") await api.installJobs.retry(job.id);
      else if (action === "repair") {
        const preferred =
          job.recoveryActions?.[0]?.action ||
          job.error?.suggestedAction ||
          job.error?.recommendedAction ||
          "retry_download";
        await api.installJobs.repair(job.id, preferred);
      } else {
        await api.installJobs.repair(job.id, action);
      }
      await Promise.all([refresh(), refreshInstallJobs()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const runPrimaryAction = async (component: SetupComponentStatus) => {
    const kind = primaryActionKind(component);
    if (!kind) return;
    if (component.installer === "asset_pack" || component.verifier === "asset_pack") {
      await runPackAction(component, kind);
      return;
    }
    setBusyId(component.id);
    setMessage(null);
    try {
      if (kind === "diagnostics") {
        await api.setupDiagnostics(component.id);
      } else if (kind === "refresh_source") {
        const result = await api.setupRefreshSource(component.id);
        if (!result.source_valid) {
          setMessage(result.error?.message ?? "Download source unavailable.");
        }
      } else if (kind === "link_existing") {
        const result = await api.setupLinkExisting(component.id);
        trackOperation(result.operation_id, result);
      } else {
        const result = await api.setupRecommendedAction(component.id);
        trackOperation(result.operation_id, result);
      }
      await refresh();
    } catch (error) {
      if (isNetworkUnavailableError(error)) {
        setMessage("Studio API is unreachable. Start the local API, then try again.");
      } else {
        setMessage(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusyId(null);
    }
  };

  const runSecondaryAction = async (component: SetupComponentStatus) => {
    await runPackAction(component, "link_existing");
  };

  const runAdvancedAction = async (component: SetupComponentStatus, action: string) => {
    if (
      action === "remove"
      && !window.confirm(
        `Remove ${component.name} from Setup configuration? Installed files are not deleted automatically.`,
      )
    ) {
      return;
    }
    setBusyId(component.id);
    setMessage(null);
    try {
      const result = await api.setupAction(
        component.id,
        action,
        pathDrafts[component.id] ?? component.installation_path ?? "",
        true,
      );
      setMessage(`${component.name}: ${result.status}${result.message ? ` — ${result.message}` : ""}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const deferUpdate = async (componentId: string) => {
    setBusyId(componentId);
    setMessage(null);
    try {
      await api.setupUpdateLater(componentId);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const answerCheckpoint = async (answer: {
    accepted?: boolean;
    license_accepted?: boolean;
    path?: string;
    completed?: boolean;
    cancelled?: boolean;
  }) => {
    if (!activeCheckpoint) return;
    setBusyId("checkpoint");
    setMessage(null);
    try {
      const operation = await api.setupCheckpoint(activeCheckpoint.operationId, {
        checkpoint_id: activeCheckpoint.checkpoint.checkpoint_id ?? activeCheckpoint.checkpoint.id,
        ...answer,
      });
      setOperations((current) => ({ ...current, [operation.operation_id]: operation }));
      setActiveCheckpoint(null);
      if (operation.status === "cancelled") {
        setTrackedOperationIds((current) => current.filter((id) => id !== operation.operation_id));
        setMessage("Setup cancelled.");
      } else {
        trackOperation(operation.operation_id, operation);
      }
      // The operation poll refreshes status after the worker reaches a terminal
      // state. Refreshing here can race the worker's selected-path write and
      // overwrite it in older API processes.
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const closeCheckpoint = () => {
    if (busyId === "checkpoint" || !activeCheckpoint) return;
    const closing = activeCheckpoint;
    setActiveCheckpoint(null);
    setTrackedOperationIds((current) => current.filter((id) => id !== closing.operationId));
    setOperations((current) => {
      const next = { ...current };
      delete next[closing.operationId];
      return next;
    });
    void api.setupCheckpoint(closing.operationId, {
      checkpoint_id: closing.checkpoint.checkpoint_id ?? closing.checkpoint.id,
      accepted: false,
      license_accepted: true,
      path: "cancelled",
      cancelled: true,
    }).then(() => {
      setMessage("Setup cancelled.");
      void refresh();
    }).catch(() => {
      setMessage("Setup dialog closed. Restart the local API before retrying this installation.");
    });
  };

  if (!status) {
    return (
      <div className="page setup-wizard-page">
        <div className="panel">
          <PanelHeading title="Setup Wizard" tip="Checks the components required for your studio." />
          <p className="empty" role="status">{message ?? "Checking studio status…"}</p>
          {message && <button type="button" onClick={() => void refresh()}>Try Again</button>}
        </div>
      </div>
    );
  }

  const visibleComponents = status.components.filter((component) => component.category !== "Avatar Runtimes");
  const required = visibleComponents.filter((component) => component.required);
  const optional = visibleComponents.filter((component) => !component.required);
  const preparing = trackedOperationIds.length > 0 || status.overall_status === "preparing";
  const openLifecyclePreflight = (component: SetupComponentStatus) => setPreflightFor(component);
  const repairLifecycleComponent = (component: SetupComponentStatus) => {
    const existing = installJobsByComponent[component.id];
    if (existing) {
      void runInstallJobAction(existing, "repair");
      return;
    }
    setPreflightFor(component);
  };
  const verifyLifecycleComponent = (component: SetupComponentStatus) => {
    void api.setupLifecycleVerify(component.id)
      .then(() => refresh())
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
  };

  return (
    <div className="page setup-wizard-page">
      <PanelHeading title="Setup Wizard" tip="Checks readiness and prepares required studio components." />
      <section className="panel" aria-label="Setup mode">
        <div className="setup-section-heading">
          <div>
            <h2>Setup Mode</h2>
            <p>Choose the setup experience that fits how you want to work right now.</p>
          </div>
        </div>
        <div className="row-actions">
          <button type="button" className={setupMode === "guided" ? "primary" : "ghost"} onClick={() => setSetupMode("guided")}>
            Guided
          </button>
          <button type="button" className={setupMode === "ai_guided" ? "primary" : "ghost"} onClick={() => setSetupMode("ai_guided")}>
            AI-Guided
          </button>
          <button type="button" className={setupMode === "manual" ? "primary" : "ghost"} onClick={() => setSetupMode("manual")}>
            Manual
          </button>
        </div>
        <p className="muted">
          {setupMode === "guided" ? "Guided keeps the existing Prepare My Studio flow front and center."
            : setupMode === "ai_guided" ? "AI-Guided recommends certified providers, compares options, and walks you through install, calibration, and certification."
            : "Manual keeps the full setup catalog, advanced actions, and Source Manager tools visible."}
        </p>
      </section>
      <SetupSummary status={status} preparing={preparing} projectId={projectId} onPrepare={() => void preparePlan()} />

      {message && <div className="setup-message" role="status">{message}</div>}

      {setupMode === "ai_guided" ? (
        <AiGuidedSetupPanel
          projectId={projectId}
          focusComponentId={focusedSetupComponentId}
          status={status}
          installJobsByComponent={installJobsByComponent}
          onInstall={openLifecyclePreflight}
          onRepair={repairLifecycleComponent}
          onVerify={verifyLifecycleComponent}
        />
      ) : (
        <>
          <DownloadSourcesPanel onMessage={setMessage} />
          <p className="setup-nav-strip">
            <Link to={`/source-manager${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`} data-testid="open-source-manager">
              Open Source Manager
            </Link>{" "}
            for provider priority, saved sources, and download queue tools.
          </p>

          <ModelStoragePanel onMessage={(m) => setMessage(m)} />

          <HostedProvidersSetupPanel onMessage={setMessage} />

          <p className="setup-nav-strip">
            <Link to="/runtime-manager" data-testid="open-runtime-manager">
              Open Runtime Manager
            </Link>{" "}
            for Docker Local runtimes, repair, and safe uninstall.
          </p>

          <AddCustomCapability onRegistered={() => void refresh()} />

          <VideoModelLibrary />
          <PromptIntelligenceBenchmarkDashboard />

          {setupMode === "manual" && (
            <div className="panel">
              <p>Manual mode keeps the full component list, advanced actions, and Source Manager workflow visible.</p>
            </div>
          )}

          <section className="setup-component-section" aria-labelledby="required-components-heading">
        <div className="setup-section-heading">
          <div>
            <h2 id="required-components-heading">Required</h2>
            <p>Needed for the core studio workflow.</p>
          </div>
          <span>{required.length} component{required.length === 1 ? "" : "s"}</span>
        </div>
        <div className="setup-component-grid">
          {required.map((component) => (
            <SetupComponentCard
              key={component.id}
              component={component}
              operation={operationsByComponent[component.id]}
              installJob={installJobsByComponent[component.id]}
              busy={busyId != null}
              onPrimaryAction={(item) => void runPrimaryAction(item)}
              onPackAction={(item, action) => void runPackAction(item, action)}
              onLater={(id) => void deferUpdate(id)}
              onInstallJobPause={(job) => void runInstallJobAction(job, "pause")}
              onInstallJobResume={(job) => void runInstallJobAction(job, "resume")}
              onInstallJobCancel={(job) => void runInstallJobAction(job, "cancel")}
              onInstallJobRetry={(job) => void runInstallJobAction(job, "retry")}
              onInstallJobRepair={(job) => void runInstallJobAction(job, "repair")}
              onInstallJobAction={(job, action) => void runInstallJobAction(job, action)}
            />
          ))}
        </div>
      </section>

          <section className="setup-component-section" aria-labelledby="optional-components-heading">
        <div className="setup-section-heading">
          <div>
            <h2 id="optional-components-heading">Optional</h2>
            <p>Add capabilities without blocking your studio.</p>
          </div>
          <span>{optional.length} component{optional.length === 1 ? "" : "s"}</span>
        </div>
        <div className="setup-component-grid">
          {optional.map((component) => (
            <SetupComponentCard
              key={component.id}
              component={component}
              operation={operationsByComponent[component.id]}
              installJob={installJobsByComponent[component.id]}
              busy={busyId != null}
              onPrimaryAction={(item) => void runPrimaryAction(item)}
              onSecondaryAction={(item) => void runSecondaryAction(item)}
              onPackAction={(item, action) => void runPackAction(item, action)}
              onLater={(id) => void deferUpdate(id)}
              onInstallJobPause={(job) => void runInstallJobAction(job, "pause")}
              onInstallJobResume={(job) => void runInstallJobAction(job, "resume")}
              onInstallJobCancel={(job) => void runInstallJobAction(job, "cancel")}
              onInstallJobRetry={(job) => void runInstallJobAction(job, "retry")}
              onInstallJobRepair={(job) => void runInstallJobAction(job, "repair")}
              onInstallJobAction={(job, action) => void runInstallJobAction(job, action)}
            />
          ))}
        </div>
      </section>
          <SetupAdvancedPanel
            status={status}
            legacy={legacyDetection}
            operations={operations}
            busyId={busyId}
            pathDrafts={pathDrafts}
            onPathChange={(componentId, value) => setPathDrafts((current) => ({ ...current, [componentId]: value }))}
            onAction={(component, action) => void runAdvancedAction(component, action)}
            onOpen={() => {
              if (!legacyDetection) {
                void api.setupDetect()
                  .then(setLegacyDetection)
                  .catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
              }
            }}
          />
        </>
      )}

      {plan && (
        <PreparationPlanDialog
          plan={plan}
          busy={busyId === "prepare"}
          onCancel={() => setPlan(null)}
          onConfirm={() => void startPreparation()}
        />
      )}
      {preflightFor && (
        <PreflightDialog
          open
          componentId={preflightFor.id}
          componentName={preflightFor.name}
          expectedBytes={preflightFor.expected_download_bytes ?? preflightFor.download_size_bytes ?? null}
          gpuSummary={preflightFor.recommended_vram_gb ? `${preflightFor.recommended_vram_gb} GB recommended` : null}
          requiresModelDownloadConfirm={(preflightFor.expected_download_bytes ?? preflightFor.download_size_bytes ?? 0) >= 10 * 1024 * 1024 * 1024}
          busy={preflightBusy}
          onClose={() => setPreflightFor(null)}
          onConfirm={(payload) => void confirmPreflight(preflightFor, payload)}
        />
      )}
      {addSourceFor && (
        <AddSourceWorkflow
          open
          componentId={addSourceFor.id}
          componentName={addSourceFor.name}
          onClose={() => setAddSourceFor(null)}
          onSaved={() => {
            setAddSourceFor(null);
            void Promise.all([refresh(), refreshInstallJobs()]);
          }}
        />
      )}
      {activeCheckpoint && (
        <SetupCheckpointDialog
          key={activeCheckpoint.checkpoint.checkpoint_id ?? activeCheckpoint.checkpoint.id ?? activeCheckpoint.operationId}
          checkpoint={activeCheckpoint.checkpoint}
          busy={busyId === "checkpoint"}
          onSubmit={(answer) => void answerCheckpoint(answer)}
          onClose={closeCheckpoint}
        />
      )}
    </div>
  );
}

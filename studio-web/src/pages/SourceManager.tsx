import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { ActiveDownloadsPanel } from "../components/ActiveDownloadsPanel";
import { AvatarRuntimeInstallPanel } from "../components/AvatarRuntimeInstallPanel";
import { CapabilityReadinessPanel, useCapabilities } from "../components/CapabilityPanel";
import { CharacterVoiceModelsPanel } from "../components/CharacterVoiceModelsPanel";
import { InstallHistoryPanel } from "../components/InstallHistoryPanel";
import { AddSourceWorkflow } from "../components/install/AddSourceWorkflow";
import { PreflightDialog, type PreflightConfirm } from "../components/install/PreflightDialog";
import { RequiredComponentsPanel } from "../components/install/RequiredComponentsPanel";
import { StudioChrome } from "../components/dashboard/StudioChrome";
import { DownloadSourcesPanel } from "../components/DownloadSourcesPanel";
import { useInstallJobsPoll } from "../hooks/useInstallJobsPoll";
import type { InstallJob } from "../contracts/installJobs";
import type { SetupComponentStatus, SourceManagerOverview, SourceManagerProvider, SourceRecord } from "../setup/types";
import { StatusBadge } from "../components/ui";

function providerTone(status: string): string {
  if (status === "Ready") return "ready";
  if (status === "Installed but not authenticated") return "attention";
  if (status === "Not installed" || status === "Unavailable") return "missing";
  return "error";
}

function providerStatusKind(status: string) {
  if (status === "Ready") return "Ready" as const;
  if (status === "Not installed") return "InstallRequired" as const;
  if (status === "Unavailable") return "Offline" as const;
  if (status === "Installed but not authenticated") return "NeedsAttention" as const;
  return "Unknown" as const;
}

export default function SourceManagerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [overview, setOverview] = useState<SourceManagerOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [setupComponents, setSetupComponents] = useState<SetupComponentStatus[]>([]);
  const [requiredOpen, setRequiredOpen] = useState(false);
  const [sourceWorkflowFor, setSourceWorkflowFor] = useState<SetupComponentStatus | null>(null);
  const [preflightFor, setPreflightFor] = useState<SetupComponentStatus | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);

  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const projectId = searchParams.get("projectId") || undefined;
  const requestedComponentId = searchParams.get("componentId") || undefined;
  const relevantSubsystems = ["models", "extensions", "workflows", "comfyui", "generation", "source_manager", "downloads", "references"];
  const { snapshot } = useCapabilities({ projectId, pollMs: 30000 });
  const { jobs: installJobs, refresh: refreshInstallJobs } = useInstallJobsPoll(true, 900, { activeOnly: false });

  const refresh = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.sourceManagerOverview();
      setOverview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const refreshSetupComponents = async () => {
    try {
      const status = await api.setupStatus();
      setSetupComponents(status.components || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void refresh();
    void refreshSetupComponents();
  }, []);

  useEffect(() => {
    if (location.hash === "#required-components") {
      setRequiredOpen(true);
      void refreshSetupComponents();
    }
  }, [location.hash]);

  const blockers = useMemo(() => {
    const all = snapshot?.blockers || [];
    return all.filter((item) => relevantSubsystems.includes(item.subsystem));
  }, [snapshot]);

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

  const removeSource = async (source: SourceRecord) => {
    if (!window.confirm(`Remove saved source “${source.displayName || source.sourceUrl}”?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.sourceManagerDeleteSource(source.id);
      setMessage("Source removed. Defaults remain recoverable for components.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const providers = overview?.providers || [];
  const sources = overview?.sources || [];

  const actionLabelFor = (component: SetupComponentStatus) => {
    const job = installJobsByComponent[component.id];
    if (job && !["ready", "completed", "failed", "repair_required", "cancelled"].includes(job.state)) {
      return "View Progress";
    }
    if (!component.source_available) return "Add Source";
    if (component.source_valid === false) return "Validate";
    if (component.status === "ready") return "Verify";
    if (component.status === "error") return "Repair";
    return "Install";
  };

  const runInstallJobAction = async (job: InstallJob, action: "repair" | "verify" | string) => {
    setBusy(true);
    setError(null);
    try {
      if (action === "verify") await api.installJobs.verify(job.id);
      else if (action === "repair") {
        const preferred =
          job.recoveryActions?.[0]?.action ||
          job.error?.suggestedAction ||
          job.error?.recommendedAction ||
          "retry_download";
        await api.installJobs.repair(job.id, preferred);
      } else if (action === "cancel" || action === "cancel_safely") {
        await api.installJobs.cancel(job.id);
      } else if (action === "retry") {
        await api.installJobs.retry(job.id);
      } else if (action === "pause") {
        await api.installJobs.pause(job.id);
      } else if (action === "resume") {
        await api.installJobs.resume(job.id);
      } else {
        await api.installJobs.repair(job.id, action);
      }
      await Promise.all([refreshInstallJobs(), refreshSetupComponents(), refresh()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const confirmPreflight = async (component: SetupComponentStatus, payload: PreflightConfirm) => {
    setPreflightBusy(true);
    setError(null);
    try {
      await api.installJobs.create(component.id, {
        projectId,
        action: component.status === "error" ? "repair" : "install",
        destinationRoot: payload.destinationRoot,
        confirm: payload.confirm,
        confirmDownloadModels: payload.confirmDownloadModels,
      });
      setPreflightFor(null);
      await Promise.all([refresh(), refreshSetupComponents(), refreshInstallJobs()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPreflightBusy(false);
    }
  };

  const handleInstallAction = async (component: SetupComponentStatus) => {
    const label = actionLabelFor(component);
    if (label === "View Progress") {
      document.getElementById("active-downloads-heading")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (label === "Add Source") {
      setSourceWorkflowFor(component);
      return;
    }
    if (label === "Validate") {
      setBusy(true);
      setError(null);
      try {
        await api.setupRefreshSource(component.id);
        await Promise.all([refresh(), refreshSetupComponents()]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
      return;
    }
    if (label === "Verify") {
      const job = installJobsByComponent[component.id];
      if (job) {
        await runInstallJobAction(job, "verify");
      } else {
        setBusy(true);
        setError(null);
        try {
          await api.setupAction(component.id, "verify", component.installation_path ?? "", true);
          await Promise.all([refresh(), refreshSetupComponents()]);
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          setBusy(false);
        }
      }
      return;
    }
    if (label === "Repair") {
      const job = installJobsByComponent[component.id];
      if (job) {
        await runInstallJobAction(job, "repair");
      } else {
        setPreflightFor(component);
      }
      return;
    }
    setPreflightFor(component);
  };

  return (
    <div className="source-manager-page" data-testid="source-manager-page">
      <StudioChrome
        variant="home"
        breadcrumbs={[
          { label: "Home", onClick: () => navigate("/") },
          { label: "Setup" },
          { label: "Source Manager" },
        ]}
      />
      <main className="setup-wizard-page">
        <div className="panel-heading">
          <h2>Source Manager</h2>
          <p>
            Central place for download providers, saved sources, and (soon) install queue, asset
            intelligence, and dependency health. Setup Wizard continues to guide Essential packs.
          </p>
        </div>

        {overview?.messages?.intro && (
          <p className="setup-message" role="status">
            {overview.messages.intro}
          </p>
        )}
        {message && (
          <p className="setup-message" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="setup-message error" role="alert">
            {error}
          </p>
        )}

        <section className="setup-component-section ds-surface" aria-labelledby="sm-capabilities-heading">
          <div className="setup-section-heading">
            <h2 id="sm-capabilities-heading">What is blocked right now</h2>
            <p>
              Read from the capability registry, so this says the same thing as the Health surface
              and the Setup Wizard. Actions here navigate — no download starts without your
              explicit approval on a component card.
            </p>
          </div>
          <CapabilityReadinessPanel
            projectId={projectId}
            title="Blocked capabilities"
            subsystems={relevantSubsystems}
            limit={12}
          />
        </section>

        <section className="setup-component-section ds-surface" aria-labelledby="sm-providers-heading">
          <div className="setup-section-heading">
            <div>
              <h2 id="sm-providers-heading">Providers</h2>
              <p>Capability-based selection — GitHub CLI preferred when authenticated.</p>
            </div>
            <button type="button" className="linkish" disabled={busy} onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          <div className="setup-component-grid" data-testid="source-manager-providers">
            {providers.map((provider: SourceManagerProvider) => (
              <article
                key={provider.id}
                className={`setup-component-card download-source-card status-${providerTone(provider.status)}`}
                data-testid={`source-provider-${provider.id}`}
                data-status={provider.status}
              >
                <header className="setup-card-header">
                  <div>
                    <h3>{provider.displayName}</h3>
                    <span className="setup-requirement">Priority {provider.priority}</span>
                  </div>
                  <StatusBadge kind={providerStatusKind(provider.status)} label={provider.status} compact />
                </header>
                <p className="setup-component-description">{provider.message || "—"}</p>
                <div className="setup-card-meta">
                  <span>{provider.available ? "Available" : "Unavailable"}</span>
                  {provider.version && <span>Version {provider.version}</span>}
                  {provider.executablePath && (
                    <span>
                      Path <code>{provider.executablePath}</code>
                    </span>
                  )}
                  <span>Auth {provider.authenticated ? "signed in" : "not required / not signed in"}</span>
                </div>
                {provider.capabilities?.length ? (
                  <div className="sm-provider-caps">
                    <strong>Capabilities</strong>
                    {provider.capabilities.join(" · ")}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>

        <CharacterVoiceModelsPanel onChanged={() => void refresh()} />
        <AvatarRuntimeInstallPanel
          components={setupComponents}
          installJobsByComponent={installJobsByComponent}
          onChanged={async () => {
            await Promise.all([refresh(), refreshSetupComponents(), refreshInstallJobs()]);
          }}
        />

        <section className="setup-component-section" aria-labelledby="sm-cli-heading">
          <div className="setup-section-heading">
            <h2 id="sm-cli-heading">CLI Download Sources</h2>
            <p>Same GitHub / Hugging Face cards as Setup Wizard — detect, install, sign in, verify.</p>
          </div>
          <DownloadSourcesPanel onMessage={setMessage} />
        </section>

        <section className="setup-component-section" aria-labelledby="sm-saved-heading">
          <div className="setup-section-heading">
            <h2 id="sm-saved-heading">Saved Sources</h2>
            <p>Normalized source records (migrated from component overrides when present).</p>
          </div>
          {sources.length === 0 ? (
            <p className="setup-message" data-testid="source-manager-empty-sources">
              No saved sources yet. Use Setup Wizard → Add Source URL, or verify a URL from a component
              card.
            </p>
          ) : (
            <div className="setup-component-grid" data-testid="source-manager-sources">
              {sources.map((source) => (
                <article
                  key={source.id}
                  className="setup-component-card"
                  data-testid={`saved-source-${source.id}`}
                >
                  <header className="setup-card-header">
                    <div>
                      <h3>{source.displayName || source.repository || "Source"}</h3>
                      <span className="setup-requirement">
                        {source.provider}
                        {source.userDefined ? " · custom" : " · default"}
                      </span>
                    </div>
                    <span className="setup-status" data-state={source.verificationStatus === "verified" ? "ready" : "attention"}>
                      {source.verificationStatus}
                    </span>
                  </header>
                  <p className="setup-component-description">
                    <a href={source.sourceUrl} target="_blank" rel="noreferrer">
                      {source.sourceUrl}
                    </a>
                  </p>
                  <div className="setup-card-meta">
                    {source.revision && <span>Revision {source.revision}</span>}
                    {source.verifiedAt && (
                      <span>Verified {new Date(source.verifiedAt).toLocaleString()}</span>
                    )}
                    <span>
                      Components {(source.componentsUsing || []).length
                        ? (source.componentsUsing || []).join(", ")
                        : "none"}
                    </span>
                  </div>
                  <div className="setup-card-actions">
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy}
                      onClick={() => void removeSource(source)}
                    >
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <ActiveDownloadsPanel onChanged={() => void Promise.all([refresh(), refreshSetupComponents(), refreshInstallJobs()])} />
        <InstallHistoryPanel />

        <section className="setup-component-section" aria-labelledby="sm-deferred-heading">
          <div className="setup-section-heading">
            <h2 id="sm-deferred-heading">Coming next</h2>
          </div>
          <div className="setup-card-meta" data-testid="source-manager-deferred">
            <span>Asset Intelligence — Phase 1C</span>
            <span>Dependency Overview — Phase 1D</span>
            <span>Health Dashboard — Phase 1E</span>
            <span>Full Rollback — Phase 1F</span>
          </div>
          <p className="setup-message">
            <Link to="/">Return home</Link>
            {" · "}
            Open any project and use Setup Wizard for Essential pack installs.
          </p>
        </section>

        <RequiredComponentsPanel
          open={requiredOpen}
          blockers={blockers}
          components={setupComponents.filter((component) => !requestedComponentId || component.id === requestedComponentId || blockers.some((blocker) => blocker.componentIds.includes(component.id)))}
          onClose={() => setRequiredOpen(false)}
          actionLabelFor={actionLabelFor}
          onUseOfficial={(component) => {
            void api.setupRefreshSource(component.id)
              .then(() => Promise.all([refresh(), refreshSetupComponents()]))
              .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
          }}
          onAddSource={(component) => setSourceWorkflowFor(component)}
          onInstall={(component) => { void handleInstallAction(component); }}
          onRepair={(component) => {
            const job = installJobsByComponent[component.id];
            if (job) {
              void runInstallJobAction(job, "repair");
            } else {
              setPreflightFor(component);
            }
          }}
          onVerify={(component) => { void handleInstallAction({ ...component, status: "ready" }); }}
        />

        {sourceWorkflowFor && (
          <AddSourceWorkflow
            open
            componentId={sourceWorkflowFor.id}
            componentName={sourceWorkflowFor.name}
            onClose={() => setSourceWorkflowFor(null)}
            onSaved={() => {
              setSourceWorkflowFor(null);
              void Promise.all([refresh(), refreshSetupComponents()]);
            }}
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
      </main>
    </div>
  );
}

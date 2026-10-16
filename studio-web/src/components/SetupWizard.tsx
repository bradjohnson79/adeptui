import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../api";
import {
  isNetworkUnavailableError,
  nextPollDelayMs,
} from "../setup/helpers";
import { installationProfileLabel, scanAllowsCompletion, setupWizardRequired } from "../setup/firstRun";
import { FirstRunSetupModal, PROFILE_COPY, type InstallProfile } from "../setup/FirstRunSetupModal";
import { ProviderKeysPanel } from "../setup/ProviderKeysPanel";
import { ModelLicenseDialog } from "../setup/ModelLicenseDialog";
import type {
  SetupCheckpoint,
  SetupComponentStatus,
  SetupOperation,
  SetupPrimaryActionKind,
  SetupStatusResponse,
} from "../setup/types";
import type { InstallJob } from "../contracts/installJobs";
import { useInstallJobsPoll } from "../hooks/useInstallJobsPoll";
import { isApiKeyCatalogComponent } from "./hostedProviderSetupCopy";
import { PanelHeading } from "./HelpTip";
import { AddSourceWorkflow } from "./install/AddSourceWorkflow";
import { PreflightDialog, type PreflightConfirm } from "./install/PreflightDialog";
import { SetupComfyStep } from "../setup/SetupComfyStep";
import { SetupLocalModels } from "../setup/SetupLocalModels";

const TERMINAL_OPERATION_STATES = new Set(["completed", "failed", "cancelled", "interrupted"]);

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
          const ltx = current.components.find((item) => item.id === "ltx_2_5_checkpoint");
          const verifiedPath = component?.installation_path || ltx?.installation_path || "";
          let fallback = verifiedPath;
          const normalized = verifiedPath.replace(/\//g, "\\");
          const modelsMarker = normalized.toLowerCase().lastIndexOf("\\models\\");
          if (componentId !== "ltx_2_5_checkpoint" && modelsMarker >= 0) {
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

export function SetupWizardPanel({ projectId }: { projectId?: string }) {
  const firstRunSaveRef = useRef(false);
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [, setOperations] = useState<Record<string, SetupOperation>>({});
  const [trackedOperationIds, setTrackedOperationIds] = useState<string[]>([]);
  const [activeCheckpoint, setActiveCheckpoint] = useState<{ operationId: string; checkpoint: SetupCheckpoint } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [addSourceFor, setAddSourceFor] = useState<SetupComponentStatus | null>(null);
  const [preflightFor, setPreflightFor] = useState<SetupComponentStatus | null>(null);
  const [licenseFor, setLicenseFor] = useState<SetupComponentStatus | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const { jobs: installJobs, refresh: refreshInstallJobs } = useInstallJobsPoll(true, 1000, { activeOnly: false });

  const refresh = useCallback(async (force = false) => {
    if (force) setScanning(true);
    try {
      const next = await api.setupStatus(force);
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
      return next;
    } finally {
      if (force) setScanning(false);
    }
  }, []);

  useEffect(() => {
    refresh().catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
  }, [refresh]);

  useEffect(() => {
    if (!status || status.firstRunSetupComplete || firstRunSaveRef.current) return;
    if (!scanAllowsCompletion(status.firstRunScan)) return;
    firstRunSaveRef.current = true;
    api.completeFirstRun()
      .then(() => {
        setStatus((current) => (current ? { ...current, firstRunSetupComplete: true } : current));
      })
      .catch((error: unknown) => {
        firstRunSaveRef.current = false;
        setMessage(error instanceof Error ? error.message : String(error));
      });
  }, [status]);

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
          <PanelHeading title="Setup" tip="Choose how Adept runs, manage local models, and save API keys." />
          <p className="empty" role="status">{message ?? "Scanning your system…"}</p>
          {message && <button type="button" onClick={() => void refresh()}>Try Again</button>}
        </div>
      </div>
    );
  }

  const toggleModel = async (component: SetupComponentStatus, selected: boolean) => {
    const profile = status?.installationProfile;
    if (profile !== "local" && profile !== "hybrid" && profile !== "api") return;
    const current = status?.selectedLocalModels || [];
    const selectedLocalModels = selected
      ? Array.from(new Set([...current, component.id]))
      : current.filter((id) => id !== component.id);
    try {
      const next = await api.saveInstallationProfile({
        profile,
        selectedLocalModels,
        selectedProviders: status?.selectedProviders || (status?.connectedProviders || []).map((item) => item.id),
      });
      setStatus(next);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const removeModel = async (component: SetupComponentStatus) => {
    setBusyId(component.id);
    setMessage(null);
    try {
      await api.removeSetupComponent(component.id, true);
      await refresh(true);
      setMessage(`${component.name} was removed.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const hiddenCatalogCategories = new Set(["Avatar Runtimes", "API Providers"]);
  const visibleComponents = status.components.filter((component) => {
    if (hiddenCatalogCategories.has(component.category || "")) return false;
    if (isApiKeyCatalogComponent(component)) return false;
    return true;
  });
  const comfyuiReady = status.components.some((component) => component.id === "comfyui" && component.status === "ready");
  const comfyComponent = status.components.find((component) => component.id === "comfyui");
  const comfyInstalled = Boolean(comfyComponent && (comfyComponent.status === "ready" || comfyComponent.installation_path));
  const preparing = trackedOperationIds.length > 0 || status.overall_status === "preparing";

  if (setupWizardRequired(status) && !wizardOpen) {
    setWizardOpen(true);
  }

  /** Permanent Setup Wizard: switching profiles here preserves saved keys, selected models, and installed files. */
  const changeProfile = async (profile: InstallProfile) => {
    if ((status.installationProfile || "") === profile) return;
    try {
      const next = await api.saveInstallationProfile({
        profile,
        selectedLocalModels: status.selectedLocalModels || [],
        selectedProviders: status.selectedProviders || (status.connectedProviders || []).map((item) => item.id),
      });
      setStatus(next);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <>
    {wizardOpen && (
      <FirstRunSetupModal
        status={status}
        scanning={scanning}
        installing={busyId === "prepare" || preparing}
        onRescan={() => refresh(true)}
        onSaveProfile={async (body) => {
          try {
            const next = await api.saveInstallationProfile(body);
            setStatus(next);
            return next;
          } catch (error) {
            setMessage(error instanceof Error ? error.message : String(error));
            return null;
          }
        }}
        onBegin={async () => {
          setBusyId("prepare");
          setMessage(null);
          try {
            const applied = await api.applyInstallationProfile();
            if (applied.errors?.length) {
              setMessage(applied.errors.map((item) => item.message).join(" "));
            }
            await refresh(true);
            await refreshInstallJobs();
            return applied;
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setMessage(message);
            return { errors: [{ id: "apply", message }] };
          } finally {
            setBusyId(null);
          }
        }}
        onFinish={() => setWizardOpen(false)}
      />
    )}
    <div className="page setup-wizard-page" hidden={wizardOpen} data-project-id={projectId || ""}>
      <PanelHeading title="Setup" tip="Choose how Adept runs, manage local models, and save API keys." />
      {message && <div className="setup-message" role="status">{message}</div>}
      <section className="panel setup-wizard-permanent" aria-label="Setup Wizard" data-testid="setup-wizard-permanent">
        <h2>Setup Wizard</h2>
        <section aria-label="Installation Profile" data-testid="setup-profile-section">
          <h3>Installation Profile</h3>
          <div className="setup-choice-list" role="radiogroup" aria-label="Installation profile">
            {(["local", "hybrid", "api"] as const).map((id) => (
              <label key={id} className={`setup-choice${(status.installationProfile || "") === id ? " is-selected" : ""}`}>
                <input
                  type="radio"
                  name="installation-profile-page"
                  checked={(status.installationProfile || "") === id}
                  data-testid={`profile-radio-${id}`}
                  onChange={() => void changeProfile(id)}
                />
                <span className="setup-choice-indicator" aria-hidden="true" />
                <span className="setup-choice-text">
                  <span className="setup-choice-title">{PROFILE_COPY[id].title}</span>
                  <span className="setup-choice-description">{PROFILE_COPY[id].body}</span>
                </span>
              </label>
            ))}
          </div>
        </section>
        <section aria-label="API Providers & Keys" data-testid="setup-api-keys-section">
          <h3>API Providers &amp; Keys</h3>
          <ProviderKeysPanel
            connectedProviders={status.connectedProviders || []}
            onChanged={() => refresh(true)}
          />
        </section>
        <section aria-label="System Configuration" data-testid="setup-system-config-section">
          <h3>System Configuration</h3>
          <p>
            Installation profile: {installationProfileLabel(status.installationProfile)}.
          </p>
          {(status.installationProfile || "") === "api" && (
            <p>ComfyUI and local generation models are not required for Full API Installation.</p>
          )}
          <p>
            Local models: {status.localModelsInstalled ?? 0} installed, {status.localModelsAvailable ?? 0} available.
          </p>
          <p>
            API providers: {(status.connectedProviders || []).length} connected
            {(status.connectedProviders || []).length ? ` (${status.connectedProviders?.map((item) => item.name).join(", ")})` : ""}.
          </p>
          <p>
            System readiness: {status.overall_label}.
          </p>
        </section>
      </section>
      <SetupLocalModels
        profile={status.installationProfile || ""}
        components={visibleComponents}
        selectedIds={status.selectedLocalModels || []}
        jobs={installJobsByComponent}
        busy={busyId != null}
        scanning={scanning}
        onInstall={(component) => void runPackAction(component, "install")}
        onUpdate={(component) => void runPackAction(component, "update")}
        onRemove={removeModel}
        onToggleSelected={(component, selected) => void toggleModel(component, selected)}
        onRescan={() => void refresh(true)}
      />
      <SetupComfyStep
        profile={
          status.installationProfile === "local" || status.installationProfile === "hybrid" || status.installationProfile === "api"
            ? status.installationProfile
            : ""
        }
        selectedLocalIds={status.selectedLocalModels || []}
        comfyReady={comfyuiReady}
        comfyInstalled={comfyInstalled}
        onRescan={() => {
          void refresh(true);
        }}
      />
    </div>

      {licenseFor?.model_license?.modelId && (
        <ModelLicenseDialog
          modelId={licenseFor.model_license.modelId}
          onClose={() => setLicenseFor(null)}
          onConfirmed={() => {
            setLicenseFor(null);
            void refresh();
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
    </>
  );
}

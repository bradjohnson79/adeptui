import { useCallback, useEffect, useState } from "react";
import { api, type RuntimeManagerPreferences, type RuntimeManagerStatus } from "../../api";

export function LocalRuntimeSettings() {
  const [status, setStatus] = useState<RuntimeManagerStatus | null>(null);
  const [prefs, setPrefs] = useState<RuntimeManagerPreferences>({
    comfyuiBackgroundManagerEnabled: false,
    localhostBackgroundManagerEnabled: false,
    startWithWindows: false,
    remoteAccessEnabled: false,
  });
  const [hosted, setHosted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setHosted(!!import.meta.env.VITE_API_BASE);
    const load = async () => {
      try {
        const [s, p] = await Promise.all([
          api.runtimeManagerStatus(),
          api.runtimeManagerPreferences(),
        ]);
        setStatus(s);
        setPrefs(p);
      } catch {
        setMessage("Could not load runtime status.");
      }
    };
    load();
  }, []);

  const savePrefs = useCallback(
    async (update: Partial<RuntimeManagerPreferences>) => {
      const merged = { ...prefs, ...update };
      try {
        const saved = await api.runtimeManagerSavePreferences(merged);
        setPrefs(saved);
        try {
          setStatus(await api.runtimeManagerStatus());
        } catch {
          /* keep saved prefs even if status refresh is delayed */
        }
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "Failed to save preferences.");
      }
    },
    [prefs],
  );

  const handleStart = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const res = await api.runtimeManagerStart();
      setMessage(res.success ? "Background services started." : `Start failed: ${res.message.slice(0, 200)}`);
      const s = await api.runtimeManagerStatus();
      setStatus(s);
    } catch {
      setMessage("Failed to start services.");
    }
    setBusy(false);
  }, []);

  const handleStop = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const res = await api.runtimeManagerStop();
      setMessage(res.success ? "Background services stopped." : `Stop failed: ${res.message.slice(0, 200)}`);
      const s = await api.runtimeManagerStatus();
      setStatus(s);
    } catch {
      setMessage("Failed to stop services.");
    }
    setBusy(false);
  }, []);

  const handleRestartApi = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const res = await api.runtimeManagerRestartApi();
      setMessage(res.success ? "Studio restart requested." : `Studio restart failed: ${res.message.slice(0, 200)}`);
      await new Promise((resolve) => setTimeout(resolve, 2500));
      try {
        setStatus(await api.runtimeManagerStatus());
      } catch {
        setMessage("Studio is restarting. It will come back on its own.");
      }
    } catch {
      setMessage("Failed to restart Studio.");
    }
    setBusy(false);
  }, []);

  const handleRestartComfy = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const res = await api.runtimeManagerRestartComfy();
      setMessage(res.success ? "Pictures restart requested." : `Pictures restart failed: ${res.message.slice(0, 200)}`);
      const s = await api.runtimeManagerStatus();
      setStatus(s);
    } catch {
      setMessage("Failed to restart pictures.");
    }
    setBusy(false);
  }, []);

  const handleRepair = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const res = await api.runtimeManagerRepair();
      setMessage(res.success ? "Background services repaired." : `Repair failed: ${res.message.slice(0, 200)}`);
      const s = await api.runtimeManagerStatus();
      setStatus(s);
    } catch {
      setMessage("Failed to repair services.");
    }
    setBusy(false);
  }, []);

  const statusBadge = (s: string | undefined) => {
    switch (s) {
      case "running":
        return <span className="badge badge--ok">Running</span>;
      case "error":
        return <span className="badge badge--warn">Needs Attention</span>;
      case "starting":
        return <span className="badge badge--busy">Starting...</span>;
      case "not_configured":
        return <span className="badge badge--off">Not Configured</span>;
      default:
        return <span className="badge badge--off">Stopped</span>;
    }
  };

  return (
    <div className="local-runtime-settings">
      <h2>Local Runtime</h2>

      {hosted && (
        <p className="muted">
          Lifecycle controls are not available from browser-hosted Adept UI.
        </p>
      )}

      {status?.adeptRuntime && (
        <div className="local-runtime-settings__card" data-testid="adept-runtime-service-status">
          <div className="local-runtime-settings__card-header">
            <span className="local-runtime-settings__card-title">Adept Background Services</span>
            {statusBadge(
              status.adeptRuntime.serviceState === "running"
                ? "running"
                : status.adeptRuntime.serviceState === "starting"
                  ? "starting"
                  : status.adeptRuntime.configured
                    ? "error"
                    : "not_configured",
            )}
          </div>
          <p className="muted">Manager: {status.adeptRuntime.serviceState.replaceAll("_", " ")}</p>
          <p className="muted">Studio: {String(status.adeptRuntime.studioApiHealth || status.studioApi.status).replaceAll("_", " ")}</p>
          <p className="muted">Pictures: {status.adeptRuntime.comfyState.replaceAll("_", " ")}</p>
          {status.gpu?.detected && <p className="muted">GPU: {status.gpu.name || "detected"}</p>}
          {status.adeptRuntime.creatorMessage && <p className="muted">{status.adeptRuntime.creatorMessage}</p>}
          <p className="muted" data-testid="adept-runtime-task-state">
            {status.adeptRuntime.taskRegistered
              ? "Starts when you sign in."
              : status.adeptRuntime.windowsStartupPresent
                ? "An older Windows startup task is still registered. Adept Background Services is not the owner."
                : "Not set to start when you sign in."}
          </p>
        </div>
      )}

      <div className="local-runtime-settings__card">
        <div className="local-runtime-settings__card-header">
          <span className="local-runtime-settings__card-title">ComfyUI Background Manager</span>
          {status && statusBadge(status.comfyui.status)}
        </div>
        <p className="muted">Run ComfyUI quietly in the background whenever Adept UI needs it.</p>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={prefs.comfyuiBackgroundManagerEnabled}
            disabled={hosted || busy}
            onChange={(e) => savePrefs({ comfyuiBackgroundManagerEnabled: e.target.checked })}
          />
          Enable Background Manager
        </label>
      </div>

      <div className="local-runtime-settings__card">
        <div className="local-runtime-settings__card-header">
          <span className="local-runtime-settings__card-title">Localhost Background Manager</span>
          {status && statusBadge(status.studioApi.status)}
        </div>
        <p className="muted">
          Keep Adept Studio Runtime, Local AI Services, and Runtime Health available without manual terminal startup.
        </p>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={prefs.localhostBackgroundManagerEnabled}
            disabled={hosted || busy}
            onChange={(e) => savePrefs({ localhostBackgroundManagerEnabled: e.target.checked })}
          />
          Enable Background Manager
        </label>
      </div>

      <div className="local-runtime-settings__card">
        <div className="local-runtime-settings__card-header">
          <span className="local-runtime-settings__card-title">MiniMax Route A</span>
          {status && statusBadge(status.routeA?.status)}
        </div>
        <p className="muted">
          Isolated MiniMax runtime. Adept reports it when it is already running; a second
          GPU stack is not started automatically.
        </p>
        {status?.routeA?.message && <p className="muted">{status.routeA.message}</p>}
        {status?.gpuAdmission?.dualResident && (
          <p className="pill warn">
            Two local video runtimes are sharing the GPU. Finish or stop one before starting the other.
          </p>
        )}
        {status?.gpuAdmission?.reason && !status.gpuAdmission.routeAAllowed && (
          <p className="muted">{status.gpuAdmission.reason}</p>
        )}
      </div>

      <div className="local-runtime-settings__section">
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={prefs.startWithWindows}
            disabled={hosted || busy}
            onChange={(e) => savePrefs({ startWithWindows: e.target.checked })}
          />
          Start with Windows
        </label>
      </div>

      <div className="local-runtime-settings__actions">
        <button
          type="button"
          className="primary"
          data-testid="restart-studio-api"
          onClick={handleRestartApi}
          disabled={hosted || busy}
        >
          Restart Studio API
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="restart-comfy"
          onClick={handleRestartComfy}
          disabled={hosted || busy}
        >
          Restart Comfy
        </button>
        <button
          type="button"
          className="ghost"
          onClick={handleStart}
          disabled={hosted || busy}
        >
          Start
        </button>
        <button
          type="button"
          className="ghost"
          onClick={handleStop}
          disabled={hosted || busy}
        >
          Stop
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="repair-background-services"
          onClick={handleRepair}
          disabled={hosted || busy}
        >
          Repair
        </button>
      </div>

      <details className="local-runtime-settings__advanced">
        <summary>Advanced</summary>
        <div className="local-runtime-settings__advanced-content">
          <h4>Remote Runtime Access</h4>
          <p className="muted">
            Allow an approved remote Adept UI client to connect to this computer.
          </p>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={prefs.remoteAccessEnabled}
              disabled={hosted || busy}
              onChange={(e) => savePrefs({ remoteAccessEnabled: e.target.checked })}
            />
            Enable Remote Access
          </label>
          {prefs.remoteAccessEnabled && status?.tunnel.status === "running" && (
            <p className="muted">
              Remote endpoint: https://{status.tunnel.hostname ?? "api-beta.adeptui.org"}/api/healthz
            </p>
          )}
        </div>
      </details>

      {message && <p className="local-runtime-settings__message" role="status">{message}</p>}

      <details className="local-runtime-settings__diagnostics">
        <summary>Diagnostics</summary>
        <pre className="local-runtime-settings__raw">
          {status ? JSON.stringify(status, null, 2) : "Loading..."}
        </pre>
      </details>
    </div>
  );
}

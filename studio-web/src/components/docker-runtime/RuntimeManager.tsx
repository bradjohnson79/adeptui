import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import type {
  DockerRuntimeDescriptor,
  PlatformStatus,
  UninstallOption,
} from "../../dockerRuntime/contracts";
import { AddCustomCapability } from "./AddCustomCapability";

function classBadge(c: string) {
  if (c === "core_mandatory") return "Core";
  if (c === "official_optional") return "Official optional";
  return "User-added";
}

export function RuntimeManager() {
  const [platform, setPlatform] = useState<PlatformStatus | null>(null);
  const [runtimes, setRuntimes] = useState<DockerRuntimeDescriptor[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [uninstallOption, setUninstallOption] = useState<UninstallOption>("container_image_and_private");

  const refresh = useCallback(async () => {
    const [p, list] = await Promise.all([api.dockerRuntime.platform(), api.dockerRuntime.list()]);
    setPlatform(p);
    setRuntimes(list.runtimes || (list as unknown as { runtimes?: DockerRuntimeDescriptor[] }).runtimes || []);
  }, []);

  useEffect(() => {
    void refresh().catch((e) => setMessage(e instanceof Error ? e.message : "Failed to load runtimes"));
  }, [refresh]);

  async function act(runtimeId: string, op: "start" | "stop" | "restart" | "test" | "repair") {
    setBusyId(runtimeId);
    setMessage(null);
    try {
      const fn = api.dockerRuntime[op];
      const res = await fn(runtimeId);
      setMessage(`${op}: ${res.ok ? "ok" : "failed"}`);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : `${op} failed`);
    } finally {
      setBusyId(null);
    }
  }

  async function uninstall(runtime: DockerRuntimeDescriptor) {
    if (!runtime.uninstallAllowed || runtime.classification === "core_mandatory") {
      setMessage("Core / protected runtimes cannot be uninstalled.");
      return;
    }
    setBusyId(runtime.id);
    setMessage(null);
    try {
      const preview = await api.dockerRuntime.uninstallPreview(runtime.id, uninstallOption);
      if (!preview.ok) {
        setMessage(preview.plan?.blockedReason || "Uninstall blocked");
        return;
      }
      const confirmed = window.confirm(
        `Uninstall ${runtime.name}?\nOption: ${uninstallOption}\nShared files and project assets are preserved.`,
      );
      if (!confirmed) return;
      const result = await api.dockerRuntime.uninstall(runtime.id, uninstallOption);
      setMessage(result.ok ? `Uninstalled ${runtime.id}` : "Uninstall failed — registry rolled back if needed");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Uninstall failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page setup-wizard-page" data-testid="runtime-manager">
      <div className="panel">
        <h1>Runtime Manager</h1>
        <p>
          Manage isolated Docker runtimes and seeded native core services. All Docker operations go through the Adept
          backend — the UI never talks to the Docker daemon.
        </p>
        <p className="setup-nav-strip">
          <Link to="/source-manager">Source Manager</Link>
          {" · "}
          <Link to="/">Home</Link>
        </p>
        {platform ? (
          <p data-testid="runtime-manager-platform">
            Platform: daemon={String(platform.daemonRunning ?? platform.daemon)} nvidia=
            {String(platform.nvidiaContainerToolkit ?? platform.nvidiaToolkit)} simulate=
            {String(platform.simulate)} ready={String(platform.readyForInstall)}
          </p>
        ) : null}
        {message ? (
          <p className="setup-message" role="status" data-testid="runtime-manager-message">
            {message}
          </p>
        ) : null}
      </div>

      <AddCustomCapability onRegistered={() => void refresh()} />

      <section className="setup-component-section" aria-labelledby="installed-runtimes-heading">
        <div className="setup-section-heading">
          <div>
            <h2 id="installed-runtimes-heading">Installed runtimes</h2>
            <p>Core cards omit Uninstall. User-added never auto-promotes to Certified.</p>
          </div>
          <label>
            Uninstall option{" "}
            <select
              data-testid="uninstall-option"
              value={uninstallOption}
              onChange={(e) => setUninstallOption(e.target.value as UninstallOption)}
            >
              <option value="ui_only">UI-only</option>
              <option value="container">Container</option>
              <option value="container_and_image">Container + image</option>
              <option value="container_image_and_private">Container + image + private files</option>
            </select>
          </label>
        </div>

        <div className="setup-component-grid">
          {runtimes.map((r) => (
            <article
              key={r.id}
              className="panel"
              data-testid={`runtime-card-${r.id}`}
              data-classification={r.classification}
              data-execution-class={r.executionClass}
            >
              <h3>{r.name}</h3>
              <p>
                <span data-testid={`runtime-badge-${r.id}`}>{classBadge(r.classification)}</span>
                {" · "}
                {r.executionClass}
                {" · "}
                {r.readiness}
                {" · "}
                {r.lifecycle}
              </p>
              <p className="production-dock-muted">
                GPU {r.gpuReady ? "ready" : "unknown"} · health {r.healthOk ? "ok" : "no"} · VRAM min{" "}
                {r.minimumVramGb ?? 0} GB
              </p>
              <details>
                <summary>Workflows / Models / Nodes</summary>
                <ul>
                  <li>Workflows: {(r.workflows || []).join(", ") || "—"}</li>
                  <li>Models: {(r.models || []).join(", ") || "—"}</li>
                  <li>Nodes: {(r.nodes || []).join(", ") || "—"}</li>
                </ul>
              </details>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                <button type="button" disabled={busyId === r.id} onClick={() => void act(r.id, "start")}>
                  Start
                </button>
                <button type="button" disabled={busyId === r.id} onClick={() => void act(r.id, "stop")}>
                  Stop
                </button>
                <button type="button" disabled={busyId === r.id} onClick={() => void act(r.id, "restart")}>
                  Restart
                </button>
                <button type="button" disabled={busyId === r.id} onClick={() => void act(r.id, "test")}>
                  Test
                </button>
                <button type="button" disabled={busyId === r.id} onClick={() => void act(r.id, "repair")}>
                  Repair
                </button>
                {r.uninstallAllowed && r.classification !== "core_mandatory" ? (
                  <button
                    type="button"
                    data-testid={`runtime-uninstall-${r.id}`}
                    disabled={busyId === r.id}
                    onClick={() => void uninstall(r)}
                  >
                    Uninstall
                  </button>
                ) : (
                  <span data-testid={`runtime-no-uninstall-${r.id}`} className="production-dock-muted">
                    Uninstall unavailable
                  </span>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default RuntimeManager;

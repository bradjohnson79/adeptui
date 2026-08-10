import { useEffect, useState } from "react";
import { api } from "../api";
import type { DownloadSourceCliStatus, DownloadSourcesResponse } from "../setup/types";

type ProviderId = "github" | "huggingface";

function statusTone(status: string): string {
  if (status === "Ready") return "ready";
  if (status === "Installed but not authenticated") return "attention";
  if (status === "Not installed") return "missing";
  return "error";
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function ProviderCard({
  title,
  provider,
  data,
  busy,
  onDetect,
  onInstall,
  onSignIn,
  onVerify,
}: {
  title: string;
  provider: string;
  data?: DownloadSourceCliStatus | null;
  busy: boolean;
  onDetect: () => void;
  onInstall: () => void;
  onSignIn: () => void;
  onVerify: () => void;
}) {
  const status = data?.status || (data ? "Unavailable" : "Checking…");
  const tone = data ? statusTone(String(data.status || "Unavailable")) : "pending";
  return (
    <article
      className={`setup-component-card download-source-card status-${tone}`}
      data-testid={`download-source-${provider}`}
      data-status={status}
    >
      <header className="setup-card-header">
        <div>
          <h3>{title}</h3>
          <span className="setup-requirement">Download Source</span>
        </div>
        <span className="setup-status" data-state={tone}>
          <span className="setup-status-mark" aria-hidden="true" />
          {busy ? "Working…" : status}
        </span>
      </header>
      <p className="setup-component-description">
        {data?.message
          || (data == null
            ? `Checking ${title} CLI…`
            : data.cli_detected
              ? `${title} CLI detected.`
              : `${title} CLI is not installed.`)}
      </p>
      <div className="setup-card-meta">
        <span>CLI {data?.cli_detected ? "detected" : "not detected"}</span>
        {data?.executable_path && (
          <span>
            Path <code>{data.executable_path}</code>
          </span>
        )}
        {data?.version && <span>Version {data.version}</span>}
        <span>
          Auth {data?.authenticated ? "signed in" : "not signed in"}
          {data?.account_name ? ` (${data.account_name})` : ""}
        </span>
        <span>Token {data?.token_available ? "available" : "not available"}</span>
        {data?.last_verified_at && (
          <span>Verified {new Date(data.last_verified_at).toLocaleString()}</span>
        )}
      </div>
      <div className="setup-card-actions">
        <button type="button" className="primary" disabled={busy} onClick={onDetect}>
          Detect CLI
        </button>
        <button type="button" disabled={busy} onClick={onInstall}>
          Install CLI
        </button>
        <button type="button" disabled={busy} onClick={onSignIn}>
          Sign In
        </button>
        <button type="button" disabled={busy} onClick={onVerify}>
          Verify
        </button>
        <button type="button" disabled={busy} onClick={onDetect}>
          Reconnect
        </button>
      </div>
    </article>
  );
}

export function DownloadSourcesPanel({
  onMessage,
}: {
  onMessage?: (message: string | null) => void;
}) {
  const [sources, setSources] = useState<DownloadSourcesResponse | null>(null);
  const [busyProvider, setBusyProvider] = useState<ProviderId | null>(null);
  const [panelMessage, setPanelMessage] = useState<string | null>(null);
  const [panelError, setPanelError] = useState<string | null>(null);

  const announce = (message: string | null, isError = false) => {
    if (isError) {
      setPanelError(message);
      setPanelMessage(null);
    } else {
      setPanelMessage(message);
      setPanelError(null);
    }
    onMessage?.(message);
  };

  const refresh = async () => {
    const next = await api.setupDownloadSources();
    setSources(next);
    return next;
  };

  const applyProviderStatus = (provider: ProviderId, status: DownloadSourceCliStatus) => {
    setSources((prev) => ({
      github: prev?.github || ({} as DownloadSourceCliStatus),
      huggingface: prev?.huggingface || ({} as DownloadSourceCliStatus),
      package_managers: prev?.package_managers,
      overrides: prev?.overrides,
      messages: prev?.messages,
      [provider]: status,
    }));
  };

  useEffect(() => {
    refresh().catch((error: unknown) => {
      announce(error instanceof Error ? error.message : String(error), true);
    });
    // Initial load only — parent onMessage identity must not re-trigger detection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (provider: ProviderId, fn: () => Promise<void>) => {
    setBusyProvider(provider);
    setPanelError(null);
    try {
      await fn();
    } catch (error: unknown) {
      announce(error instanceof Error ? error.message : String(error), true);
    } finally {
      setBusyProvider(null);
    }
  };

  const detect = (provider: ProviderId, label: string) =>
    void run(provider, async () => {
      const result = await api.setupDetectDownloadSource(provider);
      applyProviderStatus(provider, result);
      announce(`${label}: ${result.message || result.status || "detection complete."}`);
    });

  const verify = (provider: ProviderId, label: string) =>
    void run(provider, async () => {
      const result = await api.setupVerifyDownloadSource(provider);
      applyProviderStatus(provider, result);
      announce(`${label} verified: ${result.message || result.status || "OK"}`);
    });

  const signIn = (provider: ProviderId, label: string) =>
    void run(provider, async () => {
      const result = await api.setupSignInDownloadSource(provider, { launch: true });
      const summary = result.command_summary || `${label} auth login`;
      const commandLine = (result.command && result.command.length)
        ? result.command.join(" ")
        : summary;
      if (result.command_summary) {
        await copyText(commandLine);
      }
      if (result.launched) {
        announce(
          result.message
            || `${label}: opened a terminal for sign-in. Finish there, then click Verify.`,
        );
        return;
      }
      const detail = [
        result.message || `Sign in with ${label} CLI in a terminal.`,
        `Command (copied): ${commandLine}`,
        result.launch_error ? `Could not open a terminal: ${result.launch_error}` : null,
        "After signing in, click Verify.",
      ].filter(Boolean).join("\n\n");
      window.alert(detail);
      announce(`${label}: run \`${summary}\` in a terminal, then Verify.`);
    });

  const install = (provider: ProviderId, label: string) =>
    void run(provider, async () => {
      const plan = await api.setupInstallDownloadSourceCli(provider, { confirm: false });
      if (plan.already_installed) {
        await refresh();
        announce(String(plan.message || `${label} CLI is already installed.`));
        return;
      }
      const summary = String(plan.command_summary || plan.message || `Install ${label} CLI`);
      const target = String(plan.target_environment || "");
      const elevation = plan.may_require_elevation != null
        ? `\nElevation may be required: ${String(plan.may_require_elevation)}`
        : "";
      if (!window.confirm(`${summary}\n\nTarget: ${target || "system"}${elevation}\n\nRun install now?`)) {
        announce(`${label} install cancelled.`);
        return;
      }
      const result = await api.setupInstallDownloadSourceCli(provider, {
        confirm: true,
        method: plan.method as string | undefined,
      });
      await refresh();
      if (result.ok) {
        announce(
          result.already_installed
            ? String(result.message || `${label} CLI is already installed.`)
            : `${label} CLI install finished. Status refreshed.`,
        );
        return;
      }
      announce(`${label} install failed (exit ${String(result.exit_code)}).`, true);
    });

  return (
    <section className="setup-component-section" aria-labelledby="download-sources-heading">
      <div className="setup-section-heading">
        <div>
          <h2 id="download-sources-heading">Download Sources</h2>
          <p>Connect GitHub and Hugging Face so Adept UI can discover and download packs safely.</p>
        </div>
      </div>
      {panelMessage && (
        <p className="setup-message" role="status" data-testid="download-sources-message">
          {panelMessage}
        </p>
      )}
      {panelError && (
        <p className="setup-message error" role="alert" data-testid="download-sources-error">
          {panelError}
        </p>
      )}
      <div className="setup-component-grid download-sources-grid">
        <ProviderCard
          title="GitHub"
          provider="github"
          data={sources?.github}
          busy={busyProvider === "github"}
          onDetect={() => detect("github", "GitHub")}
          onVerify={() => verify("github", "GitHub")}
          onSignIn={() => signIn("github", "GitHub")}
          onInstall={() => install("github", "GitHub")}
        />
        <ProviderCard
          title="Hugging Face"
          provider="huggingface"
          data={sources?.huggingface}
          busy={busyProvider === "huggingface"}
          onDetect={() => detect("huggingface", "Hugging Face")}
          onVerify={() => verify("huggingface", "Hugging Face")}
          onSignIn={() => signIn("huggingface", "Hugging Face")}
          onInstall={() => install("huggingface", "Hugging Face")}
        />
      </div>
    </section>
  );
}

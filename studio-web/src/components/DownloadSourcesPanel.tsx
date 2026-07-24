import { useEffect, useState } from "react";
import { api } from "../api";
import type { DownloadSourceCliStatus, DownloadSourcesResponse } from "../setup/types";

function statusTone(status: string): string {
  if (status === "Ready") return "ready";
  if (status === "Installed but not authenticated") return "attention";
  if (status === "Not installed") return "missing";
  return "error";
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
  const status = data?.status || "Unavailable";
  return (
    <article
      className={`setup-component-card download-source-card status-${statusTone(status)}`}
      data-testid={`download-source-${provider}`}
      data-status={status}
    >
      <header className="setup-card-header">
        <div>
          <h3>{title}</h3>
          <span className="setup-requirement">Download Source</span>
        </div>
        <span className="setup-status" data-state={statusTone(status)}>
          <span className="setup-status-mark" aria-hidden="true" />
          {status}
        </span>
      </header>
      <p className="setup-component-description">
        {data?.message
          || (data?.cli_detected
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
        <button type="button" className="linkish" disabled={busy} onClick={onInstall}>
          Install CLI
        </button>
        <button type="button" className="linkish" disabled={busy} onClick={onSignIn}>
          Sign In
        </button>
        <button type="button" className="linkish" disabled={busy} onClick={onVerify}>
          Verify Connection
        </button>
        <button type="button" className="linkish" disabled={busy} onClick={onDetect}>
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
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const next = await api.setupDownloadSources();
    setSources(next);
    return next;
  };

  useEffect(() => {
    refresh().catch((error: unknown) => {
      onMessage?.(error instanceof Error ? error.message : String(error));
    });
  }, [onMessage]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (error: unknown) {
      onMessage?.(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="setup-component-section" aria-labelledby="download-sources-heading">
      <div className="setup-section-heading">
        <div>
          <h2 id="download-sources-heading">Download Sources</h2>
          <p>Connect GitHub and Hugging Face so Adept UI can discover and download packs safely.</p>
        </div>
      </div>
      <div className="setup-component-grid download-sources-grid">
        <ProviderCard
          title="GitHub"
          provider="github"
          data={sources?.github}
          busy={busy}
          onDetect={() => void run(async () => { await api.setupDetectDownloadSource("github"); await refresh(); })}
          onVerify={() => void run(async () => { await api.setupVerifyDownloadSource("github"); await refresh(); onMessage?.("GitHub connection verified."); })}
          onSignIn={() => void run(async () => {
            const result = await api.setupSignInDownloadSource("github");
            onMessage?.(result.message || result.command_summary || "Sign in with GitHub CLI in a terminal.");
          })}
          onInstall={() => void run(async () => {
            const plan = await api.setupInstallDownloadSourceCli("github", { confirm: false });
            const summary = String(plan.command_summary || plan.message || "Install GitHub CLI");
            if (!window.confirm(`${summary}\n\nTarget: ${String(plan.target_environment || "system")}\nElevation may be required: ${String(plan.may_require_elevation)}\n\nRun install now?`)) {
              return;
            }
            const result = await api.setupInstallDownloadSourceCli("github", { confirm: true, method: plan.method as string | undefined });
            onMessage?.(result.ok ? "GitHub CLI install finished. Re-detecting…" : `Install failed (exit ${String(result.exit_code)}).`);
            await refresh();
          })}
        />
        <ProviderCard
          title="Hugging Face"
          provider="huggingface"
          data={sources?.huggingface}
          busy={busy}
          onDetect={() => void run(async () => { await api.setupDetectDownloadSource("huggingface"); await refresh(); })}
          onVerify={() => void run(async () => { await api.setupVerifyDownloadSource("huggingface"); await refresh(); onMessage?.("Hugging Face connection verified."); })}
          onSignIn={() => void run(async () => {
            const result = await api.setupSignInDownloadSource("huggingface");
            onMessage?.(result.message || result.command_summary || "Sign in with Hugging Face CLI in a terminal.");
          })}
          onInstall={() => void run(async () => {
            const plan = await api.setupInstallDownloadSourceCli("huggingface", { confirm: false });
            const summary = String(plan.command_summary || plan.message || "Install Hugging Face CLI");
            if (!window.confirm(`${summary}\n\nTarget environment:\n${String(plan.target_environment || "")}\n\nRun install now?`)) {
              return;
            }
            const result = await api.setupInstallDownloadSourceCli("huggingface", { confirm: true });
            onMessage?.(result.ok ? "Hugging Face CLI install finished. Re-detecting…" : `Install failed (exit ${String(result.exit_code)}).`);
            await refresh();
          })}
        />
      </div>
    </section>
  );
}

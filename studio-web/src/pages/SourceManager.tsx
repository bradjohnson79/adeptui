import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ActiveDownloadsPanel } from "../components/ActiveDownloadsPanel";
import { InstallHistoryPanel } from "../components/InstallHistoryPanel";
import { StudioChrome } from "../components/dashboard/StudioChrome";
import { DownloadSourcesPanel } from "../components/DownloadSourcesPanel";
import type { SourceManagerOverview, SourceManagerProvider, SourceRecord } from "../setup/types";

function providerTone(status: string): string {
  if (status === "Ready") return "ready";
  if (status === "Installed but not authenticated") return "attention";
  if (status === "Not installed" || status === "Unavailable") return "missing";
  return "error";
}

export default function SourceManagerPage() {
  const [overview, setOverview] = useState<SourceManagerOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    void refresh();
  }, []);

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

  return (
    <div className="source-manager-page" data-testid="source-manager-page">
      <StudioChrome
        variant="home"
        rightExtra={
          <Link to="/" className="linkish">
            Back to Studio
          </Link>
        }
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

        <section className="setup-component-section" aria-labelledby="sm-providers-heading">
          <div className="setup-section-heading">
            <h2 id="sm-providers-heading">Providers</h2>
            <p>Capability-based selection — GitHub CLI preferred when authenticated.</p>
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
                  <span className="setup-status" data-state={providerTone(provider.status)}>
                    <span className="setup-status-mark" aria-hidden="true" />
                    {provider.status}
                  </span>
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
                  {provider.capabilities?.length ? (
                    <span>Capabilities {provider.capabilities.join(", ")}</span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="setup-component-section" aria-labelledby="sm-cli-heading">
          <div className="setup-section-heading">
            <h2 id="sm-cli-heading">CLI Download Sources</h2>
            <p>Same GitHub / Hugging Face cards as Setup Wizard — detect, install, sign in, verify.</p>
          </div>
          <DownloadSourcesPanel />
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

        <ActiveDownloadsPanel onChanged={() => void refresh()} />
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
      </main>
    </div>
  );
}

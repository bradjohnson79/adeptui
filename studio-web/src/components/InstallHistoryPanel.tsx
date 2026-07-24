import { useEffect, useState } from "react";
import { api } from "../api";
import type { InstallHistoryEntry, InstallReceipt } from "../setup/types";

export function InstallHistoryPanel() {
  const [entries, setEntries] = useState<InstallHistoryEntry[]>([]);
  const [selected, setSelected] = useState<InstallReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const data = await api.installHistory();
      setEntries(data.entries || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const openReceipt = async (id: string) => {
    try {
      const data = await api.getInstallReceipt(id);
      setSelected(data.receipt);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <section className="setup-component-section" aria-labelledby="install-history-heading">
      <div className="setup-section-heading">
        <h2 id="install-history-heading">Install History</h2>
        <p>Managed receipts and linked folders. Rollback arrives in a later phase.</p>
        <button type="button" className="linkish" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      {error && (
        <p className="setup-message error" role="alert">
          {error}
        </p>
      )}
      {entries.length === 0 ? (
        <p className="setup-message" data-testid="install-history-empty">
          No installations recorded yet.
        </p>
      ) : (
        <div className="setup-component-grid" data-testid="install-history-list">
          {entries.map((entry) => (
            <article key={entry.id} className="setup-component-card" data-testid={`install-history-${entry.id}`}>
              <header className="setup-card-header">
                <div>
                  <h3>{entry.componentId}</h3>
                  <span className="setup-requirement">
                    {entry.managed ? "managed" : "linked"} · {entry.providerId}
                  </span>
                </div>
                <span className="setup-status">{entry.verificationState || entry.result || "—"}</span>
              </header>
              <div className="setup-card-meta">
                {entry.version && <span>Version {entry.version}</span>}
                {entry.installedAt && (
                  <span>{new Date(entry.installedAt).toLocaleString()}</span>
                )}
                <span>{entry.fileCount ?? 0} files</span>
                <span>{entry.destinationSummary}</span>
              </div>
              <div className="setup-card-actions">
                <button type="button" className="primary" onClick={() => void openReceipt(entry.id)}>
                  View Receipt
                </button>
                <button type="button" className="linkish" disabled title="Rollback arrives in Phase 1F">
                  Rollback unavailable
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {selected && (
        <div className="setup-dialog" role="dialog" aria-modal="true" data-testid="install-receipt-dialog">
          <div className="setup-dialog-card">
            <h3>Install Receipt</h3>
            <p>
              {selected.componentId} · {selected.managed ? "Managed" : "Linked"} ·{" "}
              {selected.verification?.status}
            </p>
            <ul>
              {(selected.artifacts || []).map((art) => (
                <li key={`${art.relativePath}-${art.checksum}`}>
                  {art.relativePath} — {art.size ?? "?"} bytes
                  {art.checksum ? ` — ${art.checksum}` : ""}
                </li>
              ))}
            </ul>
            {(selected.warnings || []).map((w) => (
              <p key={w} className="setup-message">
                {w}
              </p>
            ))}
            <div className="row-actions">
              <button type="button" className="ghost" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

import { useState } from "react";
import { api } from "../api";
import { useDownloadsPoll } from "../hooks/useDownloadsPoll";
import type { DownloadOperation } from "../setup/types";

function formatBytes(n?: number | null) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

function formatSpeed(bps?: number | null) {
  if (bps == null) return "Calculating…";
  return `${formatBytes(bps)}/s`.replace(" B/s", " B/s");
}

function formatEta(sec?: number | null) {
  if (sec == null) return null;
  if (sec < 60) return "Less than a minute";
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m} minute${m === 1 ? "" : "s"}`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h} hour${h === 1 ? "" : "s"}`;
}

export function ActiveDownloadsPanel({ onChanged }: { onChanged?: () => void }) {
  const { operations, error, refresh } = useDownloadsPoll(true, 900);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const run = async (opId: string, action: () => Promise<unknown>) => {
    setBusyId(opId);
    setActionError(null);
    try {
      await action();
      await refresh();
      onChanged?.();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="setup-component-section" aria-labelledby="active-downloads-heading">
      <div className="setup-section-heading">
        <h2 id="active-downloads-heading">Active Downloads</h2>
        <p>Real progress from the persistent download queue.</p>
        <button type="button" className="linkish" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      {(error || actionError) && (
        <p className="setup-message error" role="alert">
          {actionError || error}
        </p>
      )}
      {operations.length === 0 ? (
        <p className="setup-message" data-testid="active-downloads-empty">
          No active downloads.
        </p>
      ) : (
        <div className="setup-component-grid" data-testid="active-downloads-list">
          {operations.map((op) => (
            <DownloadCard
              key={op.id}
              op={op}
              busy={busyId === op.id}
              onCancel={() => run(op.id, () => api.cancelDownload(op.id))}
              onPause={() => run(op.id, () => api.pauseDownload(op.id))}
              onResume={() => run(op.id, () => api.resumeDownload(op.id))}
              onRetry={() => run(op.id, () => api.retryDownload(op.id))}
              onPriority={(delta) =>
                run(op.id, () => api.setDownloadPriority(op.id, (op.priority || 100) + delta))
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}

function DownloadCard({
  op,
  busy,
  onCancel,
  onPause,
  onResume,
  onRetry,
  onPriority,
}: {
  op: DownloadOperation;
  busy: boolean;
  onCancel: () => void;
  onPause: () => void;
  onResume: () => void;
  onRetry: () => void;
  onPriority: (delta: number) => void;
}) {
  const prog = op.progress || {};
  const percent = prog.percent ?? 0;
  const canPause = Boolean(op.capabilities?.canPause) && op.phase === "downloading";
  const canResume =
    Boolean(op.capabilities?.canResume) && (op.phase === "paused" || op.phase === "interrupted");
  const eta = formatEta(prog.etaSeconds);
  const totalKnown = prog.bytesTotal != null;

  return (
    <article
      className="setup-component-card"
      data-testid={`download-op-${op.id}`}
      data-phase={op.phase}
    >
      <header className="setup-card-header">
        <div>
          <h3>{op.componentId}</h3>
          <span className="setup-requirement">
            {op.providerId}
            {op.queuePosition != null && op.phase === "queued" ? ` · queue #${op.queuePosition}` : ""}
          </span>
        </div>
        <span className="setup-status">{op.phase}</span>
      </header>
      <div
        className="setup-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        aria-label={`Download progress ${Math.round(percent)} percent`}
      >
        <div className="setup-progress-bar" style={{ width: `${Math.min(100, percent)}%` }} />
        <span>
          {Math.round(percent)}% · {formatBytes(prog.bytesDownloaded)} /{" "}
          {totalKnown ? formatBytes(prog.bytesTotal) : "unknown"}
        </span>
      </div>
      <div className="setup-card-meta">
        <span>Speed {op.phase === "downloading" ? formatSpeed(prog.speedBytesPerSecond) : "—"}</span>
        <span>ETA {totalKnown && eta ? eta : totalKnown ? "Calculating…" : "—"}</span>
        {op.failure?.message && <span className="error-text">{op.failure.message}</span>}
        {!canPause && op.phase === "downloading" && (
          <span title={op.capabilities?.message || undefined}>
            Pause not supported by this source
          </span>
        )}
      </div>
      <div className="setup-card-actions">
        {op.phase === "queued" && (
          <>
            <button type="button" className="linkish" disabled={busy} onClick={() => onPriority(10)}>
              Move Up
            </button>
            <button type="button" className="linkish" disabled={busy} onClick={() => onPriority(-10)}>
              Move Down
            </button>
          </>
        )}
        {canPause && (
          <button type="button" className="linkish" disabled={busy} onClick={onPause}>
            Pause
          </button>
        )}
        {canResume && (
          <button type="button" className="primary" disabled={busy} onClick={onResume}>
            Resume
          </button>
        )}
        {(op.phase === "failed" || op.phase === "interrupted") && (
          <button type="button" className="primary" disabled={busy} onClick={onRetry}>
            Retry
          </button>
        )}
        {!["installed", "cancelled"].includes(op.phase) && (
          <button type="button" className="linkish" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </article>
  );
}

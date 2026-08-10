import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { formatBytes } from "../../setup/helpers";
import { Button } from "../ui";
import "./install-progress.css";

export type PreflightConfirm = {
  destinationRoot: string;
  confirm: boolean;
  confirmDownloadModels: boolean;
};

export function PreflightDialog({
  open,
  componentId,
  componentName,
  expectedBytes,
  gpuSummary,
  requiresModelDownloadConfirm = false,
  busy = false,
  onClose,
  onConfirm,
}: {
  open: boolean;
  componentId: string;
  componentName: string;
  expectedBytes?: number | null;
  gpuSummary?: string | null;
  requiresModelDownloadConfirm?: boolean;
  busy?: boolean;
  onClose: () => void;
  onConfirm: (body: PreflightConfirm) => void;
}) {
  const [destinationRoot, setDestinationRoot] = useState("");
  const [confirmInstall, setConfirmInstall] = useState(false);
  const [confirmDownloadModels, setConfirmDownloadModels] = useState(false);
  const [busyBrowse, setBusyBrowse] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setConfirmInstall(false);
    setConfirmDownloadModels(false);
    setMessage(null);
    let cancelled = false;
    void api.setupSuggestedPath(componentId)
      .then((result) => {
        if (!cancelled) setDestinationRoot(result.suggested_path || "");
      })
      .catch(() => {
        if (!cancelled) setDestinationRoot("");
      });
    return () => {
      cancelled = true;
    };
  }, [componentId, open]);

  const browse = async () => {
    setBusyBrowse(true);
    setMessage(null);
    try {
      const result = await api.setupBrowsePath({
        mode: "directory",
        start_dir: destinationRoot || undefined,
        component_id: componentId,
        title: "Select install folder",
      });
      if (result.path) setDestinationRoot(result.path);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyBrowse(false);
    }
  };

  const canContinue = useMemo(() => {
    if (!destinationRoot.trim() || !confirmInstall) return false;
    if (requiresModelDownloadConfirm && !confirmDownloadModels) return false;
    return true;
  }, [confirmDownloadModels, confirmInstall, destinationRoot, requiresModelDownloadConfirm]);

  if (!open) return null;

  return (
    <div className="setup-dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (!busy && !busyBrowse && event.target === event.currentTarget) onClose();
    }}>
      <section className="setup-dialog install-preflight-dialog" role="dialog" aria-modal="true" aria-labelledby="install-preflight-title">
        <header className="setup-dialog-header">
          <h2 id="install-preflight-title">Confirm install</h2>
          <button type="button" className="setup-dialog-close" disabled={busy || busyBrowse} onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <div className="install-preflight-dialog__summary">
          <p>
            <strong>{componentName}</strong>
          </p>
          <div className="install-progress-card__stats">
            <span>Destination {destinationRoot ? "selected" : "needed"}</span>
            {expectedBytes != null ? <span>Download size {formatBytes(expectedBytes) || "unknown"}</span> : null}
            {gpuSummary ? <span>GPU {gpuSummary}</span> : null}
          </div>
        </div>

        <label className="setup-field">
          <span>Install destination</span>
          <input
            value={destinationRoot}
            onChange={(event) => setDestinationRoot(event.target.value)}
            placeholder="Choose a local folder"
            data-testid="install-preflight-destination"
          />
        </label>

        <div className="install-preflight-dialog__browse">
          <Button variant="secondary" onClick={() => void browse()} disabled={busy || busyBrowse}>
            {busyBrowse ? "Opening browser…" : "Browse for folder"}
          </Button>
        </div>

        <label className="install-preflight-dialog__check">
          <input
            type="checkbox"
            checked={confirmInstall}
            onChange={(event) => setConfirmInstall(event.target.checked)}
            data-testid="install-preflight-confirm"
          />
          <span>I want Adept UI to download and install this component in the selected folder.</span>
        </label>

        {requiresModelDownloadConfirm ? (
          <label className="install-preflight-dialog__check">
            <input
              type="checkbox"
              checked={confirmDownloadModels}
              onChange={(event) => setConfirmDownloadModels(event.target.checked)}
              data-testid="install-preflight-confirm-models"
            />
            <span>I confirm the larger model download for this install.</span>
          </label>
        ) : null}

        {message ? <p className="setup-message error">{message}</p> : null}

        <div className="row-actions">
          <Button
            variant="primary"
            disabled={!canContinue}
            loading={busy}
            onClick={() => onConfirm({
              destinationRoot: destinationRoot.trim(),
              confirm: true,
              confirmDownloadModels,
            })}
            data-testid="install-preflight-submit"
          >
            Start install
          </Button>
          <Button variant="ghost" disabled={busy || busyBrowse} onClick={onClose}>
            Cancel
          </Button>
        </div>
      </section>
    </div>
  );
}

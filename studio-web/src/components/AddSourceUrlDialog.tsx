import { useMemo, useState } from "react";
import { api } from "../api";
import type { SourceVerificationResult } from "../setup/types";

export function AddSourceUrlDialog({
  componentId,
  componentName,
  onClose,
  onSaved,
}: {
  componentId: string;
  componentName: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [url, setUrl] = useState("");
  const [revision, setRevision] = useState("");
  const [busy, setBusy] = useState(false);
  const [verification, setVerification] = useState<SourceVerificationResult | null>(null);
  const [message, setMessage] = useState<string | null>(
    "Paste a GitHub or Hugging Face repository, release, asset, or file URL. Adept UI will inspect it before downloading.",
  );

  const provider = useMemo(() => {
    const lower = url.toLowerCase();
    if (lower.includes("github.com")) return "GitHub";
    if (lower.includes("huggingface.co") || lower.includes("hf.co") || lower.startsWith("hf://")) {
      return "Hugging Face";
    }
    if (verification?.provider === "github") return "GitHub";
    if (verification?.provider === "huggingface") return "Hugging Face";
    return "Unknown";
  }, [url, verification]);

  const verify = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.setupVerifySourceUrl({
        url: url.trim(),
        component_id: componentId,
        revision: revision.trim() || undefined,
      });
      setVerification(result);
      setMessage(result.message || (result.ok ? "Source verified." : "Verification found problems."));
    } catch (error: unknown) {
      setVerification(null);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const previewFiles = async () => {
    setBusy(true);
    try {
      const result = await api.setupListSourceFiles({
        url: url.trim(),
        revision: revision.trim() || undefined,
      });
      setVerification((current) => ({
        ...(current || { ok: Boolean(result.ok) }),
        files: result.files || [],
        ok: Boolean(result.ok),
      }));
      setMessage(`Found ${(result.files || []).length} candidate file(s).`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const saveOverride = async () => {
    if (!verification?.ok) {
      setMessage("Verify the source successfully before saving.");
      return;
    }
    setBusy(true);
    try {
      await api.setupSaveSourceOverride(componentId, {
        url: url.trim(),
        verification,
        revision: revision.trim() || undefined,
      });
      setMessage("Custom source saved. Defaults remain recoverable.");
      onSaved();
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="setup-dialog-backdrop" role="presentation">
      <div className="setup-dialog" role="dialog" aria-modal="true" aria-labelledby="add-source-title" data-testid="add-source-url-dialog">
        <div className="setup-dialog-header">
          <h2 id="add-source-title">Add Source URL</h2>
          <button type="button" className="setup-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p>
          Component: <strong>{componentName}</strong>
        </p>
        <label className="setup-field">
          <span>Source URL</span>
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/… or https://huggingface.co/…"
            data-testid="source-url-input"
          />
        </label>
        <div className="setup-card-meta">
          <span>Detected provider: {provider}</span>
          <span>Component type: asset pack / model source</span>
        </div>
        <label className="setup-field">
          <span>Optional revision or tag</span>
          <input value={revision} onChange={(event) => setRevision(event.target.value)} placeholder="main / v1.0.0" />
        </label>

        {message && <p className="setup-message" role="status">{message}</p>}

        {verification && (
          <div className="setup-ready-details" data-testid="source-verification-summary">
            <p>
              <strong>Verification</strong> {verification.ok ? "OK" : "Blocked"} — {verification.compatibility}
            </p>
            <div className="setup-card-meta">
              <span>Provider {verification.provider}</span>
              <span>Repository {verification.repository || "—"}</span>
              <span>Revision {verification.revision || "—"}</span>
              <span>Selected {verification.selected_file || "—"}</span>
              <span>Size {verification.size != null ? `${verification.size} bytes` : "unknown"}</span>
              <span>Auth {verification.authentication_status}</span>
              <span>Method {verification.installation_method}</span>
            </div>
            {(verification.warnings || []).map((warning) => (
              <p key={warning} className="setup-issue">
                Warning: {warning}
              </p>
            ))}
            {(verification.blocking_errors || []).map((error) => (
              <p key={error.message} className="setup-issue">
                Error: {error.message}
              </p>
            ))}
            {(verification.files || []).length > 0 && (
              <details open>
                <summary>Candidate files ({verification.files?.length})</summary>
                <ul>
                  {(verification.files || []).slice(0, 30).map((file) => (
                    <li key={`${file.path || file.name}`}>
                      <code>{file.path || file.name}</code>
                      {file.size != null ? ` (${file.size} bytes)` : ""}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        <div className="row-actions">
          <button type="button" className="primary" disabled={busy || !url.trim()} onClick={() => void verify()} data-testid="verify-source-button">
            Verify Source
          </button>
          <button type="button" className="linkish" disabled={busy || !url.trim()} onClick={() => void previewFiles()}>
            Preview Files
          </button>
          <button
            type="button"
            className="primary"
            disabled={busy || !verification?.ok}
            onClick={() => void saveOverride()}
            data-testid="save-source-override-button"
          >
            Save as Source Override
          </button>
          <button type="button" className="ghost" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

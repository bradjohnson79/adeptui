import { useMemo, useState } from "react";
import { api } from "../../api";
import type { SourceVerificationResult } from "../../setup/types";
import { Button } from "../ui";
import "./install-progress.css";

type SourceType = "auto" | "github" | "huggingface" | "direct";

function providerLabel(sourceType: SourceType, url: string, verification: SourceVerificationResult | null) {
  if (sourceType !== "auto") return sourceType;
  const lower = url.toLowerCase();
  if (lower.includes("github.com")) return "github";
  if (lower.includes("huggingface.co") || lower.includes("hf.co") || lower.startsWith("hf://")) return "huggingface";
  return verification?.provider || "auto";
}

export function AddSourceWorkflow({
  open,
  componentId,
  componentName,
  onClose,
  onSaved,
}: {
  open: boolean;
  componentId: string;
  componentName: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("auto");
  const [revision, setRevision] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(
    "Paste an official GitHub or Hugging Face URL. Adept UI validates it before saving.",
  );
  const [verification, setVerification] = useState<SourceVerificationResult | null>(null);

  const provider = useMemo(
    () => providerLabel(sourceType, url, verification),
    [sourceType, url, verification],
  );

  const validate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.setupVerifySourceUrl({
        url: url.trim(),
        component_id: componentId,
        revision: revision.trim() || undefined,
      });
      setVerification(result);
      setMessage(result.message || (result.ok ? "Source verified." : "Source needs attention."));
    } catch (error) {
      setVerification(null);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!verification?.ok) {
      setMessage("Validate the source before saving it.");
      return;
    }
    setBusy(true);
    try {
      await api.sourceManagerAssignComponentSource(componentId, {
        url: url.trim(),
        sourceUrl: url.trim(),
        verification,
        revision: revision.trim() || undefined,
      });
      setMessage("Source saved.");
      onSaved();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="setup-dialog-backdrop" role="presentation">
      <section className="setup-dialog install-source-workflow" role="dialog" aria-modal="true" aria-labelledby="add-source-title" data-testid="add-source-workflow">
        <header className="setup-dialog-header">
          <h2 id="add-source-title">Add Source URL</h2>
          <button type="button" className="setup-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <p className="install-source-workflow__lead">
          Connect a verified source for <strong>{componentName}</strong>.
        </p>

        <label className="setup-field">
          <span>Source URL</span>
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/... or https://huggingface.co/..."
            data-testid="source-url-input"
          />
        </label>

        <div className="install-source-workflow__grid">
          <label className="setup-field">
            <span>Type</span>
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value as SourceType)} data-testid="source-type-select">
              <option value="auto">Auto detect</option>
              <option value="github">GitHub</option>
              <option value="huggingface">Hugging Face</option>
              <option value="direct">Direct download</option>
            </select>
          </label>

          <label className="setup-field">
            <span>Revision</span>
            <input
              value={revision}
              onChange={(event) => setRevision(event.target.value)}
              placeholder="main / v1.0.0"
              data-testid="source-revision-input"
            />
          </label>
        </div>

        <div className="setup-card-meta">
          <span>Provider {provider}</span>
          <span>Component {componentId}</span>
        </div>

        {message ? <p className="setup-message">{message}</p> : null}

        {verification ? (
          <div className="install-source-workflow__result" data-testid="source-verification-summary">
            <p>
              <strong>{verification.ok ? "Validated" : "Blocked"}</strong>
              {verification.compatibility ? ` · ${verification.compatibility}` : ""}
            </p>
            <div className="setup-card-meta">
              <span>Provider {verification.provider || "—"}</span>
              <span>Repository {verification.repository || "—"}</span>
              <span>Revision {verification.revision || "—"}</span>
              <span>Selected {verification.selected_file || "—"}</span>
            </div>
            {(verification.blocking_errors || []).map((item) => (
              <p key={item.message} className="setup-issue">{item.message}</p>
            ))}
            {(verification.warnings || []).map((warning) => (
              <p key={warning} className="setup-message">{warning}</p>
            ))}
          </div>
        ) : null}

        <div className="row-actions">
          <Button variant="primary" disabled={busy || !url.trim()} onClick={() => void validate()} data-testid="verify-source-button">
            Validate Source
          </Button>
          <Button variant="secondary" disabled={busy || !verification?.ok} onClick={() => void save()} data-testid="save-source-override-button">
            Save + Continue
          </Button>
          <Button variant="ghost" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
        </div>
      </section>
    </div>
  );
}

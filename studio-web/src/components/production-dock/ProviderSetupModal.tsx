import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";

const PROVIDERS = [
  { id: "kie", label: "Kie.ai (Recommended)" },
  { id: "wavespeed", label: "WaveSpeed.ai" },
  { id: "fal", label: "fal.ai" },
] as const;

export function ProviderSetupModal({
  open,
  onClose,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [providerId, setProviderId] = useState<(typeof PROVIDERS)[number]["id"]>("kie");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setMessage(null);
    setApiKey("");
  }, [open]);

  const run = useCallback(
    async (action: "test" | "save") => {
      setBusy(action);
      setError(null);
      setMessage(null);
      try {
        if (action === "test") {
          if (apiKey.trim()) {
            await api.hostedProvidersConnect(providerId, apiKey.trim());
          }
          const result = await api.hostedProvidersTest(providerId);
          setMessage(result?.message || `${providerId} connection looks good.`);
        } else {
          if (!apiKey.trim()) {
            setError("Paste an API key to save.");
            return;
          }
          const result = await api.hostedProvidersConnect(providerId, apiKey.trim());
          await api.hostedProvidersSetPreferred(providerId);
          const summary = result?.summary || result?.discovery?.summary;
          if (summary) {
            setMessage(
              [
                `${providerId} connected`,
                `Video ${summary.videoFound ?? 0} · Image ${summary.imageFound ?? 0} · Audio ${summary.audioFound ?? 0} · LLM ${summary.llmFound ?? 0}`,
                `Compatible: ${summary.compatible ?? 0} · Requires adapters: ${summary.requiresAdapter ?? 0}`,
              ].join(" — "),
            );
          } else {
            setMessage("Provider saved. Dock API models will refresh from discovery.");
          }
          onSaved?.();
          window.setTimeout(() => onClose(), 900);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(null);
      }
    },
    [apiKey, onClose, onSaved, providerId],
  );

  if (!open) return null;

  return (
    <div
      className="ds-dialog-backdrop production-dock-provider-modal"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="ds-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Set up hosted provider"
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
        data-testid="production-dock-provider-modal"
      >
        <h2 className="ds-dialog__title">Hosted Provider Setup</h2>
        <div className="ds-dialog__body">
          <p className="production-dock-muted">
            Connect Kie.ai, WaveSpeed.ai, or fal.ai. Keys stay on your machine — Adept routes jobs through the
            certified resolver.
          </p>
          <div className="production-dock-provider-options">
            {PROVIDERS.map((p) => (
              <label key={p.id}>
                <input
                  type="radio"
                  name="production-dock-provider"
                  checked={providerId === p.id}
                  onChange={() => setProviderId(p.id)}
                />
                {p.label}
              </label>
            ))}
          </div>
          <div className="field">
            <label htmlFor="production-dock-provider-key">API key</label>
            <input
              id="production-dock-provider-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste API key…"
            />
          </div>
          {error ? (
            <p className="production-dock-error" role="alert">
              {error}
            </p>
          ) : null}
          {message ? <p className="production-dock-muted">{message}</p> : null}
        </div>
        <div className="ds-dialog__actions">
          <Button variant="secondary" aria-label="Cancel provider setup" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="secondary"
            aria-label="Test provider connection"
            loading={busy === "test"}
            onClick={() => void run("test")}
          >
            Test
          </Button>
          <Button
            variant="primary"
            aria-label="Save provider key"
            loading={busy === "save"}
            onClick={() => void run("save")}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

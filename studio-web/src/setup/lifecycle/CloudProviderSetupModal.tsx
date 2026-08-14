import { useEffect, useState } from "react";
import { api } from "../../api";
import {
  API_KEY_INPUT_TYPE,
  API_KEY_REMOVE_LABEL,
  API_KEY_SAVE_LABEL,
  maskedKeyPlaceholder,
} from "../../components/hostedProviderSetupCopy";
import type { LifecycleCloudProvider } from "../types";
import {
  CONNECTION_TEST_UNAVAILABLE,
  CREDENTIALS_STORED_ONLY,
  cloudProviderAiPrompt,
} from "./cloudProviderCardCopy";

export function CloudProviderSetupModal({
  provider,
  onClose,
  onChanged,
  onAskCoDirector,
}: {
  provider: LifecycleCloudProvider;
  onClose: () => void;
  onChanged: (items: LifecycleCloudProvider[]) => void;
  onAskCoDirector?: (prompt: string, providerId: string) => void;
}) {
  const [keyValue, setKeyValue] = useState("");
  const [busy, setBusy] = useState<"save" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const inputId = `setup-cloud-key-${provider.providerId}`;

  useEffect(() => {
    setKeyValue("");
    setError(null);
    setMessage(null);
  }, [provider.providerId]);

  const refresh = async () => {
    const data = await api.setupLifecycleCloudProviders();
    onChanged(data.items || []);
    return data.items || [];
  };

  const save = async () => {
    const next = keyValue.trim();
    if (!next) {
      setError("Paste an API key to save.");
      return;
    }
    setBusy("save");
    setError(null);
    setMessage(null);
    try {
      const result = await api.setupLifecycleSetCloudProviderKey(provider.providerId, next);
      setKeyValue("");
      await refresh();
      setMessage(result.message || "API key saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Remove the saved ${provider.displayName} API key from this machine?`)) {
      setMessage("Remove cancelled.");
      return;
    }
    setBusy("remove");
    setError(null);
    setMessage(null);
    try {
      await api.setupLifecycleClearCloudProviderKey(provider.providerId);
      setKeyValue("");
      await refresh();
      setMessage("API key removed");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className="ds-dialog-backdrop"
      role="presentation"
      data-testid={`setup-cloud-setup-backdrop-${provider.providerId}`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="ds-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`${provider.configured ? "Manage" : "Set up"} ${provider.displayName}`}
        data-testid={`setup-cloud-setup-${provider.providerId}`}
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) onClose();
        }}
      >
        <h2 className="ds-dialog__title">
          {provider.configured ? "Manage" : "Set Up"} {provider.displayName}
        </h2>
        <div className="ds-dialog__body">
          <p className="muted">{CREDENTIALS_STORED_ONLY}</p>
          <div className="field">
            <label htmlFor={inputId}>API key</label>
            <input
              id={inputId}
              data-testid={`setup-cloud-key-input-${provider.providerId}`}
              type={API_KEY_INPUT_TYPE}
              autoComplete="off"
              spellCheck={false}
              value={keyValue}
              disabled={Boolean(busy)}
              onChange={(event) => setKeyValue(event.target.value)}
              placeholder={provider.configured ? maskedKeyPlaceholder(provider.hint) : "Paste API key..."}
            />
          </div>
          <p className="muted" data-testid={`setup-cloud-test-unavailable-${provider.providerId}`}>
            {CONNECTION_TEST_UNAVAILABLE}
          </p>
          {error ? <p className="setup-issue" role="alert">{error}</p> : null}
          {message ? <p className="muted" role="status">{message}</p> : null}
          {onAskCoDirector ? (
            <button
              type="button"
              className="linkish"
              data-testid={`setup-cloud-ask-ai-${provider.providerId}`}
              onClick={() => onAskCoDirector(cloudProviderAiPrompt(provider), provider.providerId)}
            >
              Set Up with AI
            </button>
          ) : null}
          {provider.keysUrl ? (
            <a className="linkish" href={provider.keysUrl} target="_blank" rel="noreferrer">
              Get API key
            </a>
          ) : null}
        </div>
        <div className="ds-dialog__actions">
          <button type="button" disabled={Boolean(busy)} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            disabled={Boolean(busy) || !provider.configured}
            onClick={() => void remove()}
          >
            {busy === "remove" ? "Removing..." : API_KEY_REMOVE_LABEL}
          </button>
          <button
            type="button"
            className="primary"
            disabled={Boolean(busy) || !keyValue.trim()}
            onClick={() => void save()}
          >
            {busy === "save" ? "Saving..." : API_KEY_SAVE_LABEL}
          </button>
        </div>
      </div>
    </div>
  );
}


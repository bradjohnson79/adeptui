import { useState } from "react";
import { api } from "../api";

/**
 * API Providers & Keys — the single permanent credential manager on the
 * Setup Wizard page. Shared by Windows, macOS, and Linux. Keys travel only
 * to the Adept backend secret store: validate-then-save is transactional,
 * so a failed replacement never overwrites a working credential.
 */
export const SETUP_PROVIDERS = [
  { id: "fal", name: "fal.ai", detail: "Hosted image and video models." },
  { id: "kie", name: "kie.ai", detail: "Hosted image, video, and voice models." },
  { id: "wavespeed", name: "Wavespeed.ai", detail: "Hosted image and video models." },
  { id: "elevenlabs", name: "ElevenLabs", detail: "Hosted voice, sound, and music." },
] as const;

export type SetupProviderId = (typeof SETUP_PROVIDERS)[number]["id"];

type ProviderTestState =
  | "success"
  | "auth_failed"
  | "unavailable"
  | "timeout"
  | "config_error"
  | null;

const RESULT_LABEL: Record<Exclude<ProviderTestState, null>, string> = {
  success: "Connected",
  auth_failed: "Authentication failed",
  unavailable: "Provider unavailable",
  timeout: "Timeout",
  config_error: "Configuration error",
};

function mapConnectFailure(result: { error?: string; message?: string }): { state: ProviderTestState; message: string } {
  const code = result.error || "";
  if (code === "INVALID_KEY") {
    return { state: "auth_failed", message: result.message || "The provider rejected this API key." };
  }
  if (code === "KEY_REQUIRED") {
    return { state: "config_error", message: "API key is required." };
  }
  return { state: "config_error", message: result.message || "The provider configuration is incomplete or unsupported." };
}

export function mapProviderError(error: unknown): { state: Exclude<ProviderTestState, null>; message: string } {
  const message = error instanceof Error ? error.message : "The provider could not be reached.";
  const status = typeof (error as { status?: unknown })?.status === "number" ? (error as { status: number }).status : null;
  if (status === 401 || status === 403 || status === 400) {
    return { state: "auth_failed", message };
  }
  if (status === 404 || status === 422) {
    return { state: "config_error", message };
  }
  if (status === 408 || status === 504 || message.toLowerCase().includes("timeout")) {
    return { state: "timeout", message: "The connection test timed out." };
  }
  if (/\b(rejected|invalid|unauthorized|forbidden)\b/i.test(message)) {
    return { state: "auth_failed", message };
  }
  return { state: "unavailable", message };
}

export function ProviderKeysPanel({
  connectedProviders,
  onChanged,
}: {
  connectedProviders: { id: string; name: string }[];
  onChanged: () => Promise<unknown> | void;
}) {
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<Record<string, "test" | "save" | "remove" | null>>({});
  const [result, setResult] = useState<Record<string, ProviderTestState>>({});
  const [message, setMessage] = useState<Record<string, string | null>>({});

  const configured = new Set((connectedProviders || []).map((item) => item.id));

  const setRowBusy = (id: string, value: "test" | "save" | "remove" | null) =>
    setBusy((current) => ({ ...current, [id]: value }));
  const setRowResult = (id: string, value: ProviderTestState) =>
    setResult((current) => ({ ...current, [id]: value }));
  const setRowMessage = (id: string, value: string | null) =>
    setMessage((current) => ({ ...current, [id]: value }));

  /** Validate the entered key and, only on success, store it. A failed attempt preserves the stored credential. */
  const saveProvider = async (providerId: string) => {
    const value = (keys[providerId] || "").trim();
    if (!value) {
      setRowResult(providerId, "config_error");
      setRowMessage(providerId, "Enter an API key first.");
      return;
    }
    setRowBusy(providerId, "save");
    setRowResult(providerId, null);
    setRowMessage(providerId, null);
    try {
      const outcome = await api.hostedProvidersConnect(providerId, value);
      if (outcome && outcome.ok === false) {
        const mapped = mapConnectFailure(outcome);
        setRowResult(providerId, mapped.state);
        setRowMessage(providerId, mapped.message);
        return;
      }
      setKeys((current) => ({ ...current, [providerId]: "" }));
      setRowResult(providerId, "success");
      setRowMessage(providerId, "Connected. The provider accepted and saved this key.");
      await onChanged();
    } catch (error) {
      const mapped = mapProviderError(error);
      setRowResult(providerId, mapped.state);
      setRowMessage(providerId, mapped.message);
    } finally {
      setRowBusy(providerId, null);
    }
  };

  /** Test the entered candidate key (validated without overwriting on failure), or the stored key when the field is empty. */
  const testProvider = async (providerId: string) => {
    const value = (keys[providerId] || "").trim();
    setRowBusy(providerId, "test");
    setRowResult(providerId, null);
    setRowMessage(providerId, null);
    try {
      if (value) {
        const outcome = await api.hostedProvidersConnect(providerId, value);
        if (outcome && outcome.ok === false) {
          const mapped = mapConnectFailure(outcome);
          setRowResult(providerId, mapped.state);
          setRowMessage(providerId, mapped.message);
          return;
        }
        setKeys((current) => ({ ...current, [providerId]: "" }));
        setRowResult(providerId, "success");
        setRowMessage(providerId, "Connected. The provider accepted and saved this key.");
        await onChanged();
        return;
      }
      if (!configured.has(providerId)) {
        setRowResult(providerId, "config_error");
        setRowMessage(providerId, "Enter an API key before testing the connection.");
        return;
      }
      const tested = await api.hostedProvidersTest(providerId);
      if (tested && tested.ok === false) {
        setRowResult(providerId, "auth_failed");
        setRowMessage(providerId, tested.message || tested.probe?.message || "The provider rejected the stored key.");
        return;
      }
      setRowResult(providerId, "success");
      setRowMessage(providerId, "Connected. The stored key is working.");
    } catch (error) {
      const mapped = mapProviderError(error);
      setRowResult(providerId, mapped.state);
      setRowMessage(providerId, mapped.message);
    } finally {
      setRowBusy(providerId, null);
    }
  };

  const removeProvider = async (providerId: string, name: string) => {
    if (!window.confirm(`Remove the saved ${name} API key from this machine?`)) {
      return;
    }
    setRowBusy(providerId, "remove");
    setRowResult(providerId, null);
    setRowMessage(providerId, null);
    try {
      await api.hostedProvidersClear(providerId);
      setKeys((current) => ({ ...current, [providerId]: "" }));
      setRowMessage(providerId, "The saved key was removed.");
      await onChanged();
    } catch (error) {
      const mapped = mapProviderError(error);
      setRowResult(providerId, mapped.state);
      setRowMessage(providerId, mapped.message);
    } finally {
      setRowBusy(providerId, null);
    }
  };

  return (
    <div className="setup-provider-keys" data-testid="api-providers-keys">
      {SETUP_PROVIDERS.map((provider) => {
        const isConfigured = configured.has(provider.id);
        const rowBusy = busy[provider.id] || null;
        const rowResult = result[provider.id] || null;
        const rowMessage = message[provider.id] || null;
        return (
          <div key={provider.id} className="setup-provider-row" data-testid={`provider-row-${provider.id}`}>
            <div className="setup-provider-row-head">
              <div className="setup-provider-id">
                <strong>{provider.name}</strong>
                <span className="setup-provider-detail">{provider.detail}</span>
              </div>
              <span
                className={`setup-provider-status${rowResult ? ` is-${rowResult}` : isConfigured ? " is-success" : ""}`}
                data-testid={`provider-status-${provider.id}`}
                role="status"
              >
                {rowResult ? RESULT_LABEL[rowResult] : isConfigured ? "Connected" : "Not configured"}
              </span>
            </div>
            <div className="setup-provider-controls">
              <input
                type={showKey[provider.id] ? "text" : "password"}
                autoComplete="off"
                value={keys[provider.id] || ""}
                placeholder={isConfigured ? "Key saved — enter a new key to replace" : "Paste your API key"}
                aria-label={`${provider.name} API key`}
                data-testid={`provider-key-input-${provider.id}`}
                onChange={(event) => setKeys((current) => ({ ...current, [provider.id]: event.target.value }))}
              />
              <button
                type="button"
                onClick={() => setShowKey((current) => ({ ...current, [provider.id]: !current[provider.id] }))}
              >
                {showKey[provider.id] ? "Hide key" : "Show key"}
              </button>
              <button
                type="button"
                disabled={rowBusy !== null}
                data-testid={`provider-test-${provider.id}`}
                onClick={() => void testProvider(provider.id)}
              >
                {rowBusy === "test" ? "Testing…" : "Test Connection"}
              </button>
              <button
                type="button"
                className="primary"
                disabled={rowBusy !== null}
                data-testid={`provider-save-${provider.id}`}
                onClick={() => void saveProvider(provider.id)}
              >
                {rowBusy === "save" ? "Saving…" : isConfigured ? "Update Key" : "Save Key"}
              </button>
              {isConfigured && (
                <button
                  type="button"
                  disabled={rowBusy !== null}
                  data-testid={`provider-remove-${provider.id}`}
                  onClick={() => void removeProvider(provider.id, provider.name)}
                >
                  {rowBusy === "remove" ? "Removing…" : "Remove Key"}
                </button>
              )}
            </div>
            {rowMessage && (
              <p className="setup-provider-message" role="status">
                {rowMessage}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

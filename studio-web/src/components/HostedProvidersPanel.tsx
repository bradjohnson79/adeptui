import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";

type ProviderCard = {
  providerId: string;
  displayName: string;
  role: string;
  recommended: boolean;
  priority: number;
  connectionStatus: string;
  apiKeyStatus?: { configured?: boolean; hint?: string; state?: string; verifiedAt?: string; message?: string };
  availableBalance?: unknown;
  supportedModalities?: string[];
  certifiedModels?: string[];
  estimatedPricing?: string;
  healthStatus?: string;
  lastSuccessfulExecution?: string | null;
  currentVersion?: string;
  keysUrl?: string;
  mock?: boolean;
};

const PREF_OPTIONS: { id: string; label: string }[] = [
  { id: "kie", label: "Kie.ai (Recommended)" },
  { id: "wavespeed", label: "WaveSpeed.ai" },
  { id: "fal", label: "fal.ai" },
  { id: "automatic", label: "Automatic Recommendation" },
];

export function HostedProvidersPanel() {
  const [catalog, setCatalog] = useState<any>(null);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    const c = await api.hostedProvidersCatalog();
    setCatalog(c);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [refresh]);

  const run = async (providerId: string, action: () => Promise<unknown>) => {
    setBusy(providerId);
    setError(null);
    try {
      await action();
      setKeys((k) => ({ ...k, [providerId]: "" }));
      await refresh();
      setMsg(`${providerId}: updated`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const preferred = catalog?.preferences?.preferredProvider || "automatic";
  const providers: ProviderCard[] = catalog?.providers || [];

  return (
    <div className="settings-panel" data-testid="hosted-providers-panel">
      <h3>Hosted AI Providers</h3>
      <p className="muted">
        Equally supported integrations, recommended in this order: Kie.ai → WaveSpeed.ai → fal.ai. Product surfaces
        never call a provider directly — requests flow through Canonical Intent → Capability Resolver → Certified
        Provider Resolver → Canonical Queue → Asset Library → Timeline → Provenance.
      </p>
      {catalog?.mock === true && (
        <p className="error" role="alert">
          Unexpected mock catalog — refuse to continue.
        </p>
      )}

      <section data-testid="hosted-provider-preference" style={{ marginBottom: "1.25rem" }}>
        <h4>Preferred Hosted Provider</h4>
        <div style={{ display: "grid", gap: "0.35rem" }}>
          {PREF_OPTIONS.map((o) => (
            <label key={o.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="radio"
                name="preferred-hosted"
                data-testid={`hosted-pref-${o.id}`}
                checked={preferred === o.id}
                onChange={() =>
                  void run("prefs", () => api.hostedProvidersSetPreferred(o.id as "kie" | "wavespeed" | "fal" | "automatic"))
                }
              />
              {o.label}
            </label>
          ))}
        </div>
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          Automatic Recommendation evaluates certified capability, availability, budget preference, estimated cost,
          queue time, and model availability — never silently switches after a job is submitted.
        </p>
      </section>

      <div style={{ display: "grid", gap: "1rem" }} data-testid="hosted-provider-cards">
        {providers.map((p) => (
          <article
            key={p.providerId}
            className="panel"
            data-testid={`hosted-provider-card-${p.providerId}`}
            style={{ padding: "0.75rem", border: "1px solid var(--border, #333)" }}
          >
            <header style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
              <div>
                <strong>
                  {p.recommended ? "⭐ " : ""}
                  {p.displayName}
                </strong>
                <span className="muted"> · {p.recommended ? "Recommended" : "Alternative"} · priority {p.priority}</span>
              </div>
              <span data-testid={`hosted-health-${p.providerId}`}>Health: {p.healthStatus || "—"}</span>
            </header>
            <ul className="muted" style={{ fontSize: "0.9rem", margin: "0.5rem 0" }}>
              <li>Connection: {p.connectionStatus}</li>
              <li>
                API key: {p.apiKeyStatus?.configured ? p.apiKeyStatus.hint || "configured" : "not configured"}
                {p.apiKeyStatus?.verifiedAt ? ` · checked ${p.apiKeyStatus.verifiedAt}` : ""}
              </li>
              <li>
                Balance:{" "}
                {p.availableBalance != null ? String(p.availableBalance) : "— (shown when provider supports live balance)"}
              </li>
              <li>Modalities: {(p.supportedModalities || []).join(", ") || "—"}</li>
              <li>Certified models: {(p.certifiedModels || []).join(", ") || "—"}</li>
              <li>Pricing: {p.estimatedPricing || "—"}</li>
              <li>Last successful execution: {p.lastSuccessfulExecution || "—"}</li>
              <li>Version: {p.currentVersion || "—"}</li>
            </ul>
            {p.apiKeyStatus?.message && <p className="muted">{p.apiKeyStatus.message}</p>}
            <div className="field">
              <label htmlFor={`key-${p.providerId}`}>API key</label>
              <input
                id={`key-${p.providerId}`}
                data-testid={`hosted-key-input-${p.providerId}`}
                type="password"
                autoComplete="off"
                value={keys[p.providerId] || ""}
                onChange={(e) => setKeys((k) => ({ ...k, [p.providerId]: e.target.value }))}
                placeholder={p.apiKeyStatus?.configured ? "Paste to replace…" : "Paste API key…"}
              />
            </div>
            <div className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
              <Button
                data-testid={`hosted-connect-${p.providerId}`}
                disabled={busy === p.providerId || !(keys[p.providerId] || "").trim()}
                onClick={() =>
                  void run(p.providerId, () => api.hostedProvidersConnect(p.providerId, keys[p.providerId] || ""))
                }
              >
                {busy === p.providerId ? "Checking…" : "Connect"}
              </Button>
              <Button
                data-testid={`hosted-test-${p.providerId}`}
                disabled={busy === p.providerId || !p.apiKeyStatus?.configured}
                onClick={() => void run(p.providerId, () => api.hostedProvidersTest(p.providerId))}
              >
                Test
              </Button>
              <Button
                data-testid={`hosted-preferred-${p.providerId}`}
                disabled={busy === p.providerId}
                onClick={() =>
                  void run(p.providerId, () =>
                    api.hostedProvidersSetPreferred(p.providerId as "kie" | "wavespeed" | "fal"),
                  )
                }
              >
                Preferred
              </Button>
              <Button
                data-testid={`hosted-clear-${p.providerId}`}
                disabled={busy === p.providerId || !p.apiKeyStatus?.configured}
                onClick={() => void run(p.providerId, () => api.hostedProvidersClear(p.providerId))}
              >
                Clear
              </Button>
              {p.keysUrl && (
                <a href={p.keysUrl} target="_blank" rel="noreferrer">
                  Get API key
                </a>
              )}
            </div>
          </article>
        ))}
      </div>

      {error && (
        <p className="error" role="alert" data-testid="hosted-providers-error">
          {error}
        </p>
      )}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}

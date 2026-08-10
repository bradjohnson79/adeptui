import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

type ProviderId = "kie" | "wavespeed" | "fal";

type ProviderCardData = {
  providerId: string;
  displayName: string;
  role?: string;
  recommended?: boolean;
  connectionStatus?: string;
  apiKeyStatus?: {
    configured?: boolean;
    hint?: string;
    state?: string;
    verifiedAt?: string;
    message?: string;
  };
  healthStatus?: string;
  keysUrl?: string;
  supportedModalities?: string[];
  estimatedPricing?: string;
};

const SETUP_PROVIDERS: { id: ProviderId; title: string; blurb: string }[] = [
  {
    id: "kie",
    title: "Kie.ai",
    blurb: "Recommended hosted provider for image and video generation (BYOK).",
  },
  {
    id: "wavespeed",
    title: "WaveSpeed.ai",
    blurb: "Hosted generation alternative with WaveSpeed Access Key (BYOK).",
  },
  {
    id: "fal",
    title: "fal.ai",
    blurb: "Hosted fal.ai key for certified cloud video and image routes (BYOK).",
  },
];

function statusTone(card?: ProviderCardData | null): string {
  const state = String(card?.apiKeyStatus?.state || card?.connectionStatus || "").toLowerCase();
  if (state.includes("verified") || state.includes("connected") || card?.apiKeyStatus?.configured) {
    return "ready";
  }
  if (state.includes("invalid") || state.includes("error") || state.includes("fail")) {
    return "error";
  }
  if (state.includes("checking") || state.includes("loading")) {
    return "pending";
  }
  return "attention";
}

function statusLabel(card?: ProviderCardData | null, busy?: boolean): string {
  if (busy) return "Working…";
  if (!card) return "Checking…";
  if (card.apiKeyStatus?.configured) {
    const state = card.apiKeyStatus.state || card.connectionStatus || "Configured";
    if (String(state).toLowerCase().includes("verified") || String(state).toLowerCase().includes("connected")) {
      return "Ready";
    }
    return "Configured";
  }
  return "Needs API key";
}

function HostedProviderSetupCard({
  meta,
  card,
  keyValue,
  busy,
  preferred,
  onKeyChange,
  onConnect,
  onTest,
  onClear,
  onPreferred,
}: {
  meta: (typeof SETUP_PROVIDERS)[number];
  card?: ProviderCardData | null;
  keyValue: string;
  busy: boolean;
  preferred: boolean;
  onKeyChange: (value: string) => void;
  onConnect: () => void;
  onTest: () => void;
  onClear: () => void;
  onPreferred: () => void;
}) {
  const tone = statusTone(card);
  const configured = Boolean(card?.apiKeyStatus?.configured);
  const inputId = `setup-hosted-key-${meta.id}`;

  return (
    <article
      className={`setup-component-card download-source-card status-${tone}`}
      data-testid={`setup-hosted-provider-${meta.id}`}
      data-status={statusLabel(card, busy)}
    >
      <header className="setup-card-header">
        <div>
          <h3>
            {meta.title}
            {card?.recommended ? " · Recommended" : ""}
          </h3>
          <span className="setup-requirement">Hosted API Provider</span>
        </div>
        <span className="setup-status" data-state={tone}>
          <span className="setup-status-mark" aria-hidden="true" />
          {statusLabel(card, busy)}
        </span>
      </header>
      <p className="setup-component-description">
        {card?.apiKeyStatus?.message || meta.blurb}
      </p>
      <div className="setup-card-meta">
        <span>Connection {card?.connectionStatus || "unknown"}</span>
        <span>
          Key{" "}
          {configured
            ? card?.apiKeyStatus?.hint || "configured (masked)"
            : "not configured"}
        </span>
        {card?.apiKeyStatus?.verifiedAt && (
          <span>Verified {new Date(card.apiKeyStatus.verifiedAt).toLocaleString()}</span>
        )}
        {(card?.supportedModalities || []).length > 0 && (
          <span>Modalities {(card?.supportedModalities || []).join(", ")}</span>
        )}
        {preferred && <span>Preferred provider</span>}
        {card?.estimatedPricing && <span>{card.estimatedPricing}</span>}
      </div>
      <div className="field setup-hosted-key-field">
        <label htmlFor={inputId}>API key</label>
        <input
          id={inputId}
          data-testid={`setup-hosted-key-input-${meta.id}`}
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={keyValue}
          disabled={busy}
          onChange={(e) => onKeyChange(e.target.value)}
          placeholder={configured ? "Paste to replace…" : "Paste API key…"}
        />
      </div>
      <div className="setup-card-actions">
        <button
          type="button"
          className="primary"
          data-testid={`setup-hosted-connect-${meta.id}`}
          disabled={busy || !keyValue.trim()}
          onClick={onConnect}
        >
          {busy ? "Saving…" : configured ? "Replace & Verify" : "Save & Verify"}
        </button>
        <button
          type="button"
          data-testid={`setup-hosted-test-${meta.id}`}
          disabled={busy || !configured}
          onClick={onTest}
        >
          Test
        </button>
        <button
          type="button"
          data-testid={`setup-hosted-preferred-${meta.id}`}
          disabled={busy}
          onClick={onPreferred}
        >
          {preferred ? "Preferred ✓" : "Set Preferred"}
        </button>
        <button
          type="button"
          data-testid={`setup-hosted-clear-${meta.id}`}
          disabled={busy || !configured}
          onClick={onClear}
        >
          Clear
        </button>
        {card?.keysUrl ? (
          <a
            className="linkish"
            href={card.keysUrl}
            target="_blank"
            rel="noreferrer"
            data-testid={`setup-hosted-keys-link-${meta.id}`}
          >
            Get API key
          </a>
        ) : null}
      </div>
    </article>
  );
}

/**
 * Setup Wizard section for hosted BYOK providers.
 * Keys are saved only via `/api/hosted-providers/*` (encrypted secrets) — never localStorage.
 */
type DiscoverySummary = {
  providerId?: string;
  providerDisplayName?: string;
  videoFound?: number;
  imageFound?: number;
  audioFound?: number;
  llmFound?: number;
  compatible?: number;
  requiresAdapter?: number;
  unavailable?: number;
  accountAccessible?: boolean;
};

function formatDiscoverySummary(title: string, summary?: DiscoverySummary | null): string {
  if (!summary) return `${title}: connected. Discovery summary unavailable.`;
  const name = summary.providerDisplayName || title;
  return [
    `${name} connected`,
    "",
    `Video models found: ${summary.videoFound ?? 0}`,
    `Image models found: ${summary.imageFound ?? 0}`,
    `Audio models found: ${summary.audioFound ?? 0}`,
    `LLM models found: ${summary.llmFound ?? 0}`,
    "",
    `Compatible with Adept UI: ${summary.compatible ?? 0}`,
    `Requires adapters: ${summary.requiresAdapter ?? 0}`,
    `Unavailable to account: ${summary.unavailable ?? 0}`,
  ].join("\n");
}

export function HostedProvidersSetupPanel({
  onMessage,
}: {
  onMessage?: (message: string | null) => void;
}) {
  const [providers, setProviders] = useState<ProviderCardData[]>([]);
  const [preferred, setPreferred] = useState<string>("automatic");
  const [budgetPreference, setBudgetPreference] = useState<string>("balanced");
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [panelMessage, setPanelMessage] = useState<string | null>(null);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [discoverySummary, setDiscoverySummary] = useState<DiscoverySummary | null>(null);
  const [compatName, setCompatName] = useState("OpenAI-compatible");
  const [compatBaseUrl, setCompatBaseUrl] = useState("");
  const [compatKey, setCompatKey] = useState("");
  const [compatEndpoints, setCompatEndpoints] = useState<
    { id: string; displayName?: string; baseUrl?: string; discoveredModels?: string[] }[]
  >([]);

  const announce = (message: string | null, isError = false) => {
    if (isError) {
      setPanelError(message);
      setPanelMessage(null);
    } else {
      setPanelMessage(message);
      setPanelError(null);
    }
    onMessage?.(message);
  };

  const refresh = useCallback(async () => {
    const catalog = await api.hostedProvidersCatalog();
    if (catalog?.mock === true) {
      throw new Error("Unexpected mock hosted-providers catalog — refuse to continue.");
    }
    const list: ProviderCardData[] = Array.isArray(catalog?.providers) ? catalog.providers : [];
    setProviders(list);
    setPreferred(String(catalog?.preferences?.preferredProvider || "automatic"));
    setBudgetPreference(String(catalog?.preferences?.budgetPreference || "balanced"));
    try {
      const compat = await api.hostedProvidersListOpenAICompatible();
      setCompatEndpoints(Array.isArray(compat?.endpoints) ? compat.endpoints : []);
    } catch {
      setCompatEndpoints([]);
    }
    return catalog;
  }, []);

  useEffect(() => {
    refresh().catch((error: unknown) => {
      announce(error instanceof Error ? error.message : String(error), true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (providerId: ProviderId, fn: () => Promise<void>) => {
    setBusyId(providerId);
    setPanelError(null);
    try {
      await fn();
      await refresh();
    } catch (error: unknown) {
      announce(error instanceof Error ? error.message : String(error), true);
    } finally {
      setBusyId(null);
    }
  };

  const byId = (id: ProviderId) => providers.find((p) => p.providerId === id) || null;

  return (
    <section className="setup-component-section" aria-labelledby="hosted-api-providers-heading">
      <div className="setup-section-heading">
        <div>
          <h2 id="hosted-api-providers-heading">Hosted API Providers</h2>
          <p>
            Add Kie.ai and WaveSpeed.ai API keys (and fal.ai) for Production Dock API mode. Keys stay encrypted on
            this machine — React never calls providers directly.
          </p>
        </div>
        <span>3 providers</span>
      </div>
      {panelMessage && (
        <p className="setup-message" role="status" data-testid="setup-hosted-providers-message">
          {panelMessage}
        </p>
      )}
      {panelError && (
        <p className="setup-message error" role="alert" data-testid="setup-hosted-providers-error">
          {panelError}
        </p>
      )}
      <div className="setup-component-grid download-sources-grid setup-hosted-providers-grid">
        {SETUP_PROVIDERS.map((meta) => {
          const card = byId(meta.id);
          return (
            <HostedProviderSetupCard
              key={meta.id}
              meta={meta}
              card={card}
              keyValue={keys[meta.id] || ""}
              busy={busyId === meta.id}
              preferred={preferred === meta.id}
              onKeyChange={(value) => setKeys((prev) => ({ ...prev, [meta.id]: value }))}
              onConnect={() =>
                void run(meta.id, async () => {
                  const apiKey = (keys[meta.id] || "").trim();
                  if (!apiKey) {
                    throw new Error(`Paste a ${meta.title} API key to save.`);
                  }
                  const result = await api.hostedProvidersConnect(meta.id, apiKey);
                  setKeys((prev) => ({ ...prev, [meta.id]: "" }));
                  const summary = (result?.summary || result?.discovery?.summary) as DiscoverySummary | undefined;
                  setDiscoverySummary(summary || null);
                  announce(formatDiscoverySummary(meta.title, summary));
                })
              }
              onTest={() =>
                void run(meta.id, async () => {
                  const result = await api.hostedProvidersTest(meta.id);
                  const summary = (result?.summary || result?.discovery?.summary) as DiscoverySummary | undefined;
                  if (summary) {
                    setDiscoverySummary(summary);
                    announce(formatDiscoverySummary(meta.title, summary));
                  } else {
                    announce(
                      `${meta.title}: ${result?.message || result?.connectionStatus || "connection test complete."}`,
                    );
                  }
                })
              }
              onClear={() =>
                void run(meta.id, async () => {
                  if (!window.confirm(`Clear the saved ${meta.title} API key from this machine?`)) {
                    announce(`${meta.title}: clear cancelled.`);
                    return;
                  }
                  await api.hostedProvidersClear(meta.id);
                  setKeys((prev) => ({ ...prev, [meta.id]: "" }));
                  setDiscoverySummary(null);
                  announce(`${meta.title}: API key cleared.`);
                })
              }
              onPreferred={() =>
                void run(meta.id, async () => {
                  await api.hostedProvidersSetPreferred(meta.id);
                  const discovery = await api.hostedProvidersDiscover(meta.id);
                  const summary = (discovery?.summary || discovery?.discovery?.summary) as
                    | DiscoverySummary
                    | undefined;
                  setDiscoverySummary(summary || null);
                  announce(
                    summary
                      ? `${meta.title}: set as preferred.\n\n${formatDiscoverySummary(meta.title, summary)}`
                      : `${meta.title}: set as preferred hosted provider.`,
                  );
                })
              }
            />
          );
        })}
      </div>
      {discoverySummary ? (
        <div className="setup-hosted-discovery-summary" data-testid="setup-hosted-discovery-summary">
          <h3>Dynamic API Model Discovery</h3>
          <ul>
            <li>Video models found: {discoverySummary.videoFound ?? 0}</li>
            <li>Image models found: {discoverySummary.imageFound ?? 0}</li>
            <li>Audio models found: {discoverySummary.audioFound ?? 0}</li>
            <li>LLM models found: {discoverySummary.llmFound ?? 0}</li>
            <li>Compatible with Adept UI: {discoverySummary.compatible ?? 0}</li>
            <li>Requires adapters: {discoverySummary.requiresAdapter ?? 0}</li>
            <li>Unavailable to account: {discoverySummary.unavailable ?? 0}</li>
          </ul>
          <p className="setup-nav-strip">
            Discovered models appear in Production Dock API sections. Selecting a model is required before it
            becomes active — discovery never auto-activates.
          </p>
          <button
            type="button"
            className="linkish"
            data-testid="setup-retry-discovery"
            onClick={() => {
              const pid = (["kie", "wavespeed", "fal"].includes(String(discoverySummary.providerId))
                ? discoverySummary.providerId
                : preferred !== "automatic"
                  ? preferred
                  : "kie") as ProviderId;
              void run(pid, async () => {
                const discovery = await api.hostedProvidersDiscover(pid);
                const summary = (discovery?.summary || discovery?.discovery?.summary) as
                  | DiscoverySummary
                  | undefined;
                setDiscoverySummary(summary || null);
                announce(formatDiscoverySummary(summary?.providerDisplayName || "Provider", summary));
              });
            }}
          >
            Retry Discovery
          </button>
        </div>
      ) : null}
      <div className="setup-hosted-openai-compat" data-testid="setup-openai-compatible" style={{ marginTop: "1.25rem" }}>
        <h3>OpenAI-compatible chat endpoint</h3>
        <p>
          Connect any OpenAI-compatible <code>/v1/chat/completions</code> host. Adept discovers models from{" "}
          <code>/v1/models</code> — LLM capability is shown only when detected.
        </p>
        <label>
          Display name
          <input
            data-testid="openai-compat-display-name"
            value={compatName}
            onChange={(e) => setCompatName(e.target.value)}
            aria-label="OpenAI-compatible display name"
          />
        </label>
        <label>
          API base URL
          <input
            data-testid="openai-compat-base-url"
            placeholder="https://api.example.com"
            value={compatBaseUrl}
            onChange={(e) => setCompatBaseUrl(e.target.value)}
            aria-label="OpenAI-compatible base URL"
          />
        </label>
        <label>
          API key
          <input
            data-testid="openai-compat-api-key"
            type="password"
            autoComplete="off"
            value={compatKey}
            onChange={(e) => setCompatKey(e.target.value)}
            aria-label="OpenAI-compatible API key"
          />
        </label>
        <button
          type="button"
          data-testid="openai-compat-connect"
          disabled={busyId === "openai_compatible"}
          onClick={() => {
            void (async () => {
              setBusyId("openai_compatible");
              try {
                const result = await api.hostedProvidersConnectOpenAICompatible({
                  displayName: compatName,
                  baseUrl: compatBaseUrl,
                  api_key: compatKey,
                });
                setCompatKey("");
                const models = result?.endpoint?.discoveredModels || result?.probe?.models || [];
                announce(
                  `OpenAI-compatible connected. LLM models detected: ${Array.isArray(models) ? models.length : 0}.`,
                );
                await refresh();
              } catch (error: unknown) {
                announce(error instanceof Error ? error.message : String(error), true);
              } finally {
                setBusyId(null);
              }
            })();
          }}
        >
          Test &amp; Save
        </button>
        <ul data-testid="openai-compat-endpoint-list">
          {compatEndpoints.map((ep) => (
            <li key={ep.id}>
              <strong>{ep.displayName || "OpenAI-compatible"}</strong> — {ep.baseUrl}
              <div>Models: {(ep.discoveredModels || []).length}</div>
              <button
                type="button"
                onClick={() =>
                  void api.hostedProvidersDeleteOpenAICompatible(ep.id).then(() => refresh())
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      </div>

      <label style={{ display: "block", marginTop: "1rem" }}>
        Spending preference
        <span title="Affects which hosted provider Adept recommends when several can run the job."> (?)</span>
        <select
          data-testid="hosted-budget-preference"
          value={budgetPreference}
          aria-label="Spending preference"
          onChange={(e) => {
            const value = e.target.value;
            setBudgetPreference(value);
            void api
              .hostedProvidersPutPreferences({
                preferredProvider: (preferred as "kie" | "wavespeed" | "fal" | "automatic") || "automatic",
                budgetPreference: value,
              })
              .then(() => announce(`Spending preference set to ${value}.`))
              .catch((error: unknown) => announce(error instanceof Error ? error.message : String(error), true));
          }}
        >
          <option value="low_cost">Lower cost</option>
          <option value="balanced">Balanced</option>
          <option value="quality">Higher quality</option>
        </select>
      </label>

      <p className="setup-nav-strip">
        <button
          type="button"
          className="linkish"
          data-testid="setup-open-ai-providers-settings"
          onClick={() => {
            try {
              sessionStorage.setItem("adept_settings_tab", "integrations");
            } catch {
              /* ignore */
            }
            const path = window.location.pathname.match(/^\/project\/[^/]+/)?.[0] || "/";
            const url = path === "/" ? "/?workspace=settings" : `${path}?workspace=settings`;
            window.location.assign(url);
          }}
        >
          Open Settings → AI Providers
        </button>{" "}
        for full capability matrix and preference details.
      </p>
    </section>
  );
}

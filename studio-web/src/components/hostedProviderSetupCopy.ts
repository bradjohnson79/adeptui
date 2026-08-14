export const API_KEY_PROVIDERS_CATEGORY = "API Providers";
export const API_KEY_PROVIDER_BADGE = "API Key Provider";
export const API_KEY_SAVE_LABEL = "Update";
export const API_KEY_UPDATE_LABEL = "Update";
export const API_KEY_REMOVE_LABEL = "Remove";
export const API_KEY_INPUT_TYPE = "password";

export const SETUP_PROVIDERS = [
  {
    id: "kie" as const,
    title: "Kie.ai",
    blurb: "Recommended hosted provider for image and video generation (BYOK).",
  },
  {
    id: "wavespeed" as const,
    title: "WaveSpeed.ai",
    blurb: "Hosted generation alternative with WaveSpeed Access Key (BYOK).",
  },
  {
    id: "fal" as const,
    title: "fal.ai",
    blurb: "Hosted fal.ai key for certified cloud video and image routes (BYOK).",
  },
];

export const API_KEY_PROVIDER_IDS = SETUP_PROVIDERS.map((item) => item.id);
export const API_KEY_PROVIDER_TITLES = SETUP_PROVIDERS.map((item) => item.title);
export const API_KEY_CATALOG_IDS = ["fal_key", "kie_key", "wavespeed_key"] as const;

const API_KEY_CLOUD_PROVIDER_ALIASES = new Set([
  "kie",
  "kie.ai",
  "kie_key",
  "fal",
  "fal.ai",
  "fal_key",
  "wavespeed",
  "wavespeed.ai",
  "wavespeed_key",
]);

export const STATUS = {
  NOT_CONFIGURED: "NOT CONFIGURED",
  CONNECTED: "CONNECTED",
  INVALID_CREDENTIALS: "INVALID CREDENTIALS",
  UNREACHABLE: "UNREACHABLE",
  RATE_LIMITED: "RATE LIMITED",
} as const;

export type ApiKeyProviderStatus =
  (typeof STATUS)[keyof typeof STATUS];

export type ProbeOutcome = "invalid" | "unreachable" | "rate_limited" | null;

export const FORBIDDEN_GENERIC_LABELS = [
  "Requires Setup",
  "Requires setup",
  "Needs API key",
  "Needs credentials",
  "Configured",
  "Ready",
] as const;

export type ApiKeyProviderCard = {
  connectionStatus?: string;
  healthStatus?: string;
  apiKeyStatus?: {
    configured?: boolean;
    state?: string;
    message?: string;
    hint?: string;
    verifiedAt?: string;
  };
  supportedModalities?: string[];
  certifiedModels?: string[];
  executableCapabilities?: string[];
  availableBalance?: string | number | null;
};

export type CatalogComponentLike = {
  id?: string;
  category?: string | null;
  group?: string | null;
  surfaceGroups?: string[] | null;
  name?: string | null;
};

export function normalizeProviderId(id: string | undefined | null): string {
  return String(id || "").trim().toLowerCase();
}

export function isApiKeyCloudProvider(id: string | undefined | null): boolean {
  const raw = normalizeProviderId(id);
  if (!raw) return false;
  if (API_KEY_CLOUD_PROVIDER_ALIASES.has(raw)) return true;
  const compact = raw.replace(/[._\s-]/g, "");
  return compact === "kie" || compact === "kieai" || compact === "kiekey"
    || compact === "fal" || compact === "falai" || compact === "falkey"
    || compact === "wavespeed" || compact === "wavespeedai" || compact === "wavespeedkey";
}

export function isApiKeyCatalogComponent(component: CatalogComponentLike): boolean {
  if (isApiKeyCloudProvider(component.id)) return true;
  const surfaces = [
    component.category,
    component.group,
    ...(component.surfaceGroups || []),
  ].map((value) => String(value || "").trim());
  if (surfaces.some((value) => value === "API Providers")) return true;
  const name = String(component.name || "").toLowerCase();
  return name === "fal.ai api key" || name === "kie.ai api key" || name === "wavespeed.ai api key";
}

export function filterCloudProviders<T extends { providerId?: string; id?: string }>(items: T[]): T[] {
  return items.filter((item) => !isApiKeyCloudProvider(item.providerId || item.id));
}

export function catalogApiProvidersHiddenFromOptional(): string {
  return "API Providers";
}

export function maskedKeyPlaceholder(hint?: string | null): string {
  const raw = String(hint || "").trim();
  if (!raw) return "••••••••";
  const alnum = raw.replace(/[^A-Za-z0-9]/g, "");
  const last4 = alnum.slice(-4);
  return last4.length === 4 ? `••••${last4}` : "••••••••";
}

export function apiKeyUpdatedCopy(title: string): string {
  return `${title} API key updated`;
}

export function apiKeyRemovedCopy(): string {
  return "API key removed";
}

export function copyClaimsKeyUpdated(text: string): boolean {
  return /api key updated/i.test(String(text || ""));
}

export function apiKeyProviderCardContract() {
  return SETUP_PROVIDERS.map((item) => ({
    id: item.id,
    title: item.title,
    inputType: API_KEY_INPUT_TYPE,
    updateLabel: API_KEY_UPDATE_LABEL,
    removeLabel: API_KEY_REMOVE_LABEL,
  }));
}

export function classifyProbeError(message: string, status?: number): Exclude<ProbeOutcome, null> {
  const text = String(message || "").toLowerCase();
  if (status === 429 || text.includes("rate limit") || text.includes("too many requests")) {
    return "rate_limited";
  }
  if (
    status === 401
    || status === 403
    || text.includes("rejected")
    || text.includes("invalid")
    || text.includes("unauthorized")
  ) {
    return "invalid";
  }
  if (
    status === 0
    || text.includes("could not reach")
    || text.includes("unavailable")
    || text.includes("timed out")
    || text.includes("timeout")
    || text.includes("network")
  ) {
    return "unreachable";
  }
  if (status === 400) return "invalid";
  return "unreachable";
}

export function apiKeyProviderStatusLabel(input: {
  busy?: boolean;
  card?: ApiKeyProviderCard | null;
  lastOutcome?: ProbeOutcome;
}): string {
  if (input.busy) return "Working...";
  const outcome = input.lastOutcome;
  if (outcome === "rate_limited") return STATUS.RATE_LIMITED;
  if (outcome === "invalid") return STATUS.INVALID_CREDENTIALS;
  if (outcome === "unreachable") return STATUS.UNREACHABLE;

  const card = input.card;
  if (!card) return "Checking...";

  const state = String(card.apiKeyStatus?.state || card.connectionStatus || "").toLowerCase();
  const message = String(card.apiKeyStatus?.message || "").toLowerCase();

  if (state === "rate_limited" || state.includes("rate_limit") || message.includes("rate limit")) {
    return STATUS.RATE_LIMITED;
  }
  if (state === "invalid") {
    return STATUS.INVALID_CREDENTIALS;
  }
  if (state === "unreachable") {
    return STATUS.UNREACHABLE;
  }
  if (state === "verified" || state === "connected") {
    return STATUS.CONNECTED;
  }
  if (state === "unverified" || (card.apiKeyStatus?.configured && state !== "" && state !== "missing")) {
    return STATUS.UNREACHABLE;
  }
  return STATUS.NOT_CONFIGURED;
}

export function apiKeyProviderStatusTone(label: string): string {
  if (label === STATUS.CONNECTED) return "ready";
  if (
    label === STATUS.INVALID_CREDENTIALS
    || label === STATUS.UNREACHABLE
    || label === STATUS.RATE_LIMITED
  ) {
    return "error";
  }
  if (label === "Working..." || label === "Checking...") return "pending";
  return "attention";
}

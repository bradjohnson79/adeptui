export const API_KEY_PROVIDERS_CATEGORY = "API KEY PROVIDERS";
export const API_KEY_PROVIDER_BADGE = "API Key Provider";
export const API_KEY_SAVE_LABEL = "Save";
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
  if (input.busy) return "Working…";
  const outcome = input.lastOutcome;
  if (outcome === "rate_limited") return STATUS.RATE_LIMITED;
  if (outcome === "invalid") return STATUS.INVALID_CREDENTIALS;
  if (outcome === "unreachable") return STATUS.UNREACHABLE;

  const card = input.card;
  if (!card) return "Checking…";

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
  if (label === "Working…" || label === "Checking…") return "pending";
  return "attention";
}

export function catalogApiProvidersHiddenFromOptional(): string {
  return "API Providers";
}

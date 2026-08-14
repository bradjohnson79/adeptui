import type { LifecycleCloudProvider } from "../types";

export const LEARN_MORE_FALLBACK = "Provider information is not available yet.";
export const CONNECTION_TEST_UNAVAILABLE = "Connection test is not available for this provider yet.";
export const SETUP_NOT_YET_SUPPORTED = "SETUP NOT YET SUPPORTED";
export const CREDENTIALS_STORED_ONLY = "Credentials stored only. Generation is not enabled for this provider yet.";

const CAPABILITY_LABELS: Record<string, string> = {
  "image.generate": "Image Generation",
  "image.edit": "Image Editing",
  "image.reference": "Reference Images",
  "image.upscale": "Upscale",
  "image.chroma_key": "Chroma Key",
};

export function translateCapabilityChip(operation: string): string {
  const raw = String(operation || "").trim();
  if (!raw) return "";
  return CAPABILITY_LABELS[raw] || raw.replace(/[._]/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function cloudProviderHasLearnMore(provider: Pick<LifecycleCloudProvider, "summary" | "useCases" | "localVsCloud" | "requirements" | "costPrivacyNote" | "docsUrl" | "keysUrl">): boolean {
  if (String(provider.summary || "").trim()) return true;
  if ((provider.useCases || []).some((item) => String(item || "").trim())) return true;
  if (String(provider.localVsCloud || "").trim()) return true;
  if ((provider.requirements || []).some((item) => String(item || "").trim())) return true;
  if (String(provider.costPrivacyNote || "").trim()) return true;
  if (String(provider.docsUrl || "").trim()) return true;
  if (String(provider.keysUrl || "").trim()) return true;
  return false;
}

export function cloudProviderLearnMoreCopy(provider: LifecycleCloudProvider): {
  summary: string;
  useCases: string[];
  localVsCloud: string;
  requirements: string[];
  costPrivacyNote: string;
  capabilities: string[];
  fallback: string | null;
} {
  const hasInfo = cloudProviderHasLearnMore(provider);
  return {
    summary: String(provider.summary || "").trim(),
    useCases: (provider.useCases || []).map((item) => String(item || "").trim()).filter(Boolean),
    localVsCloud: String(provider.localVsCloud || "").trim(),
    requirements: (provider.requirements || []).map((item) => String(item || "").trim()).filter(Boolean),
    costPrivacyNote: String(provider.costPrivacyNote || "").trim(),
    capabilities: (provider.operations || []).map(translateCapabilityChip).filter(Boolean),
    fallback: hasInfo ? null : LEARN_MORE_FALLBACK,
  };
}

export function cloudProviderSetupSupported(provider: Pick<LifecycleCloudProvider, "setupSupported" | "secretName">): boolean {
  if (provider.setupSupported === false) return false;
  if (provider.setupSupported === true) return true;
  return Boolean(String(provider.secretName || "").trim());
}

export function cloudProviderPrimaryAction(provider: Pick<LifecycleCloudProvider, "configured" | "setupSupported" | "secretName">): "set_up" | "manage" | "coming_soon" {
  if (!cloudProviderSetupSupported(provider)) return "coming_soon";
  return provider.configured ? "manage" : "set_up";
}

export function cloudProviderPrimaryLabel(provider: Pick<LifecycleCloudProvider, "configured" | "setupSupported" | "secretName">): string {
  const action = cloudProviderPrimaryAction(provider);
  if (action === "manage") return "Manage";
  if (action === "set_up") return "Set Up";
  return SETUP_NOT_YET_SUPPORTED;
}

export function cloudProviderStatusVocabulary(provider: Pick<LifecycleCloudProvider, "configured" | "state" | "statusLabel">): {
  statusLabel: string;
  metaLabel: string;
  claimsReady: boolean;
} {
  const state = String(provider.state || "").toLowerCase();
  const statusLabel = state === "verified"
    ? (provider.statusLabel || "Ready")
    : (provider.statusLabel && provider.statusLabel !== "Ready" ? provider.statusLabel : "Requires Setup");
  return {
    statusLabel,
    metaLabel: provider.configured ? "Configured" : "Needs credentials",
    claimsReady: state === "verified",
  };
}

export function cloudProviderAiPrompt(provider: Pick<LifecycleCloudProvider, "displayName" | "providerId">): string {
  const name = String(provider.displayName || "this cloud provider").trim();
  const id = String(provider.providerId || "").trim();
  return `Help me set up ${name}${id ? ` (provider id: ${id})` : ""}. Walk me through where to get an API key and what to paste in Setup. You cannot save the key — I will paste it in the Setup Wizard.`;
}

export function cloudProviderCardContract(provider: LifecycleCloudProvider): {
  providerId: string;
  showSetUp: boolean;
  showManage: boolean;
  showLearnMore: boolean;
  showComingSoon: boolean;
  primaryLabel: string;
  testConnectionAvailable: boolean;
  testConnectionMessage: string;
} {
  const action = cloudProviderPrimaryAction(provider);
  return {
    providerId: provider.providerId,
    showSetUp: action === "set_up",
    showManage: action === "manage",
    showLearnMore: true,
    showComingSoon: action === "coming_soon",
    primaryLabel: cloudProviderPrimaryLabel(provider),
    testConnectionAvailable: Boolean(provider.connectionTestAvailable),
    testConnectionMessage: CONNECTION_TEST_UNAVAILABLE,
  };
}


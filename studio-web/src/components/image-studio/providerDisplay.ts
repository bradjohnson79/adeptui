/**
 * Creator-facing display helpers for the Image Studio provider browser.
 * Presentation-only: readiness and capability truth stay in the backend descriptor.
 */
import type { ImageProviderDescriptor } from "../../contracts/cinematicImageStudio";
import { buildAiGuidedSetupPath } from "../../setup/navigation.ts";

type ProviderRef = Pick<ImageProviderDescriptor, "id" | "modelId">;

/** One-glance role hints for models whose name alone does not explain when to pick them. */
const PROVIDER_SUBLABELS: Record<string, string> = {
  "krea2-turbo-local": "Recommended / Fast",
  "krea2-raw-local": "Advanced / LoRA Training Base",
};

export function providerSubLabel(provider: ProviderRef): string | null {
  const key = provider.modelId || provider.id;
  return PROVIDER_SUBLABELS[key] ?? PROVIDER_SUBLABELS[provider.id] ?? null;
}

/**
 * Short license label from a backend licenseNote. Notes carry detail after an
 * em-dash or parenthesis ("Krea 2 Community License — commercial use …"), so the
 * head segment is the display name; the full note stays available as a tooltip.
 */
export function licenseShortName(licenseNote?: string | null): string | null {
  const note = (licenseNote || "").trim();
  if (!note) return null;
  const head = note.split(/\s+[—–]\s+|\s+\(/)[0]?.trim();
  return head || null;
}

/** Setup catalog component that installs the model's weights (gated/manual installs included). */
const SETUP_COMPONENT_BY_MODEL: Record<string, string> = {
  "krea2-turbo-local": "krea2_models",
  "krea2-raw-local": "krea2_models",
};

export function installComponentIdForProvider(provider: ProviderRef): string | null {
  const key = provider.modelId || provider.id;
  return SETUP_COMPONENT_BY_MODEL[key] ?? SETUP_COMPONENT_BY_MODEL[provider.id] ?? null;
}

/** In-product install guidance route (AI-guided Setup wizard) — never a raw runtime or download. */
export function installGuidanceHref(provider: ProviderRef): string | null {
  const componentId = installComponentIdForProvider(provider);
  if (!componentId) return null;
  return buildAiGuidedSetupPath({ componentId, source: "image_studio" });
}

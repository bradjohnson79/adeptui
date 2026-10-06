import type { ImageProviderDescriptor } from "../../contracts/cinematicImageStudio";

/** Sentinel for automatic selection among registered hosted image models. */
export const HOSTED_AUTO_ID = "__hosted_auto__";

export type HostedModelOption = {
  id: string;
  label: string;
  disabled: boolean;
  reason?: string;
};

function capabilityRecord(provider: ImageProviderDescriptor): Record<string, unknown> | null {
  const caps = provider.metadata?.capabilities;
  return caps && typeof caps === "object" ? (caps as Record<string, unknown>) : null;
}

/** Incompatibility the registry already states. Unknown capability stays eligible. */
export function hostedIncompatibility(
  provider: ImageProviderDescriptor,
  referenceCount: number,
): string | null {
  const caps = capabilityRecord(provider);
  if (referenceCount > 0 && caps && caps.supportsReferences === false) {
    return "Does not support reference images";
  }
  if (referenceCount > 1 && caps && caps.supportsMultiReference === false) {
    return "Does not support multiple references";
  }
  const supports = provider.metadata?.supports;
  if (referenceCount > 1 && Array.isArray(supports) && supports.length > 0) {
    const text = supports.map((item) => String(item)).join(" ").toLowerCase();
    const multi = text.includes("multi") || text.includes("reference") || text.includes("edit");
    if (!multi) return "Does not support multiple references";
  }
  return null;
}

export function isHostedImageProvider(provider: ImageProviderDescriptor): boolean {
  return provider.source === "hosted" && provider.imageCapable !== false;
}

export function hostedModelOptions(
  catalog: ImageProviderDescriptor[],
  referenceCount: number,
): HostedModelOption[] {
  const hosted = catalog.filter(isHostedImageProvider);
  const selectable = hosted.filter(
    (provider) => provider.readiness === "ready" && !hostedIncompatibility(provider, referenceCount),
  );
  const options: HostedModelOption[] = [];
  if (selectable.length > 0) {
    options.push({ id: HOSTED_AUTO_ID, label: "Auto / Best Match", disabled: false });
  }
  for (const provider of hosted) {
    const incompat = hostedIncompatibility(provider, referenceCount);
    const needsKey = provider.readiness === "needs_auth";
    const reason = needsKey
      ? "Provider not configured"
      : incompat || (provider.readiness !== "ready" ? "Unavailable" : undefined);
    options.push({
      id: provider.id,
      label: reason ? `${provider.displayName} — ${reason}` : provider.displayName,
      disabled: Boolean(reason),
      reason,
    });
  }
  return options;
}

export function resolveHostedProvider(
  catalog: ImageProviderDescriptor[],
  hostedModelId: string,
  referenceCount: number,
  preferredFamily?: string | null,
): ImageProviderDescriptor | null {
  const hosted = catalog.filter(isHostedImageProvider);
  const selectable = hosted.filter(
    (provider) => provider.readiness === "ready" && !hostedIncompatibility(provider, referenceCount),
  );
  if (hostedModelId === HOSTED_AUTO_ID || !hostedModelId) {
    if (preferredFamily) {
      const matched = selectable.find((provider) => provider.family === preferredFamily);
      if (matched) return matched;
    }
    return selectable[0] || null;
  }
  return hosted.find((provider) => provider.id === hostedModelId) || null;
}

export function hostedSelectionBlockReason(
  provider: ImageProviderDescriptor | null,
  referenceCount: number,
): string | null {
  if (!provider) return "No hosted image generator is available.";
  if (provider.readiness === "needs_auth") return "Provider not configured";
  const incompat = hostedIncompatibility(provider, referenceCount);
  if (incompat) return incompat;
  if (provider.readiness !== "ready") return "Unavailable";
  return null;
}

export function usingModelLabel(
  provider: ImageProviderDescriptor | null | undefined,
  opts: { hosted: boolean; auto: boolean },
): string {
  if (opts.hosted && opts.auto) return "Auto / Best Match";
  if (!provider) return "No model selected";
  if (!opts.hosted || provider.source !== "hosted") {
    const name = provider.displayName || "Local model";
    return name.includes("(Local)") ? name : `${name} (Local)`;
  }
  const providerName = provider.providerPreference || "API";
  return `${provider.displayName} (${providerName})`;
}

export function hostedCostLabel(
  hosted: boolean,
  provider: ImageProviderDescriptor | null | undefined,
): string {
  if (!hosted) return "Local GPU";
  const hint = (provider?.costHint || "").trim();
  if (!hint || hint === "Local GPU" || hint === "Paid hosted API") return "Hosted API pricing applies";
  return hint;
}

/** Fields the image-product compiler already uses to pin a hosted adapter. */
export function hostedExecutionFields(provider: ImageProviderDescriptor): Record<string, string> {
  const modelId = provider.modelId || provider.id;
  const named = (provider.providerPreference || "").trim().toLowerCase();
  const fields: Record<string, string> = {
    hostedModelId: modelId,
    modelId,
    source: "api",
    providerPreference: "cloud",
  };
  if (named === "kie" || named === "fal" || named === "wavespeed") {
    fields.requested_provider = named;
    fields.provider = named;
  }
  if (named === "kie") fields.kieImageModelId = modelId;
  if (named === "fal") fields.falImageModelId = modelId;
  if (named === "wavespeed") fields.wavespeedImageModelId = modelId;
  return fields;
}

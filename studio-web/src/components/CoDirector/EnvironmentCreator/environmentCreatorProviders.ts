/**
 * Environment Creator reads the existing hosted image catalog.
 * It does not keep a second provider registry.
 */
import {
  groupDiscoveredImageModelsByProvider,
  normalizeDiscoveredImageModel,
  type NormalizedDiscoveredImageModel,
} from "../../character/characterGeneratorPlan";

export const ENV_API_PROVIDER_ORDER = ["kie", "wavespeed", "fal"] as const;
export type EnvApiProviderId = (typeof ENV_API_PROVIDER_ORDER)[number];

export const ENV_API_PROVIDER_LABELS: Record<EnvApiProviderId, string> = {
  kie: "kie.ai",
  wavespeed: "wavespeed.ai",
  fal: "fal.ai",
};

export const ENV_PROVIDER_UNAVAILABLE_MESSAGE =
  "This provider is currently unavailable. Choose another configured provider.";

export type EnvCreatorApiModel = {
  id: string;
  officialModelId: string;
  label: string;
};

export type EnvCreatorApiProvider = {
  id: EnvApiProviderId;
  label: string;
  /** False when Setup Wizard has not configured this provider. The row stays visible and inactive. */
  available: boolean;
  models: EnvCreatorApiModel[];
};

export function environmentApiProviderSlots(): EnvCreatorApiProvider[] {
  return ENV_API_PROVIDER_ORDER.map((id) => ({
    id,
    label: ENV_API_PROVIDER_LABELS[id],
    available: false,
    models: [],
  }));
}

function isProviderId(value: string): value is EnvApiProviderId {
  return (ENV_API_PROVIDER_ORDER as readonly string[]).includes(value);
}

function isGptImage25(model: NormalizedDiscoveredImageModel): boolean {
  const blob = `${model.modelId} ${model.model} ${model.displayName}`.toLowerCase();
  return blob.includes("gpt-image-2.5") || blob.includes("gpt image 2.5");
}

function modelLabel(model: NormalizedDiscoveredImageModel): string {
  const raw = model.displayName || model.modelId || "Image model";
  const cut = raw.split(" — ")[0]?.trim();
  return cut || raw;
}

export function environmentApiProvidersFromDiscovered(
  rows: Array<Record<string, unknown>> | null | undefined,
): EnvCreatorApiProvider[] {
  const normalized = (rows || [])
    .map((row) => normalizeDiscoveredImageModel(row))
    .filter((row): row is NormalizedDiscoveredImageModel => Boolean(row))
    .filter((row) => row.executable && row.accountAccessible !== false && !isGptImage25(row));
  const discovered = new Map<EnvApiProviderId, EnvCreatorApiModel[]>();
  for (const group of groupDiscoveredImageModelsByProvider(normalized)) {
    if (!isProviderId(group.providerId)) continue;
    discovered.set(
      group.providerId,
      group.models.map((model) => ({
        id: model.model || model.modelId,
        officialModelId: model.modelId || model.model,
        label: modelLabel(model),
      })),
    );
  }
  return ENV_API_PROVIDER_ORDER.map((id) => {
    const models = discovered.get(id) || [];
    return {
      id,
      label: ENV_API_PROVIDER_LABELS[id],
      available: models.length > 0,
      models,
    };
  });
}

export function resolveEnvironmentApiSelection(
  providers: EnvCreatorApiProvider[],
  savedProvider: string,
  savedModelId: string,
): {
  providerId: string;
  modelId: string;
  officialModelId: string;
  modelLabel: string;
  unavailable: boolean;
} {
  const available = providers.filter((provider) => provider.available);
  if (!available.length) {
    return {
      providerId: "",
      modelId: "",
      officialModelId: "",
      modelLabel: "",
      unavailable: Boolean(savedProvider),
    };
  }
  const saved = available.find((provider) => provider.id === savedProvider);
  const provider = saved || available[0];
  const model = provider.models.find((item) => item.id === savedModelId) || provider.models[0];
  return {
    providerId: provider.id,
    modelId: model.id,
    officialModelId: model.officialModelId,
    modelLabel: model.label,
    unavailable: Boolean(savedProvider) && !saved,
  };
}
